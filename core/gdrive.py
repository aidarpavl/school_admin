"""Google Drive-қа сақтау — Google Apps Script веб-қосымшасы арқылы (ең қарапайым әдіс:
Google Cloud консолі, OAuth, қызметтік аккаунт қажет емес; файлдар сіздің Google Drive-та сақталады).

Баптау (бір рет): docs/gdrive_apps_script.gs кодын script.google.com-да жариялап, Secrets-ке қосыңыз:
  GDRIVE_SCRIPT_URL = "https://script.google.com/macros/s/.../exec"
  GDRIVE_SECRET     = "скриптегі SECRET мәні"
"""
import base64

from core.config import get_secret

MIME = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf", "doc": "application/msword", "csv": "text/csv"}


def enabled() -> bool:
    return bool(get_secret("GDRIVE_SCRIPT_URL") and get_secret("GDRIVE_SECRET"))


def upload(name: str, data: bytes, folder_path: str = "", mime: str | None = None) -> tuple[bool, str]:
    """(ok, url немесе қате мәтіні). folder_path: 'Оқу ісі/PISA/2026-2027' — жоқ папкалар құрылады."""
    if not enabled():
        return False, "Google Drive баптаулмаған (Secrets: GDRIVE_SCRIPT_URL, GDRIVE_SECRET)"
    import requests
    ext = name.rsplit(".", 1)[-1].lower()
    payload = {"secret": get_secret("GDRIVE_SECRET"), "name": name, "path": folder_path,
               "mime": mime or MIME.get(ext, "application/octet-stream"),
               "data": base64.b64encode(data).decode()}
    try:
        r = requests.post(get_secret("GDRIVE_SCRIPT_URL"), json=payload, timeout=180, allow_redirects=True)
        j = r.json()
        return (True, j.get("url", "")) if j.get("ok") else (False, j.get("error", "белгісіз қате"))
    except Exception as e:
        return False, f"Google Drive қатесі: {e}"
