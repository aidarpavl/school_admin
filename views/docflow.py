"""Құжат айналымы: әкімшілік ↔ мұғалімдер ↔ әдістемелік кабинет."""
import streamlit as st

from core.config import ADMIN_ROLES, DOC_CHANNELS, DOC_STATUSES, DOC_TYPES, ROLES, role_name
from core.db import now
from core.storage import fetch, upload
from core.ui import download_buttons, is_super


def _history(db, doc_id, actor, action, note=""):
    db.insert("doc_history", {"doc_id": doc_id, "actor": actor, "action": action, "note": note,
                              "created_at": now()})


def _doc_card(db, user, d, can_decide: bool):
    with st.expander(f"#{d['id']} · {d['title']} — **{d['status']}** · {d['doc_type']} · {d['author']}"):
        st.markdown(f"**Арна:** {d['channel']}  \n**Кімге:** {role_name(d['to_role'] or '') or ''} "
                    f"{d['to_user'] or ''}  \n**Мерзімі:** {d['due_date'] or '—'}  \n**Құрылды:** {d['created_at']}")
        if d["content"]:
            st.markdown(d["content"])
        url = d["file_url"] or ""
        for part in [u for u in url.split(" | ") if u]:
            if part.startswith("store://"):
                try:
                    data = fetch(part)
                    st.download_button(f"📎 {part.rsplit('/', 1)[-1]}", data, part.rsplit("/", 1)[-1],
                                       key=f"dl_{d['id']}_{hash(part)}")
                except Exception as e:
                    st.warning(f"Файлды алу мүмкін болмады: {e}")
            else:
                st.markdown(f"📎 [Тіркеме / сілтеме]({part})")
        if d["resolution"]:
            st.info(f"Бұрыштама: {d['resolution']}")
        hist = db.df("SELECT created_at AS Уақыт, actor AS Кім, action AS Әрекет, note AS Түсініктеме "
                      "FROM doc_history WHERE doc_id = ? ORDER BY id", (d["id"],))
        if not hist.empty:
            st.dataframe(hist, hide_index=True, use_container_width=True)
        if can_decide and d["status"] not in ("Бекітілді", "Мұрағат"):
            res = st.text_area("Бұрыштама / ескерту", key=f"res_{d['id']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("👁 Қаралуда", key=f"rv_{d['id']}"):
                db.update("documents", d["id"], {"status": "Қаралуда", "updated_at": now()})
                _history(db, d["id"], user["username"], "Қаралуда", res)
                st.rerun()
            if c2.button("✅ Бекіту", key=f"ok_{d['id']}", type="primary"):
                db.update("documents", d["id"], {"status": "Бекітілді", "resolution": res, "updated_at": now()})
                _history(db, d["id"], user["username"], "Бекітілді", res)
                st.rerun()
            if c3.button("↩ Қайтару", key=f"bk_{d['id']}"):
                db.update("documents", d["id"], {"status": "Қайтарылды", "resolution": res, "updated_at": now()})
                _history(db, d["id"], user["username"], "Қайтарылды", res)
                st.rerun()
        if d["author"] == user["username"] and d["status"] == "Қайтарылды":
            if st.button("🔁 Түзетіп, қайта жіберу", key=f"rs_{d['id']}"):
                db.update("documents", d["id"], {"status": "Жіберілді", "updated_at": now()})
                _history(db, d["id"], user["username"], "Қайта жіберілді")
                st.rerun()
        if is_super(user) and d["status"] == "Бекітілді":
            if st.button("🗄 Мұрағатқа", key=f"ar_{d['id']}"):
                db.update("documents", d["id"], {"status": "Мұрағат", "updated_at": now()})
                _history(db, d["id"], user["username"], "Мұрағатқа")
                st.rerun()


def render(db, user):
    st.header("📂 Құжат айналымы")
    st.caption("Әкімшілік ішкі құжаттары, мұғалімдер → әкімшілік, әдістемелік кабинет ↔ мұғалімдер/әкімшілік. "
               "Мәртебелер: Жоба → Жіберілді → Қаралуда → Бекітілді / Қайтарылды → Мұрағат.")
    t_new, t_in, t_out, t_all = st.tabs(["✉ Жаңа құжат", "📥 Кіріс", "📤 Шығыс", "📚 Тізілім"])

    users = db.query("SELECT username, full_name, role FROM users WHERE active = 1 ORDER BY full_name")
    ulabel = {u["username"]: f"{u['full_name'] or u['username']} ({role_name(u['role'])})" for u in users}

    with t_new:
        with st.form("new_doc", clear_on_submit=True):
            title = st.text_input("Құжат атауы *")
            c1, c2 = st.columns(2)
            dtype = c1.selectbox("Түрі", DOC_TYPES)
            channel = c2.selectbox("Арна", DOC_CHANNELS)
            to_role = c1.selectbox("Кімге (рөл)", [""] + list(ROLES), format_func=lambda r: role_name(r) or "—")
            to_user = c2.selectbox("Немесе нақты адам", [""] + list(ulabel), format_func=lambda u: ulabel.get(u, "—"))
            due = c1.date_input("Қарау мерзімі")
            draft = c2.checkbox("Жоба ретінде сақтау (жібермеу)")
            content = st.text_area("Мазмұны / ілеспе хат")
            files = st.file_uploader("Файлдар (≤50 МБ)", accept_multiple_files=True)
            link = st.text_input("немесе Google Drive сілтемесі")
            if st.form_submit_button("Жіберу", type="primary"):
                if not title or not (to_role or to_user or draft):
                    st.error("Атауы мен алушыны көрсетіңіз")
                else:
                    urls = []
                    try:
                        for f in files or []:
                            urls.append(upload(f.name, f.getvalue(), user["username"]))
                    except Exception as e:
                        st.error(f"Файл жүктелмеді: {e}")
                    if link:
                        urls.append(link)
                    did = db.insert("documents", {
                        "title": title, "doc_type": dtype, "channel": channel, "author": user["username"],
                        "to_role": to_role, "to_user": to_user, "status": "Жоба" if draft else "Жіберілді",
                        "content": content, "file_url": " | ".join(urls), "due_date": str(due),
                        "created_at": now(), "updated_at": now()})
                    _history(db, did, user["username"], "Құрылды" if draft else "Жіберілді")
                    st.success(f"Құжат №{did} тіркелді")

    with t_in:
        inbox = db.query("SELECT * FROM documents WHERE (to_user = ? OR to_role = ?) AND status <> 'Жоба' "
                         "ORDER BY id DESC", (user["username"], user["role"]))
        if is_super(user):
            inbox = db.query("SELECT * FROM documents WHERE status IN ('Жіберілді','Қаралуда') ORDER BY id DESC")
        st.metric("Қарауды күтуде", sum(1 for d in inbox if d["status"] in ("Жіберілді", "Қаралуда")))
        for d in inbox:
            _doc_card(db, user, d, can_decide=True)
        if not inbox:
            st.info("Кіріс құжаттар жоқ")

    with t_out:
        out = db.query("SELECT * FROM documents WHERE author = ? ORDER BY id DESC", (user["username"],))
        for d in out:
            _doc_card(db, user, d, can_decide=False)
            if d["status"] == "Жоба" and st.button(f"📨 №{d['id']} жіберу", key=f"send_{d['id']}"):
                db.update("documents", d["id"], {"status": "Жіберілді", "updated_at": now()})
                _history(db, d["id"], user["username"], "Жіберілді")
                st.rerun()
        if not out:
            st.info("Сіз әлі құжат жібермедіңіз")

    with t_all:
        if user["role"] not in ADMIN_ROLES:
            st.info("Толық тізілім әкімшілікке қолжетімді.")
            return
        df = db.df("SELECT id, title, doc_type, channel, author, to_role, to_user, status, due_date, created_at "
                   "FROM documents ORDER BY id DESC")
        if df.empty:
            st.info("Құжат жоқ")
            return
        c1, c2 = st.columns(2)
        sf = c1.multiselect("Мәртебе", DOC_STATUSES)
        cf = c2.multiselect("Арна", DOC_CHANNELS)
        if sf:
            df = df[df["status"].isin(sf)]
        if cf:
            df = df[df["channel"].isin(cf)]
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.bar_chart(df["status"].value_counts())
        download_buttons(df, "Құжаттар тізілімі", "doc_register")
