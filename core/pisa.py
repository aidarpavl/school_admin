"""PISA-ға дайындық тестілеуі (EDU Test және ұқсас платформалар): Excel оқу, толық талдау,
мектептің Word үлгісіндегі талдау құжаты, екі талдауды салыстыру («Өзгеріс»).

Excel форматы (EDU Test «Analysis» парағы):
  1-жол: тест атауы және күні (мыс. «... PISA-1 (2026-27) EDU Test 09.11.2026»)
  2-жол: №, Аты-жөні, Сынып, Литерал, Жалпы ұпайы, <Бағыт> · ұпай - <макс>, <Бағыт> · баға, ...
  соңғы жолдар: орташа ұпайлар және үлестер (автоматты ескерілмейді)
Бағыттар саны мен атаулары кез келген болуы мүмкін (қаржылық сауаттылық, креативті ойлау т.б.).
"""
import io
import re
from datetime import date

import pandas as pd

GRADE_CUTS = {5: 80.0, 4: 60.0, 3: 20.0}   # баға бағаны жоқ болса ғана қолданылады

SKILLS = {
    "оқу": ("оқушылардың мәтінді оқу, ақпаратты түсіну, негізгі ойды анықтау және мәтін мазмұны бойынша сұрақтарға "
            "жауап беру дағдыларының қалыптасқанын көрсетеді",
            "мәтіндегі жасырын ақпаратты анықтау, автордың көзқарасын талдау, бірнеше дереккөзді салыстыру және "
            "сыни тұрғыдан бағалау дағдыларын жетілдіру қажет"),
    "математ": ("оқушылардың математикалық білімдерін өмірлік жағдаяттарда қолдану, логикалық ойлау, есептерді "
                "шығару және математикалық заңдылықтарды анықтау дағдыларының жақсы деңгейде екенін көрсетеді",
                "мәтінді есептер, пайыздық қатынастар, диаграммалар мен кестелерді талдау, математикалық модельдеу "
                "және көпқадамды есептерді шығару дағдыларын жетілдіру қажет"),
    "жаратылыстану": ("оқушылардың ғылыми құбылыстарды түсіндіру және ғылыми ақпаратты интерпретациялау "
                      "дағдыларының қалыптасқанын көрсетеді",
                      "ғылыми құбылыстарды түсіндіру, тәжірибе нәтижелерін талдау, кесте мен диаграммалардағы "
                      "ақпаратты интерпретациялау және ғылыми дәлелдерге сүйене отырып қорытынды жасау дағдыларын "
                      "дамыту қажет. Әсіресе кесте, диаграмма, графиктермен жұмыс жасауға бағытталған тапсырмаларды "
                      "көбірек орындату маңызды"),
    "қаржы": ("оқушылардың қаржылық ұғымдарды түсіну және күнделікті қаржылық шешім қабылдау дағдыларының "
              "қалыптасқанын көрсетеді",
              "бюджет жоспарлау, пайыз, тәуекел мен пайданы бағалау бойынша практикалық жағдаяттарды көбірек "
              "қарастыру қажет"),
    "креатив": ("оқушылардың шығармашылық ойлау, идея ұсыну және оны жетілдіру дағдыларының қалыптасқанын көрсетеді",
                "ашық сұрақтар, жобалық тапсырмалар және балама шешім іздеу жаттығуларын көбейту қажет"),
}
DEFAULT_SKILL = ("оқушылардың функционалдық сауаттылық дағдыларының қалыптасып келе жатқанын көрсетеді",
                 "өмірлік жағдаяттарға негізделген практикалық тапсырмаларды көбірек орындату қажет")

DEFAULT_GOAL = ("Оқушыларды PISA халықаралық зерттеуіне сапалы дайындау, олардың функционалдық сауаттылығын дамыту, "
                "алған білімдерін өмірлік жағдаяттарда қолдана білу дағдыларын қалыптастыру және халықаралық бағалау "
                "талаптарына сәйкес білім деңгейін арттыру.")
DEFAULT_BASE = "PISA халықаралық зерттеуіне дайындық жоспары"
MONTHS = ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан",
          "қараша", "желтоқсан"]


# ---------------- көмекшілер ----------------
def f1(x, nd=1) -> str:
    """74.6 → '74,6'; 71.0 → '71'"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    v = round(float(x), nd)
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else str(int(round(v)))
    return s.replace(".", ",")


def pct(x) -> str:
    return f"{f1(x)}%"


def skill(domain: str):
    d = domain.lower()
    for k, v in SKILLS.items():
        if k in d:
            return v
    return DEFAULT_SKILL


NUM_WORDS = {2: "Екі", 3: "Үш", 4: "Төрт", 5: "Бес", 6: "Алты", 7: "Жеті"}


def level_word(p: float) -> str:
    return "жоғары" if p >= 80 else "жақсы" if p >= 65 else "орташа" if p >= 50 else "төмен"


def ablative(phrase: str) -> str:
    """'математикалық сауаттылық' → '...сауаттылықтан', 'оқу сауаттылығы' → '...сауаттылығынан'"""
    w = phrase.strip()
    last = w[-1].lower()
    front = any(ch in "әөүіе" for ch in w.split()[-1].lower()[-4:]) and not any(
        ch in "аоұы" for ch in w.split()[-1].lower()[-3:])
    if last in "аәеиоөуұүыіэюя":
        suf = "нен" if front else "нан"
    elif last in "кқпстшфхцч":
        suf = "тен" if front else "тан"
    else:
        suf = "ден" if front else "дан"
    return w + suf


def class_label(c: str) -> str:
    """'7 А' → '7 «А»'"""
    m = re.match(r"(\d+)\s*(.*)", c)
    return f"{m.group(1)} «{m.group(2)}»" if m and m.group(2) else c


def kaz_date(d: str) -> str:
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d or "")
    if not m:
        return d
    return f"{m.group(3)} жылдың {int(m.group(1))} {MONTHS[int(m.group(2)) - 1]}сында"


def names(lst, limit=25) -> str:
    lst = list(lst)
    return ", ".join(lst[:limit]) + (f" және т.б. ({len(lst)})" if len(lst) > limit else "")


# ---------------- Excel оқу ----------------
def parse_edu(file) -> dict:
    data = file.getvalue() if hasattr(file, "getvalue") else open(file, "rb").read()
    raw = pd.read_excel(io.BytesIO(data), header=None, dtype=object)
    hdr = None
    for i in range(min(15, len(raw))):
        row = [str(v).lower() for v in raw.iloc[i].tolist() if v is not None and str(v) != "nan"]
        if any("аты" in v or "фио" in v for v in row) and any("ұпай" in v or "балл" in v for v in row):
            hdr = i
            break
    if hdr is None:
        raise ValueError("«Аты-жөні» және «ұпай» бағандары бар тақырып жолы табылмады")
    title = " ".join(str(v) for v in raw.iloc[:hdr].values.ravel() if v is not None and str(v) != "nan").strip()
    cols = [str(c).strip() if c is not None and str(c) != "nan" else f"col{j}" for j, c in enumerate(raw.iloc[hdr])]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = cols
    low = [c.lower() for c in cols]
    ci = lambda *pats: next((cols[i] for i, c in enumerate(low) for p in pats if re.search(p, c)), None)
    c_name, c_cls, c_lit = ci(r"аты|фио|оқушы"), ci(r"^сынып|^класс"), ci(r"литер|әрпі|буква")
    c_tot = ci(r"жалпы ұпай|жалпы балл|общий балл|итого")
    domains = []
    for i, c in enumerate(cols):
        m = re.match(r"(.+?)\s*[·•|\-–]\s*(ұпай|балл)\D*(\d+)?", c, re.I)
        if m and "жалпы" not in c.lower():
            dname = m.group(1).strip()
            mx = float(m.group(3)) if m.group(3) else None
            grade_col = next((cols[j] for j in range(len(cols)) if cols[j].lower().startswith(dname.lower())
                              and re.search(r"баға|оценка", cols[j].lower())), None)
            domains.append({"name": dname, "max": mx, "score_col": c, "grade_col": grade_col})
    if not domains:
        raise ValueError("Бағыттар бағандары («<бағыт> · ұпай - <макс>») табылмады")
    # Платформаның ресми орташа жолы (аты-жөні бос, ұпайлар бар) — мектеп көрсеткіші осыдан алынады
    official = {}
    blank = df[df[c_name].isna() | (df[c_name].astype(str).str.strip().isin(["", "nan"]))]
    for _, row in blank.iterrows():
        vals = {d["name"]: pd.to_numeric(row[d["score_col"]], errors="coerce") for d in domains}
        if all(pd.notna(v) and v > 1 for v in vals.values()) and not official:
            official = {"domains": {k: float(v) for k, v in vals.items()},
                        "total": float(pd.to_numeric(row[c_tot], errors="coerce")) if c_tot else None}
        elif official and all(pd.notna(v) and 0 < v <= 1 for v in vals.values()):
            tot = pd.to_numeric(row[c_tot], errors="coerce") if c_tot else None
            official["pct"] = {k: float(v) * 100 for k, v in vals.items()}
            official["pct_total"] = float(tot) * 100 if tot is not None and pd.notna(tot) and tot <= 1 else None
            break
    df = df[df[c_name].notna() & (df[c_name].astype(str).str.strip() != "")]
    out = pd.DataFrame({"Оқушы": df[c_name].astype(str).str.strip()})
    if c_cls is not None:
        out["Сынып"] = df[c_cls].astype(str).str.extract(r"(\d+)")[0]
    lit = df[c_lit].astype(str).str.strip().str.upper() if c_lit else ""
    out["Класс"] = (out["Сынып"].fillna("") + " " + lit).str.strip()
    for d in domains:
        s = pd.to_numeric(df[d["score_col"]], errors="coerce")
        out[f"{d['name']}|ұпай"] = s
        if d["max"] is None:
            d["max"] = float(s.max() or 1)
        if d["grade_col"]:
            out[f"{d['name']}|баға"] = pd.to_numeric(df[d["grade_col"]], errors="coerce")
        else:
            p = s / d["max"] * 100
            out[f"{d['name']}|баға"] = p.map(lambda v: next((g for g, c in GRADE_CUTS.items() if v >= c), 2)
                                             if pd.notna(v) else None)
    score_cols = [f"{d['name']}|ұпай" for d in domains]
    out["Жалпы ұпай"] = pd.to_numeric(df[c_tot], errors="coerce") if c_tot else out[score_cols].sum(axis=1)
    out = out.reset_index(drop=True)
    dm = re.search(r"(\d{2}\.\d{2}\.\d{4})", title)
    grades = sorted({int(g) for g in out["Сынып"].dropna().astype(int)}) if "Сынып" in out else []
    return {"title": title, "date": dm.group(1) if dm else date.today().strftime("%d.%m.%Y"),
            "domains": [{"name": d["name"], "max": d["max"]} for d in domains], "students": out, "grades": grades,
            "official": official}


# ---------------- Есептеу ----------------
def _stats(df: pd.DataFrame, d: dict) -> dict:
    s, g = df[f"{d['name']}|ұпай"], df[f"{d['name']}|баға"]
    n = int(s.notna().sum())
    cnt = {k: int((g == k).sum()) for k in (5, 4, 3, 2)}
    who = {k: df.loc[g == k, "Оқушы"].tolist() for k in (5, 4, 3, 2)}
    avg = float(s.mean()) if n else 0.0
    return {"n": n, "avg": avg, "pct": avg / d["max"] * 100 if d["max"] else 0, "max": d["max"], "cnt": cnt,
            "who": who, "quality": (cnt[5] + cnt[4]) / n * 100 if n else 0,
            "success": (n - cnt[2]) / n * 100 if n else 0}


def compute(p: dict) -> dict:
    df, doms = p["students"], p["domains"]
    res = {"n": len(df), "avg_total": float(df["Жалпы ұпай"].mean()),
           "max_total": sum(d["max"] for d in doms), "school": {}, "classes": {}, "parallels": {}}
    res["pct_total"] = res["avg_total"] / res["max_total"] * 100 if res["max_total"] else 0
    off = p.get("official") or {}
    for d in doms:
        res["school"][d["name"]] = _stats(df, d)
        if off.get("domains", {}).get(d["name"]):
            v = off["domains"][d["name"]]
            res["school"][d["name"]].update({"avg": v, "pct": off.get("pct", {}).get(d["name"]) or v / d["max"] * 100})
    if off.get("total"):
        res["avg_total"] = off["total"]
        res["pct_total"] = off.get("pct_total") or (off["total"] / res["max_total"] * 100 if res["max_total"] else 0)
    for cl, g in sorted(df.groupby("Класс"), key=lambda x: (int(re.match(r"\d+", x[0]).group())
                                                            if re.match(r"\d+", x[0]) else 0, x[0])):
        res["classes"][cl] = {"n": len(g), "avg_total": float(g["Жалпы ұпай"].mean()),
                              "domains": {d["name"]: _stats(g, d) for d in doms}}
    for par, g in df.groupby("Сынып"):
        res["parallels"][str(par)] = {"n": len(g), "domains": {d["name"]: _stats(g, d) for d in doms}}
    gcols = [f"{d['name']}|баға" for d in doms]
    df = df.copy()
    df["«2» саны"] = (df[gcols] == 2).sum(axis=1)
    df["«3» саны"] = (df[gcols] == 3).sum(axis=1)
    df["«5» саны"] = (df[gcols] == 5).sum(axis=1)
    res["top"] = df.sort_values("Жалпы ұпай", ascending=False).head(10)[["Оқушы", "Класс", "Жалпы ұпай"]]
    res["risk"] = df[(df["«2» саны"] > 0) | (df["«3» саны"] >= 2)].sort_values("Жалпы ұпай")[
        ["Оқушы", "Класс", "Жалпы ұпай", "«3» саны", "«2» саны"]]
    res["all5"] = df[df["«5» саны"] == len(doms)][["Оқушы", "Класс", "Жалпы ұпай"]]
    return res


def tables(p: dict, r: dict) -> dict[str, pd.DataFrame]:
    doms = [d["name"] for d in p["domains"]]
    sch = pd.DataFrame([{"Бағыт": d, "Макс. ұпай": r["school"][d]["max"], "Орташа ұпай": round(r["school"][d]["avg"], 1),
                         "Орындалу %": round(r["school"][d]["pct"], 1), "«5»": r["school"][d]["cnt"][5],
                         "«4»": r["school"][d]["cnt"][4], "«3»": r["school"][d]["cnt"][3],
                         "«2»": r["school"][d]["cnt"][2], "Сапа %": round(r["school"][d]["quality"], 1)} for d in doms])
    rows = []
    for cl, c in r["classes"].items():
        for d in doms:
            s = c["domains"][d]
            rows.append({"Сынып": cl, "Бағыт": d, "Оқушы": s["n"], "Орташа ұпай": round(s["avg"], 1),
                         "Орындалу %": round(s["pct"], 1), "«5»": s["cnt"][5], "«4»": s["cnt"][4],
                         "«3»": s["cnt"][3], "«2»": s["cnt"][2], "Сапа %": round(s["quality"], 1)})
    cls = pd.DataFrame(rows)
    par = []
    for pr, c in r["parallels"].items():
        for d in doms:
            s = c["domains"][d]
            par.append({"Параллель": pr, "Бағыт": d, "Оқушы": s["n"], "Орындалу %": round(s["pct"], 1),
                        "Сапа %": round(s["quality"], 1)})
    return {"Мектеп (бағыттар)": sch, "Сынып × бағыт": cls,
            "Орындалу % матрицасы": cls.pivot_table(index="Сынып", columns="Бағыт", values="Орындалу %").reset_index(),
            "Параллельдер": pd.DataFrame(par), "Үздік 10 оқушы": r["top"], "Тәуекел тобы": r["risk"]}


def weak_list(p, r, norm_pct=65.0, norm_q=70.0) -> list[dict]:
    from core.uch_parsers import _w
    W = []
    for d, s in r["school"].items():
        if s["pct"] < norm_pct:
            W.append(_w("🔴" if s["pct"] < norm_pct - 10 else "🟠", "PISA", f"Мектеп / {d}", "Орындалу %",
                        round(s["pct"], 1), f"≥ {norm_pct}"))
    for cl, c in r["classes"].items():
        for d, s in c["domains"].items():
            if s["pct"] < norm_pct:
                W.append(_w("🔴" if s["pct"] < norm_pct - 10 else "🟠", "PISA", f"{cl} / {d}", "Орындалу %",
                            round(s["pct"], 1), f"≥ {norm_pct}"))
            if s["quality"] < norm_q:
                W.append(_w("🟠", "PISA", f"{cl} / {d}", "Сапа %", round(s["quality"], 1), f"≥ {norm_q}"))
            if s["cnt"][2]:
                W.append(_w("🔴", "PISA", f"{cl} / {d}", "«2»-ге орындаған оқушы саны", s["cnt"][2], "0"))
    return W


def auto_recommendations(p, r, norm_pct=65.0) -> list[str]:
    rec = []
    weak_d = sorted(r["school"].items(), key=lambda x: x[1]["pct"])
    low = [d for d, s in weak_d if s["pct"] < 75] or [weak_d[0][0]]
    rec.append(f"PISA халықаралық зерттеуіне дайындық барысында {', '.join(d.lower() for d in low)} "
               f"бағыт{'тарына' if len(low) > 1 else 'ына'} басымдық беру қажет.")
    for cl, c in r["classes"].items():
        bad = [d for d, s in c["domains"].items() if s["pct"] < norm_pct]
        if bad:
            rec.append(f"{class_label(cl)} сыныбында {' және '.join(d.lower() for d in bad)} "
                       f"бағыт{'тарына' if len(bad) > 1 else 'ына'} басымдық беріп, білім сапасын арттыру мақсатында "
                       f"пән мұғалімдерінің бірлескен түзету жұмыстарын ұйымдастыру.")
    if not r["risk"].empty:
        rec.append(f"Тәуекел тобындағы {len(r['risk'])} оқушымен («2» немесе бірнеше бағыттан «3») жеке түзету "
                   f"жоспары бойынша жұмыс жүргізу, келесі диагностикада қайта бақылау.")
    rec.append("Сабақтарда PISA форматындағы өмірлік жағдаяттарға негізделген тапсырмаларды жүйелі қолдану; "
               "ӘБ отырысында нәтижелерді талдап, тәжірибе алмасу.")
    return rec


# ---------------- Word құжаты (мектеп үлгісі) ----------------
def _doc_setup():
    from docx import Document
    from docx.shared import Cm, Pt
    doc = Document()
    s = doc.sections[0]
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Cm(3), Cm(1.5), Cm(2), Cm(2)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Times New Roman", Pt(14)
    st.element.rPr.rFonts.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
                              "Times New Roman")
    st.paragraph_format.space_after = Pt(0)
    return doc


def _p(doc, text="", bold=False, center=False, justify=True, indent=True, italic=False, size=None):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
    par = doc.add_paragraph()
    if center:
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif justify:
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent and not center:
        par.paragraph_format.first_line_indent = Cm(1.5)
    if text:
        run = par.add_run(text)
        run.bold, run.italic = bold, italic
        if size:
            run.font.size = Pt(size)
    return par


def _rich(doc, parts, indent=True):
    """parts: [(text, bold)]"""
    par = _p(doc, indent=indent)
    for t, b in parts:
        par.add_run(t).bold = b
    return par


def _table(doc, header: list, rows: list[list], bold_first_col=True, size=12):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    for j, h in enumerate(header):
        c = t.rows[0].cells[j].paragraphs[0]
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = c.add_run(str(h))
        r.bold, r.font.size = True, Pt(size)
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            c = t.rows[i].cells[j].paragraphs[0]
            c.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
            r = c.add_run(str(v))
            r.font.size = Pt(size)
            r.bold = bold_first_col and j == 0
    doc.add_paragraph()
    return t


def _chart(doc, labels, series: dict, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from docx.shared import Cm
    except Exception:
        return
    import numpy as np
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    x = np.arange(len(labels))
    w = 0.8 / max(len(series), 1)
    colors = ["#2a6fb0", "#e08a1e", "#3a9a5b", "#9b59b6", "#c0392b"]
    for i, (name, vals) in enumerate(series.items()):
        bars = ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=name, color=colors[i % len(colors)])
        ax.bar_label(bars, labels=[f1(v) for v in vals], fontsize=7, padding=1)
    ax.set_xticks(x, labels, fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, ncol=min(len(series), 3), loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png")
    plt.close(fig)
    doc.add_picture(io.BytesIO(bio.getvalue()), width=Cm(16))


def _domain_table(doc, head, stats: dict, doms):
    _table(doc, [head] + doms, [
        ["Жалпы ұпай саны"] + [f1(stats[d]["max"], 0) for d in doms],
        ["Орташа ұпай"] + [f1(stats[d]["avg"]) for d in doms],
        ["Орындалу %"] + [pct(stats[d]["pct"]) for d in doms]])


def build_docx(p: dict, r: dict, opts: dict, ai_data: dict | None = None) -> bytes:
    """opts: base, goal, signer, signer_title, contingent, teachers{(класс,бағыт): str}, notes{(класс,бағыт): str},
    platform, include_names(bool), charts(bool)"""
    doms = [d["name"] for d in p["domains"]]
    doc = _doc_setup()
    grades = p["grades"]
    gtxt = f"{grades[0]}-{grades[-1]}" if len(grades) > 1 else (str(grades[0]) if grades else "")
    plat = opts.get("platform") or "EDU TEST"
    for line in [f"{plat} платформасы арқылы", f"{gtxt}-сынып оқушыларының PISA халықаралық зерттеуіне дайындық",
                 "тестілеуінің талдауы"]:
        _p(doc, line, bold=True, center=True)
    _rich(doc, [("Мерзімі: ", True), (p["date"], False)], indent=False)
    _rich(doc, [("Негізі: ", True), (opts.get("base") or DEFAULT_BASE, False)], indent=False)
    _rich(doc, [("Мақсаты: ", True), (opts.get("goal") or DEFAULT_GOAL, False)], indent=False)
    part = f" ({pct(r['n'] / opts['contingent'] * 100)})" if opts.get("contingent") else ""
    _p(doc, f"{kaz_date(p['date'])} {plat} платформасында {gtxt}-сынып оқушыларының PISA халықаралық "
            f"зерттеуіне дайындық тестілеуі өткізілді. Тестілеуге {r['n']}{part} білім алушы қатысты. Мектеп бойынша "
            f"жалпы орташа көрсеткіш {f1(r['avg_total'])} ұпай ({pct(r['pct_total'])}) болды.")
    _p(doc, "Оның ішінде:")
    _domain_table(doc, p["date"], r["school"], doms)
    if opts.get("charts", True):
        _chart(doc, doms, {"Орындалу %": [r["school"][d]["pct"] for d in doms],
                           "Сапа %": [r["school"][d]["quality"] for d in doms]}, "Мектеп бойынша нәтижелер")

    # --- Пәндер бойынша салыстырмалы талдау ---
    _p(doc, "Пәндер бойынша салыстырмалы талдау", bold=True, center=True)
    order = sorted(doms, key=lambda d: r["school"][d]["pct"], reverse=True)
    for i, d in enumerate(order):
        s = r["school"][d]
        _p(doc, f"{d} – {pct(s['pct'])}.", bold=True)
        good, dev = skill(d)
        if i == 0:
            t = f"{NUM_WORDS.get(len(doms), len(doms))} бағыттың ішінде ең жоғары көрсеткіш тіркелген. Бұл {good}. Дегенмен, {dev}."
        else:
            diffs = [f"{ablative(order[j].lower())} {f1(r['school'][order[j]]['pct'] - s['pct'])} пайыздық тармаққа"
                     for j in range(i)]
            pos = "ең төмен нәтиже байқалады" if i == len(order) - 1 else "орташа нәтиже байқалады"
            t = (f"{NUM_WORDS.get(len(doms), len(doms))} бағыттың ішінде {pos}. Көрсеткіш {', '.join(diffs)} төмен. "
                 f"Нәтиже деңгейі – {level_word(s['pct'])}. Сондықтан {dev}.")
        t += (f" Мектеп бойынша «5»-ке – {s['cnt'][5]}, «4»-ке – {s['cnt'][4]}, «3»-ке – {s['cnt'][3]}, "
              f"«2»-ге – {s['cnt'][2]} оқушы орындады, білім сапасы – {pct(s['quality'])}.")
        _p(doc, t)
    hi, lo = order[0], order[-1]
    _p(doc, f"Диагностикалық жұмыс нәтижесі бойынша оқушылардың ең жоғары көрсеткіші {hi.lower()} бағытында – "
            f"{pct(r['school'][hi]['pct'])}, ал ең төмен көрсеткіші {lo.lower()} бағытында – "
            f"{pct(r['school'][lo]['pct'])} құрады.")
    lows = [d.lower() for d in order if r["school"][d]["pct"] < 75] or [lo.lower()]
    _p(doc, "Жалпы нәтижелер оқушылардың функционалдық сауаттылығын дамыту жұмыстары жүйелі түрде жүргізіліп "
            f"жатқанын көрсетеді. Сонымен қатар, PISA халықаралық зерттеуіне дайындық барысында {' және '.join(lows)} "
            f"бағыт{'тарына' if len(lows) > 1 else 'ына'} басымдық беру қажеттілігі анықталды.")

    # --- Параллельдер ---
    if len(r["parallels"]) > 1:
        _p(doc, "Параллельдер бойынша көрсеткіштер", bold=True, center=True)
        _table(doc, ["Параллель"] + doms + ["Қатысқаны"],
               [[f"{pr}-сынып"] + [f"{pct(c['domains'][d]['pct'])} (сапа {pct(c['domains'][d]['quality'])})"
                                   for d in doms] + [c["n"]] for pr, c in r["parallels"].items()], size=11)

    # --- Сыныптар ---
    _p(doc, "Сыныптар аралығының көрсеткіштері", bold=True, center=True)
    if opts.get("charts", True):
        cls = list(r["classes"])
        _chart(doc, [class_label(c) for c in cls], {d: [r["classes"][c]["domains"][d]["pct"] for c in cls]
                                                    for d in doms}, "Сыныптар бойынша орындалу %")
    show_names = opts.get("include_names", True)
    teachers, notes = opts.get("teachers", {}), opts.get("notes", {})
    for cl, c in r["classes"].items():
        lab = class_label(cl)
        _domain_table(doc, lab, c["domains"], doms)
        corder = sorted(doms, key=lambda d: c["domains"][d]["pct"], reverse=True)
        for i, d in enumerate(corder):
            s = c["domains"][d]
            good, dev = skill(d)
            _p(doc, f"{d} – {pct(s['pct'])}.", bold=True)
            if i == 0:
                t = f"Сынып бойынша ең жоғары көрсеткіш {d.lower()} бағытында байқалды. Бұл {good}."
            else:
                t = (f"{d} бойынша көрсеткіш {pct(s['pct'])} құрады, бұл {corder[0].lower()} бағытынан "
                     f"{f1(c['domains'][corder[0]]['pct'] - s['pct'])} пайыздық тармаққа төмен. "
                     f"Нәтиже деңгейі – {level_word(s['pct'])}.")
            t += (f" Қатысқан {s['n']} оқушының ішінде «5»-ке орындағандар – {s['cnt'][5]}, «4»-ке – {s['cnt'][4]}, "
                  f"жалпы білім сапасы – {pct(s['quality'])}.")
            if show_names:
                if s["who"][3]:
                    t += f" Орташа нәтиже, яғни «3»-ке орындағандар: {names(s['who'][3])}."
                if s["who"][2]:
                    t += f" «2»-ге орындағандар: {names(s['who'][2])}."
                if s["cnt"][5] and s["cnt"][5] <= 3:
                    t += f" «5»-ке орындаған: {names(s['who'][5])}."
            else:
                t += f" «3»-ке – {s['cnt'][3]}, «2»-ге – {s['cnt'][2]} оқушы."
            if teachers.get((cl, d)):
                t += f" Пән мұғалімі: {teachers[(cl, d)]}."
            if i > 0 or s["pct"] < 80:
                t += f" Алдағы уақытта {dev}."
            _p(doc, t)
            if notes.get((cl, d)):
                _rich(doc, [("Тақырыптық қорытынды: ", True), (notes[(cl, d)], False)])
        best, worst = corder[0], corder[-1]
        _p(doc, f"{lab} сыныбының диагностикалық жұмыс нәтижелерін талдау барысында ең жоғары көрсеткіш "
                f"{best.lower()} бағытында – {pct(c['domains'][best]['pct'])}, " +
           ", ".join(f"{d.lower()} бойынша – {pct(c['domains'][d]['pct'])}" for d in corder[1:]) + " екені анықталды.")
        weak_d = [d.lower() for d in corder if c["domains"][d]["pct"] < 70]
        if weak_d:
            _p(doc, f"Нәтижелер {' және '.join(weak_d)} бағыт{'тарында' if len(weak_d) > 1 else 'ында'} білім "
                    "олқылықтарын толықтыру, практикалық тапсырмалармен жұмыс жүргізу және функционалдық "
                    "сауаттылықты дамыту қажеттілігін көрсетеді.")
        else:
            _p(doc, "Жалпы алғанда, сынып оқушыларының функционалдық сауаттылығы жақсы деңгейде қалыптасқан.")

    # --- Қосымша: үздіктер, тәуекел ---
    if show_names:
        _p(doc, "Үздік нәтиже көрсеткен оқушылар", bold=True, center=True)
        _table(doc, ["№", "Оқушы", "Сынып", "Жалпы ұпай"],
               [[i, row["Оқушы"], class_label(row["Класс"]), f1(row["Жалпы ұпай"], 0)]
                for i, (_, row) in enumerate(r["top"].iterrows(), 1)], bold_first_col=False)
        if not r["risk"].empty:
            _p(doc, "Тәуекел тобы (жеке жұмыс жүргізілетін оқушылар)", bold=True, center=True)
            _table(doc, ["№", "Оқушы", "Сынып", "Жалпы ұпай", "«3» саны", "«2» саны"],
                   [[i, row["Оқушы"], class_label(row["Класс"]), f1(row["Жалпы ұпай"], 0), row["«3» саны"],
                     row["«2» саны"]] for i, (_, row) in enumerate(r["risk"].iterrows(), 1)], bold_first_col=False)

    # --- ЖИ қорытындысы ---
    if ai_data:
        _p(doc, "Талдау қорытындысы", bold=True, center=True)
        if ai_data.get("summary"):
            _p(doc, ai_data["summary"])
        for w in ai_data.get("weaknesses", []):
            _p(doc, f"– {w}")
    _p(doc, "Ұсыныс:", bold=True, indent=False)
    recs = []
    if ai_data and ai_data.get("recommendations"):
        recs = [f"{x.get('target', '')}: {x.get('text', '')}".strip(": ") if isinstance(x, dict) else str(x)
                for x in ai_data["recommendations"]]
    recs = recs or auto_recommendations(p, r)
    for i, x in enumerate(recs, 1):
        _p(doc, f"{i}. {x}")
    plan = (ai_data or {}).get("plan") or []
    if plan:
        _p(doc, "Олқылықтарды жою жоспары", bold=True, center=True)
        keys = ["Мәселе", "Іс-шара", "Жауапты", "Мерзімі", "Күтілетін нәтиже"]
        _table(doc, ["№"] + keys, [[i] + [str(x.get(k, "")) for k in keys] for i, x in enumerate(plan, 1)],
               bold_first_col=False, size=10)
    doc.add_paragraph()
    _p(doc, f"{opts.get('signer_title') or 'Басшының ОІЖ орынбасары'} {opts.get('signer') or ''}", indent=False)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ---------------- Өзгеріс (екі талдауды салыстыру) ----------------
def arrow(v):
    if v is None or pd.isna(v):
        return "—"
    return f"▲ +{f1(v)}" if v > 0.05 else (f"▼ {f1(v)}" if v < -0.05 else "= 0")


def compare(prev: dict, cur: dict) -> dict:
    """prev/cur: {'p': parsed, 'r': computed, 'label': str}"""
    pd_, cd = prev["r"], cur["r"]
    doms = [d["name"] for d in cur["p"]["domains"] if d["name"] in pd_["school"]]
    sch = pd.DataFrame([{"Бағыт": d, "Бұрын %": round(pd_["school"][d]["pct"], 1),
                         "Қазір %": round(cd["school"][d]["pct"], 1),
                         "Өзгеріс (п.т.)": round(cd["school"][d]["pct"] - pd_["school"][d]["pct"], 1),
                         "Сапа бұрын %": round(pd_["school"][d]["quality"], 1),
                         "Сапа қазір %": round(cd["school"][d]["quality"], 1),
                         "Сапа өзгерісі": round(cd["school"][d]["quality"] - pd_["school"][d]["quality"], 1),
                         "«2» бұрын": pd_["school"][d]["cnt"][2], "«2» қазір": cd["school"][d]["cnt"][2]}
                        for d in doms])
    total = {"Қатысқан бұрын": pd_["n"], "Қатысқан қазір": cd["n"], "Орташа % бұрын": round(pd_["pct_total"], 1),
             "Орташа % қазір": round(cd["pct_total"], 1),
             "Өзгеріс (п.т.)": round(cd["pct_total"] - pd_["pct_total"], 1)}
    rows = []
    for cl in sorted(set(pd_["classes"]) & set(cd["classes"])):
        for d in doms:
            a, b = pd_["classes"][cl]["domains"][d], cd["classes"][cl]["domains"][d]
            rows.append({"Сынып": cl, "Бағыт": d, "Бұрын %": round(a["pct"], 1), "Қазір %": round(b["pct"], 1),
                         "Өзгеріс (п.т.)": round(b["pct"] - a["pct"], 1), "Сапа бұрын %": round(a["quality"], 1),
                         "Сапа қазір %": round(b["quality"], 1), "Сапа өзгерісі": round(b["quality"] - a["quality"], 1)})
    cls = pd.DataFrame(rows)
    a = prev["p"]["students"].set_index("Оқушы")
    b = cur["p"]["students"].set_index("Оқушы")
    common = a.index.intersection(b.index)
    st = pd.DataFrame({"Оқушы": common, "Сынып": b.loc[common, "Класс"].values,
                       "Бұрын (ұпай)": a.loc[common, "Жалпы ұпай"].values,
                       "Қазір (ұпай)": b.loc[common, "Жалпы ұпай"].values})
    pmax, cmax = prev["r"]["max_total"], cur["r"]["max_total"]
    st["Бұрын %"] = (st["Бұрын (ұпай)"] / pmax * 100).round(1)
    st["Қазір %"] = (st["Қазір (ұпай)"] / cmax * 100).round(1)
    st["Өзгеріс (п.т.)"] = (st["Қазір %"] - st["Бұрын %"]).round(1)
    st = st.sort_values("Өзгеріс (п.т.)")
    only_prev = sorted(set(a.index) - set(b.index))
    only_cur = sorted(set(b.index) - set(a.index))
    return {"prev": prev["label"], "cur": cur["label"], "total": total, "school": sch, "classes": cls,
            "students": st, "only_prev": only_prev, "only_cur": only_cur,
            "new_classes": sorted(set(cd["classes"]) - set(pd_["classes"]))}


def compare_text(c: dict) -> list[str]:
    t = c["total"]
    out = [f"Салыстыру: «{c['prev']}» және «{c['cur']}». Қатысқан оқушылар: {t['Қатысқан бұрын']} → "
           f"{t['Қатысқан қазір']}. Мектеп бойынша орташа орындалу: {pct(t['Орташа % бұрын'])} → "
           f"{pct(t['Орташа % қазір'])} ({arrow(t['Өзгеріс (п.т.)'])} п.т.)."]
    for _, r in c["school"].iterrows():
        trend = "өсті" if r["Өзгеріс (п.т.)"] > 0.05 else ("төмендеді" if r["Өзгеріс (п.т.)"] < -0.05 else "өзгермеді")
        out.append(f"{r['Бағыт']}: {pct(r['Бұрын %'])} → {pct(r['Қазір %'])}, нәтиже {trend} "
                   f"({arrow(r['Өзгеріс (п.т.)'])} п.т.); білім сапасы {pct(r['Сапа бұрын %'])} → "
                   f"{pct(r['Сапа қазір %'])}.")
    if not c["classes"].empty:
        up = c["classes"].sort_values("Өзгеріс (п.т.)", ascending=False).head(3)
        dn = c["classes"].sort_values("Өзгеріс (п.т.)").head(3)
        out.append("Ең көп өскен көрсеткіштер: " + "; ".join(
            f"{class_label(r['Сынып'])} – {r['Бағыт'].lower()} ({arrow(r['Өзгеріс (п.т.)'])} п.т.)"
            for _, r in up.iterrows() if r["Өзгеріс (п.т.)"] > 0) + ".")
        neg = [f"{class_label(r['Сынып'])} – {r['Бағыт'].lower()} ({arrow(r['Өзгеріс (п.т.)'])} п.т.)"
               for _, r in dn.iterrows() if r["Өзгеріс (п.т.)"] < 0]
        if neg:
            out.append("Төмендеген көрсеткіштер (назар аудару қажет): " + "; ".join(neg) + ".")
    s = c["students"]
    if not s.empty:
        out.append(f"Екі тестілеуге де қатысқан {len(s)} оқушының {int((s['Өзгеріс (п.т.)'] > 0).sum())} нәтижесі "
                   f"жақсарды, {int((s['Өзгеріс (п.т.)'] < 0).sum())} төмендеді.")
    return out


def build_compare_docx(c: dict, opts: dict, include_names=True) -> bytes:
    doc = _doc_setup()
    for line in ["PISA халықаралық зерттеуіне дайындық тестілеулері", "нәтижелерінің өзгерісі (динамикасы)"]:
        _p(doc, line, bold=True, center=True)
    _rich(doc, [("Салыстырылған тестілеулер: ", True), (f"{c['prev']} → {c['cur']}", False)], indent=False)
    for t in compare_text(c):
        _p(doc, t)
    _p(doc, "Мектеп бойынша (бағыттар)", bold=True, center=True)
    _table(doc, ["Бағыт", "Бұрын", "Қазір", "Өзгеріс", "Сапа бұрын", "Сапа қазір", "Сапа өзгерісі"],
           [[r["Бағыт"], pct(r["Бұрын %"]), pct(r["Қазір %"]), arrow(r["Өзгеріс (п.т.)"]), pct(r["Сапа бұрын %"]),
             pct(r["Сапа қазір %"]), arrow(r["Сапа өзгерісі"])] for _, r in c["school"].iterrows()], size=11)
    if opts.get("charts", True) and not c["school"].empty:
        _chart(doc, c["school"]["Бағыт"].tolist(), {"Бұрын %": c["school"]["Бұрын %"].tolist(),
                                                    "Қазір %": c["school"]["Қазір %"].tolist()}, "Бағыттар бойынша өзгеріс")
    if not c["classes"].empty:
        _p(doc, "Сыныптар бойынша", bold=True, center=True)
        _table(doc, ["Сынып", "Бағыт", "Бұрын", "Қазір", "Өзгеріс", "Сапа өзгерісі"],
               [[class_label(r["Сынып"]), r["Бағыт"], pct(r["Бұрын %"]), pct(r["Қазір %"]), arrow(r["Өзгеріс (п.т.)"]),
                 arrow(r["Сапа өзгерісі"])] for _, r in c["classes"].iterrows()], size=10)
    if c["new_classes"]:
        _p(doc, f"Тек соңғы тестілеуде бар сыныптар: {', '.join(class_label(x) for x in c['new_classes'])}.")
    if include_names and not c["students"].empty:
        s = c["students"]
        _p(doc, "Нәтижесі төмендеген оқушылар", bold=True, center=True)
        down = s[s["Өзгеріс (п.т.)"] < 0]
        _table(doc, ["№", "Оқушы", "Сынып", "Бұрын", "Қазір", "Өзгеріс"],
               [[i, r["Оқушы"], class_label(r["Сынып"]), pct(r["Бұрын %"]), pct(r["Қазір %"]), arrow(r["Өзгеріс (п.т.)"])]
                for i, (_, r) in enumerate(down.iterrows(), 1)] or [["", "жоқ", "", "", "", ""]],
               bold_first_col=False, size=10)
        _p(doc, "Ең көп өскен оқушылар", bold=True, center=True)
        upn = s[s["Өзгеріс (п.т.)"] > 0].sort_values("Өзгеріс (п.т.)", ascending=False).head(15)
        _table(doc, ["№", "Оқушы", "Сынып", "Бұрын", "Қазір", "Өзгеріс"],
               [[i, r["Оқушы"], class_label(r["Сынып"]), pct(r["Бұрын %"]), pct(r["Қазір %"]), arrow(r["Өзгеріс (п.т.)"])]
                for i, (_, r) in enumerate(upn.iterrows(), 1)] or [["", "жоқ", "", "", "", ""]],
               bold_first_col=False, size=10)
    if opts.get("ai_text"):
        _p(doc, "Қорытынды және ұсыныстар", bold=True, center=True)
        for line in opts["ai_text"].split("\n"):
            if line.strip():
                _p(doc, line.strip())
    doc.add_paragraph()
    _p(doc, f"{opts.get('signer_title') or 'Басшының ОІЖ орынбасары'} {opts.get('signer') or ''}", indent=False)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()
