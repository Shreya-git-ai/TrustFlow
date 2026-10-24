# TrustFlow frontend

The Vite development server serves the evidence review console on port `5173`. API requests go through `/api` and are proxied to the backend at `http://localhost:3000`.

From this directory:

```sh
npm install
npm run dev
```

Run the frontend checks with `npm run lint` and `npm run build`.

To point a built frontend at a different API host, set `VITE_API_BASE_URL` to the API base URL before building, and add the frontend origin to the backend's `CORS_ORIGINS`. The backend exposes `GET /health` and `POST /assessments`. See the repository README for backend setup and Gemini configuration.
