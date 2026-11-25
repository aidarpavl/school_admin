"""⭐ Оқушылар рейтингі (reytingstudentszhd2026 үлгісімен) + 🪜 «Баспалдақтар» бөлімі."""
from datetime import date

import pandas as pd
import streamlit as st

from core.config import ADMIN_ROLES, CLASSES, LINKS
from core.ui import download_buttons, external_app, is_super
from views.feedback import feedback_form

CATEGORIES = {
    "Оқу үлгерімі": {"Үздік (5)": 10, "Екпінді (4-5)": 6, "Тоқсанды жақсы аяқтады": 3},
    "Олимпиада": {"Мектепішілік: 1 орын": 5, "Мектепішілік: 2-3 орын": 3, "Аудандық/қалалық: жүлде": 10,
                  "Облыстық: жүлде": 20, "Республикалық: жүлде": 40, "Халықаралық: жүлде": 60,
                  "Қатысу": 1},
    "Ғылыми жоба": {"Мектепішілік": 5, "Облыстық жүлде": 20, "Республикалық жүлде": 40, "Халықаралық": 60},
    "Спорт": {"Мектепішілік: жүлде": 4, "Аудандық/қалалық": 8, "Облыстық": 15, "Республикалық": 30,
              "Президенттік тест: жоғары": 5},
    "Шығармашылық": {"Мектепішілік": 3, "Қалалық": 8, "Облыстық": 15, "Республикалық": 25},
    "Қоғамдық белсенділік": {"Іс-шара ұйымдастыру": 4, "Еріктілік": 3, "Парламент мүшесі": 5,
                             "«Адал азамат» белсендісі": 4},
    "Тәртіп (айыппұл балл)": {"Ескерту": -3, "Сабақ босату": -5, "Тәртіп бұзу": -10},
}
EDITORS = ADMIN_ROLES | {"teacher", "pe", "nvp", "psychologist", "soc_ped"}


def rating(db, user):
    st.header("⭐ Оқушылар рейтингі")
    t1, t2, t3, t4 = st.tabs(["🏆 Рейтинг кестесі", "➕ Балл қосу", "👩‍🎓 Оқушылар тізімі", "🔗 Бастапқы сайт"])
    students = db.records("rating", "student")
    points = db.records("rating", "points")

    with t3:
        st.caption("Оқушыларды CSV арқылы жүктеу: бағандар «ТАӘ», «Сынып».")
        up = st.file_uploader("CSV / Excel", type=["csv", "xlsx"], key="st_up")
        if up is not None and user["role"] in ADMIN_ROLES and st.button("Импорттау"):
            d = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
            n = 0
            have = set(zip(students.get("name", []), students.get("class", []))) if not students.empty else set()
            for _, r in d.iterrows():
                nm, cl = str(r.iloc[0]).strip(), str(r.iloc[1]).strip()
                if nm and (nm, cl) not in have:
                    db.add_record("rating", "student", user["username"], {"name": nm, "class": cl})
                    n += 1
            st.success(f"{n} оқушы қосылды")
            st.rerun()
        with st.form("add_st", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            nm = c1.text_input("Оқушы ТАӘ")
            cl = c2.selectbox("Сынып", CLASSES)
            if st.form_submit_button("Қосу") and nm:
                db.add_record("rating", "student", user["username"], {"name": nm.strip(), "class": cl})
                st.rerun()
        if not students.empty:
            st.dataframe(students[["name", "class"]].rename(columns={"name": "ТАӘ", "class": "Сынып"}),
                         hide_index=True, use_container_width=True)

    with t2:
        if user["role"] not in EDITORS:
            st.info("Балл қосу құқығы жоқ")
        elif students.empty:
            st.warning("Алдымен «Оқушылар тізімі» бөліміне оқушыларды қосыңыз")
        else:
            with st.form("add_pts", clear_on_submit=True):
                opts = [f"{r['name']} ({r['class']})" for _, r in students.iterrows()]
                who = st.multiselect("Оқушы(лар)", opts)
                c1, c2 = st.columns(2)
                cat = c1.selectbox("Санат", list(CATEGORIES))
                lvl = c2.selectbox("Деңгей / нәтиже", list(CATEGORIES[cat].keys()) + ["Қолмен балл"])
                manual = c1.number_input("Қолмен балл (тек «Қолмен балл» үшін)", value=0)
                ev = c2.text_input("Іс-шара / пән")
                dt = c1.date_input("Күні", date.today())
                if st.form_submit_button("➕ Қосу", type="primary") and who:
                    pts = manual if lvl == "Қолмен балл" else CATEGORIES[cat][lvl]
                    for w in who:
                        name, cls = w.rsplit(" (", 1)
                        db.add_record("rating", "points", user["username"],
                                      {"name": name, "class": cls.rstrip(")"), "category": cat, "level": lvl,
                                       "points": pts, "event": ev, "date": str(dt)})
                    st.success(f"{len(who)} оқушыға {pts} балл қосылды")
                    st.rerun()

    with t1:
        if points.empty:
            st.info("Әзірге балл жоқ")
        else:
            points["points"] = pd.to_numeric(points["points"], errors="coerce").fillna(0)
            points["parallel"] = points["class"].str.extract(r"(\d+)")[0]
            c1, c2, c3 = st.columns(3)
            par = c1.selectbox("Параллель", ["Барлығы"] + sorted(points["parallel"].dropna().unique(), key=int))
            cls = c2.selectbox("Сынып", ["Барлығы"] + sorted(points["class"].unique()))
            per = c3.selectbox("Кезең", ["Оқу жылы", "Осы ай"])
            d = points
            if par != "Барлығы":
                d = d[d["parallel"] == par]
            if cls != "Барлығы":
                d = d[d["class"] == cls]
            if per == "Осы ай":
                d = d[d["date"].astype(str).str[:7] == str(date.today())[:7]]
            board = d.pivot_table(index=["name", "class"], columns="category", values="points",
                                  aggfunc="sum", fill_value=0)
            board["ЖАЛПЫ"] = board.sum(axis=1)
            board = board.sort_values("ЖАЛПЫ", ascending=False).reset_index()
            board.insert(0, "Орын", range(1, len(board) + 1))
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            board["Орын"] = board["Орын"].map(lambda x: f"{medals.get(x, '')} {x}")
            top = board.head(3)
            cols = st.columns(3)
            for i, (_, r) in enumerate(top.iterrows()):
                cols[i].metric(f"{r['Орын']} {r['name']}", f"{r['ЖАЛПЫ']:.0f} балл", r["class"])
            st.dataframe(board.rename(columns={"name": "Оқушы", "class": "Сынып"}), hide_index=True,
                         use_container_width=True)
            st.bar_chart(board.head(15).set_index("name")["ЖАЛПЫ"])
            st.markdown("**Сыныптар рейтингі**")
            cl = d.groupby("class")["points"].sum().sort_values(ascending=False)
            st.bar_chart(cl)
            download_buttons(board, "Оқушылар рейтингі", "rating")
            if is_super(user):
                with st.expander("Балл жазбаларын түзету"):
                    st.dataframe(points, hide_index=True, use_container_width=True)
                    rid = st.number_input("Өшірілетін жазба ID", step=1, value=0)
                    if st.button("Өшіру") and rid:
                        db.delete("records", int(rid))
                        st.rerun()

    with t4:
        external_app("Бастапқы рейтинг сайты", LINKS["rating"], key="rating_src")


def stupeni(db, user):
    st.header("🪜 Баспалдақтар (Ступени)")
    t1, t2, t3 = st.tabs(["🪜 Қосымша", "💬 Рөлдер бойынша пікір жіберу", "📥 Келген пікірлер"])
    with t1:
        external_app("«Ступени» қосымшасы (толық нұсқа)", LINKS["stupeni"], height=900, key="stupeni")
    with t2:
        st.caption("«Ступени» бойынша пікіріңіз таңдалған рөлге барады және ортақ талдауға қосылады.")
        feedback_form(db, user, source="Ступени", key="fb_stupeni", default_role="zavuch_innov")
    with t3:
        df = db.df("SELECT created_at, target_role, category, text, status FROM feedback WHERE source = 'Ступени' "
                   "ORDER BY id DESC")
        if not is_super(user) and not df.empty:
            df = df[df["target_role"] == user["role"]]
        if df.empty:
            st.info("Пікір жоқ")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.bar_chart(df["target_role"].value_counts())
