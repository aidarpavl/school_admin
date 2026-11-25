"""Роли, сілтемелер және жалпы баптаулар."""
import os

APP_TITLE = "Мектеп әкімшілігінің цифрлық платформасы"

# --- Сыртқы сілтемелер (пайдаланушы берген) ---
LINKS = {
    "ecosvet": "https://ecosvetzhd.streamlit.app/",
    "library": "https://script.google.com/macros/s/AKfycbw5qIFrfLDUM3s5_xOMfmgmrzSX8e_c2dSht38GaB3DEuiQJ0KMKwh7pG47otgjPbqt/exec",
    "talismasters": "https://talismasters.streamlit.app/",
    "rating": "https://reytingstudentszhd2026.streamlit.app/",
    "stupeni": "https://stupeni.streamlit.app/",
    "canteen": "https://zhd-stolovaya-zaiavka.streamlit.app/",
    "birthday": "https://personalbirthdayzhd.streamlit.app/",
    "zavuch_form": "https://raw.githack.com/aidarpavl/-young_teacher/main/zavuch_poseshenie.html",
    "young_journal": "https://raw.githack.com/aidarpavl/-young_teacher/main/journal.html",
}

# --- Рөлдер ---
ROLES = {
    "admin": "Бас администратор",
    "director": "Директор",
    "zavuch_uch": "Оқу ісі жөніндегі орынбасар",
    "zavuch_vosp": "Тәрбие ісі жөніндегі орынбасар",
    "zavuch_it": "Ақпараттандыру жөніндегі орынбасар",
    "zavuch_innov": "Инновация және кадр жөніндегі орынбасар",
    "zavuch_gifted": "Дарынды балалармен жұмыс жөніндегі орынбасар",
    "metodist": "Әдістемелік кабинет",
    "zavhoz": "Шаруашылық меңгерушісі (завхоз)",
    "soc_ped": "Әлеуметтік педагог",
    "psychologist": "Педагог-психолог",
    "librarian": "Кітапханашы",
    "nvp": "АӘТД (НВП) мұғалімі",
    "pe": "Дене шынықтыру мұғалімі",
    "proforg": "Кәсіподақ төрағасы (профорг)",
    "teacher": "Мұғалім",
}

ADMIN_ROLES = {"admin", "director", "zavuch_uch", "zavuch_vosp", "zavuch_it",
               "zavuch_innov", "zavuch_gifted", "metodist", "zavhoz"}
SUPER_ROLES = {"admin", "director"}

DOC_STATUSES = ["Жоба", "Жіберілді", "Қаралуда", "Бекітілді", "Қайтарылды", "Мұрағат"]
DOC_TYPES = ["Бұйрық", "Хат / хабарлама", "Есеп", "Анықтама", "ҚМЖ / КТЖ", "Жоспар",
             "Хаттама", "Өтініш", "Әдістемелік материал", "Басқа"]
DOC_CHANNELS = ["Әкімшілік ішкі", "Мұғалім → әкімшілік", "Әкімшілік → мұғалімдер",
                "Мұғалім ↔ әдістемелік кабинет", "Әдістемелік кабинет ↔ әкімшілік"]

CLASSES = [f"{g}{l}" for g in range(1, 12) for l in "АӘБВГ"]


def role_name(code: str) -> str:
    return ROLES.get(code, code)


def get_secret(key: str, default=None):
    """st.secrets → орта айнымалысы → default."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)
