"""💬 Ұсыныстар мен пікірлер + автоматты талдау және әкімшілікке ұсыныстар."""
import streamlit as st

from core.analysis import analyze_feedback, llm_recommendations, sentiment, sentiment_label, topics
from core.config import ADMIN_ROLES, ROLES, role_name
from core.db import now
from core.export import doc_bytes, esc
from core.ui import download_buttons, is_super

CATS = ["Ұсыныс", "Пікір / отзыв", "Шағым", "Алғыс", "Сұрақ"]


def feedback_form(db, user, source="Жалпы", key="fb", default_role="director"):
    roles = [r for r in ROLES if r not in ("teacher", "admin")]
    with st.form(f"form_{key}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        target = c1.selectbox("Кімге (рөл)", roles, index=roles.index(default_role) if default_role in roles else 0,
                              format_func=role_name)
        cat = c2.selectbox("Түрі", CATS)
        text = st.text_area("Мәтін *", height=130)
        anon = st.checkbox("Анонимді жіберу (автор әкімшілікке көрсетілмейді)")
        if st.form_submit_button("📨 Жіберу", type="primary"):
            if len(text.strip()) < 5:
                st.error("Мәтінді жазыңыз")
            else:
                s = sentiment(text)
                db.insert("feedback", {"author": user["username"], "anonymous": int(anon), "target_role": target,
                                       "source": source, "category": cat, "text": text.strip(), "sentiment": s,
                                       "topics": "; ".join(topics(text)), "status": "Жаңа", "created_at": now()})
                st.success("Рахмет! Пікіріңіз жіберілді.")


def render(db, user):
    st.header("💬 Ұсыныстар мен пікірлер")
    tabs = ["✍ Жазу", "📜 Менің пікірлерім"]
    if user["role"] in ADMIN_ROLES:
        tabs += ["📥 Маған келгендер", "🧠 Талдау және ұсыныстар"]
    t = st.tabs(tabs)

    with t[0]:
        st.caption("Ұсынысыңыз таңдалған рөлдегі әкімшілік мүшесіне барады. Жүйе мәтінді автоматты талдап, "
                   "тақырыбы мен көңіл күйін анықтайды.")
        feedback_form(db, user)

    with t[1]:
        mine = db.df("SELECT created_at, target_role, category, text, status, response FROM feedback "
                     "WHERE author = ? ORDER BY id DESC", (user["username"],))
        if mine.empty:
            st.info("Әзірге жоқ")
        else:
            mine["target_role"] = mine["target_role"].map(role_name)
            st.dataframe(mine, hide_index=True, use_container_width=True)

    if user["role"] not in ADMIN_ROLES:
        return

    df = db.df("SELECT * FROM feedback ORDER BY id DESC")
    if not df.empty and not is_super(user):
        df = df[df["target_role"] == user["role"]]
    if not df.empty:
        df["author_view"] = df.apply(lambda r: "Аноним" if int(r["anonymous"]) else r["author"], axis=1)

    with t[2]:
        if df.empty:
            st.info("Пікір жоқ")
        else:
            sf = st.multiselect("Мәртебе", ["Жаңа", "Қаралуда", "Шешілді"], default=["Жаңа", "Қаралуда"])
            for _, r in df[df["status"].isin(sf)].iterrows():
                with st.container(border=True):
                    st.markdown(f"**{r['category']}** · {sentiment_label(float(r['sentiment']))} · "
                                f"{r['topics']} · {r['author_view']} → {role_name(r['target_role'])} · "
                                f"{r['created_at']} · _{r['source']}_")
                    st.write(r["text"])
                    c1, c2 = st.columns([3, 1])
                    resp = c1.text_input("Жауап", value=r["response"] or "", key=f"resp_{r['id']}")
                    stt = c2.selectbox("Мәртебе", ["Жаңа", "Қаралуда", "Шешілді"],
                                       index=["Жаңа", "Қаралуда", "Шешілді"].index(r["status"]),
                                       key=f"st_{r['id']}")
                    if st.button("Сақтау", key=f"sv_{r['id']}"):
                        db.update("feedback", int(r["id"]), {"response": resp, "status": stt})
                        st.rerun()

    with t[3]:
        if df.empty:
            st.info("Талдау үшін пікір жоқ")
            return
        c1, c2 = st.columns(2)
        roles_f = c1.multiselect("Рөл бойынша", sorted(df["target_role"].unique()), format_func=role_name)
        src_f = c2.multiselect("Дереккөз", sorted(df["source"].dropna().unique()))
        d = df
        if roles_f:
            d = d[d["target_role"].isin(roles_f)]
        if src_f:
            d = d[d["source"].isin(src_f)]
        a = analyze_feedback(d)
        m = st.columns(5)
        m[0].metric("Барлығы", a["total"])
        m[1].metric("🙂 Оң", a["positive"])
        m[2].metric("😐 Бейтарап", a["neutral"])
        m[3].metric("🙁 Теріс", a["negative"])
        m[4].metric("Көңіл күй индексі", a["mean"], help="-1 (теріс) ... +1 (оң)")
        st.subheader("Тақырыптар бойынша")
        st.dataframe(a["topics"], hide_index=True, use_container_width=True)
        st.bar_chart(a["topics"].set_index("topic")["саны"])
        st.subheader("📌 Әкімшілікке ұсыныстар (автоматты)")
        if a["recommendations"].empty:
            st.success("Шұғыл мәселе анықталмады.")
        else:
            st.dataframe(a["recommendations"], hide_index=True, use_container_width=True)
        st.subheader("Жиі қолданылған сөздер")
        st.write(", ".join(f"{w} ({c})" for w, c in a["words"]))
        dyn = d.assign(ай=d["created_at"].str[:7]).groupby("ай")["sentiment"].mean()
        if len(dyn) > 1:
            st.line_chart(dyn.rename("Көңіл күй динамикасы"))

        if st.button("🤖 ЖИ арқылы терең ұсыныстар (ANTHROPIC_API_KEY болса)"):
            out = llm_recommendations(d["text"].tolist())
            st.markdown(out or "ЖИ кілті баптаулмаған — жоғарыдағы ереже негізіндегі ұсыныстар қолданылады.")

        body = (f"<h1>Мұғалімдердің ұсыныстары мен пікірлерін талдау</h1><p>Барлығы: {a['total']}; оң: "
                f"{a['positive']}; теріс: {a['negative']}; индекс: {a['mean']}</p><h2>Тақырыптар</h2>"
                f"{a['topics'].to_html(index=False)}<h2>Ұсыныстар</h2>"
                f"{a['recommendations'].to_html(index=False) if not a['recommendations'].empty else '—'}"
                f"<h2>Пікірлер</h2>" + "".join(f"<p>• [{esc(r['category'])}] {esc(r['text'])}</p>"
                                              for _, r in d.iterrows()))
        st.download_button("⬇ Талдау есебі (Word)", doc_bytes("Пікірлер талдауы", body), "feedback_analysis.doc")
        download_buttons(d[["created_at", "target_role", "category", "topics", "sentiment", "text", "status"]],
                         "Пікірлер тізімі", "feedback_list")
