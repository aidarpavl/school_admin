"""🌍 PISA: EDU Test Excel жүктеу → толық Word талдау (мектеп үлгісі) → сақтау (бағдарлама, мұрағат, Google Drive)
→ «📈 Өзгеріс»: алдыңғы және соңғы тестілеуді салыстыру → Word."""
import re
from datetime import date

import pandas as pd
import streamlit as st

from core import ai, gdrive
from core import pisa as P
from core.github_store import academic_year, get_store, save_file

MODULE = "pisa_edu"
ARCHIVE_DIR = "01_Akimshilik/Oqu_isi/PISA"


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", s, flags=re.UNICODE).strip("_")[:80]


def _tests(db) -> pd.DataFrame:
    df = db.records(MODULE, "test")
    if not df.empty:
        df["_sort"] = pd.to_datetime(df["date"], format="%d.%m.%Y", errors="coerce")
        df = df.sort_values(["_sort", "_id"], ascending=False)
    return df


def _load(rec) -> dict:
    return {"title": rec["title"], "date": rec["date"], "domains": rec["domains"], "grades": rec["grades"],
            "official": rec.get("official") or {}, "students": pd.DataFrame(rec["students"]),
            "label": rec.get("label") or rec["title"]}


def _store_everywhere(name: str, data: bytes, author: str, to_archive=True, to_drive=True) -> list[str]:
    msgs = []
    if to_archive:
        try:
            pth = save_file(get_store(), ARCHIVE_DIR, name, data, author)
            msgs.append(f"🗄 Мұрағат: {pth}")
        except Exception as e:
            msgs.append(f"⚠ Мұрағатқа сақталмады: {e}")
    if to_drive:
        ok, info = gdrive.upload(name, data, f"Оқу ісі/PISA/{academic_year()}")
        msgs.append(f"☁ Google Drive: {info}" if ok else f"⚠ Google Drive: {info}")
    return msgs


def _label(r) -> str:
    return f"{r['date']} · {r.get('label') or r['title']} (#{r['_id']})"


# ---------------- 1. Жүктеу ----------------
def upload_tab(db, user):
    st.caption("EDU Test (немесе ұқсас платформа) «Analysis» Excel файлы: Аты-жөні, Сынып, Литерал, Жалпы ұпайы, "
               "<бағыт> · ұпай - <макс>, <бағыт> · баға. Бағыттар саны кез келген. Бірнеше файлды бірге жүктеуге болады.")
    files = st.file_uploader("PISA Excel файл(дар)ы", type=["xlsx", "xls"], accept_multiple_files=True, key="pisa_up")
    if not files:
        return
    existing = _tests(db)
    c1, c2 = st.columns(2)
    to_arch = c1.checkbox("Түпнұсқа Excel-ді мұрағатқа сақтау", value=True, key="pisa_arch")
    to_drive = c2.checkbox("Google Drive-қа сақтау", value=gdrive.enabled(), disabled=not gdrive.enabled(),
                           key="pisa_drive")
    for i, f in enumerate(files):
        with st.container(border=True):
            try:
                p = P.parse_edu(f)
            except Exception as e:
                st.error(f"«{f.name}»: {e}")
                continue
            r = P.compute(p)
            st.markdown(f"**{f.name}** — {p['title']}")
            m = st.columns(4)
            m[0].metric("Күні", p["date"])
            m[1].metric("Оқушы", r["n"])
            m[2].metric("Сыныптар", ", ".join(P.class_label(c) for c in r["classes"]))
            m[3].metric("Орташа", P.pct(r["pct_total"]))
            st.write(" · ".join(f"{d['name']}: макс {P.f1(d['max'], 0)}, орындалу {P.pct(r['school'][d['name']]['pct'])}"
                                for d in p["domains"]))
            label = st.text_input("Атауы (салыстыруда көрінеді)", re.sub(r"\s*\d{2}\.\d{2}\.\d{4}", "", p["title"]),
                                  key=f"pl_{i}")
            dup = (not existing.empty) and ((existing["title"] == p["title"]) & (existing["date"] == p["date"])).any()
            if dup:
                st.warning("Бұл тестілеу бұрын жүктелген. Қайта сақтасаңыз, екінші нұсқа қосылады.")
            if st.button("💾 Сақтау", key=f"psave_{i}", type="primary"):
                rid = db.add_record(MODULE, "test", user["username"], {
                    "label": label, "title": p["title"], "date": p["date"], "domains": p["domains"],
                    "grades": p["grades"], "official": p["official"], "file": f.name,
                    "students": p["students"].to_dict("records")})
                st.success(f"Сақталды (#{rid}). «Талдау + ЖИ» бөліміне өтіңіз.")
                for msg in _store_everywhere(f"PISA_{_safe(p['date'])}_{_safe(f.name)}", f.getvalue(),
                                             user["username"], to_arch, to_drive):
                    st.caption(msg)


# ---------------- 2. Талдау + ЖИ ----------------
def analysis_tab(db, user):
    tests = _tests(db)
    if tests.empty:
        st.info("Алдымен «📥 Жүктеу» бөлімінде Excel файлын жүктеп, сақтаңыз.")
        return
    opts_lbl = [_label(r) for _, r in tests.iterrows()]
    sel = st.selectbox("Тестілеу", opts_lbl, key="pa_sel")
    rec = tests.iloc[opts_lbl.index(sel)]
    p = _load(rec)
    r = P.compute(p)
    doms = [d["name"] for d in p["domains"]]
    prev_an = db.records(MODULE, "analysis")
    prev_an = prev_an[prev_an["test_id"] == rec["_id"]] if not prev_an.empty else prev_an
    saved_opts = prev_an.iloc[0]["opts"] if not prev_an.empty else {}

    # --- Көрсеткіштер ---
    m = st.columns(len(doms) + 2)
    m[0].metric("Қатысқан", r["n"])
    m[1].metric("Жалпы орташа", f"{P.f1(r['avg_total'])} ({P.pct(r['pct_total'])})")
    for i, d in enumerate(doms):
        m[i + 2].metric(d, P.pct(r["school"][d]["pct"]), f"сапа {P.pct(r['school'][d]['quality'])}",
                        delta_color="off")
    tabs = P.tables(p, r)
    view = st.radio("Кесте", list(tabs), horizontal=True, key="pa_view")
    st.dataframe(tabs[view], hide_index=True, use_container_width=True)
    mat = tabs["Орындалу % матрицасы"].set_index("Сынып")
    st.bar_chart(mat, stack=False)

    # --- Баптаулар ---
    with st.expander("⚙ Талдау құжатының баптаулары (мұғалімдер, тақырыптық қорытынды, қол қоюшы)",
                     expanded=not bool(saved_opts)):
        c1, c2 = st.columns(2)
        o = {"platform": c1.text_input("Платформа", saved_opts.get("platform", "EDU TEST"), key="po_pl"),
             "contingent": c2.number_input("Параллельдердегі барлық оқушы саны (қатысу % үшін, 0 — көрсетпеу)",
                                           value=int(saved_opts.get("contingent", 0)), min_value=0, key="po_cn"),
             "base": st.text_input("Негізі", saved_opts.get("base", P.DEFAULT_BASE), key="po_bs"),
             "goal": st.text_area("Мақсаты", saved_opts.get("goal", P.DEFAULT_GOAL), key="po_gl"),
             "signer_title": c1.text_input("Қол қоюшының лауазымы", saved_opts.get("signer_title",
                                                                                 "Басшының ОІЖ орынбасары"), key="po_st"),
             "signer": c2.text_input("Аты-жөні", saved_opts.get("signer", user.get("full_name") or ""), key="po_sg"),
             "include_names": c1.checkbox("Оқушылардың аты-жөнін құжатқа енгізу", saved_opts.get("include_names", True),
                                          key="po_nm"),
             "charts": c2.checkbox("Диаграммаларды қосу", saved_opts.get("charts", True), key="po_ch")}
        st.markdown("**Пән мұғалімдері және тақырыптық қорытынды** (міндетті емес, құжатқа енеді)")
        base_rows = pd.DataFrame([{"Сынып": cl, "Бағыт": d, "Мұғалім": "", "Тақырыптық қорытынды": ""}
                                  for cl in r["classes"] for d in doms])
        if saved_opts.get("extra"):
            old = pd.DataFrame(saved_opts["extra"])
            base_rows = base_rows.drop(columns=["Мұғалім", "Тақырыптық қорытынды"]).merge(
                old, on=["Сынып", "Бағыт"], how="left").fillna("")
        extra = st.data_editor(base_rows, hide_index=True, use_container_width=True, disabled=["Сынып", "Бағыт"],
                               key=f"po_ex_{rec['_id']}")
        o["extra"] = extra.to_dict("records")
    o["teachers"] = {(x["Сынып"], x["Бағыт"]): x["Мұғалім"] for x in o["extra"] if x.get("Мұғалім")}
    o["notes"] = {(x["Сынып"], x["Бағыт"]): x["Тақырыптық қорытынды"] for x in o["extra"]
                  if x.get("Тақырыптық қорытынды")}

    # --- Олқылықтар ---
    with st.expander("🔎 Автоматты анықталған олқылықтар"):
        c1, c2 = st.columns(2)
        npct = c1.number_input("Норма: орындалу % ≥", value=65.0, key="pa_np")
        nq = c2.number_input("Норма: сапа % ≥", value=70.0, key="pa_nq")
        weak = P.weak_list(p, r, npct, nq)
        st.dataframe(pd.DataFrame(weak), hide_index=True, use_container_width=True) if weak else st.success("Олқылық жоқ")
        st.markdown("**Тәуекел тобы**")
        st.dataframe(r["risk"], hide_index=True, use_container_width=True)

    # --- ЖИ ---
    sk = f"pisa_ai_{rec['_id']}"
    if sk not in st.session_state and not prev_an.empty and prev_an.iloc[0].get("ai"):
        st.session_state[sk] = {"ok": True, "data": prev_an.iloc[0]["ai"]}
    prov = ai.provider()
    c1, c2 = st.columns([1, 2])
    if c1.button("🤖 ЖИ талдауы мен ұсыныстары", disabled=not prov, key="pa_ai", use_container_width=True):
        safe_tables = {k: v for k, v in tabs.items() if k not in ("Үздік 10 оқушы", "Тәуекел тобы")}
        with st.spinner("ЖИ талдап жатыр..."):
            st.session_state[sk] = ai.run_analysis(
                f"PISA-ға дайындық тестілеуі ({p['title']})", p["date"], safe_tables, weak,
                context=f"Бағыттар: {', '.join(doms)}. Тәуекел тобында {len(r['risk'])} оқушы. "
                        "Ұсыныстарды сыныптар мен бағыттар бойынша нақты жаз.")
    c2.caption(f"ЖИ: {prov or 'кілт жоқ — ұсыныстар ереже бойынша жазылады'}. ЖИ-ге оқушы аттары жіберілмейді.")
    res = st.session_state.get(sk)
    ai_data = res.get("data") if res and res.get("ok") else None
    if res and not res.get("ok"):
        st.error(res.get("error"))
    if ai_data:
        st.markdown(f"**Қорытынды:** {ai_data.get('summary', '')}")
        st.markdown("\n".join(f"- {x.get('target', '')}: {x.get('text', '')}" if isinstance(x, dict) else f"- {x}"
                              for x in ai_data.get("recommendations", [])))
        if ai_data.get("plan"):
            st.dataframe(pd.DataFrame(ai_data["plan"]), hide_index=True, use_container_width=True)
    else:
        st.markdown("**Ұсыныстар (автоматты):**\n" + "\n".join(f"- {x}" for x in P.auto_recommendations(p, r, npct)))

    # --- Word ---
    st.divider()
    docx_bytes = P.build_docx(p, r, o, ai_data)
    fname = f"PISA_taldau_{_safe(p['date'])}.docx"
    c1, c2 = st.columns(2)
    c1.download_button("📄 Word талдауын жүктеп алу", docx_bytes, fname, type="primary", use_container_width=True,
                       mime=gdrive.MIME["docx"], key="pa_dl")
    if c2.button("💾 Талдауды сақтау (бағдарлама + мұрағат + Google Drive)", use_container_width=True, key="pa_sv"):
        opts_store = {k: v for k, v in o.items() if k not in ("teachers", "notes")}
        msgs = _store_everywhere(fname, docx_bytes, user["username"], True, gdrive.enabled())
        links = [m_ for m_ in msgs if not m_.startswith("⚠")]
        if not prev_an.empty:
            db.update_record(int(prev_an.iloc[0]["_id"]), {"test_id": int(rec["_id"]), "opts": opts_store,
                                                           "ai": ai_data, "file": fname, "links": links,
                                                           "updated": str(date.today())})
        else:
            db.add_record(MODULE, "analysis", user["username"], {"test_id": int(rec["_id"]), "opts": opts_store,
                                                                 "ai": ai_data, "file": fname, "links": links})
        st.success("Талдау сақталды")
        for m_ in msgs:
            st.caption(m_)
    if not prev_an.empty:
        st.caption("Бұл тестілеудің талдауы бұрын сақталған: " + "; ".join(prev_an.iloc[0].get("links") or []))


# ---------------- 3. Өзгеріс ----------------
def change_tab(db, user):
    tests = _tests(db)
    if len(tests) < 2:
        st.info("Өзгерісті есептеу үшін кемінде екі тестілеу жүктеңіз.")
        return
    lbls = [_label(r) for _, r in tests.iterrows()]
    c1, c2 = st.columns(2)
    prev_l = c1.selectbox("Алдыңғы талдау", lbls, index=1, key="ch_prev")
    cur_l = c2.selectbox("Соңғы талдау", lbls, index=0, key="ch_cur")
    if prev_l == cur_l:
        st.warning("Екі түрлі тестілеуді таңдаңыз.")
        return
    if st.button("📈 Өзгеріс", type="primary", use_container_width=True, key="ch_btn"):
        st.session_state["ch_pair"] = (prev_l, cur_l)
    if st.session_state.get("ch_pair") != (prev_l, cur_l):
        return
    pr, cr = tests.iloc[lbls.index(prev_l)], tests.iloc[lbls.index(cur_l)]
    pp, cp = _load(pr), _load(cr)
    c = P.compare({"p": pp, "r": P.compute(pp), "label": f"{pp['date']} {pp['label']}"},
                  {"p": cp, "r": P.compute(cp), "label": f"{cp['date']} {cp['label']}"})
    t = c["total"]
    m = st.columns(len(c["school"]) + 2)
    m[0].metric("Қатысқан", t["Қатысқан қазір"], t["Қатысқан қазір"] - t["Қатысқан бұрын"])
    m[1].metric("Мектеп орташа %", P.pct(t["Орташа % қазір"]), f"{P.f1(t['Өзгеріс (п.т.)'])} п.т.")
    for i, (_, rr) in enumerate(c["school"].iterrows()):
        m[i + 2].metric(rr["Бағыт"], P.pct(rr["Қазір %"]), f"{P.f1(rr['Өзгеріс (п.т.)'])} п.т.")
    for line in P.compare_text(c):
        st.markdown(f"- {line}")
    t1, t2, t3 = st.tabs(["Бағыттар", "Сыныптар", "Оқушылар"])
    with t1:
        st.dataframe(c["school"], hide_index=True, use_container_width=True)
        st.bar_chart(c["school"].set_index("Бағыт")[["Бұрын %", "Қазір %"]], stack=False)
    with t2:
        if c["classes"].empty:
            st.info("Ортақ сыныптар жоқ (мысалы, басқа параллельдер тестіленген).")
        else:
            st.dataframe(c["classes"].style.map(lambda v: "color: #c0392b" if isinstance(v, (int, float)) and v < 0
                                                else ("color: #1e8449" if isinstance(v, (int, float)) and v > 0 else ""),
                                                subset=["Өзгеріс (п.т.)", "Сапа өзгерісі"]),
                         hide_index=True, use_container_width=True)
    with t3:
        st.dataframe(c["students"], hide_index=True, use_container_width=True)
        if c["only_cur"]:
            st.caption(f"Тек соңғы тестілеуде: {len(c['only_cur'])} оқушы; тек алдыңғысында: {len(c['only_prev'])}.")

    sk = f"ch_ai_{pr['_id']}_{cr['_id']}"
    if ai.provider() and st.button("🤖 ЖИ: өзгеріс себептері және ұсыныстар", key="ch_ai"):
        prompt = ("Сен дарынды балалар мектебінің оқу ісі жөніндегі орынбасарысың. PISA-ға дайындық тестілеулерінің "
                  "екі нәтижесін салыстыру деректері берілген. Қазақ тілінде, ресми талдау стилінде: 1) өсу/кему "
                  "қорытындысы (сандармен), 2) ықтимал себептері, 3) төмендеген сыныптар мен бағыттар бойынша нақты "
                  "ұсыныстар және 2–4 апталық жоспар. Оқушы аттарын атама. Тек абзацтар, markdown белгілерінсіз.\n\n"
                  f"Жалпы: {t}\n\nБағыттар:\n{c['school'].to_csv(index=False)}\n\nСыныптар:\n"
                  f"{c['classes'].to_csv(index=False)}")
        with st.spinner("ЖИ жазып жатыр..."):
            try:
                st.session_state[sk] = ai.ask(prompt, 2500)
            except Exception as e:
                st.error(str(e))
    ai_text = st.session_state.get(sk, "")
    if ai_text:
        st.markdown(ai_text)
    o = {"signer": user.get("full_name") or "", "signer_title": "Басшының ОІЖ орынбасары", "ai_text": ai_text,
         "charts": True}
    inc = st.checkbox("Оқушылар тізімін құжатқа енгізу", value=True, key="ch_names")
    data = P.build_compare_docx(c, o, include_names=inc)
    fname = f"PISA_ozgeris_{_safe(pp['date'])}_{_safe(cp['date'])}.docx"
    c1, c2 = st.columns(2)
    c1.download_button("📄 Өзгеріс есебі (Word)", data, fname, type="primary", use_container_width=True,
                       mime=gdrive.MIME["docx"], key="ch_dl")
    if c2.button("💾 Сақтау (бағдарлама + мұрағат + Google Drive)", use_container_width=True, key="ch_sv"):
        msgs = _store_everywhere(fname, data, user["username"], True, gdrive.enabled())
        db.add_record(MODULE, "change", user["username"], {"prev_id": int(pr["_id"]), "cur_id": int(cr["_id"]),
                                                           "file": fname, "ai_text": ai_text,
                                                           "links": [m_ for m_ in msgs if not m_.startswith("⚠")]})
        st.success("Сақталды")
        for m_ in msgs:
            st.caption(m_)


# ---------------- 4. Сақталғандар ----------------
def saved_tab(db, user):
    tests = _tests(db)
    if tests.empty:
        st.info("Әзірге жоқ")
        return
    an = db.records(MODULE, "analysis")
    ch = db.records(MODULE, "change")
    rows = []
    for _, t in tests.iterrows():
        a = an[an["test_id"] == t["_id"]] if not an.empty else an
        rows.append({"ID": t["_id"], "Күні": t["date"], "Атауы": t.get("label") or t["title"],
                     "Оқушы": len(t["students"]), "Талдау": "✅" if not a.empty else "—",
                     "Сақталған жері": "; ".join(a.iloc[0].get("links") or []) if not a.empty else "",
                     "Жүктеген": t["_author"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    # Динамика графигі
    dyn = []
    for _, t in tests.iterrows():
        r = P.compute(_load(t))
        for d, s in r["school"].items():
            dyn.append({"Тестілеу": f"{t['date']}", "Бағыт": d, "Орындалу %": round(s["pct"], 1)})
    if dyn and len(tests) > 1:
        st.markdown("**Тестілеулер динамикасы (мектеп бойынша)**")
        dd = pd.DataFrame(dyn)
        dd["_d"] = pd.to_datetime(dd["Тестілеу"], format="%d.%m.%Y", errors="coerce")
        st.line_chart(dd.sort_values("_d").pivot_table(index="Тестілеу", columns="Бағыт", values="Орындалу %",
                                                       sort=False))
    if not ch.empty:
        st.markdown("**Сақталған өзгеріс есептері**")
        st.dataframe(ch[["file", "_author", "_created"]], hide_index=True, use_container_width=True)
    if user["role"] in ("admin", "director", "zavuch_uch"):
        with st.expander("🗑 Тестілеуді өшіру"):
            rid = st.selectbox("ID", tests["_id"].tolist(), key="pd_del")
            if st.button("Өшіру", key="pd_delb"):
                db.delete("records", int(rid))
                if not an.empty:
                    for aid in an[an["test_id"] == rid]["_id"]:
                        db.delete("records", int(aid))
                st.rerun()


def render(db, user):
    if not gdrive.enabled():
        st.caption("☁ Google Drive әлі қосылмаған: README → «Google Drive» бөлімі (5 минут). "
                   "Оған дейін файлдар бағдарламада және мұрағатта сақталады.")
    t = st.tabs(["📥 Жүктеу", "📊 Талдау + ЖИ", "📈 Өзгеріс", "🗂 Сақталған талдаулар"])
    with t[0]:
        upload_tab(db, user)
    with t[1]:
        analysis_tab(db, user)
    with t[2]:
        change_tab(db, user)
    with t[3]:
        saved_tab(db, user)
