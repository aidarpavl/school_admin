"""📈 Мектептің даму жоспарын жасау парағы: talismasters → SWOT → бөлімдер бойынша ұсыныстар → МДЖ құрастыру."""
import json
from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.analysis import MDJ_SECTIONS, build_mdj, swot_from_survey
from core.config import ADMIN_ROLES, LINKS
from core.export import doc_bytes
from core.github_store import get_store, save_file
from core.ui import external_app, is_super


def _get_swot(db) -> dict:
    df = db.records("mdj", "swot")
    if df.empty:
        return {"S": [], "W": [], "O": [], "T": []}
    r = df.iloc[0]
    return {k: list(r.get(k) or []) for k in "SWOT"}


def render(db, user):
    st.header("📈 Мектептің даму жоспарын жасау парағы")
    if user["role"] not in ADMIN_ROLES:
        st.info("Бұл бет әкімшілік мүшелеріне арналған. Ұсыныстарыңызды «Ұсыныстар мен пікірлер» бөлімі арқылы жіберіңіз.")
        return
    t1, t2, t3, t4 = st.tabs(["1️⃣ Сауалнама (talismasters)", "2️⃣ SWOT-талдау",
                              "3️⃣ Бөлімдер бойынша ұсыныстар", "4️⃣ МДЖ құрастыру"])

    with t1:
        external_app("Сауалнама: talismasters", LINKS["talismasters"], height=700, key="talis")
        st.markdown("**Сауалнама жауаптарын жүктеу** (talismasters-тен CSV/Excel экспорты)")
        up = st.file_uploader("Жауаптар файлы", type=["csv", "xlsx"], key="talis_up")
        scale = st.number_input("Шкаланың максимумы (мыс. 5)", value=5.0)
        if up is not None:
            d = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
            st.dataframe(d.head(50), use_container_width=True)
            num = d.select_dtypes("number")
            if not num.empty:
                st.bar_chart(num.mean().sort_values())
            auto = swot_from_survey(d, scale)
            st.markdown("**Автоматты SWOT ұсынысы:**")
            st.json(auto)
            if st.button("➡ SWOT-қа қосу", type="primary"):
                cur = _get_swot(db)
                merged = {k: list(dict.fromkeys(cur[k] + auto[k])) for k in "SWOT"}
                db.execute("DELETE FROM records WHERE module = 'mdj' AND kind = 'swot'")
                db.add_record("mdj", "swot", user["username"], merged)
                db.add_record("mdj", "survey", user["username"],
                              {"file": up.name, "rows": len(d), "means": json.loads(num.mean().to_json()) if not num.empty else {}})
                st.success("SWOT жаңартылды")

    with t2:
        cur = _get_swot(db)
        st.caption("Әр жолға бір тармақ. Сауалнамадан келген тармақтарды түзетуге болады.")
        c1, c2 = st.columns(2)
        names = {"S": "💪 Күшті жақтары (S)", "W": "⚠ Әлсіз жақтары (W)",
                 "O": "🌱 Мүмкіндіктер (O)", "T": "⛔ Қауіптер (T)"}
        new = {}
        for i, k in enumerate("SWOT"):
            col = c1 if i % 2 == 0 else c2
            new[k] = col.text_area(names[k], "\n".join(cur[k]), height=220, key=f"swot_{k}")
        if st.button("💾 SWOT сақтау", type="primary"):
            db.execute("DELETE FROM records WHERE module = 'mdj' AND kind = 'swot'")
            db.add_record("mdj", "swot", user["username"],
                          {k: [x.strip() for x in new[k].splitlines() if x.strip()] for k in "SWOT"})
            st.success("Сақталды")

    with t3:
        st.caption("Әр әкімшілік мүшесі өз бөлімі бойынша тақырыптар мен ұсыныстарын енгізеді.")
        with st.form("mdj_prop", clear_on_submit=True):
            sec = st.selectbox("Бөлім", MDJ_SECTIONS)
            topic = st.text_input("Тақырып / іс-шара *")
            prop = st.text_area("Ұсыныс, күтілетін нәтиже")
            c1, c2, c3 = st.columns(3)
            ind = c1.text_input("Индикатор (мыс. сапа 65% → 70%)")
            dl = c2.text_input("Мерзімі", f"{date.today().year}-{date.today().year + 1}")
            resp = c3.text_input("Жауапты", user.get("position") or "")
            if st.form_submit_button("➕ Қосу", type="primary") and topic:
                db.add_record("mdj", "proposal", user["username"],
                              {"section": sec, "topic": topic, "proposal": prop, "indicator": ind,
                               "deadline": dl, "responsible": resp})
                st.success("Қосылды")
        props = db.records("mdj", "proposal")
        if not props.empty:
            for sec in MDJ_SECTIONS:
                part = props[props["section"] == sec]
                if part.empty:
                    continue
                st.markdown(f"**{sec}** — {len(part)}")
                st.dataframe(part[["topic", "proposal", "indicator", "deadline", "responsible", "_author", "_id"]],
                             hide_index=True, use_container_width=True)
            mine = props if is_super(user) else props[props["_author"] == user["username"]]
            if not mine.empty:
                rid = st.selectbox("Өз ұсынысыңызды өшіру (ID)", mine["_id"].tolist())
                if st.button("🗑 Өшіру"):
                    db.delete("records", int(rid))
                    st.rerun()
            filled = props["section"].nunique()
            st.progress(filled / len(MDJ_SECTIONS), text=f"Толтырылған бөлімдер: {filled}/{len(MDJ_SECTIONS)}")

    with t4:
        c1, c2 = st.columns(2)
        school = c1.text_input("Мектеп атауы", "Дарынды балаларға арналған мектеп")
        y = date.today().year
        period = c2.text_input("Кезең", f"{y}–{y + 3} жылдар")
        mission = st.text_area("Миссия және пайымдау",
                               "Дарынды оқушылардың әлеуетін ашып, ұлттық құндылықтар негізінде бәсекеге қабілетті, "
                               "адал азамат тәрбиелеу.")
        st.info("Барлық бөлімдер толтырылғаннан кейін ғана төмендегі батырманы басыңыз.")
        if st.button("🏗 МДЖ құрастыру", type="primary", use_container_width=True):
            html = build_mdj(school, period, mission, _get_swot(db), db.records("mdj", "proposal"))
            st.session_state["mdj_html"] = html
            db.add_record("mdj", "built", user["username"], {"period": period, "html": html})
        if st.session_state.get("mdj_html"):
            html = st.session_state["mdj_html"]
            data = doc_bytes("Мектептің даму жоспары", html)
            st.download_button("📄 МДЖ (Word)", data, "MDZh.doc", type="primary")
            if st.button("🗄 Мұрағатқа сақтау (05_MDZh_SWOT)"):
                try:
                    p = save_file(get_store(), "05_MDZh_SWOT", f"MDZh_{date.today()}.doc", data, user["username"])
                    st.success(f"Сақталды: {p}")
                except Exception as e:
                    st.error(str(e))
            components.html(f"<div style='font-family:serif;background:#fff;color:#000;padding:16px'>{html}</div>",
                                  height=700, scrolling=True)
