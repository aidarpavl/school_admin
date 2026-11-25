"""Мектеп әкімшілігінің цифрлық платформасы — Streamlit.
Іске қосу:  streamlit run app.py
"""
import streamlit as st

from core.auth import (bootstrap_admin, create_admin, finish_reset, get_user, has_admin, login, register,
                       start_reset)
from core.config import ADMIN_ROLES, APP_TITLE, LINKS, role_name
from core.db import get_db
from core.ui import external_app, is_super
from views import admin_pages, archive, docflow, feedback, mdj, observation, rating, tasks, workspaces

st.set_page_config(page_title=APP_TITLE, page_icon="🏫", layout="wide")
st.markdown("""<style>
[data-testid="stSidebar"] {background: linear-gradient(180deg,#0b3d6e 0%,#145c9e 100%);}
[data-testid="stSidebar"] * {color: #fff !important;}
[data-testid="stSidebar"] .stRadio label {padding: 2px 0;}
div[data-testid="stMetric"] {background:#f3f7fc;border-radius:10px;padding:8px 12px;}
</style>""", unsafe_allow_html=True)

db = get_db()
bootstrap_admin(db)


def setup_screen():
    """Базада бірде-бір бас әкімші жоқ кезде ғана шығады (алғашқы іске қосу)."""
    st.title("🏫 " + APP_TITLE)
    st.warning("Бас әкімші әлі құрылмаған. Алғашқы баптау: бас әкімшінің логині мен құпиясөзін енгізіңіз.")
    with st.form("setup_admin"):
        un = st.text_input("Логин", "Aidar")
        pw = st.text_input("Құпиясөз (≥6)", type="password")
        pw2 = st.text_input("Құпиясөзді қайталаңыз", type="password")
        em = st.text_input("Email (құпиясөзді қалпына келтіру үшін)")
        if st.form_submit_button("Бас әкімшіні құру", type="primary"):
            if len(pw.strip()) < 6 or pw.strip() != pw2.strip() or len(un.strip()) < 3:
                st.error("Логин ≥3 таңба, құпиясөз ≥6 таңба және екеуі бірдей болуы керек")
            elif has_admin(db):
                st.error("Бас әкімші бар. Кіру бетін пайдаланыңыз.")
            else:
                create_admin(db, un, pw, em)
                st.session_state["user"] = get_user(db, un.strip())
                st.success("Бас әкімші құрылды")
                st.rerun()


def auth_screen():
    if not has_admin(db):
        setup_screen()
        return
    st.title("🏫 " + APP_TITLE)
    st.caption("Дарынды балаларға арналған мектеп · әкімшілік, мұғалімдер, мамандар")
    t1, t2, t3 = st.tabs(["🔐 Кіру", "📝 Тіркелу", "❓ Құпиясөзді ұмыттым"])
    with t1:
        with st.form("login"):
            un = st.text_input("Логин")
            pw = st.text_input("Құпиясөз", type="password")
            if st.form_submit_button("Кіру", type="primary"):
                u = login(db, un, pw)
                if u:
                    st.session_state["user"] = u
                    st.rerun()
                else:
                    st.error("Логин немесе құпиясөз қате (немесе аккаунт бұғатталған)")
    with t2:
        st.caption("Тіркелгеннен кейін рөліңіз «Мұғалім» болады. Әкімшілік рөлін бас әкімші береді.")
        with st.form("reg", clear_on_submit=True):
            c1, c2 = st.columns(2)
            un = c1.text_input("Логин *")
            fn = c2.text_input("ТАӘ *")
            em = c1.text_input("Email * (құпиясөзді қалпына келтіру үшін)")
            subj = c2.text_input("Пәні")
            pw = c1.text_input("Құпиясөз * (≥6)", type="password")
            pw2 = c2.text_input("Құпиясөзді қайталаңыз *", type="password")
            if st.form_submit_button("Тіркелу", type="primary"):
                if pw != pw2:
                    st.error("Құпиясөздер сәйкес емес")
                elif not fn:
                    st.error("ТАӘ енгізіңіз")
                else:
                    ok, msg = register(db, un, pw, fn, em, "teacher", "Мұғалім", subj)
                    (st.success if ok else st.error)(msg)
    with t3:
        key = st.text_input("Логин немесе email", key="rs_key")
        if st.button("📧 Кодты поштаға жіберу"):
            ok, msg = start_reset(db, key)
            (st.success if ok else st.error)(msg)
        with st.form("reset2"):
            code = st.text_input("Поштаға келген 6 таңбалы код")
            npw = st.text_input("Жаңа құпиясөз", type="password")
            if st.form_submit_button("Құпиясөзді жаңарту"):
                ok, msg = finish_reset(db, key, code, npw)
                (st.success if ok else st.error)(msg)


if "user" not in st.session_state:
    auth_screen()
    st.stop()

# рөл өзгерген болса — жаңарту
fresh = get_user(db, st.session_state["user"]["username"])
if not fresh or int(fresh.get("active") or 0) != 1:
    st.session_state.clear()
    st.rerun()
st.session_state["user"] = fresh
user = fresh
role = user["role"]

MENU = [("🏠 Басты бет", lambda: admin_pages.home(db, user), True),
        ("✅ Тапсырмалар", lambda: tasks.render(db, user), True),
        ("📂 Құжат айналымы", lambda: docflow.render(db, user), True),
        ("🗄 Электрондық мұрағат", lambda: archive.render(db, user), True),
        ("💬 Ұсыныстар мен пікірлер", lambda: feedback.render(db, user), True),
        ("🧰 Менің жұмыс орным", lambda: workspaces.render(db, user), role in workspaces.WORKSPACES),
        ("🧭 Барлық жұмыс орындары", None, is_super(user)),
        ("📘 Өзара сабаққа қатысу (жас педагог)", lambda: observation.young_journal(db, user), True),
        ("🛠 Өтінімдер (IT, жөндеу)", lambda: admin_pages.requests_page(db, user), True),
        ("⭐ Оқушылар рейтингі", lambda: rating.rating(db, user), True),
        ("🪜 Баспалдақтар (Ступени)", lambda: rating.stupeni(db, user), True),
        ("📈 Мектептің даму жоспары", lambda: mdj.render(db, user), role in ADMIN_ROLES),
        ("🍽 Асхана жұмысы", lambda: admin_pages.canteen(db, user), True),
        ("📚 Кітапхана", lambda: external_app("📚 Кітапхана", LINKS["library"], key="lib_main"), True),
        ("👥 Пайдаланушылар", lambda: admin_pages.users_admin(db, user), is_super(user)),
        ("⚙ Профиль", lambda: admin_pages.profile(db, user), True),
        ("📖 Нұсқаулық / промт", lambda: admin_pages.guide(db, user), True)]
items = [(n, f) for n, f, ok in MENU if ok]

with st.sidebar:
    st.markdown(f"### 🏫 Мектеп платформасы\n**{user.get('full_name') or user['username']}**  \n_{role_name(role)}_")
    choice = st.radio("Мәзір", [n for n, _ in items], label_visibility="collapsed")
    st.divider()
    st.link_button("🍽 Асхана жұмысы", LINKS["canteen"], use_container_width=True)
    if st.button("🚪 Шығу", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.caption("ДБ: " + ("Supabase (PostgreSQL)" if db.kind == "pg" else "жергілікті SQLite"))

if choice == "🧭 Барлық жұмыс орындары":
    r = st.selectbox("Рөл", list(workspaces.WORKSPACES), format_func=role_name)
    workspaces.render(db, user, r)
else:
    dict(items)[choice]()
