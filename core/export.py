"""Word (.doc) және CSV экспорты. Word HTML форматын ашады — қосымша кітапхана қажет емес."""
import html

import pandas as pd


def doc_bytes(title: str, body_html: str, landscape: bool = False) -> bytes:
    page = "size: 29.7cm 21cm; margin: 1.5cm;" if landscape else "size: 21cm 29.7cm; margin: 2cm;"
    doc = f"""<html xmlns:o='urn:schemas-microsoft-com:office:office'
xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
<head><meta charset='utf-8'><title>{html.escape(title)}</title>
<style>@page {{ {page} }} body {{ font-family: 'Times New Roman'; font-size: 12pt; }}
table {{ border-collapse: collapse; width: 100%; }} td, th {{ border: 1px solid #000; padding: 4px; vertical-align: top; }}
th {{ background: #e8eef7; }} h1 {{ font-size: 15pt; text-align: center; }} h2 {{ font-size: 13pt; }}</style>
</head><body>{body_html}</body></html>"""
    return doc.encode("utf-8")


def df_to_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p>Деректер жоқ</p>"
    cols = [c for c in df.columns if not str(c).startswith("_")]
    return df[cols].to_html(index=False, border=1, escape=True)


def esc(x) -> str:
    return html.escape("" if x is None else str(x)).replace("\n", "<br>")


def csv_bytes(df: pd.DataFrame) -> bytes:
    cols = [c for c in df.columns if not str(c).startswith("_")]
    return df[cols].to_csv(index=False).encode("utf-8-sig")
