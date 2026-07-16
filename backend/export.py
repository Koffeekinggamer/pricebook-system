"""Export master rows to Excel / CSV / PDF bytes."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

RENAME = {
    "vendor": "Vendor",
    "collection": "Collection",
    "part_number": "Part #",
    "description": "Description",
    "dimensions": "Dimensions",
    "option_key": "Option",
    "species": "Species",
    "species_tier": "Tier",
    "finish_state": "Finish",
    "base_price": "Base / Wholesale",
    "price_basis": "Price Basis",
    "multiplier": "Multiplier",
    "adjusted_price": "Retail (Adjusted)",
    "unit": "Unit",
    "notes": "Notes",
    "source_file": "Source",
    "imported_at": "Imported",
}


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    export = df.copy()
    if "id" in export.columns:
        export = export.drop(columns=["id"])
    export = export.rename(columns={k: v for k, v in RENAME.items() if k in export.columns})
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="Price Book")
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    export = df.copy()
    if "id" in export.columns:
        export = export.drop(columns=["id"])
    return export.to_csv(index=False).encode("utf-8")


def to_pdf_bytes(df: pd.DataFrame, title: str = "Price Book Export") -> bytes:
    try:
        from fpdf import FPDF
    except ImportError:
        lines = [title, "=" * len(title), ""]
        cols = [c for c in df.columns if c != "id"]
        lines.append(" | ".join(cols))
        lines.append("-" * 80)
        for _, row in df.iterrows():
            lines.append(" | ".join(str(row.get(c, "") or "")[:40] for c in cols))
        return "\n".join(lines).encode("utf-8")

    pdf = FPDF(orientation="L", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    try:
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    except TypeError:
        pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Helvetica", "", 8)
    gen = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  {len(df)} rows"
    try:
        pdf.cell(0, 6, gen, new_x="LMARGIN", new_y="NEXT")
    except TypeError:
        pdf.cell(0, 6, gen, ln=True)
    pdf.ln(2)

    show_cols = [
        c
        for c in [
            "vendor",
            "collection",
            "part_number",
            "description",
            "species",
            "base_price",
            "multiplier",
            "adjusted_price",
        ]
        if c in df.columns
    ]
    labels = {
        "vendor": "Vendor",
        "collection": "Collection",
        "part_number": "Part #",
        "description": "Description",
        "species": "Species",
        "base_price": "Base",
        "multiplier": "Mult",
        "adjusted_price": "Retail",
    }
    widths = {
        "vendor": 28,
        "collection": 30,
        "part_number": 24,
        "description": 70,
        "species": 32,
        "base_price": 20,
        "multiplier": 14,
        "adjusted_price": 20,
    }

    pdf.set_font("Helvetica", "B", 7)
    for c in show_cols:
        pdf.cell(widths.get(c, 25), 6, labels.get(c, c), border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for _, row in df.iterrows():
        for c in show_cols:
            val = row.get(c, "")
            if c in ("base_price", "adjusted_price") and val is not None and val != "":
                try:
                    text = f"${float(val):,.2f}"
                except (TypeError, ValueError):
                    text = str(val)
            elif c == "multiplier" and val is not None and val != "":
                try:
                    text = f"{float(val):.2f}"
                except (TypeError, ValueError):
                    text = str(val)
            else:
                text = str(val if val is not None else "")
            max_chars = max(4, int(widths.get(c, 25) / 1.6))
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            pdf.cell(widths.get(c, 25), 5, text, border=1)
        pdf.ln()

    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()
