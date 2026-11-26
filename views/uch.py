"""📚 Оқу ісі (оқу ісі жөніндегі орынбасар): МОДО, ҰБТ, PISA, Үлгерім, Сабаққа қатысу, Анализдер."""
import hashlib
import io
from datetime import date

import pandas as pd
import streamlit as st

from core import ai
from core import uch_parsers as U
from core.config import ROLES, role_name
from core.db import now
from core.export import doc_bytes, esc
from core.ui import download_buttons
from views import observation

PERIODS = ["1 тоқсан", "2 тоқсан", "3 тоқсан", "4 тоқсан", "1 жартыжылдық", "2 жартыжылдық", "Жылдық"]
PER_MAP = {"1 четверть": "1 тоқсан", "2 четверть": "2 тоқсан", "3 четверть": "3 тоқсан", "4 четверть": "4 тоқсан"}


def _year_default():
    d = date.today()
    y = d.year if d.month >= 9 else d.year - 1
    return f"{y}-{y + 1}"


def _period_inputs(key, meta=None):
    meta = meta or {}
    c1, c2 = st.columns(2)
    y = meta.get("Учебный год") or meta.get("Год обучения") or _year_default()
    year = c1.text_input("Оқу жылы", str(y).replace(" ", ""), key=f"y_{key}")
    p = PER_MAP.get(str(meta.get("Период", "")).strip().lower(), None)
    period = c2.selectbox("Кезең", PERIODS, index=PERIODS.index(p) if p in PERIODS else 0, key=f"p_{key}")
    return year, period


def _thresholds(key):
    th = dict(U.THRESHOLDS)
    with st.expander("⚙ Нормалар (әлсіз жақты анықтау шектері)"):
        c = st.columns(4)
        th["quality"] = c[0].number_input("Сапа % ≥", value=float(th["quality"]), key=f"thq_{key}")
        th["avg"] = c[1].number_input("Орташа балл ≥", value=float(th["avg"]), step=0.1, key=f"tha_{key}")
        th["attendance"] = c[2].number_input("Қатысу % ≥", value=float(th["attendance"]), key=f"tht_{key}")
        th["sor_quality"] = c[3].number_input("БЖБ/ТЖБ сапа % ≥", value=float(th["sor_quality"]), key=f"ths_{key}")
    return th


def _chart_for(df: pd.DataFrame):
    if df is None or df.empty:
        return
    for metric in ["Сапа %", "Қатысу %", "Орташа сапа %", "Орташа %"]:
        if metric in df.columns:
            idx = [c for c in df.columns if df[c].dtype == object or c in ("Параллель",)]
            if not idx:
                return
            key = idx[0] if len(idx) == 1 or len(df) == df[idx[0]].nunique() else idx[:2]
            s = df.set_index(key)[metric] if isinstance(key, str) else \
                df.assign(_k=df[key].astype(str).agg(" / ".join, axis=1)).set_index("_k")[metric]
            st.bar_chart(s.head(40))
            return


def _report_html(title, year, period, tables, weak, ai_data, plan):
    h = [f"<h1>{esc(title)}</h1><p style='text-align:center'>{esc(year)} оқу жылы, {esc(period)}</p>"]
    if ai_data:
        h.append(f"<h2>Қорытынды</h2><p>{esc(ai_data.get('summary', ''))}</p>")
        if ai_data.get("strengths"):
            h.append("<h3>Күшті жақтар</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in ai_data["strengths"]) + "</ul>")
    for n, d in tables.items():
        if isinstance(d, pd.DataFrame) and not d.empty:
            h.append(f"<h2>{esc(n)}</h2>{d.to_html(index=False, na_rep='')}")
    h.append("<h2>Анықталған олқылықтар</h2>")
    h.append(pd.DataFrame(weak).to_html(index=False) if weak else "<p>Олқылық анықталмады.</p>")
    if ai_data:
        if ai_data.get("weaknesses"):
            h.append("<h3>Әлсіз жақтар және себептері</h3><ul>" +
                     "".join(f"<li>{esc(x)}</li>" for x in ai_data["weaknesses"]) + "</ul>")
        if ai_data.get("recommendations"):
            h.append("<h2>Ұсыныстар</h2><ul>" + "".join(
                f"<li><b>{esc(r.get('target', ''))}:</b> {esc(r.get('text', ''))}</li>" if isinstance(r, dict)
                else f"<li>{esc(r)}</li>" for r in ai_data["recommendations"]) + "</ul>")
    if plan is not None and not plan.empty:
        h.append(f"<h2>Олқылықтарды жою жоспары</h2>{plan.to_html(index=False)}")
    h.append("<p><br>Оқу ісі жөніндегі орынбасар: ____________</p>")
    return "".join(h)


def _ai_and_plan(db, user, kind, title, year, period, tables, weak, files_key, context=""):
    """ЖИ талдауы + ереже негізіндегі жоспар + сақтау + Word + тапсырмаға айналдыру."""
    st.subheader("🔎 Анықталған олқылықтар")
    if weak:
        wdf = pd.DataFrame(weak)
        st.dataframe(wdf, hide_index=True, use_container_width=True)
        c = st.columns(3)
        c[0].metric("🔴 Шұғыл", sum(w["Деңгей"] == "🔴" for w in weak))
        c[1].metric("🟠 Назар аудару", sum(w["Деңгей"] == "🟠" for w in weak))
        c[2].metric("🟢 Резерв / мүмкіндік", sum(w["Деңгей"] == "🟢" for w in weak))
    else:
        st.success("Белгіленген нормалар бойынша олқылық анықталмады.")

    st.subheader("🤖 ЖИ талдауы, ұсыныстар және жоспар")
    sk = f"ai_{kind}_{files_key}"
    prov = ai.provider()
    st.caption(f"ЖИ: {prov or 'баптаулмаған — ереже негізіндегі ұсыныстар қолданылады'} · "
               "ЖИ-ге тек жиынтық сандар жіберіледі, оқушылардың аты-жөні жіберілмейді.")
    if st.button("🤖 ЖИ арқылы талдау жасау", type="primary", key=f"aib_{sk}", disabled=not prov):
        with st.spinner("ЖИ талдап жатыр..."):
            st.session_state[sk] = ai.run_analysis(title, f"{year}, {period}", tables, weak, context)
    res = st.session_state.get(sk)
    ai_data = res.get("data") if res else None
    if res and not res.get("ok"):
        st.error(res.get("error"))
        if res.get("raw"):
            st.markdown(res["raw"])
    if ai_data:
        st.markdown(f"**Қорытынды.** {ai_data.get('summary', '')}")
        c1, c2 = st.columns(2)
        c1.markdown("**💪 Күшті жақтар**\n" + "\n".join(f"- {x}" for x in ai_data.get("strengths", [])))
        c2.markdown("**⚠ Әлсіз жақтар**\n" + "\n".join(f"- {x}" for x in ai_data.get("weaknesses", [])))
        st.markdown("**📌 Ұсыныстар**\n" + "\n".join(
            f"- **{r.get('target', '')}:** {r.get('text', '')}" if isinstance(r, dict) else f"- {r}"
            for r in ai_data.get("recommendations", [])))
        plan = pd.DataFrame(ai_data.get("plan", []))
    else:
        plan = U.rule_plan(weak)
        if not plan.empty:
            st.caption("Төмендегі жоспар ережелер бойынша автоматты құрылды (ЖИ кілті қосылса — толығырақ болады).")
    st.markdown("**🗓 Олқылықтарды жою жоспары** (кестені түзетуге, жол қосуға болады)")
    plan = st.data_editor(plan if not plan.empty else pd.DataFrame(
        columns=["Мәселе", "Іс-шара", "Жауапты", "Мерзімі", "Күтілетін нәтиже"]),
        num_rows="dynamic", use_container_width=True, key=f"plan_{sk}")

    c1, c2, c3 = st.columns(3)
    html = _report_html(title, year, period, tables, weak, ai_data, plan)
    c1.download_button("📄 Анализ + жоспар (Word)", doc_bytes(title, html, landscape=True),
                       f"{kind}_{year}_{period}.doc", key=f"doc_{sk}", use_container_width=True)
    if c2.button("💾 Анализді сақтау", key=f"save_{sk}", use_container_width=True):
        db.add_record("uch_an", kind, user["username"], {
            "title": title, "year": year, "period": period,
            "tables": {n: d.head(300).to_dict("records") for n, d in tables.items() if isinstance(d, pd.DataFrame)},
            "weak": weak, "ai": ai_data, "plan": plan.to_dict("records")})
        st.success("Сақталды («Сақталған анализдер» және «Үлгерім» динамикасында көрінеді)")
    with c3.popover("✅ Жоспарды тапсырмаға айналдыру", use_container_width=True):
        roles = st.multiselect("Кімге (рөл)", list(ROLES), default=["zavuch_uch"], format_func=role_name,
                               key=f"tr_{sk}")
        due = st.date_input("Мерзімі", key=f"td_{sk}")
        if st.button("Тапсырма беру", key=f"tb_{sk}") and not plan.empty:
            us = [u["username"] for u in db.query("SELECT username, role FROM users WHERE active = 1")
                  if u["role"] in roles]
            n = 0
            for _, r in plan.iterrows():
                for un in us:
                    db.insert("tasks", {"title": str(r.get("Іс-шара", ""))[:200], "description":
                                        f"{title} ({period}). Мәселе: {r.get('Мәселе', '')}. Нәтиже: "
                                        f"{r.get('Күтілетін нәтиже', '')}", "assignee": un,
                                        "created_by": user["username"], "due_date": str(due),
                                        "priority": "🟠 Маңызды", "done": 0, "created_at": now()})
                    n += 1
            st.success(f"{n} тапсырма берілді")


def _files_key(files):
    h = hashlib.md5()
    for f in files:
        h.update(f.name.encode())
        h.update(str(f.size).encode())
    return h.hexdigest()[:10]


HELP = {
    "school": "Kundelik/Bilimal: «Данные по успеваемости школы» — параллельдер бойынша есеп (1 файл).",
    "subject": "«Данные по предмету» — бір пән бойынша барлық сыныптар. Бірнеше пәннің файлын бірге жүктеңіз → "
               "пәндер, параллельдер, сыныптар бойынша салыстыру.",
    "klass": "«Данные по успеваемости класса» — оқушылар × пәндер. Барлық сыныптардың файлын бірге жүктеңіз → "
             "мектеп бойынша сыныптар/параллельдер/пәндер есебі және резерв оқушылар.",
    "report": "Report constructor (үлгерім): пәндер бойынша «Барлық сыныптар» немесе параллельдер бойынша.",
    "sor": "БЖБ/ТЖБ (СОР/СОЧ) нәтижелерін талдау файлдары. Барлық мұғалімдердің файлдарын бірге жүктеңіз → "
           "пәндер, сыныптар, параллельдер, мұғалімдер бойынша.",
    "attend": "Report constructor (сабаққа қатысу): пәндер × параллельдер × сыныптар бойынша қалған сабақтар.",
}


def analysis_tab(db, user, kind):
    st.markdown(f"#### {U.TYPE_NAMES[kind]}")
    st.caption(HELP[kind])
    files = st.file_uploader("Excel файл(дар)ы", type=["xlsx", "xls"], accept_multiple_files=True, key=f"up_{kind}")
    if not files:
        st.info("Файлды жүктеңіз. Бағдарлама файл түрін өзі тексереді.")
        return
    parsed, metas, errors = [], [], []
    for f in files:
        try:
            raw = U.read_raw(f)
            k = U.detect_type(raw)
            if k != kind:
                errors.append(f"«{f.name}»: бұл файл «{U.TYPE_NAMES.get(k, 'белгісіз')}» түріне ұқсайды — "
                              f"сәйкес бөлімге жүктеңіз.")
                continue
            p = getattr(U, f"parse_{kind}")(raw)
            parsed.append(p)
            metas.append(p["meta"])
        except Exception as e:
            errors.append(f"«{f.name}»: оқу қатесі — {e}")
    for e in errors:
        st.warning(e)
    if not parsed:
        return
    year, period = _period_inputs(kind, metas[0] if metas else {})
    th = _thresholds(kind)

    total = None
    if kind == "school":
        tables, total = parsed[0]["tables"], parsed[0]["total"]
    elif kind == "subject":
        tables = U.agg_subject(pd.concat([p["tables"]["Сыныптар бойынша"] for p in parsed], ignore_index=True))
    elif kind == "klass":
        tables = U.agg_klass(pd.concat([p["tables"]["Оқушылар"] for p in parsed], ignore_index=True),
                             pd.concat([p["tables"]["Пәндер бойынша"] for p in parsed], ignore_index=True))
    elif kind == "report":
        tables = parsed[0]["tables"] if len(parsed) == 1 else {
            "Пәндер бойынша": pd.concat([p["tables"]["Пәндер бойынша"] for p in parsed], ignore_index=True)}
    elif kind == "sor":
        tables = U.agg_sor(pd.concat([p["tables"]["Жұмыстар"] for p in parsed], ignore_index=True))
    else:
        tables = U.agg_attend(pd.concat([p["tables"]["Деректер"] for p in parsed], ignore_index=True))
    weak = U.find_weak(kind, tables, th)

    st.success(f"Өңделді: {len(parsed)} файл")
    m = st.columns(4)
    if total:
        m[0].metric("Оқушы", int(total["Оқушы саны"]))
        m[1].metric("Сапа %", total["Сапа %"])
        m[2].metric("Үлгерім %", total["Үлгерім %"])
        m[3].metric("Орташа балл", total["Орташа балл"])
    else:
        first = next(iter(tables.values()))
        for i, col in enumerate([c for c in ["Сапа %", "Үлгерім %", "Қатысу %", "Орташа сапа %", "Орташа балл"]
                                 if c in first.columns][:4]):
            m[i].metric(f"Орташа {col}", round(pd.to_numeric(first[col], errors="coerce").mean(), 2))
    view = st.radio("Есеп түрі", list(tables.keys()), horizontal=True, key=f"view_{kind}")
    df = tables[view]
    st.dataframe(df, hide_index=True, use_container_width=True)
    _chart_for(df)
    download_buttons(df, f"{U.TYPE_NAMES[kind]} — {view}", f"{kind}_{view}")
    _ai_and_plan(db, user, kind, U.TYPE_NAMES[kind], year, period, tables, weak, _files_key(files))


# ---------------- МОДО / PISA (баллдық бағалау) ----------------
MODO_AREAS = ["Математикалық сауаттылық", "Оқу сауаттылығы", "Жаратылыстану сауаттылығы",
              "Қазақстан тарихы", "Қазақ тілі", "Орыс тілі", "Ағылшын тілі"]
PISA_AREAS = ["Оқу сауаттылығы", "Математикалық сауаттылық", "Жаратылыстану сауаттылығы", "Қаржылық сауаттылық",
              "Креативті ойлау"]


def pisa_level(p):
    if p is None or pd.isna(p):
        return None
    for lim, name in [(20, "1-ден төмен"), (35, "1-деңгей"), (50, "2-деңгей (базалық)"), (65, "3-деңгей"),
                      (80, "4-деңгей"), (90, "5-деңгей")]:
        if p < lim:
            return name
    return "6-деңгей"


def modo_level(p):
    if p is None or pd.isna(p):
        return None
    return "Төмен" if p < 40 else ("Орта" if p < 85 else "Жоғары")


def scored_module(db, user, module, title, areas, level_fn, low_levels, help_txt):
    st.caption(help_txt)
    t_in, t_an, t_hist = st.tabs(["📥 Нәтижелерді енгізу", "📊 Талдау + ЖИ", "🗂 Тарих / динамика"])
    tmpl = pd.DataFrame({"Оқушы": ["Мысал Оқушы"], "Сынып": ["9 А"], "Бағыт": [areas[0]], "Балл": [12.0],
                         "Макс. балл": [20.0]})
    with t_in:
        bio = io.BytesIO()
        tmpl.to_excel(bio, index=False)
        st.download_button("⬇ Excel үлгісі", bio.getvalue(), f"{module}_template.xlsx", key=f"tpl_{module}")
        c1, c2, c3 = st.columns(3)
        year = c1.text_input("Оқу жылы", _year_default(), key=f"yy_{module}")
        stage = c2.text_input("Кезең / байқау атауы", "1-байқау", key=f"st_{module}")
        dt = c3.date_input("Күні", key=f"dt_{module}")
        up = st.file_uploader("Excel/CSV (бағандар: Оқушы, Сынып, Бағыт, Балл, Макс. балл)", type=["xlsx", "csv"],
                              key=f"upl_{module}")
        data = tmpl.iloc[0:0]
        if up is not None:
            data = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
        data = st.data_editor(data, num_rows="dynamic", use_container_width=True, key=f"ed_{module}",
                              column_config={"Бағыт": st.column_config.SelectboxColumn(options=areas)})
        if st.button("💾 Нәтижелерді сақтау", type="primary", key=f"sv_{module}") and not data.empty:
            db.add_record(module, "results", user["username"], {"year": year, "stage": stage, "date": str(dt),
                                                                "rows": data.to_dict("records")})
            st.success(f"{len(data)} жол сақталды")

    hist = db.records(module, "results")
    with t_an:
        if hist.empty:
            st.info("Алдымен нәтижелерді енгізіңіз.")
        else:
            opts = [f"{r['year']} · {r['stage']} · {r['date']} (#{r['_id']})" for _, r in hist.iterrows()]
            sel = st.selectbox("Қай нәтижені талдау", opts, key=f"sel_{module}")
            rec = hist.iloc[opts.index(sel)]
            d = pd.DataFrame(rec["rows"])
            d["Балл"] = pd.to_numeric(d["Балл"], errors="coerce")
            d["Макс. балл"] = pd.to_numeric(d["Макс. балл"], errors="coerce")
            d["%"] = (d["Балл"] / d["Макс. балл"] * 100).round(1)
            d["Деңгей"] = d["%"].map(level_fn)
            d["Параллель"] = d["Сынып"].map(lambda x: U.parse_class(x)[0])
            th = st.number_input("Норма: орташа % ≥", value=60.0, key=f"thm_{module}")

            def grp(by):
                g = d.groupby(by).agg(**{"Нәтиже саны": ("%", "size"), "Орташа %": ("%", "mean")}).round(1)
                g["Төмен деңгей үлесі %"] = (d[d["Деңгей"].isin(low_levels)].groupby(by).size() /
                                             d.groupby(by).size() * 100).fillna(0).round(1)
                return g.reset_index()
            tables = {"Бағыттар бойынша": grp("Бағыт"), "Сыныптар бойынша": grp("Сынып"),
                      "Параллельдер бойынша": grp("Параллель"), "Сынып × бағыт": grp(["Сынып", "Бағыт"]),
                      "Деңгейлер бөлінісі": d.pivot_table(index="Бағыт", columns="Деңгей", values="%",
                                                          aggfunc="count", fill_value=0).reset_index()}
            view = st.radio("Есеп", list(tables), horizontal=True, key=f"v_{module}")
            st.dataframe(tables[view], hide_index=True, use_container_width=True)
            _chart_for(tables[view])
            weak = []
            for name, oc in [("Бағыттар бойынша", ["Бағыт"]), ("Сынып × бағыт", ["Сынып", "Бағыт"])]:
                for _, r in tables[name].iterrows():
                    obj = " / ".join(str(r[c]) for c in oc)
                    if r["Орташа %"] < th:
                        weak.append(U._w("🔴" if r["Орташа %"] < th - 15 else "🟠", title, obj, "Орташа %",
                                         r["Орташа %"], f"≥ {th}"))
                    if r["Төмен деңгей үлесі %"] > 20:
                        weak.append(U._w("🟠", title, obj, "Төмен деңгейдегі оқушылар үлесі %",
                                         r["Төмен деңгей үлесі %"], "≤ 20"))
            low_students = d[d["Деңгей"].isin(low_levels)][["Оқушы", "Сынып", "Бағыт", "%", "Деңгей"]]
            with st.expander(f"👩‍🎓 Төмен деңгейдегі оқушылар ({len(low_students)}) — жеке жұмыс үшін"):
                st.dataframe(low_students, hide_index=True, use_container_width=True)
            _ai_and_plan(db, user, module, title, rec["year"], rec["stage"], tables, weak, f"{rec['_id']}",
                         context=f"Бағалау: {title}. Деңгейлер: {', '.join(low_levels)} — төмен деңгейлер.")
    with t_hist:
        if hist.empty:
            st.info("Тарих жоқ")
        else:
            rows = []
            for _, r in hist.iterrows():
                d = pd.DataFrame(r["rows"])
                d["%"] = pd.to_numeric(d["Балл"], errors="coerce") / pd.to_numeric(d["Макс. балл"], errors="coerce") * 100
                for area, v in d.groupby("Бағыт")["%"].mean().items():
                    rows.append({"Кезең": f"{r['date']} {r['stage']}", "Бағыт": area, "Орташа %": round(v, 1)})
            dyn = pd.DataFrame(rows)
            st.line_chart(dyn.pivot_table(index="Кезең", columns="Бағыт", values="Орташа %"))
            st.dataframe(dyn, hide_index=True, use_container_width=True)


# ---------------- ҰБТ ----------------
ENT_COLS = {"Қазақстан тарихы": 20, "Оқу сауаттылығы": 10, "Математикалық сауаттылық": 10,
            "Профиль 1 балл": 50, "Профиль 2 балл": 50}


def ent_module(db, user):
    st.caption("Сынақ ҰБТ нәтижелері: міндетті пәндер + 2 бейіндік пән (барлығы 140 балл). "
               "Шекті балдарды ресми талаптармен тексеріп, қажет болса өзгертіңіз.")
    t_in, t_an, t_dyn = st.tabs(["📥 Нәтижелер", "📊 Талдау + ЖИ", "📈 Динамика"])
    cols = ["Оқушы", "Сынып", "Профиль 1", "Профиль 2"] + list(ENT_COLS)
    tmpl = pd.DataFrame([{"Оқушы": "Мысал Оқушы", "Сынып": "11 А", "Профиль 1": "Математика", "Профиль 2": "Физика",
                          "Қазақстан тарихы": 15, "Оқу сауаттылығы": 8, "Математикалық сауаттылық": 8,
                          "Профиль 1 балл": 35, "Профиль 2 балл": 30}])
    with t_in:
        bio = io.BytesIO()
        tmpl.to_excel(bio, index=False)
        st.download_button("⬇ Excel үлгісі", bio.getvalue(), "ent_template.xlsx", key="ent_tpl")
        c1, c2, c3 = st.columns(3)
        year = c1.text_input("Оқу жылы", _year_default(), key="ent_y")
        stage = c2.text_input("Байқау", "1-сынақ ҰБТ", key="ent_s")
        dt = c3.date_input("Күні", key="ent_d")
        up = st.file_uploader("Excel/CSV", type=["xlsx", "csv"], key="ent_up")
        data = pd.DataFrame(columns=cols)
        if up is not None:
            data = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
        data = st.data_editor(data, num_rows="dynamic", use_container_width=True, key="ent_ed")
        if st.button("💾 Сақтау", type="primary", key="ent_sv") and not data.empty:
            db.add_record("ent", "results", user["username"], {"year": year, "stage": stage, "date": str(dt),
                                                              "rows": data.to_dict("records")})
            st.success("Сақталды")
    hist = db.records("ent", "results")
    with t_an:
        if hist.empty:
            st.info("Нәтиже енгізілмеген")
            return
        opts = [f"{r['year']} · {r['stage']} · {r['date']} (#{r['_id']})" for _, r in hist.iterrows()]
        sel = st.selectbox("Байқау", opts, key="ent_sel")
        rec = hist.iloc[opts.index(sel)]
        d = pd.DataFrame(rec["rows"])
        for c in ENT_COLS:
            d[c] = pd.to_numeric(d.get(c), errors="coerce").fillna(0)
        d["Жалпы балл"] = d[list(ENT_COLS)].sum(axis=1)
        with st.expander("⚙ Шекті балдар"):
            c = st.columns(6)
            thr_total = c[0].number_input("Жалпы ≥", value=50, key="ent_t")
            thr_nat = c[1].number_input("Ұлттық ЖОО ≥", value=65, key="ent_n")
            mins = {"Қазақстан тарихы": c[2].number_input("Тарих ≥", value=5, key="ent_m1"),
                    "Оқу сауаттылығы": c[3].number_input("Оқу сауат. ≥", value=3, key="ent_m2"),
                    "Математикалық сауаттылық": c[4].number_input("Мат. сауат. ≥", value=3, key="ent_m3"),
                    "Профиль 1 балл": c[5].number_input("Профиль ≥", value=5, key="ent_m4")}
            mins["Профиль 2 балл"] = mins["Профиль 1 балл"]
        d["Шекті балдан өтті"] = d["Жалпы балл"] >= thr_total
        for c_, mn in mins.items():
            d["Шекті балдан өтті"] &= d[c_] >= mn
        d["Бейін"] = d["Профиль 1"].astype(str) + " + " + d["Профиль 2"].astype(str)
        m = st.columns(4)
        m[0].metric("Қатысқан", len(d))
        m[1].metric("Орташа балл", round(d["Жалпы балл"].mean(), 1))
        m[2].metric("Шекті балдан өтті", f"{d['Шекті балдан өтті'].mean() * 100:.0f}%")
        m[3].metric(f"≥ {thr_nat} балл", f"{(d['Жалпы балл'] >= thr_nat).mean() * 100:.0f}%")
        subj = pd.DataFrame({"Пән": list(ENT_COLS), "Макс": list(ENT_COLS.values()),
                             "Орташа балл": [round(d[c].mean(), 1) for c in ENT_COLS]})
        subj["Орташа %"] = (subj["Орташа балл"] / subj["Макс"] * 100).round(1)
        prof = pd.concat([d[["Профиль 1", "Профиль 1 балл"]].set_axis(["Пән", "Балл"], axis=1),
                          d[["Профиль 2", "Профиль 2 балл"]].set_axis(["Пән", "Балл"], axis=1)])
        prof = prof.groupby("Пән")["Балл"].agg(["size", "mean"]).round(1).reset_index() \
            .rename(columns={"size": "Тапсырған", "mean": "Орташа балл"})
        prof["Орташа %"] = (prof["Орташа балл"] / 50 * 100).round(1)
        bycls = d.groupby("Сынып").agg(**{"Оқушы": ("Жалпы балл", "size"), "Орташа балл": ("Жалпы балл", "mean"),
                                          "Өтті %": ("Шекті балдан өтті", "mean")}).round(2).reset_index()
        bycls["Өтті %"] = (bycls["Өтті %"] * 100).round(0)
        bycomb = d.groupby("Бейін").agg(**{"Оқушы": ("Жалпы балл", "size"),
                                           "Орташа балл": ("Жалпы балл", "mean")}).round(1).reset_index()
        tables = {"Пәндер бойынша": subj, "Бейіндік пәндер": prof, "Сыныптар бойынша": bycls,
                  "Бейін комбинациялары": bycomb}
        view = st.radio("Есеп", list(tables), horizontal=True, key="ent_v")
        st.dataframe(tables[view], hide_index=True, use_container_width=True)
        _chart_for(tables[view])
        risk = d[~d["Шекті балдан өтті"] | (d["Жалпы балл"] < thr_nat)][["Оқушы", "Сынып", "Бейін", "Жалпы балл"]
                                                                        + list(ENT_COLS)]
        with st.expander(f"🚩 Тәуекел тобы ({len(risk)}) — шекті/ұлттық ЖОО балына жетпегендер"):
            st.dataframe(risk.sort_values("Жалпы балл"), hide_index=True, use_container_width=True)
        weak = []
        for _, r in pd.concat([subj.rename(columns={"Пән": "Нысан"}), prof.rename(columns={"Пән": "Нысан"})]).iterrows():
            if r["Орташа %"] < 60:
                weak.append(U._w("🔴" if r["Орташа %"] < 45 else "🟠", "ҰБТ", r["Нысан"], "Орташа %", r["Орташа %"], "≥ 60"))
        nfail = int((~d["Шекті балдан өтті"]).sum())
        if nfail:
            weak.append(U._w("🔴", "ҰБТ", "Мектеп", "Шекті балдан өтпеген оқушы саны", nfail, "0"))
        _ai_and_plan(db, user, "ent", "Сынақ ҰБТ нәтижелері", rec["year"], rec["stage"], tables, weak,
                     f"{rec['_id']}", context=f"ҰБТ: макс 140 балл, шекті балл {thr_total}, ұлттық ЖОО {thr_nat}.")
    with t_dyn:
        rows = []
        for _, r in hist.iterrows():
            d = pd.DataFrame(r["rows"])
            tot = sum(pd.to_numeric(d.get(c), errors="coerce").fillna(0) for c in ENT_COLS)
            rows.append({"Байқау": f"{r['date']} {r['stage']}", "Орташа балл": round(tot.mean(), 1),
                         "Оқушы": len(d)})
        dyn = pd.DataFrame(rows).sort_values("Байқау")
        st.line_chart(dyn.set_index("Байқау")["Орташа балл"])
        st.dataframe(dyn, hide_index=True, use_container_width=True)
        # Оқушы динамикасы
        per = []
        for _, r in hist.iterrows():
            d = pd.DataFrame(r["rows"])
            d["Жалпы"] = sum(pd.to_numeric(d.get(c), errors="coerce").fillna(0) for c in ENT_COLS)
            for _, s in d.iterrows():
                per.append({"Оқушы": s.get("Оқушы"), "Байқау": f"{r['date']} {r['stage']}", "Балл": s["Жалпы"]})
        if per:
            pv = pd.DataFrame(per).pivot_table(index="Оқушы", columns="Байқау", values="Балл")
            if pv.shape[1] >= 2:
                pv["Өзгеріс"] = pv.iloc[:, -1] - pv.iloc[:, -2]
                st.markdown("**Оқушылар динамикасы (соңғы екі байқау)** — теріс өзгерістер жоғарыда")
                st.dataframe(pv.sort_values("Өзгеріс").reset_index(), hide_index=True, use_container_width=True)


# ---------------- Үлгерім (динамика) ----------------
def progress_tab(db, user):
    st.caption("Сақталған анализдер негізіндегі динамика. Жаңа деректер үшін «Анализдер» бөлімінде файл жүктеп, "
               "«💾 Анализді сақтау» батырмасын басыңыз.")
    sch = db.records("uch_an", "school")
    if not sch.empty:
        rows = []
        for _, r in sch.iterrows():
            for x in r["tables"].get("Параллельдер бойынша", []):
                rows.append({"Кезең": f"{r['year']} {r['period']}", "Параллель": x["Параллель"],
                             "Сапа %": x["Сапа %"], "Орташа балл": x["Орташа балл"]})
        d = pd.DataFrame(rows)
        st.markdown("**Параллельдер бойынша білім сапасы динамикасы**")
        st.line_chart(d.pivot_table(index="Кезең", columns="Параллель", values="Сапа %"))
        st.dataframe(d.pivot_table(index="Параллель", columns="Кезең", values="Сапа %").reset_index(),
                     hide_index=True, use_container_width=True)
    rep = db.records("uch_an", "report")
    if not rep.empty:
        rows = []
        for _, r in rep.iterrows():
            for x in r["tables"].get("Пәндер бойынша", []):
                rows.append({"Кезең": f"{r['year']} {r['period']}", "Пән": x["Пән"], "Сапа %": x["Сапа %"]})
        d = pd.DataFrame(rows)
        st.markdown("**Пәндер бойынша білім сапасы динамикасы**")
        pv = d.pivot_table(index="Пән", columns="Кезең", values="Сапа %")
        if pv.shape[1] >= 2:
            pv["Өзгеріс"] = pv.iloc[:, -1] - pv.iloc[:, -2]
            pv = pv.sort_values("Өзгеріс")
        st.dataframe(pv.round(1).reset_index(), hide_index=True, use_container_width=True)
    kl = db.records("uch_an", "klass")
    if not kl.empty:
        last = kl.iloc[0]
        r = pd.DataFrame(last["tables"].get("Резерв және тәуекел оқушылар", []))
        st.markdown(f"**Резерв және тәуекел оқушылар** ({last['year']} {last['period']})")
        if not r.empty:
            st.dataframe(r, hide_index=True, use_container_width=True)
    if sch.empty and rep.empty and kl.empty:
        st.info("Әзірге сақталған анализ жоқ.")


def saved_tab(db, user):
    df = db.records("uch_an")
    if df.empty:
        st.info("Сақталған анализ жоқ")
        return
    rows = db.query("SELECT id, kind FROM records WHERE module = 'uch_an'")
    kinds = {r["id"]: r["kind"] for r in rows}
    df["Түрі"] = df["_id"].map(lambda i: U.TYPE_NAMES.get(kinds.get(i), kinds.get(i)))
    st.dataframe(df[["_id", "Түрі", "year", "period", "_author", "_created"]], hide_index=True, use_container_width=True)
    rid = st.selectbox("Ашу", df["_id"].tolist(), format_func=lambda i: f"#{i} · {df.set_index('_id').loc[i, 'Түрі']}")
    r = df.set_index("_id").loc[rid]
    tables = {n: pd.DataFrame(v) for n, v in (r["tables"] or {}).items()}
    plan = pd.DataFrame(r.get("plan") or [])
    html = _report_html(r.get("title") or r["Түрі"], r["year"], r["period"], tables, r.get("weak") or [],
                        r.get("ai"), plan)
    st.download_button("📄 Word", doc_bytes("Анализ", html, landscape=True), f"analysis_{rid}.doc")
    if r.get("ai"):
        st.markdown(f"**Қорытынды:** {r['ai'].get('summary', '')}")
    if not plan.empty:
        st.markdown("**Жоспар**")
        st.dataframe(plan, hide_index=True, use_container_width=True)
    if st.button("🗑 Өшіру", key="del_an"):
        db.delete("records", int(rid))
        st.rerun()


def render(db, user):
    st.header("📚 Оқу ісі (оқу ісі жөніндегі орынбасар)")
    t = st.tabs(["🧪 МОДО", "🎓 ҰБТ", "🌍 PISA", "📈 Үлгерім", "👁 Сабаққа қатысу", "🔬 Анализдер"])
    with t[0]:
        scored_module(db, user, "modo", "МОДО нәтижелері", MODO_AREAS, modo_level, ["Төмен"],
                      "Білім алушылардың оқу жетістіктерін сырттай бағалау (МОДО) немесе сынақ МОДО нәтижелері. "
                      "Деңгейлер: Төмен < 40%, Орта 40–84%, Жоғары ≥ 85%.")
    with t[1]:
        ent_module(db, user)
    with t[2]:
        scored_module(db, user, "pisa", "PISA форматындағы функционалдық сауаттылық", PISA_AREAS, pisa_level,
                      ["1-ден төмен", "1-деңгей"],
                      "PISA тәрізді диагностика нәтижелері. Деңгейлер пайыз бойынша шартты түрде есептеледі; "
                      "2-деңгей — базалық деңгей, одан төмені — тәуекел.")
    with t[3]:
        progress_tab(db, user)
    with t[4]:
        a, b = st.tabs(["📝 Сабақты бақылау парағы", "📊 Қатысу қорытындысы"])
        with a:
            observation.zavuch_form(db, user)
        with b:
            observation.observation_stats(db)
        st.caption("Оқушылардың сабаққа қатысуын (қалған сабақтар) талдау: «🔬 Анализдер → Сабаққа қатысу».")
    with t[5]:
        sub = st.tabs(["🏫 Мектеп (параллельдер)", "📘 Пән бойынша", "👥 Сынып бойынша", "📑 Пәндер жиынтығы",
                       "📝 БЖБ / ТЖБ", "🚸 Сабаққа қатысу", "🗂 Сақталған анализдер"])
        for tab, kind in zip(sub[:6], ["school", "subject", "klass", "report", "sor", "attend"]):
            with tab:
                analysis_tab(db, user, kind)
        with sub[6]:
            saved_tab(db, user)
