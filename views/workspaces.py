"""Рөлдер бойынша жұмыс орындары: функциялар тізімі + автоматтандырылған журналдар + сілтемелер."""
import pandas as pd
import streamlit as st

from core.config import LINKS, role_name
from core.ui import download_buttons, external_app, render_journal
from views import observation

LEVELS = ["Мектепішілік", "Аудандық/қалалық", "Облыстық", "Республикалық", "Халықаралық"]
PLACES = ["1 орын", "2 орын", "3 орын", "Алғыс хат / номинация", "Қатысу"]
STATUS = ["Жаңа", "Орындалуда", "Орындалды", "Тоқтатылды"]


def J(module, kind, title, fields, private=False, help=""):
    return {"module": module, "kind": kind, "title": title, "fields": fields, "private": private, "help": help}


def F(key, label, type="text", options=None, required=False, **kw):
    return {"key": key, "label": label, "type": type, "options": options, "required": required, **kw}


WORKSPACES = {
    "zavuch_uch": {
        "functions": ["Оқу жоспары, РОЖ, сабақ кестесі, ауыстырулар", "Тарификация, жүктеме",
                      "Электрондық журнал бақылауы (Kundelik/Bilimal)", "БЖБ/ТЖБ мониторингі, сапа және үлгерім",
                      "Мектепішілік бақылау (ВШК), сабаққа қатысу", "ҰБТ/МОДО/ВОУД дайындығы, қорытынды аттестация",
                      "Үлгерімі төмен оқушылармен жұмыс", "Білім бөліміне есептер"],
        "special": ["observation", "grades"],
        "journals": [
            J("uch", "vshk", "Мектепішілік бақылау жоспары", [
                F("topic", "Бақылау тақырыбы", required=True), F("type", "Түрі", "select",
                  ["Тақырыптық", "Фронталды", "Жеке", "Сынып-жалпылама", "Құжаттар тексеру"]),
                F("object", "Нысаны (сынып/мұғалім/пән)"), F("deadline", "Мерзімі", "date"),
                F("resp", "Жауапты"), F("status", "Мәртебе", "select", STATUS), F("result", "Нәтиже / анықтама", "textarea")]),
            J("uch", "replace", "Сабақ ауыстыру журналы", [
                F("date", "Күні", "date"), F("absent", "Жоқ мұғалім", required=True), F("reason", "Себебі", "select",
                  ["Ауру", "Курс", "Іссапар", "Басқа"]), F("sub", "Ауыстырушы мұғалім", required=True),
                F("class", "Сынып", "class"), F("subject", "Пән"), F("hours", "Сағат", "number", default=1)]),
            J("uch", "weak", "Үлгерімі төмен оқушылармен жұмыс", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"), F("subject", "Пән"),
                F("teacher", "Мұғалім"), F("plan", "Жеке жоспар / шара", "textarea"),
                F("status", "Нәтиже", "select", ["Жоспарланды", "Оң динамика", "Өзгеріс жоқ", "Жақсарды"])]),
        ],
    },
    "zavuch_vosp": {
        "functions": ["Тәрбие жұмысының жоспары, «Адал азамат», «Біртұтас тәрбие»", "Сынып жетекшілер жұмысы",
                      "Мектеп парламенті, өзін-өзі басқару", "Құқық бұзушылық профилактикасы",
                      "Ата-аналармен жұмыс", "Үйірмелер мен секциялар, жазғы демалыс"],
        "journals": [
            J("vosp", "events", "Тәрбие іс-шаралары", [
                F("name", "Іс-шара", required=True), F("date", "Күні", "date"),
                F("direction", "Бағыты", "select", ["Адал азамат", "Патриоттық", "Рухани-адамгершілік",
                  "Құқықтық", "Экологиялық", "Еңбек", "Денсаулық", "Мәдени", "Отбасы"]),
                F("level", "Деңгейі", "select", LEVELS), F("classes", "Сыныптар"),
                F("coverage", "Қамтылған оқушы саны", "number"), F("resp", "Жауапты"),
                F("link", "Фото/сілтеме")]),
            J("vosp", "kl", "Сынып жетекшілер есебі", [
                F("class", "Сынып", "class"), F("teacher", "Сынып жетекші", required=True),
                F("month", "Айы", "select", ["Қыркүйек", "Қазан", "Қараша", "Желтоқсан", "Қаңтар", "Ақпан",
                                             "Наурыз", "Сәуір", "Мамыр"]),
                F("hours", "Тәрбие сағаты саны", "number"), F("parents", "Ата-аналар жиналысы", "checkbox"),
                F("visits", "Үйге бару саны", "number"), F("notes", "Мәселелер / жетістіктер", "textarea")]),
            J("vosp", "clubs", "Үйірмелер мен секциялар", [
                F("name", "Үйірме", required=True), F("leader", "Жетекшісі"), F("kind", "Бағыты", "select",
                  ["Спорт", "Шығармашылық", "Ғылыми", "IT/робототехника", "Тіл", "Басқа"]),
                F("students", "Оқушы саны", "number"), F("schedule", "Кестесі")]),
        ],
    },
    "zavuch_it": {
        "functions": ["Цифрлық инфрақұрылым, интернет", "Техника есебі, жөндеу/есептен шығару",
                      "Мектеп сайты, әлеуметтік желі", "Kundelik/Bilimal әкімшілігі",
                      "Киберқауіпсіздік", "Педагогтердің цифрлық сауаттылығы"],
        "journals": [
            J("it", "inventory", "Техника тізімі", [
                F("name", "Құрылғы", required=True), F("inv", "Инв. нөмірі"), F("room", "Кабинет"),
                F("type", "Түрі", "select", ["Компьютер", "Ноутбук", "Проектор", "Интерактивті тақта",
                                             "Принтер/МФУ", "Желілік құрылғы", "Басқа"]),
                F("state", "Жағдайы", "select", ["Жұмыс істейді", "Жөндеу қажет", "Есептен шығару"]),
                F("year", "Жылы", "number", default=2024)]),
            J("it", "help", "IT-көмек өтінімдері", [
                F("room", "Кабинет", required=True), F("problem", "Мәселе", "textarea", required=True),
                F("urgency", "Шұғылдығы", "select", ["Қалыпты", "Шұғыл"]),
                F("status", "Мәртебе", "select", STATUS)], help="Кез келген мұғалім өтінім қалдыра алады."),
            J("it", "posts", "Сайт / әлеуметтік желі жарияланымдары", [
                F("title", "Тақырыбы", required=True), F("date", "Күні", "date"),
                F("platform", "Платформа", "select", ["Сайт", "Instagram", "Facebook", "Telegram", "TikTok"]),
                F("link", "Сілтеме")]),
        ],
    },
    "zavuch_innov": {
        "functions": ["Кадрлық құрам, педагогтер базасы", "Аттестация (модератор/сарапшы/зерттеуші/шебер)",
                      "Біліктілікті арттыру курстары", "Жас мамандар, тәлімгерлік, өзара сабаққа қатысу",
                      "Lesson Study, зерттеу, инновациялық жобалар", "Тәжірибені жинақтау, кәсіби байқаулар"],
        "special": ["young_journal"],
        "journals": [
            J("innov", "staff", "Педагогтер базасы және аттестация", [
                F("name", "ТАӘ", required=True), F("subject", "Пәні"), F("category", "Санаты", "select",
                  ["педагог", "педагог-модератор", "педагог-сарапшы", "педагог-зерттеуші", "педагог-шебер",
                   "санатсыз"]), F("exp", "Педагогикалық өтілі (жыл)", "number"),
                F("att_year", "Келесі аттестация жылы", "number", default=2027),
                F("education", "Білімі")]),
            J("innov", "courses", "Курстар", [
                F("name", "Педагог", required=True), F("course", "Курс атауы", required=True),
                F("org", "Ұйым"), F("hours", "Сағат", "number", default=72), F("date", "Аяқталған күні", "date"),
                F("cert", "Сертификат сілтемесі")]),
            J("innov", "mentor", "Тәлімгерлік жұптары", [
                F("mentor", "Тәлімгер", required=True), F("young", "Жас маман", required=True),
                F("plan", "Жоспар", "textarea"), F("result", "Нәтиже", "textarea")]),
            J("innov", "projects", "Инновациялық жобалар, Lesson Study", [
                F("name", "Жоба", required=True), F("team", "Топ"), F("status", "Кезеңі", "select", STATUS),
                F("result", "Нәтижесі", "textarea")]),
        ],
    },
    "zavuch_gifted": {
        "functions": ["Дарындылықты анықтау, дарынды балалар банкі", "Олимпиадалар (мектепішілік → халықаралық)",
                      "Ғылыми жобалар («Дарын», МАН, «Зерде»)", "Жеке білім беру траекториясы",
                      "Оқушылар рейтингі", "«Дарын» РҒПО-на есептер"],
        "links": [("⭐ Оқушылар рейтингі (бастапқы сайт)", LINKS["rating"])],
        "journals": [
            J("gifted", "olymp", "Олимпиада / байқау нәтижелері", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"), F("subject", "Пән / бағыт"),
                F("event", "Олимпиада / байқау", required=True), F("level", "Деңгейі", "select", LEVELS),
                F("place", "Нәтиже", "select", PLACES), F("mentor", "Жетекші мұғалім"), F("date", "Күні", "date")],
                help="Нәтижелерді «Оқушылар рейтингі» бөліміне де балл ретінде қосыңыз."),
            J("gifted", "bank", "Дарынды балалар банкі", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"),
                F("area", "Дарындылық саласы", "select", ["Математика", "Жаратылыстану", "Тілдер",
                  "Гуманитарлық", "IT", "Спорт", "Өнер", "Көшбасшылық"]), F("mentor", "Жетекші"),
                F("route", "Жеке траектория", "textarea")]),
        ],
    },
    "metodist": {
        "functions": ["Әдістемелік бірлестіктер (ӘБ)", "Педкеңес, әдістемелік кеңес хаттамалары",
                      "Ашық сабақтар, семинарлар", "Тәжірибені жинақтау", "Авторлық бағдарламалар сараптамасы",
                      "Мұғалімдерге әдістемелік көмек"],
        "journals": [
            J("met", "protocol", "Хаттамалар (ӘБ / педкеңес / әдіс кеңес)", [
                F("body", "Орган", "select", ["Педкеңес", "Әдістемелік кеңес", "ӘБ"]),
                F("num", "Хаттама №"), F("date", "Күні", "date"), F("agenda", "Күн тәртібі", "textarea", required=True),
                F("decision", "Шешім", "textarea"), F("link", "Файл сілтемесі")]),
            J("met", "open", "Ашық сабақтар / семинарлар", [
                F("teacher", "Мұғалім", required=True), F("topic", "Тақырып"), F("class", "Сынып", "class"),
                F("date", "Күні", "date"), F("level", "Деңгейі", "select", LEVELS),
                F("feedback", "Пікір", "textarea")]),
        ],
    },
    "zavhoz": {
        "functions": ["МТБ, жөндеу, инвентарь", "Санитарлық жағдай", "Өрт және антитеррор қауіпсіздігі",
                      "Коммуналдық қызметтер, энергия үнемдеу (ЭкоСвет)", "Асхана жұмысы"],
        "links": [("💡 ЭкоСвет — электр энергиясын үнемдеу", LINKS["ecosvet"]),
                  ("🍽 Асхана жұмысы", LINKS["canteen"])],
        "special": ["meters"],
        "journals": [
            J("hoz", "repair", "Жөндеу өтінімдері", [
                F("room", "Орны / кабинет", required=True), F("problem", "Ақау", "textarea", required=True),
                F("priority", "Басымдық", "select", ["Қалыпты", "Шұғыл", "Апат"]),
                F("status", "Мәртебе", "select", STATUS), F("cost", "Шығын (тг)", "number")],
                help="Мұғалімдер де өтінім қалдыра алады."),
            J("hoz", "inventory", "Инвентарь", [
                F("name", "Атауы", required=True), F("inv", "Инв. №"), F("room", "Орны"),
                F("qty", "Саны", "number", default=1), F("state", "Жағдайы", "select",
                  ["Жақсы", "Жөндеу қажет", "Есептен шығару"])]),
            J("hoz", "safety", "Қауіпсіздік тексерістері / эвакуация", [
                F("type", "Түрі", "select", ["Өрт қауіпсіздігі", "Антитеррор", "Эвакуация жаттығуы",
                                             "Санитарлық тексеру", "Электр қауіпсіздігі"]),
                F("date", "Күні", "date"), F("result", "Нәтиже / ескертулер", "textarea")]),
        ],
    },
    "soc_ped": {
        "functions": ["Мектептің әлеуметтік паспорты", "Көп балалы, аз қамтылған, жетім, ЕБҚ балалар есебі",
                      "Мектепішілік және ЮП (ПДН) есебі", "Тегін тамақтану", "Жалпыға бірдей оқыту (всеобуч)",
                      "Тұрмыстық жағдайды тексеру актілері, рейдтер", "Бала құқығын қорғау"],
        "journals": [
            J("soc", "passport", "Әлеуметтік паспорт", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"),
                F("cats", "Санаттар", "multiselect", ["Көп балалы отбасы", "Аз қамтылған", "Жетім",
                  "Ата-ана қамқорлығынсыз", "Қамқорлықтағы", "Толық емес отбасы", "Мүгедектігі бар",
                  "ЕБҚ (ПМПК)", "Мектепішілік есеп", "ЮП есебі", "Тегін тамақ", "Оралман/қандас"]),
                F("address", "Мекенжайы"), F("parent", "Ата-ана / телефон"), F("note", "Ескерту", "textarea")],
                private=True, help="Құпия: тек әлеуметтік педагог пен директорға көрінеді."),
            J("soc", "visits", "Отбасыға бару актілері / рейдтер", [
                F("student", "Оқушы / отбасы", required=True), F("date", "Күні", "date"),
                F("type", "Түрі", "select", ["Тұрмыстық жағдайды тексеру", "Рейд", "Профилактикалық әңгіме",
                                             "Сабақ босату себебі"]),
                F("result", "Қорытынды", "textarea")], private=True),
            J("soc", "attendance", "Сабақ босату (всеобуч)", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"), F("date", "Күні", "date"),
                F("days", "Күн саны", "number", default=1), F("reason", "Себебі", "select",
                  ["Ауру", "Отбасылық", "Себепсіз"]), F("action", "Шара")], private=True),
        ],
    },
    "psychologist": {
        "functions": ["Диагностика (1/5/10 сынып бейімделуі, мазасыздық, кәсіби бағдар, суицидтік тәуекел)",
                      "Оқушы, ата-ана, мұғалім кеңестері", "Түзету-дамыту жұмысы", "Тәуекел тобы",
                      "Психологиялық ағарту, тренингтер"],
        "special": ["risk"],
        "journals": [
            J("psy", "diag", "Диагностика нәтижелері", [
                F("student", "Оқушы (немесе код)", required=True), F("class", "Сынып", "class"),
                F("method", "Әдістеме", "select", ["Бейімделу", "Мазасыздық (Филлипс/Спилбергер)", "Өзін-өзі бағалау",
                  "Кәсіби бағдар", "Суицидтік тәуекел скрининг", "Буллинг", "Басқа"]),
                F("date", "Күні", "date"), F("score", "Балл", "number"),
                F("risk", "Тәуекел деңгейі", "select", ["Төмен", "Орташа", "Жоғары"]),
                F("note", "Қорытынды", "textarea")], private=True,
                help="Құпия: тек психолог пен директорға көрінеді. Аты орнына кодты қолдануға болады."),
            J("psy", "consult", "Кеңестер журналы", [
                F("who", "Кім", "select", ["Оқушы", "Ата-ана", "Мұғалім"]), F("person", "Аты / коды"),
                F("date", "Күні", "date"), F("topic", "Мәселе", "select", ["Оқу", "Қарым-қатынас", "Отбасы",
                  "Эмоция/стресс", "Кәсіби бағдар", "Буллинг", "Басқа"]),
                F("result", "Ұсыныс", "textarea")], private=True),
            J("psy", "groups", "Түзету-дамыту сабақтары / тренингтер", [
                F("name", "Атауы", required=True), F("class", "Сынып", "class"), F("date", "Күні", "date"),
                F("count", "Қатысушылар", "number")]),
        ],
    },
    "librarian": {
        "functions": ["Кітап қоры, электрондық кітапхана", "Кітап беру/қайтару", "Оқулықпен қамтамасыз ету",
                      "Оқу мәдениеті іс-шаралары"],
        "links": [("📚 Кітапхана жүйесі (Google Apps Script)", LINKS["library"])],
        "journals": [
            J("lib", "events", "Кітапхана іс-шаралары", [
                F("name", "Іс-шара", required=True), F("date", "Күні", "date"), F("class", "Сынып", "class"),
                F("count", "Қатысушылар", "number")]),
        ],
    },
    "nvp": {
        "functions": ["10–11 сыныптарда АӘТД", "Жасөспірімдерді әскери есепке тіркеу (приписка)",
                      "Оқу-дала жиындары", "Әскери-патриоттық іс-шаралар", "Азаматтық қорғаныс, эвакуация"],
        "special": ["norms_nvp"],
        "journals": [
            J("nvp", "conscripts", "Әскерге шақырылушылар тізімі", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"), F("birth", "Туған жылы", "number",
                  default=2009), F("registered", "Есепке тұрды", "checkbox"),
                F("health", "Денсаулық тобы", "select", ["Негізгі", "Дайындық", "Арнайы"]), F("note", "Ескерту")]),
            J("nvp", "events", "Әскери-патриоттық іс-шаралар / эвакуация", [
                F("name", "Атауы", required=True), F("date", "Күні", "date"),
                F("type", "Түрі", "select", ["Іс-шара", "Эвакуация жаттығуы", "Оқу-дала жиыны", "Жарыс"]),
                F("count", "Қатысушы", "number"), F("result", "Нәтиже", "textarea")]),
        ],
    },
    "pe": {
        "functions": ["Дене шынықтыру сабақтары", "Нормативтер, Президенттік тесттер", "Денсаулық топтары",
                      "Спорт секциялары", "Жарыстар (нәтижелер рейтингке)"],
        "special": ["norms_pe"],
        "journals": [
            J("pe", "health", "Денсаулық топтары", [
                F("student", "Оқушы", required=True), F("class", "Сынып", "class"),
                F("group", "Топ", "select", ["Негізгі", "Дайындық", "Арнайы", "Босатылған"]),
                F("until", "Мерзімі", "date"), F("note", "Анықтама")]),
            J("pe", "comp", "Жарыстар", [
                F("name", "Жарыс", required=True), F("date", "Күні", "date"), F("level", "Деңгейі", "select", LEVELS),
                F("team", "Қатысушылар"), F("place", "Нәтиже", "select", PLACES)]),
        ],
    },
    "proforg": {
        "functions": ["Кәсіподақ мүшелерінің есебі", "Мүшелік жарна", "Ұжымдық шарт", "Материалдық көмек",
                      "Құттықтау, туған күндер", "Мәдени-көпшілік іс-шаралар", "Хаттамалар, еңбекті қорғау"],
        "links": [("🎂 Әріптестердің туған күндері", LINKS["birthday"])],
        "journals": [
            J("prof", "members", "Кәсіподақ мүшелері", [
                F("name", "ТАӘ", required=True), F("position", "Лауазымы"), F("joined", "Кірген күні", "date"),
                F("fee", "Айлық жарна (тг)", "number"), F("phone", "Телефон")]),
            J("prof", "aid", "Материалдық көмек өтініштері", [
                F("name", "Өтініш беруші", required=True), F("reason", "Себебі", "select",
                  ["Емделу", "Той/мереке", "Қайғылы жағдай", "Басқа"]), F("amount", "Сомасы (тг)", "number"),
                F("status", "Шешім", "select", ["Қаралуда", "Бекітілді", "Бас тартылды"]),
                F("date", "Күні", "date")]),
            J("prof", "protocols", "Кәсіподақ жиналысының хаттамалары", [
                F("num", "№"), F("date", "Күні", "date"), F("agenda", "Күн тәртібі", "textarea", required=True),
                F("decision", "Шешім", "textarea")]),
            J("prof", "events", "Мәдени-көпшілік іс-шаралар, құттықтаулар", [
                F("name", "Атауы", required=True), F("date", "Күні", "date"), F("budget", "Шығын (тг)", "number"),
                F("note", "Ескерту")]),
        ],
    },
}
WORKSPACES["director"] = {"functions": ["Жалпы басшылық, бұйрықтар", "Міндеттерді бөлу, бақылау", "МДЖ",
                                        "Кадрлар, қаржы"], "journals": []}


# ---------------- Арнайы құралдар ----------------
def grades_tool():
    st.subheader("📊 БЖБ/ТЖБ, тоқсан бағалары: сапа және үлгерім")
    st.caption("CSV/Excel: бағандар — Сынып, Пән, Мұғалім, Оқушы, Баға (2–5). Kundelik экспортын осы түрге келтіріңіз.")
    up = st.file_uploader("Бағалар файлы", type=["csv", "xlsx"], key="grades_up")
    if up is None:
        return
    d = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
    if "Баға" not in d.columns:
        st.error("«Баға» бағаны табылмады")
        return
    d["Баға"] = pd.to_numeric(d["Баға"], errors="coerce")
    by = st.multiselect("Топтау", [c for c in ["Сынып", "Пән", "Мұғалім"] if c in d.columns], default=["Сынып"])
    if not by:
        return
    g = d.groupby(by)["Баға"]
    res = pd.DataFrame({"Оқушы/баға саны": g.size(), "Орташа балл": g.mean().round(2),
                        "Үлгерім %": g.apply(lambda s: (s >= 3).mean() * 100).round(1),
                        "Сапа %": g.apply(lambda s: (s >= 4).mean() * 100).round(1),
                        "«2» саны": g.apply(lambda s: (s == 2).sum())}).reset_index()
    c1, c2 = st.columns(2)
    c1.metric("Мектеп бойынша сапа", f"{(d['Баға'] >= 4).mean() * 100:.1f}%")
    c2.metric("Мектеп бойынша үлгерім", f"{(d['Баға'] >= 3).mean() * 100:.1f}%")
    st.dataframe(res, hide_index=True, use_container_width=True)
    st.bar_chart(res.set_index(by[0])["Сапа %"])
    low = res[res["Сапа %"] < 50]
    if not low.empty:
        st.warning("Сапасы 50%-дан төмен: " + ", ".join(str(x) for x in low[by[0]].tolist()))
    download_buttons(res, "Сапа және үлгерім мониторингі", "grades")


def meters_tool(db, user):
    st.subheader("⚡ Коммуналдық есептегіштер және үнемдеу")
    with st.form("meters", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        month = c1.text_input("Ай (ЖЖЖЖ-АА)", pd.Timestamp.today().strftime("%Y-%m"))
        el = c2.number_input("Электр (кВт·сағ)", 0.0)
        wt = c3.number_input("Су (м³)", 0.0)
        ht = c1.number_input("Жылу (Гкал)", 0.0)
        cost = c2.number_input("Жалпы төлем (тг)", 0.0)
        if st.form_submit_button("Сақтау"):
            db.add_record("hoz", "meters", user["username"],
                          {"month": month, "electricity": el, "water": wt, "heat": ht, "cost": cost})
            st.rerun()
    df = db.records("hoz", "meters")
    if df.empty:
        return
    df = df.sort_values("month").drop_duplicates("month", keep="last").set_index("month")
    st.line_chart(df[["electricity"]].rename(columns={"electricity": "Электр, кВт·сағ"}))
    if len(df) >= 2:
        last, prev = df["electricity"].iloc[-1], df["electricity"].iloc[-2]
        ch = (last - prev) / prev * 100 if prev else 0
        st.metric("Электр: соңғы ай", f"{last:.0f} кВт·сағ", f"{ch:+.1f}% алдыңғы айға", delta_color="inverse")
        if ch > 5:
            st.warning("Шығын өсті: ЭкоСвет ұсыныстарын тексеріңіз, бос кабинеттердегі жарықты бақылаңыз.")
    download_buttons(df.reset_index()[["month", "electricity", "water", "heat", "cost"]], "Коммуналдық шығындар",
                     "meters")


PE_NORMS = pd.DataFrame([
    {"Норматив": "30 м жүгіру (сек)", "Кері (аз = жақсы)": True, "5": 5.0, "4": 5.5, "3": 6.0},
    {"Норматив": "1000 м жүгіру (мин)", "Кері (аз = жақсы)": True, "5": 4.0, "4": 4.5, "3": 5.0},
    {"Норматив": "Ұзындыққа секіру (см)", "Кері (аз = жақсы)": False, "5": 200, "4": 180, "3": 160},
    {"Норматив": "Тартылу (рет)", "Кері (аз = жақсы)": False, "5": 10, "4": 7, "3": 4},
])
NVP_NORMS = pd.DataFrame([
    {"Норматив": "АК толық емес бөлшектеу (сек)", "Кері (аз = жақсы)": True, "5": 18, "4": 22, "3": 26},
    {"Норматив": "АК жинау (сек)", "Кері (аз = жақсы)": True, "5": 25, "4": 30, "3": 35},
    {"Норматив": "Газтұмылдырық кию (сек)", "Кері (аз = жақсы)": True, "5": 7, "4": 8, "3": 10},
    {"Норматив": "Атыс (ұпай)", "Кері (аз = жақсы)": False, "5": 40, "4": 33, "3": 25},
])


def norms_tool(db, user, kind: str, base: pd.DataFrame):
    st.subheader("⏱ Нормативтер — бағаны автоматты қою")
    st.caption("⚠ Кестедегі шектер — мысал. Ресми нормативтер кестесімен (сынып, жыныс бойынша) тексеріп, түзетіңіз.")
    saved = db.records(kind, "norms_table")
    table = pd.DataFrame(saved.iloc[0]["rows"]) if not saved.empty else base
    table = st.data_editor(table, num_rows="dynamic", use_container_width=True, key=f"nt_{kind}")
    if st.button("Нормативтер кестесін сақтау", key=f"nts_{kind}"):
        db.execute("DELETE FROM records WHERE module = ? AND kind = 'norms_table'", (kind,))
        db.add_record(kind, "norms_table", user["username"], {"rows": table.to_dict("records")})
    with st.form(f"norm_res_{kind}", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        st_name = c1.text_input("Оқушы")
        cls = c2.text_input("Сынып")
        norm = c3.selectbox("Норматив", table["Норматив"].tolist())
        val = c4.number_input("Нәтиже", 0.0, step=0.1)
        if st.form_submit_button("Бағалау және сақтау") and st_name:
            r = table[table["Норматив"] == norm].iloc[0]
            rev = bool(r["Кері (аз = жақсы)"])
            grade = 2
            for gname in ["5", "4", "3"]:
                th = float(r[gname])
                if (val <= th) if rev else (val >= th):
                    grade = int(gname)
                    break
            db.add_record(kind, "norm_result", user["username"],
                          {"student": st_name, "class": cls, "norm": norm, "value": val, "grade": grade})
            st.success(f"{st_name}: {norm} = {val} → баға {grade}")
    res = db.records(kind, "norm_result")
    if not res.empty:
        st.dataframe(res[["student", "class", "norm", "value", "grade", "_created"]], hide_index=True,
                     use_container_width=True)
        st.bar_chart(res["grade"].astype(str).value_counts())
        download_buttons(res[["student", "class", "norm", "value", "grade"]], "Нормативтер нәтижелері",
                         f"norms_{kind}")


def risk_tool(db, user):
    st.subheader("🚩 Тәуекел тобы (автоматты)")
    d = db.records("psy", "diag")
    if not d.empty and user["role"] not in ("admin", "director"):
        d = d[d["_author"] == user["username"]]
    if d.empty:
        st.info("Диагностика нәтижелері жоқ")
        return
    hi = d[d["risk"] == "Жоғары"].sort_values("_created").drop_duplicates("student", keep="last")
    c1, c2, c3 = st.columns(3)
    c1.metric("Диагностика жазбалары", len(d))
    c2.metric("Жоғары тәуекел", len(hi))
    c3.metric("Орташа тәуекел", int((d["risk"] == "Орташа").sum()))
    if not hi.empty:
        st.error("Жоғары тәуекел тобындағы оқушылар — жеке жоспар және ата-анамен жұмыс қажет:")
        st.dataframe(hi[["student", "class", "method", "date", "note"]], hide_index=True, use_container_width=True)
    st.bar_chart(d.groupby(["class", "risk"]).size().unstack(fill_value=0))


def render(db, user, role: str | None = None):
    role = role or user["role"]
    ws = WORKSPACES.get(role)
    st.header(f"🧰 Жұмыс орны: {role_name(role)}")
    if not ws:
        st.info("Бұл рөлге арнайы жұмыс орны жоқ.")
        return
    with st.expander("📋 Функционалдық міндеттер және не автоматтандырылған", expanded=False):
        for f in ws["functions"]:
            st.markdown(f"- {f}")
        duties = db.query("SELECT duty FROM duties WHERE username = ?", (user["username"],))
        if duties:
            st.markdown("**Әкімші бекіткен міндеттеріңіз:** " + "; ".join(d["duty"] for d in duties))
    names = [j["title"] for j in ws["journals"]]
    specials = {"observation": "📝 Сабаққа қатысу парағы", "grades": "📊 Сапа/үлгерім",
                "young_journal": "📘 Жас педагогтер журналы", "meters": "⚡ Есептегіштер",
                "norms_pe": "⏱ Нормативтер", "norms_nvp": "⏱ АӘТД нормативтері", "risk": "🚩 Тәуекел тобы"}
    sp = ws.get("special", [])
    link_tabs = [l[0] for l in ws.get("links", [])]
    tab_names = [specials[s] for s in sp] + names + link_tabs
    if role == "zavuch_uch":
        tab_names.append("📈 Қатысу қорытындысы")
    if not tab_names:
        return
    tabs = st.tabs(tab_names)
    i = 0
    for s in sp:
        with tabs[i]:
            if s == "observation":
                observation.zavuch_form(db, user)
            elif s == "grades":
                grades_tool()
            elif s == "young_journal":
                observation.young_journal(db, user)
            elif s == "meters":
                meters_tool(db, user)
            elif s == "norms_pe":
                norms_tool(db, user, "pe", PE_NORMS)
            elif s == "norms_nvp":
                norms_tool(db, user, "nvp", NVP_NORMS)
            elif s == "risk":
                risk_tool(db, user)
        i += 1
    for j in ws["journals"]:
        with tabs[i]:
            render_journal(db, user, j)
        i += 1
    for title, url in ws.get("links", []):
        with tabs[i]:
            external_app(title, url, key=f"lnk_{role}_{i}")
        i += 1
    if role == "zavuch_uch":
        with tabs[i]:
            observation.observation_stats(db)
