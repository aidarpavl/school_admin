"""Ортақ UI көмекшілері: әмбебап журнал, сілтемелер, жүктеу батырмалары."""
from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.config import CLASSES, SUPER_ROLES
from core.export import csv_bytes, doc_bytes, df_to_html, esc


def is_super(user: dict) -> bool:
    return user.get("role") in SUPER_ROLES


def external_app(title: str, url: str, height: int = 750, embed: bool = True, key: str = ""):
    """Сыртқы қосымшаны батырма + ендірілген терезе ретінде көрсету."""
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"**{title}**  \n`{url}`")
    c2.link_button("↗ Жаңа терезеде ашу", url, use_container_width=True)
    if embed:
        src = url
        if "streamlit.app" in url:
            src = url.rstrip("/") + "/?embed=true"
        show = st.toggle("Осы бетте ашу (ендіру)", value=True, key=f"emb_{key or title}")
        if show:
            components.iframe(src, height=height, scrolling=True)
            st.caption("Егер терезе бос болса — сайт ендіруге рұқсат бермейді, «Жаңа терезеде ашу» батырмасын басыңыз.")


def download_buttons(df: pd.DataFrame, title: str, key: str, extra_html: str = ""):
    c1, c2 = st.columns(2)
    c1.download_button("⬇ CSV (Excel)", csv_bytes(df) if not df.empty else b"", f"{key}.csv",
                       "text/csv", use_container_width=True, key=f"csv_{key}", disabled=df.empty)
    body = f"<h1>{esc(title)}</h1><p>Құрылған күні: {date.today():%d.%m.%Y}</p>{extra_html}{df_to_html(df)}"
    c2.download_button("⬇ Word (.doc)", doc_bytes(title, body, landscape=len(df.columns) > 6),
                       f"{key}.doc", "application/msword", use_container_width=True, key=f"doc_{key}")


def _field_input(f: dict, key: str, users: list[str]):
    t = f.get("type", "text")
    label = f["label"] + (" *" if f.get("required") else "")
    if t == "textarea":
        return st.text_area(label, key=key)
    if t == "select":
        return st.selectbox(label, f["options"], key=key)
    if t == "multiselect":
        return st.multiselect(label, f["options"], key=key)
    if t == "number":
        return st.number_input(label, value=float(f.get("default", 0)), step=float(f.get("step", 1)), key=key)
    if t == "date":
        return st.date_input(label, value=date.today(), key=key)
    if t == "checkbox":
        return st.checkbox(label, key=key)
    if t == "class":
        return st.selectbox(label, CLASSES, key=key)
    if t == "user":
        return st.selectbox(label, users or ["—"], key=key)
    return st.text_input(label, key=key)


def summary_html(df: pd.DataFrame, fields: list[dict]) -> tuple[str, list]:
    """Автоматты есеп: таңдау өрістері бойынша саны, сандық өрістер бойынша орташа/қосынды."""
    parts, tables = [], []
    if df.empty:
        return "", []
    parts.append(f"<p><b>Барлық жазба:</b> {len(df)}</p>")
    for f in fields:
        k = f["key"]
        if k not in df.columns:
            continue
        if f.get("type") in ("select", "class", "user", "checkbox"):
            vc = df[k].astype(str).value_counts().rename_axis(f["label"]).reset_index(name="Саны")
            tables.append((f["label"], vc))
            parts.append(f"<h3>{esc(f['label'])}</h3>{vc.to_html(index=False)}")
        elif f.get("type") == "multiselect":
            vc = df[k].explode().dropna().astype(str).value_counts().rename_axis(f["label"]).reset_index(name="Саны")
            tables.append((f["label"], vc))
            parts.append(f"<h3>{esc(f['label'])}</h3>{vc.to_html(index=False)}")
        elif f.get("type") == "number":
            s = pd.to_numeric(df[k], errors="coerce")
            parts.append(f"<p><b>{esc(f['label'])}:</b> қосынды {s.sum():.1f}, орташа {s.mean():.2f}</p>")
    return "".join(parts), tables


def render_journal(db, user: dict, spec: dict, users: list[str] | None = None):
    """spec = {module, kind, title, fields, private(bool), help}"""
    module, kind, fields = spec["module"], spec["kind"], spec["fields"]
    key = f"{module}_{kind}"
    if spec.get("help"):
        st.caption(spec["help"])
    with st.expander(f"➕ Жаңа жазба: {spec['title']}", expanded=False):
        with st.form(f"form_{key}", clear_on_submit=True):
            vals = {}
            cols = st.columns(2)
            for i, f in enumerate(fields):
                with cols[i % 2] if f.get("type") != "textarea" else st.container():
                    vals[f["key"]] = _field_input(f, f"in_{key}_{f['key']}", users or [])
            if st.form_submit_button("💾 Сақтау", type="primary"):
                missing = [f["label"] for f in fields if f.get("required") and not vals.get(f["key"])]
                if missing:
                    st.error("Толтырыңыз: " + ", ".join(missing))
                else:
                    db.add_record(module, kind, user["username"], vals, private=spec.get("private", False))
                    st.success("Сақталды")
                    st.rerun()

    df = db.records(module, kind)
    if spec.get("private") and not is_super(user) and not df.empty:
        df = df[df["_author"] == user["username"]]
    if df.empty:
        st.info("Әзірге жазба жоқ.")
        return df
    q = st.text_input("🔎 Іздеу", key=f"q_{key}")
    view = df
    if q:
        mask = df.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
        view = df[mask]
    labels = {f["key"]: f["label"] for f in fields}
    show_cols = [f["key"] for f in fields if f["key"] in view.columns] + ["_author", "_created", "_id"]
    st.dataframe(view[show_cols].rename(columns={**labels, "_author": "Автор", "_created": "Күні", "_id": "ID"}),
                 use_container_width=True, hide_index=True)

    shtml, tables = summary_html(view, fields)
    with st.expander("📊 Автоматты есеп"):
        st.metric("Жазбалар саны", len(view))
        for label, t in tables[:4]:
            st.markdown(f"**{label}**")
            st.bar_chart(t.set_index(t.columns[0]))
    export = view[[c for c in show_cols if not c.startswith("_")]].rename(columns=labels)
    download_buttons(export, spec["title"], key, extra_html=shtml)

    own = view if is_super(user) else view[view["_author"] == user["username"]]
    if not own.empty:
        with st.expander("🗑 Жазбаны өшіру"):
            rid = st.selectbox("ID", own["_id"].tolist(), key=f"del_{key}")
            if st.button("Өшіру", key=f"delb_{key}"):
                db.delete("records", int(rid))
                st.rerun()
    return df
