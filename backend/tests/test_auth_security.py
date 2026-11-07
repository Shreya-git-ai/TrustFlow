import unittest
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.security import allowed_origins, get_current_user
from app.services import auth


class AuthSecurityTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_password_hash_is_one_way_and_verifiable(self):
        password = "a long private password 42"
        encoded = auth.hash_password(password)
        self.assertNotEqual(encoded, password)
        self.assertTrue(encoded.startswith(("$argon2", "scrypt$")))
        self.assertTrue(auth.verify_password(encoded, password))
        self.assertFalse(auth.verify_password(encoded, "wrong password"))

    def test_signup_validates_role_and_sets_http_only_session_cookie(self):
        user = {"id": "u1", "name": "A Client", "email": "a@example.test", "role": "client"}
        with patch("app.routers.auth.email_delivery_configured", return_value=False), \
             patch("app.routers.auth.auth.create_user", return_value=(user, "opaque-session", "csrf-token")) as create:
            response = self.client.post("/auth/signup", json={
                "name": "A Client", "email": " A@Example.Test ", "password": "a sufficiently long password", "role": "client",
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"], user)
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertNotIn("opaque-session", response.text)
        self.assertEqual(create.call_args.args[0], "a@example.test")
        self.assertFalse(response.json()["email_confirmation_enabled"])

        invalid = self.client.post("/auth/signup", json={
            "name": "A", "email": "a@example.test", "password": "a sufficiently long password", "role": "admin",
        })
        self.assertEqual(invalid.status_code, 422)

    def test_signup_sends_confirmation_without_creating_a_session(self):
        user = {"id": "u2", "name": "A Freelancer", "email": "f@example.test", "role": "freelancer", "email_verified": False}
        with patch("app.routers.auth.email_delivery_configured", return_value=True), \
             patch("app.routers.auth.auth.create_pending_user", return_value=(user, "one-time-token")) as create, \
             patch("app.routers.auth.send_verification_email", return_value=True) as send:
            response = self.client.post("/auth/signup", json={
                "name": "A Freelancer", "email": "f@example.test", "password": "a sufficiently long password", "role": "freelancer",
            })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["verification_required"])
        self.assertTrue(response.json()["email_sent"])
        self.assertNotIn("set-cookie", response.headers)
        create.assert_called_once()
        send.assert_called_once_with("f@example.test", "A Freelancer", "one-time-token")

    def test_unverified_user_cannot_login(self):
        user = {"id": "u2", "email": "f@example.test", "name": "A Freelancer", "role": "freelancer", "email_verified": False}
        with patch("app.routers.auth.auth.check_login_rate", return_value=True), \
             patch("app.routers.auth.auth.authenticate", return_value=user), \
             patch("app.routers.auth.auth.create_session") as create_session:
            response = self.client.post("/auth/login", json={"email": "f@example.test", "password": "a sufficiently long password"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Confirm your email before signing in")
        create_session.assert_not_called()

    def test_login_rate_limit_blocks_before_password_lookup(self):
        with patch("app.routers.auth.auth.check_login_rate", return_value=False), patch("app.routers.auth.auth.authenticate") as authenticate:
            response = self.client.post("/auth/login", json={"email": "a@example.test", "password": "irrelevant"})
        self.assertEqual(response.status_code, 429)
        authenticate.assert_not_called()

    def test_current_user_requires_a_valid_unexpired_session(self):
        self.client.cookies.set("trustflow_session", "expired-session")
        with patch("app.security.lookup_session", return_value=None):
            response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_vercel_frontend_signup_login_and_session_persist_at_api_alias(self):
        origin = "https://trustflow-paypal.vercel.app"
        pending_user = {
            "id": "u-vercel", "name": "Vercel Client", "email": "vercel@example.test",
            "role": "client", "email_verified": False,
        }
        authenticated_user = {**pending_user, "email_verified": True}
        session_user = {**authenticated_user, "csrf_token": "csrf-vercel"}
        client = TestClient(app, base_url=origin)
        headers = {"origin": origin}

        with patch.dict(os.environ, {
            "TRUSTFLOW_ENV": "production",
            "CORS_ORIGINS": origin,
        }), patch("app.routers.auth.email_delivery_configured", return_value=True), \
             patch("app.routers.auth.auth.create_pending_user", return_value=(pending_user, "verification-token")), \
             patch("app.routers.auth.send_verification_email", return_value=True):
            signup = client.post("/api/auth/signup", headers=headers, json={
                "name": "Vercel Client", "email": "vercel@example.test",
                "password": "a sufficiently long password", "role": "client",
            })

        self.assertEqual(signup.status_code, 201, signup.text)
        self.assertTrue(signup.json()["verification_required"])
        self.assertNotIn("set-cookie", signup.headers)
        with patch.dict(os.environ, {"CORS_ORIGINS": origin}):
            self.assertEqual(allowed_origins(), {origin})

        with patch.dict(os.environ, {
            "VERCEL_ENV": "production",
            "CORS_ORIGINS": origin,
        }), patch("app.routers.auth.auth.check_login_rate", return_value=True), \
             patch("app.routers.auth.auth.authenticate", return_value=authenticated_user), \
             patch("app.routers.auth.auth.clear_login_rate"), \
             patch("app.routers.auth.auth.create_session", return_value=("opaque-session", "csrf-vercel")), \
             patch("app.routers.auth.auth.revoke_session"), \
             patch("app.security.lookup_session", return_value=session_user):
            login = client.post("/api/auth/login", headers=headers, json={
                "email": "vercel@example.test", "password": "a sufficiently long password",
            })
            self.assertEqual(login.status_code, 200, login.text)
            cookie = login.headers["set-cookie"].lower()
            self.assertIn("httponly", cookie)
            self.assertIn("secure", cookie)
            self.assertIn("samesite=lax", cookie)
            self.assertNotIn("domain=", cookie)
            self.assertNotIn("opaque-session", login.text)

            current = client.get("/api/auth/me")
            self.assertEqual(current.status_code, 200, current.text)
            self.assertEqual(current.json()["user"]["email"], "vercel@example.test")
            self.assertEqual(current.json()["csrf_token"], "csrf-vercel")

            logout = client.post(
                "/api/auth/logout",
                headers={**headers, "x-csrf-token": "csrf-vercel"},
                json={},
            )
            self.assertEqual(logout.status_code, 200, logout.text)
            deletion_cookie = logout.headers["set-cookie"].lower()
            self.assertIn("httponly", deletion_cookie)
            self.assertIn("secure", deletion_cookie)
            self.assertIn("samesite=lax", deletion_cookie)

    def test_api_auth_me_alias_rejects_missing_session(self):
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_csrf_and_revokes_current_session(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user-1", "name": "Client", "email": "c@example.test", "role": "client", "csrf_token": "csrf-secret",
        }
        self.client.cookies.set("trustflow_session", "opaque-session")
        missing = self.client.post("/auth/logout", json={})
        self.assertEqual(missing.status_code, 403)
        with patch("app.routers.auth.auth.revoke_session") as revoke:
            response = self.client.post("/auth/logout", json={}, headers={"x-csrf-token": "csrf-secret", "origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        revoke.assert_called_once_with("opaque-session")


if __name__ == "__main__":
    unittest.main()
