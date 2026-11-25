"""Тапсырмалар (галочкамен) және міндеттерді бөлу матрицасы."""
from datetime import date

import pandas as pd
import streamlit as st

from core.config import ADMIN_ROLES, role_name
from core.db import now
from core.ui import download_buttons, is_super

DUTIES = [
    "Оқу жоспары, РОЖ, сабақ кестесі", "Тарификация, жүктеме", "Электрондық журналды бақылау",
    "БЖБ/ТЖБ мониторингі", "Мектепішілік бақылау (ВШК)", "Сабаққа қатысу", "ҰБТ/МОДО/ВОУД дайындығы",
    "Тәрбие жоспары, «Адал азамат»", "Сынып жетекшілер жұмысы", "Құқық бұзушылық профилактикасы",
    "Үйірмелер мен секциялар", "Ата-аналармен жұмыс", "Цифрлық инфрақұрылым, техника",
    "Мектеп сайты, әлеуметтік желі", "Kundelik/Bilimal әкімшілігі", "Педагогтер аттестациясы",
    "Біліктілікті арттыру курстары", "Жас мамандар, тәлімгерлік", "Инновациялық жобалар",
    "Олимпиадалар", "Ғылыми жобалар", "Дарынды балалар банкі", "Оқушылар рейтингі",
    "Әдістемелік бірлестіктер", "Педкеңес хаттамалары", "МТБ, жөндеу, инвентарь",
    "Өрт/антитеррор қауіпсіздігі", "Энергия үнемдеу", "Асхана бақылауы", "МДЖ әзірлеу",
]


def _users(db, roles=None):
    us = db.query("SELECT username, full_name, role FROM users WHERE active = 1 ORDER BY full_name")
    if roles:
        us = [u for u in us if u["role"] in roles]
    return us


def render(db, user):
    st.header("✅ Тапсырмалар және міндеттер")
    tabs = ["📋 Менің тапсырмаларым"]
    if user["role"] in ADMIN_ROLES:
        tabs += ["➕ Тапсырма беру", "📊 Орындалу бақылауы"]
    if is_super(user):
        tabs += ["🧩 Міндеттерді бөлу (галочка)"]
    t = st.tabs(tabs)

    with t[0]:
        my = db.query("SELECT * FROM tasks WHERE assignee = ? ORDER BY done, due_date", (user["username"],))
        if not my:
            st.info("Сізге берілген тапсырма жоқ.")
        for task in my:
            overdue = not task["done"] and task["due_date"] and task["due_date"] < str(date.today())
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"**{task['title']}** {'🔴 мерзімі өтті' if overdue else ''}  \n"
                            f"{task['description'] or ''}  \n"
                            f"📅 {task['due_date'] or '—'} · {task['priority'] or ''} · беруші: {task['created_by']}")
                done = c2.checkbox("Орындалды", value=bool(task["done"]), key=f"td_{task['id']}")
                if done != bool(task["done"]):
                    db.update("tasks", task["id"], {"done": int(done), "done_at": now() if done else None})
                    st.rerun()
                rep = st.text_input("Есеп / түсініктеме", value=task["report"] or "", key=f"tr_{task['id']}")
                if rep != (task["report"] or ""):
                    db.update("tasks", task["id"], {"report": rep})

    if user["role"] in ADMIN_ROLES:
        with t[1]:
            users = _users(db)
            labels = {u["username"]: f"{u['full_name'] or u['username']} — {role_name(u['role'])}" for u in users}
            with st.form("new_task", clear_on_submit=True):
                title = st.text_input("Тапсырма *")
                desc = st.text_area("Сипаттама")
                c1, c2 = st.columns(2)
                due = c1.date_input("Мерзімі", value=date.today())
                pr = c2.selectbox("Басымдық", ["🔴 Шұғыл", "🟠 Маңызды", "🟢 Қалыпты"], index=2)
                by_role = st.multiselect("Рөл бойынша барлығына", sorted({u["role"] for u in users}),
                                         format_func=role_name)
                who = st.multiselect("Немесе нақты адамдар", list(labels), format_func=lambda x: labels[x])
                if st.form_submit_button("Тапсырма беру", type="primary"):
                    targets = set(who) | {u["username"] for u in users if u["role"] in by_role}
                    if not title or not targets:
                        st.error("Тапсырма мәтіні мен орындаушыны көрсетіңіз")
                    else:
                        for a in targets:
                            db.insert("tasks", {"title": title, "description": desc, "assignee": a,
                                                "created_by": user["username"], "due_date": str(due),
                                                "priority": pr, "done": 0, "created_at": now()})
                        st.success(f"{len(targets)} адамға жіберілді")

        with t[2]:
            df = db.df("SELECT * FROM tasks ORDER BY id DESC")
            if not is_super(user) and not df.empty:
                df = df[df["created_by"] == user["username"]]
            if df.empty:
                st.info("Тапсырмалар жоқ")
            else:
                df["done"] = df["done"].astype(int)
                stat = df.groupby("assignee").agg(барлығы=("id", "size"), орындалды=("done", "sum")).reset_index()
                stat["%"] = (stat["орындалды"] / stat["барлығы"] * 100).round(0)
                today = str(date.today())
                over = df[(df["done"] == 0) & (df["due_date"] < today)]
                c1, c2, c3 = st.columns(3)
                c1.metric("Барлық тапсырма", len(df))
                c2.metric("Орындалды", f"{df['done'].mean() * 100:.0f}%")
                c3.metric("Мерзімі өткен", len(over))
                st.dataframe(stat, hide_index=True, use_container_width=True)
                st.bar_chart(stat.set_index("assignee")["%"])
                # Әкімші де галочка қоя алады
                ed = st.data_editor(df[["id", "title", "assignee", "due_date", "priority", "done", "report"]]
                                    .assign(done=lambda d: d["done"].astype(bool)),
                                    disabled=["id", "title", "assignee", "due_date", "priority", "report"],
                                    hide_index=True, use_container_width=True, key="task_editor")
                if st.button("💾 Белгілерді сақтау"):
                    for _, r in ed.iterrows():
                        db.update("tasks", int(r["id"]), {"done": int(bool(r["done"]))})
                    st.success("Сақталды")
                download_buttons(df.drop(columns=["description"]), "Тапсырмалардың орындалуы", "tasks")

    if is_super(user):
        with t[-1]:
            st.caption("Әкімшілік мүшелеріне функционалдық міндеттерді галочка арқылы бекітіңіз.")
            admins = _users(db, ADMIN_ROLES - {"admin"})
            if not admins:
                st.warning("Әкімшілік мүшелері тіркелмеген. «Пайдаланушылар» бөлімінен қосыңыз.")
                return
            custom = st.text_input("Жаңа міндет қосу (тізімде жоқ болса)")
            existing = db.query("SELECT * FROM duties")
            duty_list = DUTIES + sorted({d["duty"] for d in existing} - set(DUTIES))
            if custom and custom not in duty_list:
                duty_list.append(custom)
            have = {(d["duty"], d["username"]) for d in existing}
            names = {u["username"]: (u["full_name"] or u["username"]) for u in admins}
            mat = pd.DataFrame({"Міндет": duty_list})
            for un, nm in names.items():
                mat[nm] = [(d, un) in have for d in duty_list]
            ed = st.data_editor(mat, hide_index=True, use_container_width=True, disabled=["Міндет"],
                                key="duty_matrix", height=600)
            if st.button("💾 Міндеттерді бекіту", type="primary"):
                db.execute("DELETE FROM duties")
                for _, r in ed.iterrows():
                    for un, nm in names.items():
                        if bool(r[nm]):
                            db.insert("duties", {"duty": r["Міндет"], "username": un,
                                                 "assigned_by": user["username"], "created_at": now()})
                st.success("Міндеттер бөлінді")
            download_buttons(ed.replace({True: "✔", False: ""}), "Әкімшілік мүшелерінің міндеттерін бөлу", "duties")
