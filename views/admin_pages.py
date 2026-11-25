"""Басты бет, пайдаланушылар, профиль, өтінімдер, нұсқаулық."""
import os
from datetime import date

import streamlit as st

from core.auth import hash_password, register, set_password, verify_password
from core.config import ADMIN_ROLES, LINKS, ROLES, role_name
from core.ui import download_buttons, external_app, is_super, render_journal
from views.workspaces import WORKSPACES


def home(db, user):
    st.header(f"👋 Сәлеметсіз бе, {user.get('full_name') or user['username']}!")
    st.caption(f"Рөліңіз: {role_name(user['role'])} · {date.today():%d.%m.%Y}")
    today = str(date.today())
    my_tasks = db.query("SELECT * FROM tasks WHERE assignee = ? AND done = 0 ORDER BY due_date", (user["username"],))
    inbox = db.query("SELECT id FROM documents WHERE (to_user = ? OR to_role = ?) AND status IN ('Жіберілді','Қаралуда')",
                     (user["username"], user["role"]))
    c = st.columns(4)
    c[0].metric("Орындалмаған тапсырма", len(my_tasks))
    c[1].metric("Мерзімі өткен", sum(1 for t in my_tasks if t["due_date"] and t["due_date"] < today))
    c[2].metric("Кіріс құжаттар", len(inbox))
    if user["role"] in ADMIN_ROLES:
        fb = db.query("SELECT sentiment FROM feedback WHERE status = 'Жаңа'" +
                      ("" if is_super(user) else " AND target_role = ?"), () if is_super(user) else (user["role"],))
        c[3].metric("Жаңа пікірлер", len(fb))
    if my_tasks:
        st.subheader("📌 Жақын тапсырмалар")
        for t in my_tasks[:5]:
            st.markdown(f"- **{t['title']}** — {t['due_date'] or ''} {t['priority'] or ''}")
    if is_super(user):
        st.subheader("🏫 Мектеп бойынша")
        u = db.query("SELECT role, COUNT(*) AS n FROM users GROUP BY role")
        d = db.query("SELECT status, COUNT(*) AS n FROM documents GROUP BY status")
        t = db.query("SELECT done, COUNT(*) AS n FROM tasks GROUP BY done")
        c1, c2, c3 = st.columns(3)
        c1.metric("Пайдаланушылар", sum(x["n"] for x in u))
        c2.metric("Құжаттар", sum(x["n"] for x in d))
        tot = sum(x["n"] for x in t)
        done = sum(x["n"] for x in t if int(x["done"]) == 1)
        c3.metric("Тапсырмалар орындалуы", f"{done / tot * 100:.0f}%" if tot else "—")
    st.subheader("🔗 Жылдам сілтемелер")
    cols = st.columns(4)
    for i, (lbl, key) in enumerate([("🍽 Асхана жұмысы", "canteen"), ("💡 ЭкоСвет", "ecosvet"),
                                    ("📚 Кітапхана", "library"), ("🎂 Туған күндер", "birthday")]):
        cols[i].link_button(lbl, LINKS[key], use_container_width=True)


def requests_page(db, user):
    st.header("🛠 Өтінімдер (IT және шаруашылық)")
    t1, t2 = st.tabs(["💻 IT-көмек", "🔧 Жөндеу (завхоз)"])
    with t1:
        render_journal(db, user, WORKSPACES["zavuch_it"]["journals"][1])
    with t2:
        render_journal(db, user, WORKSPACES["zavhoz"]["journals"][0])


def canteen(db, user):
    st.header("🍽 Асхана жұмысы")
    external_app("Асханаға өтінім", LINKS["canteen"], key="canteen")


def users_admin(db, user):
    st.header("👥 Пайдаланушылар және рөлдер")
    if not is_super(user):
        st.error("Тек бас әкімші / директор")
        return
    t1, t2 = st.tabs(["Тізім және рөлдер", "➕ Жаңа пайдаланушы"])
    with t1:
        df = db.df("SELECT id, username, full_name, email, role, position, subject, active, created_at FROM users "
                   "ORDER BY role, full_name")
        if df.empty:
            return
        df["active"] = df["active"].astype(int).astype(bool)
        ed = st.data_editor(df, hide_index=True, use_container_width=True, key="users_ed",
                            disabled=["id", "username", "created_at"],
                            column_config={"role": st.column_config.SelectboxColumn(
                                "Рөл", options=list(ROLES), required=True)})
        if st.button("💾 Өзгерістерді сақтау", type="primary"):
            for _, r in ed.iterrows():
                if r["username"] == user["username"] and r["role"] != "admin" and user["role"] == "admin":
                    continue  # өзін-өзі админнен шығармау
                db.update("users", int(r["id"]), {"full_name": r["full_name"], "email": r["email"],
                                                  "role": r["role"], "position": r["position"],
                                                  "subject": r["subject"], "active": int(bool(r["active"]))})
            st.success("Сақталды")
        st.caption("Рөл кодтары: " + "; ".join(f"{k} — {v}" for k, v in ROLES.items()))
        with st.expander("🔑 Пайдаланушы құпиясөзін ауыстыру"):
            un = st.selectbox("Пайдаланушы", df["username"].tolist())
            npw = st.text_input("Жаңа құпиясөз", type="password")
            if st.button("Орнату") and len(npw) >= 6:
                set_password(db, un, npw)
                st.success("Құпиясөз өзгертілді")
        download_buttons(df.drop(columns=["id"]), "Пайдаланушылар", "users")
    with t2:
        with st.form("new_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            un = c1.text_input("Логин *")
            pw = c2.text_input("Уақытша құпиясөз *", type="password")
            fn = c1.text_input("ТАӘ *")
            em = c2.text_input("Email *")
            rl = c1.selectbox("Рөл", list(ROLES), format_func=role_name)
            pos = c2.text_input("Лауазымы")
            subj = c1.text_input("Пәні")
            if st.form_submit_button("Құру", type="primary"):
                ok, msg = register(db, un, pw, fn, em, rl, pos, subj)
                (st.success if ok else st.error)(msg)


def profile(db, user):
    st.header("⚙ Профиль")
    st.write(f"**Логин:** {user['username']}  \n**Рөл:** {role_name(user['role'])}")
    with st.form("prof"):
        fn = st.text_input("ТАӘ", user.get("full_name") or "")
        em = st.text_input("Email (құпиясөзді қалпына келтіру үшін)", user.get("email") or "")
        pos = st.text_input("Лауазымы", user.get("position") or "")
        subj = st.text_input("Пәні", user.get("subject") or "")
        if st.form_submit_button("Сақтау"):
            db.update("users", user["id"], {"full_name": fn, "email": em, "position": pos, "subject": subj})
            st.session_state["user"].update({"full_name": fn, "email": em, "position": pos, "subject": subj})
            st.success("Сақталды")
    with st.form("pw"):
        st.subheader("🔑 Құпиясөзді ауыстыру")
        old = st.text_input("Ағымдағы құпиясөз", type="password")
        new = st.text_input("Жаңа құпиясөз (≥6)", type="password")
        new2 = st.text_input("Қайталаңыз", type="password")
        if st.form_submit_button("Ауыстыру"):
            row = db.query("SELECT password_hash FROM users WHERE id = ?", (user["id"],))[0]
            if not verify_password(old, row["password_hash"]):
                st.error("Ағымдағы құпиясөз қате")
            elif new != new2 or len(new) < 6:
                st.error("Жаңа құпиясөздер сәйкес емес немесе қысқа")
            else:
                db.update("users", user["id"], {"password_hash": hash_password(new)})
                st.success("Құпиясөз ауыстырылды")


def guide(db, user):
    st.header("📖 Нұсқаулық және супер-промт")
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PROMPT.md")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        st.download_button("⬇ PROMPT.md", txt.encode("utf-8"), "PROMPT.md")
        st.markdown(txt)
