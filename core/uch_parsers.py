"""Оқу ісі: Kundelik / Bilimal / Report constructor Excel файлдарын тану, талдау, әлсіз жақтарды табу.

Қолдау көрсетілетін 6 түр:
  school   — «Данные по успеваемости школы» (параллельдер бойынша)
  subject  — «Данные по предмету» (бір пән, барлық сыныптар)
  klass    — «Данные по успеваемости класса» (сынып оқушылары × пәндер)
  report   — Report constructor: үлгерім (пәндер × параллельдер)
  sor      — БЖБ/ТЖБ (СОР/СОЧ) талдауы
  attend   — Report constructor: сабаққа қатысу (пәндер × параллельдер × сыныптар)
"""
import io
import re

import pandas as pd

THRESHOLDS = {"quality": 70.0, "success": 100.0, "avg": 4.0, "attendance": 95.0,
              "unexcused": 0, "sor_quality": 70.0, "sor_low": 0}

TYPE_NAMES = {
    "school": "Мектеп бойынша үлгерім (параллельдер)",
    "subject": "Пән бойынша үлгерім (сыныптар)",
    "klass": "Сынып бойынша үлгерім (оқушылар)",
    "report": "Пәндер бойынша жиынтық есеп (Report constructor)",
    "sor": "БЖБ / ТЖБ (СОР / СОЧ) талдауы",
    "attend": "Оқушылардың сабаққа қатысуы",
}


# ---------------- көмекшілер ----------------
def num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def txt(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def parse_class(name: str):
    """'10 А ҚАЗ' → (10, 'А', '10 А')"""
    m = re.match(r"\s*(\d{1,2})\s*([^\s\d]*)", txt(name))
    if not m:
        return None, "", txt(name)
    par, letter = int(m.group(1)), m.group(2).upper()
    return par, letter, f"{par} {letter}".strip()


def read_raw(file) -> pd.DataFrame:
    data = file.getvalue() if hasattr(file, "getvalue") else open(file, "rb").read()
    return pd.read_excel(io.BytesIO(data), header=None, dtype=object)


def _cells(raw, rows=15):
    return " ".join(txt(v) for v in raw.head(rows).values.ravel() if txt(v)).lower()


def detect_type(raw: pd.DataFrame) -> str | None:
    t = _cells(raw, 15)
    if "сор" in t and ("соч" in t or "суммативн" in t) or "бжб" in t and "тжб" in t:
        return "sor"
    if "сабаққа қатысу" in t or "посещаемость" in t or "себепсіз" in t or "пропущ" in t:
        return "attend"
    if "фамилия и имя" in t or "аты-жөні" in t:
        return "klass"
    if "параллель" in t and ("отличники" in t or "үздік" in t) and ("предмет (на" in t or "пән (" in t):
        return "report"
    if "параллель" in t and ("качество знаний" in t or "білім сапасы" in t):
        return "school"
    if "предмет" in t and "класс" in t or "пән" in t and "сынып" in t:
        return "subject"
    return None


def find_col(cols, *patterns):
    low = [str(c).lower() for c in cols]
    for p in patterns:
        for i, c in enumerate(low):
            if re.search(p, c):
                return cols[i]
    return None


def _header_df(raw, first_cell_pattern=None, any_cell=None):
    idx = 0
    for i in range(min(len(raw), 40)):
        row = [txt(v).lower() for v in raw.iloc[i].tolist()]
        if first_cell_pattern and re.search(first_cell_pattern, row[0]):
            idx = i
            break
        if any_cell and any(re.search(any_cell, c) for c in row):
            idx = i
            break
    df = raw.iloc[idx + 1:].copy()
    df.columns = [txt(c) or f"col{j}" for j, c in enumerate(raw.iloc[idx].tolist())]
    return df.reset_index(drop=True)


def _meta(raw, stop_pattern, rows=12):
    meta = {}
    for i in range(min(rows, len(raw))):
        r = [txt(v) for v in raw.iloc[i].tolist()]
        if re.search(stop_pattern, r[0].lower()):
            break
        vals = [v for v in r[1:] if v]
        if r[0] and vals:
            meta[r[0]] = vals[0]
    return meta


def _q(exc, good, graded):
    return round((exc + good) / graded * 100, 2) if graded else None


# ---------------- 1) Мектеп / параллельдер ----------------
def parse_school(raw):
    df = _header_df(raw, any_cell=r"^параллель$")
    c_par = find_col(df.columns, r"^параллель")
    out = pd.DataFrame({
        "Параллель": df[c_par].map(txt),
        "Оқушы саны": df[find_col(df.columns, r"кол-во учен|оқушы саны")].map(num),
        "Үздік": df[find_col(df.columns, r"отличник|үздік")].map(num),
        "Екпінді": df[find_col(df.columns, r"хорошист|екпінді")].map(num),
        "Үлгерімі төмен": df[find_col(df.columns, r"неусп|үлгермейт")].map(num),
        "Бір «4»-пен": df[find_col(df.columns, r'одному предмету "4"|бір.*4')].map(num),
        "Бір «3»-пен": df[find_col(df.columns, r'одному предмету "3"|бір.*3')].map(num),
        "Сапа %": df[find_col(df.columns, r"качество|сапа")].map(num),
        "Үлгерім %": df[find_col(df.columns, r"успеваемость|үлгерім")].map(num),
        "Орташа балл": df[find_col(df.columns, r"средний|орташа")].map(num),
    })
    # «Всего» жолы бірінші бағанда тұрады — бағандар ығысқан
    total_row = df[df.iloc[:, 0].map(txt).str.lower().str.contains("всего|барлығы|итого")]
    out = out[out["Параллель"].str.fullmatch(r"\d{1,2}")].copy()
    out["Параллель"] = out["Параллель"].astype(int)
    tot = {"Оқушы саны": out["Оқушы саны"].sum(), "Үздік": out["Үздік"].sum(), "Екпінді": out["Екпінді"].sum()}
    tot["Сапа %"] = round((tot["Үздік"] + tot["Екпінді"]) / tot["Оқушы саны"] * 100, 2) if tot["Оқушы саны"] else None
    tot["Үлгерім %"] = round((1 - out["Үлгерімі төмен"].sum() / tot["Оқушы саны"]) * 100, 2) if tot["Оқушы саны"] else None
    tot["Орташа балл"] = round((out["Орташа балл"] * out["Оқушы саны"]).sum() / tot["Оқушы саны"], 2)
    _ = total_row
    return {"meta": {}, "tables": {"Параллельдер бойынша": out}, "total": tot}


# ---------------- 2) Пән бойынша (сыныптар) ----------------
SUBJ_COLS = ["Сынып", "Оқушы саны", "5", "4", "3", "2", "Сынақ", "Сынақ емес", "Босатылған", "Баға жоқ",
             "Аттестатталмаған", "Уақытша аттест.", "Орташа балл", "Үлгерім %", "Сапа %"]


def parse_subject(raw):
    meta = _meta(raw, r"^(класс|сынып)$")
    start = None
    for i in range(len(raw)):
        if txt(raw.iloc[i, 0]).lower() in ("класс", "сынып"):
            start = i + 2
            break
    df = raw.iloc[start:, :15].copy() if start is not None else raw.iloc[:0, :15]
    df.columns = SUBJ_COLS[:df.shape[1]]
    df = df[df["Сынып"].map(txt) != ""]
    df = df[~df["Сынып"].map(txt).str.lower().str.contains("всего|барлығы|итого")]
    for c in SUBJ_COLS[1:]:
        if c in df:
            df[c] = df[c].map(num)
    df["Сынып"] = df["Сынып"].map(lambda x: parse_class(x)[2])
    df["Параллель"] = df["Сынып"].map(lambda x: parse_class(x)[0])
    df["Пән"] = meta.get("Предмет") or meta.get("Пән") or "Пән"
    return {"meta": meta, "tables": {"Сыныптар бойынша": df.reset_index(drop=True)}}


def agg_subject(df: pd.DataFrame) -> dict:
    """Бірнеше пән файлын біріктіріп, параллель және пән бойынша есептейді."""
    df = df.copy()
    df["бағаланды"] = df[["5", "4", "3", "2"]].sum(axis=1)

    def grp(by):
        g = df.groupby(by).agg(**{"Оқушы саны": ("Оқушы саны", "sum"), "5": ("5", "sum"), "4": ("4", "sum"),
                                  "3": ("3", "sum"), "2": ("2", "sum"), "бағаланды": ("бағаланды", "sum")})
        g["Сапа %"] = ((g["5"] + g["4"]) / g["бағаланды"] * 100).round(2)
        g["Үлгерім %"] = ((g["бағаланды"] - g["2"]) / g["бағаланды"] * 100).round(2)
        g["Орташа балл"] = ((g["5"] * 5 + g["4"] * 4 + g["3"] * 3 + g["2"] * 2) / g["бағаланды"]).round(2)
        return g.drop(columns=["бағаланды"]).reset_index()

    res = {"Пән × сынып": df.drop(columns=["бағаланды"]),
           "Параллель × пән": grp(["Параллель", "Пән"]), "Пәндер бойынша": grp("Пән"),
           "Сыныптар бойынша (барлық пән)": grp("Сынып")}
    if df["Пән"].nunique() > 1:
        res["Сапа матрицасы (сынып × пән)"] = df.pivot_table(index="Сынып", columns="Пән", values="Сапа %",
                                                              aggfunc="mean").round(1).reset_index()
    return res


# ---------------- 3) Сынып (оқушылар × пәндер) ----------------
def parse_klass(raw):
    meta = {}
    for i in range(min(10, len(raw))):
        r = [txt(v) for v in raw.iloc[i].tolist()]
        vals = [v for v in r[1:] if v]
        if r[0] and vals and not r[0].lower().startswith(("фамилия", "аты")):
            meta[r[0]] = vals[0]
    df = _header_df(raw, first_cell_pattern=r"^(фамилия|аты)")
    name_col = df.columns[0]
    stop = df[name_col].map(txt).str.lower().str.contains("средний балл по предмету|орташа балл")
    if stop.any():
        df = df.iloc[:stop.idxmax()]
    df = df[df[name_col].map(txt) != ""]
    subj = [c for c in df.columns[1:] if not re.search(r"средний|орташа", c.lower()) and not c.startswith("col")]
    grades = df[subj].apply(lambda col: col.map(lambda v: num(v) if num(v) in (2.0, 3.0, 4.0, 5.0) else None))
    grades = grades.apply(pd.to_numeric, errors="coerce").astype(float)
    klass = parse_class(meta.get("Класс") or meta.get("Сынып") or "")[2] or "Сынып"
    students = pd.DataFrame({"Оқушы": df[name_col].map(txt)})
    students["Орташа балл"] = grades.mean(axis=1).round(2)
    students["«5» саны"] = (grades == 5).sum(axis=1)
    students["«4» саны"] = (grades == 4).sum(axis=1)
    students["«3» саны"] = (grades == 3).sum(axis=1)
    students["«2» саны"] = (grades == 2).sum(axis=1)

    def cat(r):
        if r["«2» саны"] > 0:
            return "Үлгермейтін"
        if r["«3» саны"] == 1:
            return "Бір «3»-пен (екпінді резерві)"
        if r["«3» саны"] > 1:
            return "Үлгерімі орташа"
        if r["«4» саны"] == 0:
            return "Үздік"
        if r["«4» саны"] == 1:
            return "Бір «4»-пен (үздік резерві)"
        return "Екпінді"
    students["Санат"] = students.apply(cat, axis=1)
    students["Сынып"] = klass
    per_subj = pd.DataFrame({
        "Пән": subj,
        "Орташа балл": [round(grades[s].mean(), 2) if grades[s].notna().any() else None for s in subj],
        "Сапа %": [round((grades[s] >= 4).sum() / grades[s].notna().sum() * 100, 2) if grades[s].notna().any() else None
                   for s in subj],
        "Үлгерім %": [round((grades[s] >= 3).sum() / grades[s].notna().sum() * 100, 2) if grades[s].notna().any()
                      else None for s in subj],
        "«3» саны": [int((grades[s] == 3).sum()) for s in subj],
    }).dropna(subset=["Орташа балл"])
    per_subj["Сынып"] = klass
    per_subj["Параллель"] = parse_class(klass)[0]
    return {"meta": meta, "tables": {"Оқушылар": students, "Пәндер бойынша": per_subj}, "klass": klass}


def agg_klass(students: pd.DataFrame, subj: pd.DataFrame) -> dict:
    st = students.copy()
    st["Параллель"] = st["Сынып"].map(lambda x: parse_class(x)[0])
    st["Орташа балл"] = pd.to_numeric(st["Орташа балл"], errors="coerce")
    cls = st.groupby("Сынып").agg(**{"Оқушы саны": ("Оқушы", "size"), "Орташа балл": ("Орташа балл", "mean")})
    for c in ["Үздік", "Екпінді", "Бір «4»-пен (үздік резерві)", "Бір «3»-пен (екпінді резерві)", "Үлгермейтін"]:
        cls[c] = st[st["Санат"] == c].groupby("Сынып").size()
    cls = cls.fillna(0)
    cls["Сапа %"] = ((cls["Үздік"] + cls["Екпінді"] + cls["Бір «4»-пен (үздік резерві)"]) / cls["Оқушы саны"]
                     * 100).round(2)
    cls["Үлгерім %"] = ((cls["Оқушы саны"] - cls["Үлгермейтін"]) / cls["Оқушы саны"] * 100).round(2)
    cls["Орташа балл"] = cls["Орташа балл"].round(2)
    par = cls.reset_index()
    par["Параллель"] = par["Сынып"].map(lambda x: parse_class(x)[0])
    pg = par.groupby("Параллель").sum(numeric_only=True)
    pg["Сапа %"] = ((pg["Үздік"] + pg["Екпінді"] + pg["Бір «4»-пен (үздік резерві)"]) / pg["Оқушы саны"] * 100).round(2)
    pg["Үлгерім %"] = ((pg["Оқушы саны"] - pg["Үлгермейтін"]) / pg["Оқушы саны"] * 100).round(2)
    pg = pg.drop(columns=["Орташа балл"], errors="ignore")
    res = {"Сыныптар бойынша": cls.reset_index(), "Параллельдер бойынша": pg.reset_index(),
           "Пәндер бойынша (сыныптарда)": subj,
           "Пәндер бойынша (мектеп)": subj.groupby("Пән").agg(**{"Орташа балл": ("Орташа балл", "mean"),
                                                                 "Сапа %": ("Сапа %", "mean"),
                                                                 "«3» саны": ("«3» саны", "sum")}).round(2).reset_index(),
           "Резерв және тәуекел оқушылар": st[st["Санат"].str.contains("резерв|Үлгермейтін|орташа")]
           [["Сынып", "Оқушы", "Санат", "Орташа балл", "«3» саны", "«2» саны"]]}
    return res


# ---------------- 4) Report constructor: үлгерім ----------------
def parse_report(raw):
    df = _header_df(raw, any_cell=r"параллель")
    c = lambda *p: find_col(df.columns, *p)
    out = pd.DataFrame({
        "Параллель": df[c(r"параллель")].map(txt),
        "Пән": df[c(r"на казахском|қазақша")].map(txt) if c(r"на казахском|қазақша") else df[c(r"предмет|пән")].map(txt),
        "Оқушы саны": df[c(r"всего учащихся|барлық оқушы")].map(num),
        "Үздік": df[c(r"^отличники|үздік")].map(num),
        "Екпінді": df[c(r"^хорошисты|екпінді")].map(num),
        "«3»": df[c(r"удовлетвор|қанағат")].map(num),
        "Үлгермейтін": df[c(r"неуспевающ|үлгермей")].map(num),
        "Сапа %": df[c(r"качество|сапа")].map(num),
        "Үлгерім %": df[c(r"успеваемость|үлгерім")].map(num),
    })
    out = out[(out["Пән"] != "") & (~out["Пән"].str.upper().isin(["ИТОГО", "БАРЛЫҒЫ"]))]
    out = out[out["Сапа %"].notna() & (out["Үздік"].fillna(0) + out["Екпінді"].fillna(0) + out["«3»"].fillna(0) > 0)]
    out["Параллель"] = out["Параллель"].replace({"ВСЕ КЛАССЫ": "Барлығы", "БАРЛЫҚ СЫНЫПТАР": "Барлығы"})
    tables = {"Пәндер бойынша": out.sort_values("Сапа %").reset_index(drop=True)}
    if out["Параллель"].nunique() > 1:
        tables["Сапа матрицасы (параллель × пән)"] = out.pivot_table(index="Пән", columns="Параллель",
                                                                       values="Сапа %").round(1).reset_index()
    return {"meta": {}, "tables": tables}


# ---------------- 5) БЖБ / ТЖБ (СОР / СОЧ) ----------------
def parse_sor(raw):
    lines = [txt(raw.iloc[i, 0]) for i in range(len(raw))]
    head = " ".join(lines[:6])
    m = re.search(r"по предмету\s+(.+?)(?:$|\s{2,})", lines[1] if len(lines) > 1 else "") or \
        re.search(r"([^\s]+(?:\s[^\s]+)?)\s+пәні", head)
    subject = (m.group(1).strip() if m else "Пән")
    g = lambda pat: next((re.sub(pat, "", l, flags=re.I).strip() for l in lines[:8] if re.match(pat, l, re.I)), "")
    klass = parse_class(g(r"^(класс|сынып)\s*:"))[2]
    teacher = g(r"^(педагог|мұғалім)\s*:")
    period = ""
    pm = re.search(r"за\s+(\d\s*четверт\w*|\d\s*полугод\w*)|(\d\s*тоқсан)", head, re.I)
    if pm:
        period = pm.group(0)
    rows, names = [], {}
    in_names = False
    for i in range(len(raw)):
        r = [raw.iloc[i, j] if j < raw.shape[1] else None for j in range(8)]
        first = txt(r[0])
        if re.match(r"^1\.", first):
            in_names = True
        if not re.match(r"^(сор|соч|бжб|тжб)", first.lower()):
            continue
        if not in_names and num(r[1]) is not None:
            rows.append({"Жұмыс": first, "Оқушы": num(r[1]), "Макс. балл": num(r[2]),
                         "Төмен (0-39%)": num(r[3]) or 0, "Орта (40-84%)": num(r[4]) or 0,
                         "Жоғары (85-100%)": num(r[5]) or 0, "Сапа %": num(r[6]), "Үлгерім %": num(r[7])})
        elif in_names:
            names[first] = {"low": txt(r[1]), "mid": txt(r[3]), "high": txt(r[6])}
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Тип"] = df["Жұмыс"].str.upper().str.extract(r"^(СОР|СОЧ|БЖБ|ТЖБ)")[0].replace({"БЖБ": "СОР", "ТЖБ": "СОЧ"})
        df["Пән"], df["Сынып"], df["Мұғалім"] = subject, klass, teacher
        df["Параллель"] = parse_class(klass)[0]
        df["Төмен деңгейдегі оқушылар"] = df["Жұмыс"].map(lambda w: names.get(w, {}).get("low", ""))
    return {"meta": {"Пән": subject, "Сынып": klass, "Педагог": teacher, "Кезең": period},
            "tables": {"Жұмыстар": df}}


def agg_sor(df: pd.DataFrame) -> dict:
    def grp(by):
        g = df.groupby(by).agg(**{"Жұмыс саны": ("Жұмыс", "size"), "Төмен": ("Төмен (0-39%)", "sum"),
                                  "Орта": ("Орта (40-84%)", "sum"), "Жоғары": ("Жоғары (85-100%)", "sum"),
                                  "Орташа сапа %": ("Сапа %", "mean"), "Орташа үлгерім %": ("Үлгерім %", "mean")})
        tot = g["Төмен"] + g["Орта"] + g["Жоғары"]
        g["Жоғары деңгей %"] = (g["Жоғары"] / tot * 100).round(1)
        return g.round(1).reset_index()
    return {"Барлық жұмыстар": df, "Пәндер бойынша": grp("Пән"), "Сыныптар бойынша": grp("Сынып"),
            "Параллельдер бойынша": grp("Параллель"), "Пән × сынып": grp(["Пән", "Сынып"]),
            "Мұғалімдер бойынша": grp("Мұғалім"), "СОР / СОЧ салыстыру": grp(["Пән", "Тип"])}


# ---------------- 6) Сабаққа қатысу ----------------
def parse_attend(raw):
    df = _header_df(raw, any_cell=r"параллель")
    c = lambda *p: find_col(df.columns, *p)
    out = pd.DataFrame({
        "Параллель": df[c(r"параллель")].map(num),
        "Әрпі": df[c(r"әрпі|буква|литер")].map(txt) if c(r"әрпі|буква|литер") else "",
        "Пән": df[c(r"қазақша атауы|на казахском")].map(txt) if c(r"қазақша атауы|на казахском")
        else df[c(r"пән|предмет")].map(txt),
        "Сабақ саны": df[c(r"[cс]абақ саны|всего урок")].map(num),
        "Себеппен": df[c(r"^себеппен|уважит")].map(num),
        "Ауруы": df[c(r"ауру|болезн")].map(num),
        "Себепсіз": df[c(r"себепсіз|без уваж")].map(num),
        "Барлық қалу": df[c(r"барлық сабақтан қалу|всего пропущ")].map(num),
    })
    out = out[out["Параллель"].notna() & (out["Сабақ саны"].fillna(0) > 0)].copy()
    out["Параллель"] = out["Параллель"].astype(int)
    out["Сынып"] = (out["Параллель"].astype(str) + " " + out["Әрпі"].fillna("")).str.strip()
    out["Қатысу %"] = ((1 - out["Барлық қалу"] / out["Сабақ саны"]) * 100).round(2)
    return {"meta": {}, "tables": {"Деректер": out.reset_index(drop=True)}}


def agg_attend(df: pd.DataFrame) -> dict:
    def grp(by):
        g = df.groupby(by)[["Сабақ саны", "Себеппен", "Ауруы", "Себепсіз", "Барлық қалу"]].sum()
        g["Қатысу %"] = ((1 - g["Барлық қалу"] / g["Сабақ саны"]) * 100).round(2)
        den = g["Барлық қалу"].where(g["Барлық қалу"] > 0)
        g["Ауру үлесі %"] = (g["Ауруы"] / den * 100).round(1)
        return g.reset_index().sort_values("Қатысу %")
    res = {"Параллельдер бойынша": grp("Параллель"), "Пәндер бойынша": grp("Пән"),
           "Параллель × пән": grp(["Параллель", "Пән"])}
    if df["Әрпі"].fillna("").astype(str).str.len().gt(0).any():
        res["Сыныптар бойынша"] = grp("Сынып")
    return res


# ---------------- Әлсіз жақтарды табу ----------------
def _w(level, area, obj, indicator, value, norm):
    return {"Деңгей": level, "Бағыт": area, "Нысан": obj, "Көрсеткіш": indicator, "Мәні": value, "Норма": norm}


def find_weak(kind: str, tables: dict, th: dict = None) -> list[dict]:
    th = {**THRESHOLDS, **(th or {})}
    W = []

    def fmt(v):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)

    def check(df, obj_col, area, qcol="Сапа %", scol="Үлгерім %", acol="Орташа балл"):
        if df is None or df.empty:
            return
        for _, r in df.iterrows():
            obj = " / ".join(fmt(r[c]) for c in ([obj_col] if isinstance(obj_col, str) else obj_col))
            q = r.get(qcol)
            if q is not None and pd.notna(q) and q < th["quality"]:
                W.append(_w("🔴" if q < th["quality"] - 15 else "🟠", area, obj, "Білім сапасы %", round(q, 1),
                            f"≥ {th['quality']}"))
            s = r.get(scol)
            if s is not None and pd.notna(s) and s < th["success"]:
                W.append(_w("🔴", area, obj, "Үлгерім %", round(s, 1), f"{th['success']}"))
            a = r.get(acol)
            if a is not None and pd.notna(a) and a < th["avg"]:
                W.append(_w("🟠", area, obj, "Орташа балл", round(a, 2), f"≥ {th['avg']}"))

    if kind == "school":
        check(tables.get("Параллельдер бойынша"), "Параллель", "Параллель")
    elif kind == "subject":
        check(tables.get("Пән × сынып"), ["Пән", "Сынып"], "Пән × сынып")
        check(tables.get("Параллель × пән"), ["Параллель", "Пән"], "Параллель × пән")
    elif kind == "klass":
        check(tables.get("Сыныптар бойынша"), "Сынып", "Сынып")
        check(tables.get("Пәндер бойынша (сыныптарда)"), ["Сынып", "Пән"], "Сынып × пән")
        risk = tables.get("Резерв және тәуекел оқушылар")
        if risk is not None and not risk.empty:
            for cl, g in risk.groupby("Сынып"):
                n3 = (g["Санат"].str.contains("«3»")).sum()
                n4 = (g["Санат"].str.contains("«4»")).sum()
                if n3:
                    W.append(_w("🟠", "Резерв", cl, "Бір «3»-пен оқушылар", int(n3), "0"))
                if n4:
                    W.append(_w("🟢", "Резерв", cl, "Бір «4»-пен оқушылар (үздік резерві)", int(n4), "—"))
    elif kind == "report":
        check(tables.get("Пәндер бойынша"), ["Параллель", "Пән"], "Пән")
    elif kind == "sor":
        df = tables.get("Барлық жұмыстар")
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                obj = f"{r['Пән']} / {r['Сынып']} / {r['Жұмыс']}"
                if (r["Төмен (0-39%)"] or 0) > th["sor_low"]:
                    W.append(_w("🔴", "БЖБ/ТЖБ", obj, "Төмен деңгей (0-39%) оқушы саны", int(r["Төмен (0-39%)"]), "0"))
                if r["Сапа %"] is not None and pd.notna(r["Сапа %"]) and r["Сапа %"] < th["sor_quality"]:
                    W.append(_w("🟠", "БЖБ/ТЖБ", obj, "Сапа %", r["Сапа %"], f"≥ {th['sor_quality']}"))
            cmp_ = tables.get("СОР / СОЧ салыстыру")
            if cmp_ is not None and not cmp_.empty:
                p = cmp_.pivot_table(index="Пән", columns="Тип", values="Орташа сапа %")
                if {"СОР", "СОЧ"} <= set(p.columns):
                    for subj, r in p.iterrows():
                        if pd.notna(r["СОР"]) and pd.notna(r["СОЧ"]) and r["СОР"] - r["СОЧ"] >= 15:
                            W.append(_w("🟠", "Объективтілік", subj, "СОР мен СОЧ сапасының айырмасы",
                                        round(r["СОР"] - r["СОЧ"], 1), "< 15"))
    elif kind == "attend":
        cols = {"Параллельдер бойынша": ["Параллель"], "Сыныптар бойынша": ["Сынып"], "Пәндер бойынша": ["Пән"],
                "Параллель × пән": ["Параллель", "Пән"]}
        for name, oc in cols.items():
            df = tables.get(name)
            if df is None:
                continue
            for _, r in df.iterrows():
                obj = " / ".join(fmt(r[c]) for c in oc)
                if r["Қатысу %"] < th["attendance"]:
                    W.append(_w("🔴" if r["Қатысу %"] < th["attendance"] - 3 else "🟠", "Қатысу", obj,
                                "Сабаққа қатысу %", r["Қатысу %"], f"≥ {th['attendance']}"))
                if r["Себепсіз"] > th["unexcused"] and len(oc) == 1:
                    W.append(_w("🔴", "Қатысу", obj, "Себепсіз қалған сабақ", int(r["Себепсіз"]), "0"))
    return W


# ---------------- Ереже негізіндегі ұсыныс және жоспар (ЖИ жоқ кезде) ----------------
PLAN_TEMPLATES = {
    "Білім сапасы %": ("Пән мұғалімдерімен ӘБ отырысында нәтижені талдау; «бір 4-пен» оқушылармен жеке жұмыс; "
                       "саралап оқыту тапсырмаларын ҚМЖ-ға енгізу; қосымша/консультация сабақтары",
                       "Оқу ісі орынбасары, ӘБ жетекшісі, пән мұғалімі", "Келесі тоқсан ішінде"),
    "Үлгерім %": ("Үлгермейтін оқушыларға жеке түзету жоспары; ата-аналармен кездесу; апта сайын мониторинг",
                  "Пән мұғалімі, сынып жетекші, оқу ісі орынбасары", "2 апта ішінде"),
    "Орташа балл": ("Пән бойынша қиын тақырыптарды қайталау; формативті бағалауды күшейту",
                    "Пән мұғалімі", "Келесі тоқсан"),
    "Бір «3»-пен оқушылар": ("Тізімді пән мұғалімдеріне беру; жеке консультация кестесі; тоқсан соңына дейін бақылау",
                             "Сынып жетекші, пән мұғалімі", "Тоқсан аяғына дейін"),
    "Бір «4»-пен оқушылар (үздік резерві)": ("Үздік резервімен жеке жұмыс, олимпиадалық тапсырмалар",
                                             "Пән мұғалімі", "Тоқсан аяғына дейін"),
    "Төмен деңгей (0-39%) оқушы саны": ("Қиындық тудырған оқу мақсаттарын анықтау; түзету жұмысы; қайта бағалау; "
                                         "тапсырма спецификациясын тексеру", "Пән мұғалімі, ӘБ жетекшісі", "1 апта"),
    "Сапа %": ("БЖБ/ТЖБ нәтижесін ӘБ-де талдау; ұқсас тапсырмалармен жаттығу; дескрипторларды оқушыларға түсіндіру",
               "Пән мұғалімі", "Келесі БЖБ-ға дейін"),
    "СОР мен СОЧ сапасының айырмасы": ("Бағалау объективтілігін тексеру: модерация, ӘБ-де өзара тексеру",
                                       "Оқу ісі орынбасары, ӘБ жетекшісі", "Тоқсан ішінде"),
    "Сабаққа қатысу %": ("Сынып жетекші мен әлеуметтік педагогтің бірлескен мониторингі; ата-анамен байланыс; "
                         "ауру себептерін медбикемен талдау", "Сынып жетекші, әлеуметтік педагог", "Апта сайын"),
    "Себепсіз қалған сабақ": ("Себепсіз қалған әр жағдайды тексеру, ата-ананы шақыру, профилактикалық кеңес",
                              "Әлеуметтік педагог, тәрбие ісі орынбасары", "3 күн ішінде"),
}


def rule_plan(weak: list[dict]) -> pd.DataFrame:
    rows, seen = [], set()
    for w in sorted(weak, key=lambda x: {"🔴": 0, "🟠": 1, "🟢": 2}.get(x["Деңгей"], 3)):
        t = PLAN_TEMPLATES.get(w["Көрсеткіш"])
        if not t:
            continue
        key = (w["Көрсеткіш"], w["Нысан"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"Басымдық": w["Деңгей"], "Нысан": w["Нысан"], "Мәселе": f"{w['Көрсеткіш']}: {w['Мәні']} "
                     f"(норма {w['Норма']})", "Іс-шара": t[0], "Жауапты": t[1], "Мерзімі": t[2],
                     "Күтілетін нәтиже": f"{w['Көрсеткіш']} нормаға жетеді ({w['Норма']})"})
    return pd.DataFrame(rows)
