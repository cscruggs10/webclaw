"""Authenticated upload and download of deal paperwork and title scans."""
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response

import db
import storage
from auth.jwt_utils import get_signing_secret, verify_token

router = APIRouter(tags=["files"])


def _unauthorized(message: str, status: int = 401) -> JSONResponse:
    return JSONResponse({"status": "error", "message": message}, status_code=status)


def _require_user(request: Request) -> JSONResponse | None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return _unauthorized("Authentication required")
    conn = db.get_connection()
    try:
        secret = get_signing_secret(conn)
        payload = verify_token(header[7:], secret, expected_type="access")
    finally:
        conn.close()
    if not payload:
        return _unauthorized("Invalid or expired token")
    return None


@router.post("/api/v1/files/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    denied = _require_user(request)
    if denied:
        return denied
    data = await file.read()
    try:
        saved = storage.save_upload(file.filename or "upload.bin", data, file.content_type or "")
    except ValueError as exc:
        status = 413 if "25MB" in str(exc) else 400
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=status)
    except Exception:
        return JSONResponse(
            {"status": "error", "message": "Could not store the file"},
            status_code=500,
        )
    return saved


@router.get("/api/v1/files/{key}")
async def download_file(key: str, request: Request):
    denied = _require_user(request)
    if denied:
        return denied
    try:
        data, content_type, filename = storage.open_upload(key)
    except FileNotFoundError:
        return JSONResponse({"status": "error", "message": "File not found"}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse(
            {"status": "error", "message": "Could not read the file"},
            status_code=500,
        )
    safe_name = filename.replace('"', "")
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )
