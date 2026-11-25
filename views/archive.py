"""🗄 Электрондық мұрағат: GitHub-тағы папкалар мен ішкі папкалар."""
import pandas as pd
import streamlit as st

from core.github_store import (FOLDERS, MAX_FILE_MB, REPO_SOFT_LIMIT_GB, ROOT, academic_year, can,
                               ensure_structure, get_store, safe_name, save_file)
from core.ui import is_super


def _size(b):
    b = float(b or 0)
    for u in ["Б", "КБ", "МБ", "ГБ"]:
        if b < 1024:
            return f"{b:.0f} {u}" if u == "Б" else f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} ТБ"


def render(db, user):
    st.header("🗄 Электрондық құжаттар мұрағаты")
    store = get_store()
    ok, info = store.check()
    (st.success if ok else st.error)(("GitHub: " if store.kind == "github" else "") + info)
    if store.kind == "local":
        st.caption("GitHub баптаулмаған — файлдар серверде уақытша сақталады. Secrets-ке GITHUB_TOKEN және "
                   "GITHUB_DOCS_REPO қосыңыз (README).")

    visible = [f for f in FOLDERS if can(user, f[0], "read")]
    if not visible:
        st.info("Сізге қолжетімді папка жоқ.")
        return

    t_browse, t_up, t_search, t_admin = st.tabs(["📁 Папкалар", "⬆ Жүктеу", "🔎 Іздеу", "⚙ Баптау / көлем"])

    with t_browse:
        folder = st.selectbox("Папка", [f[0] for f in visible],
                              format_func=lambda p: ("    " * p.count("/")) + dict((f[0], f[1]) for f in FOLDERS)[p])
        base = f"{ROOT}/{folder}"
        path = st.session_state.get("arch_path", base)
        if not path.startswith(base):
            path = base
        crumbs = path.split("/")
        st.caption("📍 " + " / ".join(crumbs[1:]))
        if path != base and st.button("⬅ Жоғары"):
            st.session_state["arch_path"] = path.rsplit("/", 1)[0]
            st.rerun()
        try:
            items = [i for i in store.list_dir(path) if i["name"] != ".gitkeep"]
        except Exception as e:
            st.error(f"Оқу қатесі: {e}")
            items = []
        for it in sorted(items, key=lambda x: (x["type"] != "dir", x["name"])):
            c1, c2, c3 = st.columns([6, 2, 2])
            if it["type"] == "dir":
                if c1.button(f"📁 {it['name']}", key=f"dir_{it['path']}"):
                    st.session_state["arch_path"] = it["path"]
                    st.rerun()
            else:
                c1.write(f"📄 {it['name']}")
                c2.caption(_size(it["size"]))
                if c3.button("⬇ Алу", key=f"get_{it['path']}"):
                    st.session_state["arch_dl"] = it["path"]
        if st.session_state.get("arch_dl", "").startswith(path):
            p = st.session_state["arch_dl"]
            try:
                st.download_button(f"💾 {p.rsplit('/', 1)[-1]} сақтау", store.get(p), p.rsplit("/", 1)[-1],
                                   key="arch_dl_btn", type="primary")
            except Exception as e:
                st.error(str(e))
        if not items:
            st.info("Папка бос")
        if can(user, folder, "write"):
            with st.expander("➕ Ішкі папка құру / 🗑 файлды өшіру"):
                newf = st.text_input("Жаңа ішкі папка атауы", key="newsub")
                if st.button("Құру") and newf:
                    store.put(f"{path}/{safe_name(newf)}/.gitkeep", b"", f"{user['username']}: папка {newf}")
                    st.rerun()
                files = [i["path"] for i in items if i["type"] == "file"]
                if files and (is_super(user) or user["role"] != "teacher"):
                    dp = st.selectbox("Өшірілетін файл", files, key="delf")
                    if st.button("Өшіру"):
                        store.delete(dp, f"{user['username']}: өшірді")
                        st.rerun()

    with t_up:
        writable = [f for f in visible if can(user, f[0], "write")]
        if not writable:
            st.info("Сізде жүктеу құқығы бар папка жоқ.")
        else:
            with st.form("arch_up", clear_on_submit=True):
                fld = st.selectbox("Қай папкаға", [f[0] for f in writable],
                                   format_func=lambda p: dict((f[0], f[1]) for f in FOLDERS)[p])
                sub = st.text_input("Ішкі папка (міндетті емес, мысалы: 7А сынып немесе Қараша)")
                by_year = st.checkbox(f"Оқу жылы бойынша бөлу ({academic_year()})", value=True)
                files = st.file_uploader(f"Файлдар (әрқайсысы ≤ {MAX_FILE_MB} МБ)", accept_multiple_files=True)
                if st.form_submit_button("⬆ Жүктеу", type="primary"):
                    target = fld + (f"/{safe_name(sub)}" if sub else "")
                    for f in files or []:
                        try:
                            p = save_file(store, target, f.name, f.getvalue(), user["username"], by_year)
                            db.add_record("archive", "upload", user["username"],
                                          {"path": p, "size": f.size, "folder": fld})
                            st.success(f"✔ {p}")
                        except Exception as e:
                            st.error(f"{f.name}: {e}")

    with t_search:
        q = st.text_input("Файл атауы бойынша іздеу")
        if q:
            try:
                allf = store.all_files()
            except Exception as e:
                st.error(str(e))
                allf = []
            res = [f for f in allf if q.lower() in f["path"].lower() and not f["path"].endswith(".gitkeep")
                   and can(user, f["path"].split("/", 1)[-1], "read")]
            st.write(f"Табылды: {len(res)}")
            for f in res[:100]:
                c1, c2 = st.columns([8, 2])
                c1.write(f"📄 {f['path']} · {_size(f['size'])}")
                if c2.button("⬇", key=f"s_{f['path']}"):
                    st.download_button("💾 Сақтау", store.get(f["path"]), f["path"].rsplit("/", 1)[-1],
                                       key=f"sd_{f['path']}")

        log = db.records("archive", "upload")
        if not log.empty:
            st.caption("Соңғы жүктеулер")
            st.dataframe(log[["path", "_author", "_created"]].head(30), hide_index=True, use_container_width=True)

    with t_admin:
        if not is_super(user):
            st.info("Тек бас әкімшіге.")
            return
        if st.button("🏗 Папкалар құрылымын құру/тексеру", type="primary"):
            try:
                n = ensure_structure(store, user["username"])
                st.success(f"Дайын. Жаңа папкалар: {n}")
            except Exception as e:
                st.error(str(e))
        try:
            allf = store.all_files()
            total = sum(f["size"] for f in allf)
            st.metric("Мұрағат көлемі", _size(total), help="GitHub: репо < 5 ГБ ұсынылады")
            st.progress(min(total / (REPO_SOFT_LIMIT_GB * 1024 ** 3), 1.0),
                        text=f"{total / (REPO_SOFT_LIMIT_GB * 1024 ** 3) * 100:.1f}% / {REPO_SOFT_LIMIT_GB} ГБ")
            if total > 3.5 * 1024 ** 3:
                st.warning("Көлем 3.5 ГБ-тан асты. Келесі оқу жылына жаңа репо ашыңыз "
                           "(GITHUB_DOCS_REPO = ...-{year}).")
            if allf:
                df = pd.DataFrame(allf)
                df["Папка"] = df["path"].str.split("/").str[1]
                st.bar_chart((df.groupby("Папка")["size"].sum() / 1024 ** 2).rename("МБ"))
        except Exception as e:
            st.error(str(e))
