"""Завучтың сабаққа қатысу парағы (5-қосымша үлгісі) және жас педагогтердің өзара сабаққа қатысу журналы."""
from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.config import CLASSES, LINKS
from core.export import doc_bytes, esc
from core.ui import download_buttons

CRITERIA = {
    "I. Жоспарлау": {
        "1.1 Сабақ мақсаттары": [
            "оқу бағдарламасындағы оқыту мақсаттарына сәйкес келеді",
            "барлық оқушыларға түсінікті және қолжетімді",
            "уақытқа сәйкес, оқушылардың қатысуына мүмкіндік береді"],
        "1.2 Оқыту әдістері мен ресурстары": [
            "мақсатқа, оқушылардың жасы мен білім алу қажеттіліктеріне сәйкес"],
        "1.3 Бағалау әдістері мен құралдары": [
            "мақсатқа және оқушылардың жасына сәйкес",
            "барлық кезеңдерде өзін-өзі бағалау жоспарланған",
            "зерттеуге (педагог-зерттеуші) / авторлық бағдарламаға (педагог-шебер) негізделген"],
    },
    "II. Оқыту": {
        "2.1 Функционалдық сауаттылықты ескеріп материалды беру": [
            "ұғымдар жүйелі беріледі", "әртүрлі дереккөзден ақпарат іздеу және түсіну",
            "білімді практикада қолдану"],
        "2.2 Цифрлық білім беру ресурстары": ["жеке қажеттіліктерді ескеріп қолданылады"],
        "2.3 Әдістер, тапсырмалар, саралау": [
            "оқушылардың өзара әрекеттесуі", "қажеттіліктер мен ерекшеліктер ескерілген",
            "тапсырмалар сараланған (үлгерімі төмен оқушыларға қосымша нұсқау)"],
        "2.4 Құрылым және уақыт": [
            "құрылым икемді сақталған", "уақыт тиімді бөлінген", "барлық оқушылар қатысады",
            "мұғалім мен оқушы сөйлеуінің теңгерімі"],
        "2.5 Өзара әрекетті ұйымдастыру": [
            "жұмыс түрлерінің теңгерімі", "топтағы рөлдер бөлінген", "талқылауға белсенді қатысу"],
        "2.6 «Адал азамат» құндылықтары": [
            "бағдарлама құндылықтары көрініс тапқан", "оқудың практикалық, әлеуметтік маңызы сезіледі",
            "тәртіп, академиялық адалдық, мемлекеттік рәміздерге, тілге, дәстүрге құрмет"],
    },
    "III. Бағалау": {
        "3.1 Бағалау әдістері мен құралдары": [
            "мақсатқа жетуге көмектеседі", "уақтылы кері байланыс беріледі",
            "барлық кезеңде өзін-өзі бағалау мүмкіндігі", "мақсатқа сай рефлексия"],
    },
    "IV. Рефлексия": {
        "4.1 Сабақ рефлексиясы": ["оқушылардың мақсатқа жетуіне негізделген"],
        "4.2 Сабақ сапасы": ["тәжірибені дамыту бағыттары мен нақты әрекеттер анықталған"],
    },
}
MAX_SCORE = 3 * sum(len(v) for sec in CRITERIA.values() for v in sec.values())


def dictation_widget(key: str):
    """Браузердің дауыспен теру құралы (Chrome/Edge). Мәтінді көшіріп, өріске қойыңыз."""
    components.html(f"""
<div style="font-family:sans-serif">
 <select id="lang{key}"><option value="kk-KZ">Қазақша</option><option value="ru-RU">Русский</option></select>
 <button id="b{key}">🎤 Жазуды бастау</button> <button id="c{key}">📋 Көшіру</button>
 <span id="s{key}" style="color:#888"></span>
 <textarea id="t{key}" style="width:100%;height:90px;margin-top:6px" placeholder="Түймені басып, сөйлеуді бастаңыз..."></textarea>
</div>
<script>
const SR = window.SpeechRecognition || window.webkitSpeechRecognition; let rec=null, on=false;
const b=document.getElementById('b{key}'), t=document.getElementById('t{key}'), s=document.getElementById('s{key}');
b.onclick=()=>{{ if(!SR){{s.textContent='Тек Chrome/Edge';return;}}
 if(on){{rec.stop();return;}} rec=new SR(); rec.lang=document.getElementById('lang{key}').value;
 rec.continuous=true; rec.interimResults=false;
 rec.onresult=e=>{{for(let i=e.resultIndex;i<e.results.length;i++) if(e.results[i].isFinal) t.value+=e.results[i][0].transcript+' ';}};
 rec.onend=()=>{{on=false;b.textContent='🎤 Жазуды бастау';s.textContent='';}};
 rec.start(); on=true; b.textContent='🛑 Тоқтату'; s.textContent='Тыңдап тұр… сөйлеңіз'; }};
document.getElementById('c{key}').onclick=()=>{{t.select();navigator.clipboard.writeText(t.value);s.textContent='Көшірілді ✔';}};
</script>""", height=160)


def level(pct: float) -> str:
    if pct >= 85:
        return "Жоғары (үлгілі сабақ)"
    if pct >= 65:
        return "Жеткілікті"
    if pct >= 45:
        return "Орташа (әдістемелік қолдау қажет)"
    return "Төмен (қайта қатысу, тәлімгер бекіту)"


def zavuch_form(db, user):
    st.subheader("📝 Орта білім беру ұйымы педагогінің сабағын бақылау парағы")
    st.caption(f"Түпнұсқа үлгі: {LINKS['zavuch_form']}")
    teachers = db.query("SELECT username, full_name FROM users WHERE active = 1 ORDER BY full_name")
    tnames = [t["full_name"] or t["username"] for t in teachers] or ["—"]
    c1, c2, c3 = st.columns(3)
    head = {
        "Педагог": c1.selectbox("Педагогтің ТАӘ", tnames, key="ob_t"),
        "Лауазымы": c2.text_input("Лауазымы", "мұғалім", key="ob_pos"),
        "Біліктілік санаты": c3.selectbox("Санаты", ["педагог", "педагог-модератор", "педагог-сарапшы",
                                                     "педагог-зерттеуші", "педагог-шебер"], key="ob_cat"),
        "Пән": c1.text_input("Пән", key="ob_subj"),
        "Сынып": c2.selectbox("Сынып", CLASSES, key="ob_cls"),
        "Бақылау күні": str(c3.date_input("Бақылау күні", date.today(), key="ob_date")),
        "Тақырып": st.text_input("Сабақ тақырыбы", key="ob_topic"),
        "Мақсаты": st.text_area("Сабақ мақсаттары", key="ob_goal", height=70),
        "Бақылаушы": user.get("full_name") or user["username"],
        "Бақылаушы лауазымы": user.get("position") or "",
    }
    scores, total = {}, 0
    for sec, crits in CRITERIA.items():
        st.markdown(f"#### {sec}")
        for crit, inds in crits.items():
            st.markdown(f"**{crit}**")
            for i, ind in enumerate(inds):
                v = st.radio(ind, [0, 1, 2, 3], index=2, horizontal=True, key=f"ob_{crit}_{i}")
                scores[f"{crit} — {ind}"] = v
                total += v
    pct = total / MAX_SCORE * 100
    st.metric("Барлығы / Жиыны", f"{total} / {MAX_SCORE}", f"{pct:.0f}% · {level(pct)}")
    st.markdown("**Ұсыныстар** (дауыспен теру: төменде сөйлеп, көшіріп, өріске қойыңыз)")
    dictation_widget("obs")
    recs = st.text_area("Ұсыныстар", key="ob_recs", height=120)
    if st.button("💾 Сақтау", type="primary", key="ob_save"):
        db.add_record("observation", "zavuch", user["username"],
                      {**head, "scores": scores, "total": total, "max": MAX_SCORE, "percent": round(pct, 1),
                       "level": level(pct), "recommendations": recs})
        st.success("Бақылау парағы сақталды")
    rows = "".join(f"<tr><td>{esc(k)}</td><td style='text-align:center'>{v}</td></tr>" for k, v in scores.items())
    body = (f"<p style='text-align:right'>5-қосымша</p><h1>Орта білім беру ұйымы педагогінің сабағын бақылау парағы</h1>"
            + "".join(f"<p><b>{esc(k)}:</b> {esc(v)}</p>" for k, v in head.items())
            + f"<table><tr><th>Критерий / көрсеткіш</th><th>Балл (0–3)</th></tr>{rows}"
              f"<tr><th>Барлығы / Жиыны</th><th>{total} / {MAX_SCORE} ({pct:.0f}%)</th></tr></table>"
              f"<p><b>Деңгейі:</b> {level(pct)}</p><h2>Ұсыныстар</h2><p>{esc(recs)}</p>"
              f"<p>Бақылаушы: ____________ {esc(head['Бақылаушы'])}</p>"
              f"<p>Танысты: ____________ {esc(head['Педагог'])}</p>")
    st.download_button("📄 Word-қа сақтау", doc_bytes("Сабақты бақылау парағы", body),
                       f"bakylau_{head['Педагог']}_{head['Бақылау күні']}.doc", key="ob_doc")


def observation_stats(db):
    df = db.records("observation", "zavuch")
    if df.empty:
        st.info("Әзірге бақылау парақтары жоқ")
        return
    view = df[["Бақылау күні", "Педагог", "Пән", "Сынып", "Тақырып", "total", "percent", "level", "_author"]]
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.bar_chart(df.groupby("Педагог")["percent"].mean().sort_values())
    # Критерийлер бойынша әлсіз жақтар
    sc = pd.DataFrame(list(df["scores"])).mean().sort_values().head(8)
    st.markdown("**Мектеп бойынша ең әлсіз көрсеткіштер (әдістемелік жұмысқа):**")
    st.dataframe(sc.rename("орташа балл").reset_index().rename(columns={"index": "көрсеткіш"}),
                 hide_index=True, use_container_width=True)
    download_buttons(view, "Сабаққа қатысу қорытындысы", "observations")


def young_journal(db, user):
    st.subheader("📘 Өзара сабаққа қатысу журналы (жас педагогтер)")
    st.caption(f"Түпнұсқа үлгі: {LINKS['young_journal']}")
    c1, c2 = st.columns(2)
    school = c1.text_input("Мектеп аты", key="yj_school")
    year = c2.text_input("Оқу жылы", "2026 – 2027", key="yj_year")
    base = pd.DataFrame([{"Мерзімі": str(date.today()), "Пәні": "", "Сыныбы": "", "Пән мұғалімі": "",
                          "Сабақтың тақырыбы": ""}])
    rows = st.data_editor(base, num_rows="dynamic", use_container_width=True, key="yj_rows")
    goal = st.text_area("Сабаққа қатысу мақсатым:", key="yj_goal")
    vis = st.text_area("Көрнекілігі:", key="yj_vis")
    notes = st.text_area("Өзіме түртіп алдым:", key="yj_notes")
    dictation_widget("yj")
    if st.button("💾 Журналға сақтау", type="primary", key="yj_save"):
        db.add_record("young_journal", "visit", user["username"],
                      {"school": school, "year": year, "rows": rows.to_dict("records"), "goal": goal,
                       "visual": vis, "notes": notes})
        st.success("Сақталды")
    body = (f"<p>Павлодар облысы білім беру басқармасының</p><p>{esc(school)}</p>"
            f"<h1>Өзара сабаққа қатысу журналы</h1><p style='text-align:center'>{esc(year)} оқу жылы</p>"
            f"<p>Педагог: {esc(user.get('full_name') or user['username'])}</p>"
            f"<h2>Өзара сабаққа қатынасу парағы</h2>{rows.to_html(index=False)}"
            f"<p><b>Сабаққа қатысу мақсатым:</b> {esc(goal)}</p><p><b>Көрнекілігі:</b> {esc(vis)}</p>"
            f"<p><b>Өзіме түртіп алдым:</b> {esc(notes)}</p>")
    st.download_button("📄 Word-қа сақтау (.doc)", doc_bytes("Өзара сабаққа қатысу журналы", body),
                       "ozara_katysu.doc", key="yj_doc")
    hist = db.records("young_journal", "visit")
    if not hist.empty:
        st.markdown("**Журнал жазбалары**")
        mine = hist if user["role"] in ("admin", "director", "zavuch_innov", "metodist", "zavuch_uch") \
            else hist[hist["_author"] == user["username"]]
        flat = [{**r, "Педагог": h["_author"], "Сақталды": h["_created"]}
                for _, h in mine.iterrows() for r in (h["rows"] or [])]
        if flat:
            fdf = pd.DataFrame(flat)
            st.dataframe(fdf, hide_index=True, use_container_width=True)
            st.bar_chart(fdf["Педагог"].value_counts())
