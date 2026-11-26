"""ЖИ қосылымы: Anthropic Claude (ANTHROPIC_API_KEY) немесе Google Gemini (GEMINI_API_KEY).
Кілт жоқ болса — None қайтарады, бағдарлама ереже негізіндегі ұсыныстарды қолданады.

Құпиялылық: ЖИ-ге тек жиынтық сандар жіберіледі, оқушылардың аты-жөні жіберілмейді.
"""
import json
import re

import pandas as pd

from core.config import get_secret


def provider() -> str | None:
    if get_secret("ANTHROPIC_API_KEY"):
        return "Claude"
    if get_secret("GEMINI_API_KEY"):
        return "Gemini"
    return None


def ask(prompt: str, max_tokens: int = 4000) -> str | None:
    import requests
    if get_secret("ANTHROPIC_API_KEY"):
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=180, headers={
            "x-api-key": get_secret("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
            "content-type": "application/json"},
            json={"model": get_secret("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    if get_secret("GEMINI_API_KEY"):
        model = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          params={"key": get_secret("GEMINI_API_KEY")}, timeout=180,
                          json={"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"maxOutputTokens": max_tokens}})
        r.raise_for_status()
        c = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in c)
    return None


def _compact(df: pd.DataFrame, max_rows: int = 60) -> str:
    drop = [c for c in df.columns if re.search(r"оқушы$|оқушылар|ученик|фио|^оқушы", str(c).lower())
            and df[c].dtype == object]
    return df.drop(columns=drop).head(max_rows).to_csv(index=False)


def analysis_prompt(title: str, period: str, tables: dict, weak: list[dict], context: str = "") -> str:
    parts = [f"### {name}\n{_compact(df)}" for name, df in tables.items() if isinstance(df, pd.DataFrame)
             and not df.empty][:8]
    weak_txt = "\n".join(f"- {w['Деңгей']} {w['Нысан']}: {w['Көрсеткіш']} = {w['Мәні']} (норма {w['Норма']})"
                         for w in weak[:60]) or "- автоматты түрде анықталған олқылық жоқ"
    return f"""Сен Қазақстандағы дарынды балаларға арналған мамандандырылған мектеп-лицейдің оқу ісі жөніндегі
тәжірибелі орынбасарысың және білім сапасы талдаушысысың. Төменде «{title}» бойынша деректер ({period}).
{context}

ДЕРЕКТЕР (CSV):
{chr(10).join(parts)}

АВТОМАТТЫ АНЫҚТАЛҒАН ОЛҚЫЛЫҚТАР:
{weak_txt}

Тапсырма (қазақ тілінде, нақты сандармен, сыныптар, параллельдер және пәндер бойынша):
1) Қысқа қорытынды (күшті жақтар және динамика).
2) Әлсіз жақтар мен олқылықтар, ықтимал себептері.
3) Әр олқылыққа нақты ұсыныс (кімге, не істеу керек).
4) Олқылықтарды жою жоспары.
Дарынды балалар мектебі екенін ескер: сапа деңгейі жоғары болуы керек, үздік резервімен жұмыс маңызды.

ЖАУАПТЫ ТЕК мына JSON форматында бер (басқа мәтінсіз):
{{"summary": "...", "strengths": ["..."], "weaknesses": ["..."],
 "recommendations": [{{"target": "кімге", "text": "ұсыныс"}}],
 "plan": [{{"Мәселе": "...", "Іс-шара": "...", "Жауапты": "...", "Мерзімі": "...", "Күтілетін нәтиже": "...",
           "Индикатор": "..."}}]}}"""


def parse_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def run_analysis(title, period, tables, weak, context="") -> dict:
    """{'ok': bool, 'provider', 'data': dict|None, 'raw': str, 'error': str}"""
    p = provider()
    if not p:
        return {"ok": False, "provider": None, "data": None, "raw": "",
                "error": "ЖИ кілті баптаулмаған (Secrets: ANTHROPIC_API_KEY немесе GEMINI_API_KEY)"}
    try:
        raw = ask(analysis_prompt(title, period, tables, weak, context))
        data = parse_json(raw)
        return {"ok": data is not None, "provider": p, "data": data, "raw": raw or "",
                "error": "" if data else "ЖИ жауабы JSON форматында емес"}
    except Exception as e:
        return {"ok": False, "provider": p, "data": None, "raw": "", "error": str(e)}
