"""Пікірлерді талдау, ұсыныстар, SWOT және МДЖ құрастыру.

Ереже негізіндегі талдау (қазақ + орыс сөздіктері) интернетсіз жұмыс істейді.
ANTHROPIC_API_KEY секреті болса, ЖИ арқылы кеңейтілген ұсыныстар да алуға болады.
"""
import re
from collections import Counter

import pandas as pd

from core.config import get_secret

POSITIVE = ["жақсы", "керемет", "рахмет", "алғыс", "тамаша", "ұнады", "ұнайды", "қолдау", "пайдалы",
            "нәтижелі", "ыңғайлы", "сапалы", "жарайсыңдар", "хорош", "отлично", "спасибо", "благодар",
            "нравит", "удобн", "полезн", "поддерж", "молодц", "прекрасн", "супер", "качествен"]
NEGATIVE = ["жаман", "нашар", "қиын", "шаршадым", "шаршау", "көп", "жетіспейді", "жоқ", "бұзылған",
            "уақыт жоқ", "кешік", "әділетсіз", "мәселе", "проблема", "плохо", "трудно", "устал", "много",
            "не хватает", "нет ", "сломан", "несправедлив", "опозда", "перегруз", "жалоб", "неудоб",
            "долго", "сложно", "бюрократ", "нехватк", "мешает", "ұзақ", "кедергі", "шу", "суық", "холодно"]

TOPICS = {
    "Жүктеме / нагрузка": ["жүктеме", "сағат", "нагрузк", "часов", "перегруз", "шаршау", "шаршадым", "устал", "демалыс"],
    "Құжаттар / бюрократия": ["құжат", "қағаз", "есеп", "отчет", "отчёт", "документ", "бумаг", "бюрократ", "журнал"],
    "Жалақы, ынталандыру": ["жалақы", "айлық", "сыйақы", "үстеме", "зарплат", "преми", "доплат", "стимул"],
    "Материалдық база, жабдық": ["компьютер", "проектор", "принтер", "интернет", "жабдық", "кабинет", "жөндеу",
                                "оборудован", "ремонт", "техник", "мебел", "парта", "wi-fi", "вайфай"],
    "Оқушылар тәртібі": ["тәртіп", "бұзақы", "дисциплин", "поведен", "телефон", "сабақ үзу", "кешігу"],
    "Әдістемелік қолдау, курстар": ["әдістеме", "семинар", "курс", "тренинг", "методич", "обучени", "тәлімгер",
                                    "наставни", "аттестац"],
    "Қарым-қатынас, ұжым": ["ұжым", "қарым-қатынас", "әкімшілік", "коллектив", "отношени", "администрац",
                            "уважени", "құрмет", "конфликт", "жанжал"],
    "Цифрландыру": ["kundelik", "күнделік", "bilimal", "электрон", "цифр", "платформ", "онлайн", "жүйе"],
    "Асхана, тамақтану": ["асхана", "тамақ", "столов", "питани", "буфет"],
    "Қауіпсіздік, денсаулық": ["қауіпсіз", "күзет", "денсаулық", "медбике", "безопасн", "охран", "здоров", "суық",
                               "холод", "жылу", "отоплен"],
    "Ата-аналармен жұмыс": ["ата-ана", "ата ана", "родител"],
    "Дарынды балалар, олимпиада": ["олимпиада", "дарын", "ғылыми жоба", "одарен", "конкурс", "жарыс"],
}

RECOMMENDATIONS = {
    "Жүктеме / нагрузка": "Тарификацияны қайта қарау, жүктемені тең бөлу; бір күнге 6+ сабақты азайту; "
                          "кезекшілік пен қосымша тапсырмаларды кесте бойынша ротациялау.",
    "Құжаттар / бюрократия": "Міндетті құжаттар тізімін (МП РК бұйрығы) ғана талап ету; қайталанатын есептерді "
                             "платформадағы автоматты есептермен алмастыру; бір есепті бір рет жинау.",
    "Жалақы, ынталандыру": "Ынталандыру ережесін ашық жариялау; үстемеақы критерийлерін түсіндіру; "
                           "жетістіктер үшін бонус/алғыс хат жүйесін енгізу.",
    "Материалдық база, жабдық": "Завхоз пен IT орынбасарына өтінімдер тізімін беру; ақаулы жабдықты 1 апта ішінде "
                                "жөндеу кестесін құру; бюджетке сатып алу жоспарын енгізу.",
    "Оқушылар тәртібі": "Тәрбие ісі орынбасары + әлеуметтік педагог + психолог бірлескен профилактика жоспары; "
                        "сынып жетекшілермен телефон ережесін бекіту; ата-аналар жиналысы.",
    "Әдістемелік қолдау, курстар": "Әдістемелік кабинет арқылы ішкі семинарлар, Lesson Study, тәлімгерлік "
                                   "жұптарын кеңейту; курс кестесін алдын ала жариялау.",
    "Қарым-қатынас, ұжым": "Ашық есік күндері, жеке кездесулер; психологтың ұжымдық тренингі; "
                           "кері байланыс нәтижесін ұжымға жариялау («сіз айттыңыз — біз жасадық»).",
    "Цифрландыру": "Kundelik/Bilimal бойынша қысқа нұсқаулықтар, IT-кеңес сағаты; интернет пен техниканы тексеру.",
    "Асхана, тамақтану": "Асхана өтінімдерін бақылау, мәзірді ата-аналар комиссиясымен тексеру.",
    "Қауіпсіздік, денсаулық": "Жылу/күзет/медициналық қызмет бойынша завхозбен бірге тексеру актісі; жедел шара.",
    "Ата-аналармен жұмыс": "Ата-аналармен байланыс регламентін бекіту, сынып жетекшілерге қолдау.",
    "Дарынды балалар, олимпиада": "Олимпиадаға дайындық кестесі, жетекшілерге сағат/сыйақы, жетістіктерді рейтингке қосу.",
}


def sentiment(text: str) -> float:
    t = " " + (text or "").lower() + " "
    pos = sum(t.count(w) for w in POSITIVE)
    neg = sum(t.count(w) for w in NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 2)


def topics(text: str) -> list[str]:
    t = (text or "").lower()
    found = [name for name, kws in TOPICS.items() if any(k in t for k in kws)]
    return found or ["Басқа"]


def sentiment_label(s: float) -> str:
    if s > 0.2:
        return "🙂 Оң"
    if s < -0.2:
        return "🙁 Теріс"
    return "😐 Бейтарап"


STOP = set("және мен бен пен да де та те бір бұл сол үшін деп мен біз сіз олар осы ол ма ме ба бе па пе "
           "и в во на не что как это для по с со к у о от из за а но или же бы ли мы вы они".split())


def top_words(texts: list[str], n: int = 20) -> list[tuple[str, int]]:
    words = []
    for t in texts:
        words += [w for w in re.findall(r"[a-zа-яәіңғүұқөһё\-]{4,}", (t or "").lower()) if w not in STOP]
    return Counter(words).most_common(n)


def analyze_feedback(df: pd.DataFrame) -> dict:
    """df: text, sentiment, topics (', '), target_role бағандары."""
    if df.empty:
        return {"total": 0}
    rows = []
    for _, r in df.iterrows():
        for tp in str(r.get("topics") or "Басқа").split("; "):
            rows.append({"topic": tp, "sentiment": float(r.get("sentiment") or 0)})
    t = pd.DataFrame(rows)
    stat = t.groupby("topic").agg(саны=("sentiment", "size"), орташа_көңіл_күй=("sentiment", "mean")).reset_index()
    # Басымдық: көп айтылған және теріс тақырыптар жоғары
    stat["басымдық"] = (stat["саны"] * (1 - stat["орташа_көңіл_күй"])).round(2)
    stat = stat.sort_values("басымдық", ascending=False)
    recs = []
    for _, r in stat.iterrows():
        if r["topic"] in RECOMMENDATIONS and (r["орташа_көңіл_күй"] < 0.2 or r["саны"] >= 3):
            level = "🔴 Жоғары" if r["басымдық"] >= 3 else ("🟠 Орташа" if r["басымдық"] >= 1.5 else "🟢 Төмен")
            recs.append({"Басымдық": level, "Тақырып": r["topic"], "Пікір саны": int(r["саны"]),
                         "Ұсыныс": RECOMMENDATIONS[r["topic"]]})
    pos = (df["sentiment"].astype(float) > 0.2).sum()
    neg = (df["sentiment"].astype(float) < -0.2).sum()
    return {"total": len(df), "positive": int(pos), "negative": int(neg),
            "neutral": int(len(df) - pos - neg), "mean": round(float(df["sentiment"].astype(float).mean()), 2),
            "topics": stat, "recommendations": pd.DataFrame(recs),
            "words": top_words(df["text"].tolist())}


def llm_recommendations(texts: list[str], context: str = "мектеп әкімшілігі") -> str | None:
    """Қосымша: ANTHROPIC_API_KEY болса ЖИ ұсыныстары."""
    key = get_secret("ANTHROPIC_API_KEY")
    if not key:
        return None
    import requests
    joined = "\n".join(f"- {t}" for t in texts[:150])
    prompt = (f"Сен Қазақстандағы дарынды балаларға арналған мектептің басқару кеңесшісісің. Төменде мұғалімдердің "
              f"{context} үшін жазған ұсыныстары мен пікірлері берілген. Қазақ тілінде: 1) негізгі 5 мәселе, "
              f"2) әрқайсысына нақты шара, жауапты (рөл) және мерзім, 3) жылдам жеңістер (1 апта). "
              f"Құпиялылықты сақта, адам аттарын атама.\n\nПікірлер:\n{joined}")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": get_secret("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    except Exception as e:
        return f"ЖИ ұсынысын алу мүмкін болмады: {e}"


# ---------------- SWOT (talismasters сауалнамасынан) ----------------
def swot_from_survey(df: pd.DataFrame, scale_max: float | None = None) -> dict:
    """Сауалнама CSV: сандық бағандар (балл) → жоғары = күшті, төмен = әлсіз.
    Мәтіндік бағандардағы теріс/оң сөздер → мүмкіндік/қауіп ұсыныстары."""
    res = {"S": [], "W": [], "O": [], "T": []}
    num = df.select_dtypes("number")
    if not num.empty:
        means = num.mean().sort_values(ascending=False)
        mx = scale_max or float(num.max().max() or 1)
        for col, v in means.items():
            pct = v / mx * 100 if mx else 0
            if pct >= 70:
                res["S"].append(f"{col}: орташа {v:.2f} ({pct:.0f}%)")
            elif pct < 55:
                res["W"].append(f"{col}: орташа {v:.2f} ({pct:.0f}%)")
    texts = []
    for c in df.select_dtypes(exclude="number").columns:
        texts += [str(x) for x in df[c].dropna().tolist() if len(str(x)) > 15]
    tp = Counter()
    for t in texts:
        s = sentiment(t)
        for name in topics(t):
            if name == "Басқа":
                continue
            tp[(name, "neg" if s < 0 else "pos")] += 1
    for (name, kind), cnt in tp.most_common(12):
        if kind == "pos":
            res["O"].append(f"{name} — {cnt} оң пікір (дамыту мүмкіндігі)")
        else:
            res["T"].append(f"{name} — {cnt} алаңдаушылық (тәуекел)")
    return res


MDJ_SECTIONS = [
    "1. Білім беру сапасы (оқу ісі)",
    "2. Тәрбие жұмысы және «Адал азамат»",
    "3. Дарынды балалармен жұмыс",
    "4. Кадрлық әлеует, аттестация, инновация",
    "5. Цифрландыру және ақпараттық орта",
    "6. Әдістемелік жұмыс",
    "7. Әлеуметтік-психологиялық қолдау, инклюзия",
    "8. Материалдық-техникалық база, қауіпсіздік, энергия үнемдеу",
    "9. Денсаулық, дене шынықтыру, АӘТД",
    "10. Ата-аналармен және серіктестермен жұмыс",
]


def build_mdj(school: str, period: str, mission: str, swot: dict, proposals: pd.DataFrame) -> str:
    """МДЖ HTML мәтінін құрастырады."""
    from core.export import esc
    h = [f"<h1>{esc(school)}<br>МЕКТЕПТІҢ ДАМУ ЖОСПАРЫ<br>{esc(period)}</h1>"]
    h.append(f"<h2>Миссия және пайымдау</h2><p>{esc(mission)}</p>")
    h.append("<h2>SWOT-талдау</h2><table><tr><th>Күшті жақтары (S)</th><th>Әлсіз жақтары (W)</th></tr>")
    li = lambda xs: "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in xs) + "</ul>" if xs else "—"
    h.append(f"<tr><td>{li(swot.get('S', []))}</td><td>{li(swot.get('W', []))}</td></tr>")
    h.append("<tr><th>Мүмкіндіктер (O)</th><th>Қауіптер (T)</th></tr>")
    h.append(f"<tr><td>{li(swot.get('O', []))}</td><td>{li(swot.get('T', []))}</td></tr></table>")
    h.append("<h2>Стратегиялық мақсаттар</h2><ul>")
    for w in swot.get("W", [])[:5]:
        h.append(f"<li>Әлсіз аспектіні жақсарту: {esc(w)}</li>")
    for s in swot.get("S", [])[:3]:
        h.append(f"<li>Күшті жақты сақтау және тарату: {esc(s)}</li>")
    h.append("</ul>")
    h.append("<h2>Бөлімдер бойынша іс-шаралар жоспары</h2>")
    for sec in MDJ_SECTIONS:
        part = proposals[proposals["section"] == sec] if not proposals.empty else pd.DataFrame()
        h.append(f"<h3>{esc(sec)}</h3>")
        if part.empty:
            h.append("<p><i>Ұсыныстар енгізілмеген</i></p>")
            continue
        h.append("<table><tr><th>№</th><th>Тақырып / іс-шара</th><th>Ұсыныс, күтілетін нәтиже</th>"
                 "<th>Индикатор</th><th>Мерзімі</th><th>Жауапты</th></tr>")
        for i, (_, r) in enumerate(part.iterrows(), 1):
            h.append(f"<tr><td>{i}</td><td>{esc(r.get('topic'))}</td><td>{esc(r.get('proposal'))}</td>"
                     f"<td>{esc(r.get('indicator'))}</td><td>{esc(r.get('deadline'))}</td>"
                     f"<td>{esc(r.get('responsible'))}</td></tr>")
        h.append("</table>")
    h.append("<h2>Мониторинг</h2><p>Жоспардың орындалуы тоқсан сайын әкімшілік кеңесінде қаралады; "
             "индикаторлар платформа есептері арқылы бақыланады; жыл соңында қорытынды талдау жасалады.</p>")
    return "\n".join(h)
