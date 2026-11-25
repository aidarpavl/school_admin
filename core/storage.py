"""Құжат айналымы тіркемелері.
Басымдық: GitHub мұрағаты (GITHUB_TOKEN) → Supabase Storage → жергілікті archive/.
Сонымен қатар құжатқа Google Drive сілтемесін тіркеуге болады."""
from urllib.parse import quote

from core.config import get_secret
from core.github_store import get_store, safe_name, save_file


def upload(file_name: str, data: bytes, author: str = "user", folder: str = "06_Kuzhat_ainalymy") -> str:
    if get_secret("GITHUB_TOKEN") or not get_secret("SUPABASE_URL"):
        store = get_store()
        path = save_file(store, folder, file_name, data, author)
        return f"store://{path}"
    import time
    import requests
    url, key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    bucket = get_secret("SUPABASE_BUCKET", "documents")
    path = f"{int(time.time())}_{safe_name(file_name)}"
    r = requests.post(f"{url.rstrip('/')}/storage/v1/object/{bucket}/{quote(path)}",
                      headers={"Authorization": f"Bearer {key}", "apikey": key, "x-upsert": "true"},
                      data=data, timeout=120)
    r.raise_for_status()
    return f"{url.rstrip('/')}/storage/v1/object/public/{bucket}/{quote(path)}"


def fetch(file_url: str) -> bytes | None:
    """store:// жолындағы файлды бағдарлама арқылы жүктеу (жеке репо — токенмен)."""
    if file_url and file_url.startswith("store://"):
        return get_store().get(file_url[len("store://"):])
    return None
