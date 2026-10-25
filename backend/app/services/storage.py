from __future__ import annotations

import re
import uuid

# Vercel limits function request bodies to roughly 4.5 MB. Leave room for JSON,
# base64 expansion, cookies, and the other evidence fields in the same request.
MAX_UPLOAD_BYTES = 3 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
    "text/csv": ".csv",
}


class UnsafeUpload(ValueError):
    pass


def safe_filename(name: str) -> str:
    leaf = name.replace("\\", "/").split("/")[-1]
    leaf = re.sub(r"[^A-Za-z0-9._ -]", "_", leaf).strip(" .")[:120]
    return leaf or "evidence-file"


def store_upload(name: str, claimed_type: str, content: bytes) -> tuple[str, str, str, bytes]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise UnsafeUpload("File exceeds the 3 MB limit")
    extension = ALLOWED_TYPES.get(claimed_type.lower())
    if extension is None:
        raise UnsafeUpload("Allowed file types are PDF, PNG, JPEG, TXT, and CSV")
    valid = {
        "application/pdf": content.startswith(b"%PDF-"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "text/plain": b"\x00" not in content,
        "text/csv": b"\x00" not in content,
    }[claimed_type.lower()]
    if not valid:
        raise UnsafeUpload("File contents do not match the declared file type")
    if claimed_type.lower().startswith("text/"):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UnsafeUpload("Text evidence must be UTF-8 encoded") from error

    key = f"{uuid.uuid4().hex}{extension}"
    return key, safe_filename(name), claimed_type.lower(), content
