from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
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


def store_upload(name: str, claimed_type: str, content: bytes) -> tuple[str, str, str]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise UnsafeUpload("File exceeds the 10 MB limit")
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

    root = Path(os.getenv("TRUSTFLOW_UPLOAD_DIR", "data/private-uploads")).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = f"{uuid.uuid4().hex}{extension}"
    target = root / key
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)
    return key, safe_filename(name), claimed_type.lower()


def remove_upload(key: str | None) -> None:
    if not key or not re.fullmatch(r"[a-f0-9]{32}\.(pdf|png|jpg|txt|csv)", key):
        return
    root = Path(os.getenv("TRUSTFLOW_UPLOAD_DIR", "data/private-uploads")).resolve()
    try:
        (root / key).unlink(missing_ok=True)
    except OSError:
        pass
