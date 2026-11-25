"""Электрондық құжаттар мұрағаты GitHub-та (жеке, бөлек репозиторий).

Неге бөлек репо: Streamlit Cloud бағдарлама репосын әр іске қосқанда толық көшіреді.
Құжаттар (2–4 ГБ) бағдарлама репосында болса, іске қосу баяулап, сәтсіз болуы мүмкін.

GitHub шектеулері:
  * бір файл ≤ 100 МБ (API арқылы; біз 50 МБ шегін қоямыз — base64 көлемді 33% үлкейтеді);
  * репо көлемі ұсынылатыны < 1 ГБ, қатаң ұсыныс < 5 ГБ → әр оқу жылына жеке репо
    (GITHUB_DOCS_REPO = "aidarpavl/school-docs-{year}" үлгісі).

Секреттер: GITHUB_TOKEN (fine-grained, Contents: Read & Write), GITHUB_DOCS_REPO, GITHUB_DOCS_BRANCH.
Токен жоқ болса — дәл осындай құрылымдағы жергілікті archive/ папкасы қолданылады.
"""
import base64
import os
import re
from datetime import date

from core.config import get_secret

MAX_FILE_MB = 50
REPO_SOFT_LIMIT_GB = 4.5
ROOT = "documents"

# Папкалар құрылымы: (жол, көрсетілетін атау, оқи алатын рөлдер, жаза алатын рөлдер)
# "*" — барлық тіркелген пайдаланушылар. admin/director әрқашан бәрін көреді.
ADM = ["zavuch_uch", "zavuch_vosp", "zavuch_it", "zavuch_innov", "zavuch_gifted", "metodist", "zavhoz"]
FOLDERS = [
    ("01_Akimshilik", "01 Әкімшілік", ADM, ADM),
    ("01_Akimshilik/Buyryqtar", "Бұйрықтар", ["*"], ["director"]),
    ("01_Akimshilik/Oqu_isi", "Оқу ісі (ВШК, БЖБ/ТЖБ, кесте)", ["*"], ["zavuch_uch"]),
    ("01_Akimshilik/Tarbie_isi", "Тәрбие ісі", ["*"], ["zavuch_vosp"]),
    ("01_Akimshilik/Aqparattandyru", "Ақпараттандыру", ADM, ["zavuch_it"]),
    ("01_Akimshilik/Innovaciya_kadr", "Инновация және кадр (аттестация, курстар)", ADM, ["zavuch_innov"]),
    ("01_Akimshilik/Daryndy_balalar", "Дарынды балалар (олимпиада, жоба)", ["*"], ["zavuch_gifted"]),
    ("01_Akimshilik/Sharuashylyq", "Шаруашылық (завхоз)", ADM, ["zavhoz"]),
    ("02_Mugalimder", "02 Мұғалімдер", ["*"], ["*"]),
    ("02_Mugalimder/KTZh_QMZh", "КТЖ / ҚМЖ", ["*"], ["*"]),
    ("02_Mugalimder/BZhB_TZhB", "БЖБ / ТЖБ материалдары", ["*"], ["*"]),
    ("02_Mugalimder/Synyp_zhetekshi", "Сынып жетекші құжаттары", ["*"], ["*"]),
    ("02_Mugalimder/Portfolio_attestaciya", "Портфолио, аттестация", ["*"], ["*"]),
    ("03_Adistemelik_kabinet", "03 Әдістемелік кабинет", ["*"], ["metodist"]),
    ("03_Adistemelik_kabinet/AB_hattamalary", "ӘБ хаттамалары", ["*"], ["metodist", "*"]),
    ("03_Adistemelik_kabinet/Pedkenes", "Педкеңес, әдістемелік кеңес", ["*"], ["metodist"]),
    ("03_Adistemelik_kabinet/Ashyq_sabaqtar", "Ашық сабақтар, тәжірибе", ["*"], ["*"]),
    ("04_Mamandar", "04 Мамандар", ["*"], ADM),
    ("04_Mamandar/Aleumettik_pedagog", "Әлеуметтік педагог (құпия)", ["soc_ped"], ["soc_ped"]),
    ("04_Mamandar/Psiholog", "Психолог (құпия)", ["psychologist"], ["psychologist"]),
    ("04_Mamandar/Kitaphana", "Кітапхана", ["*"], ["librarian"]),
    ("04_Mamandar/AATD_NVP", "АӘТД (НВП)", ADM + ["nvp"], ["nvp"]),
    ("04_Mamandar/Dene_shynyqtyru", "Дене шынықтыру", ADM + ["pe"], ["pe"]),
    ("04_Mamandar/Kasipodaq", "Кәсіподақ", ["*"], ["proforg"]),
    ("05_MDZh_SWOT", "05 МДЖ, SWOT", ADM, ADM),
    ("06_Kuzhat_ainalymy", "06 Құжат айналымы тіркемелері", ["*"], ["*"]),
]


def academic_year(d: date | None = None) -> str:
    d = d or date.today()
    y = d.year if d.month >= 9 else d.year - 1
    return f"{y}-{y + 1}"


def safe_name(name: str) -> str:
    base, ext = os.path.splitext(name)
    base = re.sub(r"[^\w\-]+", "_", base, flags=re.UNICODE).strip("_")[:80] or "file"
    return base + ext.lower()


def folder_meta(path: str):
    """Ең жақын анықталған папканың баптауларын қайтарады."""
    best = None
    for f in FOLDERS:
        if path == f[0] or path.startswith(f[0] + "/"):
            if best is None or len(f[0]) > len(best[0]):
                best = f
    return best


def can(user: dict, path: str, mode: str = "read") -> bool:
    if user.get("role") in ("admin", "director"):
        return True
    meta = folder_meta(path)
    if not meta:
        return False
    allowed = meta[2] if mode == "read" else meta[3]
    return "*" in allowed or user.get("role") in allowed


class GitHubStore:
    kind = "github"

    def __init__(self, token: str, repo: str, branch: str = "main"):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}",
                               "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})
        self.repo = repo.replace("{year}", academic_year())
        self.branch = branch
        self.api = f"https://api.github.com/repos/{self.repo}"

    def _url(self, path: str) -> str:
        from urllib.parse import quote
        return f"{self.api}/contents/{quote(path)}"

    def check(self) -> tuple[bool, str]:
        r = self.s.get(self.api, timeout=20)
        if r.status_code == 200:
            j = r.json()
            return True, f"{self.repo} ({'жеке' if j.get('private') else '⚠ АШЫҚ — жеке етіңіз!'})"
        return False, f"{self.repo}: {r.status_code} {r.text[:200]}"

    def _sha(self, path: str):
        r = self.s.get(self._url(path), params={"ref": self.branch}, timeout=30)
        return r.json().get("sha") if r.status_code == 200 and isinstance(r.json(), dict) else None

    def put(self, path: str, data: bytes, message: str) -> str:
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise ValueError(f"Файл {MAX_FILE_MB} МБ-тан үлкен. Үлкен бейне/архивті Google Drive-қа салып, сілтемесін тіркеңіз.")
        body = {"message": message, "content": base64.b64encode(data).decode(), "branch": self.branch}
        sha = self._sha(path)
        if sha:
            body["sha"] = sha
        r = self.s.put(self._url(path), json=body, timeout=300)
        r.raise_for_status()
        return path

    def list_dir(self, path: str) -> list[dict]:
        r = self.s.get(self._url(path), params={"ref": self.branch}, timeout=30)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        items = r.json() if isinstance(r.json(), list) else []
        return [{"name": i["name"], "path": i["path"], "type": "dir" if i["type"] == "dir" else "file",
                 "size": i.get("size", 0), "sha": i.get("sha")} for i in items]

    def get(self, path: str) -> bytes:
        r = self.s.get(self._url(path), params={"ref": self.branch}, timeout=300,
                       headers={"Accept": "application/vnd.github.raw+json"})
        r.raise_for_status()
        return r.content

    def delete(self, path: str, message: str):
        sha = self._sha(path)
        if sha:
            r = self.s.delete(self._url(path), json={"message": message, "sha": sha, "branch": self.branch},
                              timeout=60)
            r.raise_for_status()

    def all_files(self) -> list[dict]:
        r = self.s.get(f"{self.api}/git/trees/{self.branch}", params={"recursive": "1"}, timeout=60)
        if r.status_code in (404, 409):  # бос репо
            return []
        r.raise_for_status()
        return [{"path": t["path"], "size": t.get("size", 0)} for t in r.json().get("tree", [])
                if t["type"] == "blob"]


class LocalStore:
    """GitHub баптаулмаған кезде — жергілікті archive/ папкасы (тест/офлайн)."""
    kind = "local"

    def __init__(self, base: str = "archive"):
        self.base = base
        self.repo = os.path.abspath(base)
        os.makedirs(base, exist_ok=True)

    def _p(self, path):
        full = os.path.normpath(os.path.join(self.base, path))
        if not full.startswith(os.path.normpath(self.base)):
            raise ValueError("Жол қате")
        return full

    def check(self):
        return True, f"Жергілікті папка: {self.repo}"

    def put(self, path, data, message=""):
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise ValueError(f"Файл {MAX_FILE_MB} МБ-тан үлкен")
        full = self._p(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        return path

    def list_dir(self, path):
        full = self._p(path)
        if not os.path.isdir(full):
            return []
        out = []
        for n in sorted(os.listdir(full)):
            fp = os.path.join(full, n)
            out.append({"name": n, "path": f"{path}/{n}", "type": "dir" if os.path.isdir(fp) else "file",
                        "size": os.path.getsize(fp) if os.path.isfile(fp) else 0})
        return out

    def get(self, path):
        with open(self._p(path), "rb") as f:
            return f.read()

    def delete(self, path, message=""):
        full = self._p(path)
        if os.path.isfile(full):
            os.remove(full)

    def all_files(self):
        out = []
        for root, _, files in os.walk(self.base):
            for n in files:
                fp = os.path.join(root, n)
                out.append({"path": os.path.relpath(fp, self.base).replace(os.sep, "/"),
                            "size": os.path.getsize(fp)})
        return out


def get_store():
    token = get_secret("GITHUB_TOKEN")
    repo = get_secret("GITHUB_DOCS_REPO")
    if token and repo:
        return GitHubStore(token, repo, get_secret("GITHUB_DOCS_BRANCH", "main"))
    return LocalStore()


def ensure_structure(store, author: str = "system"):
    """Барлық папкаларды .gitkeep арқылы құрады (GitHub бос папканы сақтамайды)."""
    created = 0
    existing = {f["path"] for f in store.all_files()}
    for path, label, *_ in FOLDERS:
        p = f"{ROOT}/{path}/.gitkeep"
        if p not in existing:
            store.put(p, f"{label}\n".encode(), f"Папка құру: {label} ({author})")
            created += 1
    return created


def save_file(store, folder: str, file_name: str, data: bytes, author: str, by_year: bool = True) -> str:
    """documents/<папка>/<оқу жылы>/<файл> жолымен сақтайды, қайталанса уақыт белгісін қосады."""
    from datetime import datetime
    sub = f"{ROOT}/{folder}" + (f"/{academic_year()}" if by_year else "")
    name = safe_name(file_name)
    existing = {i["name"] for i in store.list_dir(sub)}
    if name in existing:
        b, e = os.path.splitext(name)
        name = f"{b}_{datetime.now():%Y%m%d_%H%M%S}{e}"
    return store.put(f"{sub}/{name}", data, f"{author}: {name} жүктелді")
