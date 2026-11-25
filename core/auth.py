"""Авторизация: құпиясөз хэші, тіркелу, кіру, поштамен қалпына келтіру."""
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from core.config import get_secret
from core.db import DB, now

ITER = 200_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITER)
    return f"pbkdf2${ITER}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(it))
        return hmac.compare_digest(dk.hex(), h)
    except Exception:
        return False


def get_user(db: DB, username: str) -> dict | None:
    rows = db.query("SELECT * FROM users WHERE lower(username) = lower(?)", (username.strip(),))
    return rows[0] if rows else None


def has_admin(db: DB) -> bool:
    return bool(db.query("SELECT id FROM users WHERE role = 'admin' AND active = 1"))


def create_admin(db: DB, username: str, password: str, email: str = "", full_name: str = "Бас администратор"):
    username, password = username.strip(), password.strip()
    u = get_user(db, username)
    if u is None:
        db.insert("users", {
            "username": username, "password_hash": hash_password(password),
            "full_name": full_name, "email": email, "role": "admin",
            "position": "Бас администратор", "active": 1, "created_at": now(),
        })
    else:  # бар болса — админ етіп, құпиясөзін жаңартып, бұғаттан шығару
        db.execute("UPDATE users SET password_hash = ?, role = 'admin', active = 1 WHERE id = ?",
                   (hash_password(password), u["id"]))


def bootstrap_admin(db: DB):
    """Secrets-те ADMIN_PASSWORD болса — бас админді құрады немесе құпиясөзін Secrets-пен теңестіреді.
    Secrets жоқ болса — кіру бетінде «Бас әкімшіні құру» формасы шығады (тек әкімші жоқ кезде)."""
    username = str(get_secret("ADMIN_USERNAME", "Aidar")).strip()
    password = get_secret("ADMIN_PASSWORD")
    if not password:
        return
    password = str(password).strip()
    force = str(get_secret("ADMIN_RESET", "")).lower() in ("1", "true", "yes", "иә")
    if get_user(db, username) is None or force:
        # ADMIN_RESET = true → құпиясөз Secrets-тегі мәнге қайтарылады (ұмытып қалсаңыз)
        create_admin(db, username, password, str(get_secret("ADMIN_EMAIL", "")))


def register(db: DB, username: str, password: str, full_name: str, email: str,
             role: str = "teacher", position: str = "", subject: str = "") -> tuple[bool, str]:
    username = username.strip()
    if len(username) < 3:
        return False, "Логин кемінде 3 таңба болуы керек"
    if len(password) < 6:
        return False, "Құпиясөз кемінде 6 таңба болуы керек"
    if "@" not in email:
        return False, "Электрондық поштаны дұрыс енгізіңіз (құпиясөзді қалпына келтіру үшін қажет)"
    if get_user(db, username):
        return False, "Мұндай логин бар"
    db.insert("users", {
        "username": username, "password_hash": hash_password(password),
        "full_name": full_name.strip(), "email": email.strip(), "role": role,
        "position": position, "subject": subject, "active": 1, "created_at": now(),
    })
    return True, "Тіркелу сәтті өтті. Енді кіріңіз."


def login(db: DB, username: str, password: str) -> dict | None:
    u = get_user(db, username)
    if not u or int(u.get("active") or 0) != 1:
        return None
    # көшіргенде қосылып кететін бос орындарды ескеру
    for pw in (password, password.strip()):
        if verify_password(pw, u["password_hash"]):
            return u
    return None


def set_password(db: DB, username: str, new_password: str):
    db.execute("UPDATE users SET password_hash = ? WHERE lower(username) = lower(?)",
               (hash_password(new_password), username))


# --- Поштамен қалпына келтіру ---
def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    host = get_secret("SMTP_HOST", "smtp.gmail.com")
    port = int(get_secret("SMTP_PORT", 465))
    user = get_secret("SMTP_USER")
    pwd = get_secret("SMTP_PASSWORD")
    if not (user and pwd):
        return False, "SMTP баптаулары енгізілмеген (Secrets: SMTP_USER, SMTP_PASSWORD)"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = get_secret("SMTP_FROM", user)
    msg["To"] = to
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd)
                s.send_message(msg)
        return True, "Хат жіберілді"
    except Exception as e:
        return False, f"Хат жіберілмеді: {e}"


def start_reset(db: DB, login_or_email: str) -> tuple[bool, str]:
    key = login_or_email.strip()
    rows = db.query("SELECT * FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
                    (key, key))
    if not rows or not rows[0].get("email"):
        # Қауіпсіздік үшін пайдаланушы бар-жоғын ашпаймыз
        return True, "Егер пайдаланушы табылса, поштаға код жіберілді."
    u = rows[0]
    code = f"{secrets.randbelow(10**6):06d}"
    expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    db.insert("reset_codes", {"username": u["username"], "code": code, "expires_at": expires, "used": 0})
    ok, info = send_email(
        u["email"], "Құпиясөзді қалпына келтіру коды",
        f"Сәлеметсіз бе, {u.get('full_name') or u['username']}!\n\n"
        f"Логин: {u['username']}\nҚалпына келтіру коды: {code}\nКод 15 минут жарамды.\n\n"
        f"Егер сіз сұрамаған болсаңыз, бұл хатты елемеңіз.")
    if not ok:
        return False, info
    return True, "Егер пайдаланушы табылса, поштаға код жіберілді."


def finish_reset(db: DB, login_or_email: str, code: str, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 6:
        return False, "Құпиясөз кемінде 6 таңба"
    key = login_or_email.strip()
    rows = db.query("SELECT username FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
                    (key, key))
    if not rows:
        return False, "Код қате немесе мерзімі өтті"
    username = rows[0]["username"]
    codes = db.query("SELECT * FROM reset_codes WHERE username = ? AND code = ? AND used = 0 ORDER BY id DESC",
                     (username, code.strip()))
    if not codes or codes[0]["expires_at"] < now():
        return False, "Код қате немесе мерзімі өтті"
    set_password(db, username, new_password)
    db.update("reset_codes", codes[0]["id"], {"used": 1})
    return True, "Құпиясөз жаңартылды. Енді кіріңіз."
