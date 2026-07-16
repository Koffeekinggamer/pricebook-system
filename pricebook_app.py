"""
Price Book System — Streamlit UI (full product)

Tabs: Search · Import · Batch · Quotes · Vendors · Admin
All logic via backend.PriceBookService

Run:  streamlit run pricebook_app.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from backend import PriceBookService
from backend.config import DEFAULT_MULTIPLIER

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@st.cache_resource
def get_service() -> PriceBookService:
    svc = PriceBookService()
    svc.init()
    return svc


svc = get_service()

st.set_page_config(
    page_title="FAF Price Book",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🔥 FAF Price Book")
st.sidebar.caption("Foothills Amish Furniture")
stats = svc.stats()
st.sidebar.metric("Master rows", f"{stats['rows']:,}")
st.sidebar.caption(
    f"{stats['vendors']} vendors · {stats['collections']} collections · "
    f"{stats.get('quotes', 0)} quotes"
)

multiplier = st.sidebar.number_input(
    "Default multiplier",
    min_value=0.1,
    max_value=20.0,
    value=float(DEFAULT_MULTIPLIER),
    step=0.1,
)

st.sidebar.divider()
if st.sidebar.button("Recompute ALL retail × sidebar mult"):
    n = svc.reapply_multiplier(float(multiplier))
    st.sidebar.success(f"Updated {n:,} rows")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _bytes(upload) -> bytes:
    data = upload.getvalue() if hasattr(upload, "getvalue") else upload.read()
    if hasattr(upload, "seek"):
        try:
            upload.seek(0)
        except Exception:
            pass
    return data


def render_commit(rows: list[dict], source_name: str, vendor_hint: str = "") -> None:
    preview_df = pd.DataFrame(rows)
    st.markdown(f"**{len(preview_df):,}** rows ready")
    if preview_df.empty:
        st.warning("Nothing to import.")
        return
    show = [
        c
        for c in [
            "vendor",
            "collection",
            "part_number",
            "description",
            "species",
            "finish_state",
            "base_price",
            "multiplier",
            "adjusted_price",
        ]
        if c in preview_df.columns
    ]
    st.dataframe(preview_df[show].head(40), use_container_width=True)

    mode = st.radio(
        "Commit mode",
        ["upsert", "append", "replace_source"],
        format_func=lambda m: {
            "upsert": "Upsert (smart update)",
            "append": "Append always",
            "replace_source": "Replace this filename",
        }[m],
        horizontal=True,
        key=f"mode_{source_name}",
    )
    if st.button("➕ Commit to master", type="primary", key=f"go_{source_name}"):
        result = svc.add_rows(rows, mode=mode)
        vend = vendor_hint or (rows[0].get("vendor") if rows else "")
        if vend and rows:
            svc.set_vendor_multiplier(vend, float(rows[0].get("multiplier") or multiplier))
        st.success(
            f"Done · total {result.get('total', 0):,} · "
            f"in {result.get('inserted', 0):,} · up {result.get('updated', 0):,} · "
            f"del {result.get('deleted', 0):,}"
        )
        st.balloons()


def money_cols(df: pd.DataFrame):
    return {
        "base_price": st.column_config.NumberColumn("Base", format="$%.2f"),
        "adjusted_price": st.column_config.NumberColumn("Retail", format="$%.2f"),
        "unit_retail": st.column_config.NumberColumn("Each", format="$%.2f"),
        "line_total": st.column_config.NumberColumn("Line", format="$%.2f"),
        "multiplier": st.column_config.NumberColumn("Mult", format="%.2f"),
    }


# ===========================================================================
# TABS
# ===========================================================================

tab_search, tab_import, tab_batch, tab_quotes, tab_vendors, tab_admin = st.tabs(
    ["🔎 Search", "📥 Import", "📁 Batch", "🧾 Quotes", "🏭 Vendors", "⚙️ Admin"]
)

# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Master price book")
    vendors = ["All"] + svc.list_vendors()
    collections = ["All"] + svc.list_collections()
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        q = st.text_input("Search", placeholder="oak queen · A591 · nightstand", key="sq")
    with c2:
        vf = st.selectbox("Vendor", vendors, key="sv")
    with c3:
        cf = st.selectbox("Collection", collections, key="sc")
    with c4:
        lim = st.number_input("Max", 50, 5000, 500, 50, key="sl")

    preview_mult = st.checkbox("Preview retail with sidebar multiplier", key="sp")
    results = svc.search(
        q,
        vendor=None if vf == "All" else vf,
        collection=None if cf == "All" else cf,
        limit=int(lim),
    )
    display = results.copy()
    if preview_mult and not display.empty and "base_price" in display.columns:
        display["multiplier"] = float(multiplier)
        display["adjusted_price"] = (display["base_price"] * float(multiplier)).round(2)

    st.caption(f"{len(display):,} shown · {svc.row_count():,} total")
    if display.empty:
        st.info("Empty master — import builders under **Import** or **Batch**.")
    else:
        view = display.drop(columns=["id"], errors="ignore")
        st.dataframe(view, use_container_width=True, column_config=money_cols(view))

        # quick add to quote
        if "id" in results.columns and not results.empty:
            with st.expander("Add selected search hit to a quote"):
                qlist = svc.list_quotes(limit=50)
                if qlist.empty:
                    st.caption("Create a quote under the Quotes tab first.")
                else:
                    labels = {
                        int(r["id"]): f"{r['quote_number']} — {r.get('customer_name') or 'draft'}"
                        for _, r in qlist.iterrows()
                    }
                    qid = st.selectbox(
                        "Quote",
                        list(labels.keys()),
                        format_func=lambda i: labels[i],
                        key="search_qid",
                    )
                    row_id = st.number_input(
                        "Pricebook row id (from search results)",
                        min_value=1,
                        value=int(results.iloc[0]["id"]),
                        key="search_rid",
                    )
                    qty = st.number_input("Qty", 0.1, 999.0, 1.0, 1.0, key="search_qty")
                    if st.button("Add line to quote", key="search_add"):
                        try:
                            svc.add_quote_line_from_id(int(qid), int(row_id), qty=float(qty))
                            st.success("Added.")
                        except Exception as e:
                            st.error(str(e))

        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button(
                "⬇️ Excel",
                svc.export_excel(view),
                f"pricebook_{stamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with e2:
            st.download_button(
                "⬇️ CSV",
                svc.export_csv(view),
                f"pricebook_{stamp}.csv",
                "text/csv",
            )
        with e3:
            pdf = svc.export_pdf(display.head(200), "Price Book Export")
            st.download_button(
                "⬇️ PDF (200)",
                pdf,
                f"pricebook_{stamp}.pdf" if pdf[:4] == b"%PDF" else f"pricebook_{stamp}.txt",
            )

# ---------------------------------------------------------------------------
# IMPORT single file
# ---------------------------------------------------------------------------
with tab_import:
    st.subheader("Import one supplier file")
    vend = st.text_input("Vendor name", placeholder="Genuine Oak, FVWW, Schrock's…", key="iv")
    coll = st.text_input("Default collection (optional)", key="ic")
    upload = st.file_uploader("Excel or PDF", type=["xlsx", "xls", "xlsm", "pdf"], key="iu")
    pdf_pages = st.number_input("PDF max pages (0=all)", 0, 500, 0, key="ip")

    if upload:
        data = _bytes(upload)
        name = upload.name
        st.write(f"**{name}**")

        if name.lower().endswith(".pdf"):
            max_p: Optional[int] = int(pdf_pages) if pdf_pages > 0 else None
            with st.spinner("Parsing PDF…"):
                prelim = svc.preview_pdf(
                    data,
                    filename=name,
                    vendor=vend.strip(),
                    default_collection=coll.strip(),
                    multiplier=float(multiplier),
                    max_pages=max_p,
                )
            if prelim.stats.get("likely_scanned"):
                st.warning("Scanned PDF — little text. Prefer Excel.")
            elif not prelim.results:
                st.error("No prices found.")
            else:
                labels = [f"{r.label} — {len(r.df):,}" for r in prelim.results]
                idx = st.selectbox(
                    "Strategy",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key="pdf_i",
                )
                prev = svc.preview_pdf(
                    data,
                    filename=name,
                    vendor=vend.strip(),
                    default_collection=coll.strip(),
                    multiplier=float(multiplier),
                    max_pages=max_p,
                    strategy_index=idx,
                )
                st.dataframe(prev.long_df.head(25), use_container_width=True)
                render_commit(prev.rows, name, vend.strip())

        else:
            with st.spinner("Scanning workbook…"):
                prev = svc.preview_excel(
                    data,
                    filename=name,
                    vendor=vend.strip(),
                    default_collection=coll.strip(),
                    multiplier=float(multiplier),
                )
            use_mult = float(multiplier)
            if prev.detected_markup:
                st.info(f"Workbook markup **{prev.detected_markup:g}**")
                if st.checkbox(
                    f"Use workbook markup ({prev.detected_markup:g})",
                    value=True,
                    key="ium",
                ):
                    use_mult = float(prev.detected_markup)

            if prev.sheets_tried:
                st.dataframe(pd.DataFrame(prev.sheets_tried), use_container_width=True)

            with_rows = [s["sheet"] for s in prev.sheets_tried if s.get("rows", 0) > 0]
            cands = [
                s["sheet"] for s in prev.sheets_tried if s.get("layout") != "skip"
            ]
            if not with_rows:
                st.warning("Auto parse empty — manual map:")
                df_raw = svc.read_excel_bytes(data)
                auto = svc.map_columns(df_raw)
                st.json(auto)
                from backend.normalize import normalize_dataframe

                fields = ["part_number", "description", "base_price", "species"]
                all_cols = ["—"] + list(map(str, df_raw.columns))
                manual = {}
                cols = st.columns(len(fields))
                for i, f in enumerate(fields):
                    choice = cols[i].selectbox(f, all_cols, key=f"man_{f}")
                    if choice != "—":
                        manual[f] = choice
                if st.button("Preview manual"):
                    rows = normalize_dataframe(
                        df_raw,
                        source_file=name,
                        vendor=vend.strip(),
                        default_collection=coll.strip(),
                        multiplier=use_mult,
                        column_map=manual,
                    )
                    render_commit(rows, name, vend.strip())
            else:
                selected = st.multiselect(
                    "Sheets", cands or prev.sheet_names, default=with_rows, key="isheets"
                )
                prev = svc.preview_excel(
                    data,
                    filename=name,
                    vendor=vend.strip(),
                    default_collection=coll.strip(),
                    multiplier=use_mult,
                    sheet_filter=selected or None,
                    use_workbook_markup=False,
                )
                # force mult
                from backend.normalize import long_df_to_rows

                long_df = prev.long_df
                if not long_df.empty and "species" in long_df.columns:
                    opts = sorted(
                        s for s in long_df["species"].dropna().astype(str).unique() if s
                    )
                    if len(opts) > 1:
                        keep = st.multiselect("Species tiers", opts, default=opts, key="isp")
                        if keep:
                            long_df = long_df[
                                long_df["species"].isna() | long_df["species"].isin(keep)
                            ]
                rows = long_df_to_rows(
                    long_df,
                    source_file=name,
                    multiplier=use_mult,
                    vendor=vend.strip(),
                    default_collection=coll.strip(),
                )
                st.success(f"{len(rows):,} long-form rows · mult {use_mult:g}")
                if not long_df.empty:
                    st.dataframe(long_df.head(40), use_container_width=True)
                render_commit(rows, name, vend.strip())

# ---------------------------------------------------------------------------
# BATCH
# ---------------------------------------------------------------------------
with tab_batch:
    st.subheader("Batch import a folder of price lists")
    st.caption("Excel preferred. Upsert by default. Vendor name derived from filename.")

    default_folder = str(
        Path.home()
        / "Documents"
        / "Judson's old mac book pro"
        / "Downloads"
        / "Builder Updates 07172025"
        / "Ready for Web Upload"
        / "Completed Excel Pricebooks"
    )
    folder = st.text_input("Folder path", value=default_folder, key="bf")
    b1, b2, b3 = st.columns(3)
    with b1:
        recursive = st.checkbox("Recursive", value=False)
    with b2:
        excel_only = st.checkbox("Excel only (skip PDF)", value=True)
    with b3:
        use_markup = st.checkbox("Use workbook markup sheets", value=True)
    mode = st.selectbox("Mode", ["upsert", "append", "replace_source"], key="bm")
    vend_over = st.text_input("Force one vendor name for all (optional)", key="bvo")

    if st.button("Scan folder"):
        paths = svc.discover_batch_files(folder, recursive=recursive)
        if excel_only:
            paths = [p for p in paths if p.suffix.lower() in {".xlsx", ".xls", ".xlsm"}]
        st.write(f"**{len(paths)}** files found")
        st.code("\n".join(p.name for p in paths[:80]) or "(none)")

    if st.button("🚀 Run batch import", type="primary"):
        if not Path(folder).is_dir():
            st.error("Folder not found.")
        else:
            prog = st.progress(0.0, text="Starting…")
            status = st.empty()

            def on_prog(msg: str):
                status.caption(msg)

            with st.spinner("Batch importing…"):
                result = svc.batch_import(
                    folder,
                    recursive=recursive,
                    mode=mode,
                    multiplier=float(multiplier),
                    use_workbook_markup=use_markup,
                    vendor_override=vend_over.strip(),
                    excel_only=excel_only,
                    progress=on_prog,
                )
            prog.progress(1.0, text="Done")
            rows = [
                {
                    "file": Path(f.path).name,
                    "vendor": f.vendor,
                    "status": f.status,
                    "inserted": f.inserted,
                    "updated": f.updated,
                    "total": f.total,
                    "message": f.message,
                }
                for f in result.files
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.success(
                f"{result.ok_count} ok · {result.error_count} errors · "
                f"{result.rows_total:,} rows written · master now {svc.row_count():,}"
            )

# ---------------------------------------------------------------------------
# QUOTES
# ---------------------------------------------------------------------------
with tab_quotes:
    st.subheader("Quote builder")

    left, right = st.columns([1, 2])

    with left:
        st.markdown("##### Quotes")
        if st.button("➕ New quote"):
            qid = svc.create_quote(customer_name="New customer")
            st.session_state["active_quote"] = qid
            st.rerun()

        qdf = svc.list_quotes(limit=100)
        if qdf.empty:
            st.caption("No quotes yet.")
            active_id = None
        else:
            options = {
                int(r["id"]): f"{r['quote_number']} · {r.get('customer_name') or '—'} · "
                f"${float(r.get('lines_subtotal') or 0):,.0f}"
                for _, r in qdf.iterrows()
            }
            default = st.session_state.get("active_quote")
            keys = list(options.keys())
            idx = keys.index(default) if default in keys else 0
            active_id = st.radio(
                "Select",
                keys,
                index=idx,
                format_func=lambda i: options[i],
                key="qradio",
            )
            st.session_state["active_quote"] = active_id

    with right:
        active_id = st.session_state.get("active_quote")
        if not active_id:
            st.info("Create or select a quote.")
        else:
            quote = svc.get_quote(int(active_id))
            if not quote:
                st.error("Quote not found.")
            else:
                st.markdown(f"### {quote.get('quote_number')}")
                g1, g2 = st.columns(2)
                with g1:
                    cust = st.text_input(
                        "Customer", value=quote.get("customer_name") or "", key="qc"
                    )
                    phone = st.text_input(
                        "Phone", value=quote.get("customer_phone") or "", key="qp"
                    )
                with g2:
                    email = st.text_input(
                        "Email", value=quote.get("customer_email") or "", key="qe"
                    )
                    status = st.selectbox(
                        "Status",
                        ["draft", "sent", "won", "lost"],
                        index=["draft", "sent", "won", "lost"].index(
                            quote.get("status") or "draft"
                        ),
                        key="qs",
                    )
                notes = st.text_area("Notes", value=quote.get("notes") or "", key="qn")
                d1, d2 = st.columns(2)
                with d1:
                    disc = st.number_input(
                        "Quote discount %",
                        0.0,
                        100.0,
                        float(quote.get("discount_pct") or 0),
                        0.5,
                        key="qd",
                    )
                with d2:
                    tax = st.number_input(
                        "Tax %",
                        0.0,
                        30.0,
                        float(quote.get("tax_pct") or 0),
                        0.25,
                        key="qt",
                    )
                if st.button("Save quote header"):
                    svc.update_quote(
                        int(active_id),
                        customer_name=cust,
                        customer_phone=phone,
                        customer_email=email,
                        status=status,
                        notes=notes,
                        discount_pct=disc,
                        tax_pct=tax,
                    )
                    st.success("Saved.")

                st.markdown("##### Lines")
                lines = svc.quote_lines(int(active_id))
                if lines.empty:
                    st.caption("No lines — add from search below.")
                else:
                    st.dataframe(
                        lines[
                            [
                                c
                                for c in [
                                    "id",
                                    "qty",
                                    "part_number",
                                    "description",
                                    "species",
                                    "unit_retail",
                                    "line_discount_pct",
                                    "line_total",
                                ]
                                if c in lines.columns
                            ]
                        ],
                        use_container_width=True,
                        column_config=money_cols(lines),
                    )
                    # edit line
                    with st.expander("Edit / remove line"):
                        lid = st.number_input(
                            "Line id", min_value=1, value=int(lines.iloc[0]["id"])
                        )
                        nq = st.number_input("New qty", 0.1, 999.0, 1.0)
                        nd = st.number_input("Line discount %", 0.0, 100.0, 0.0)
                        e1, e2 = st.columns(2)
                        with e1:
                            if st.button("Update line"):
                                svc.update_quote_line(
                                    int(lid), qty=nq, line_discount_pct=nd
                                )
                                st.rerun()
                        with e2:
                            if st.button("Delete line"):
                                svc.delete_quote_line(int(lid))
                                st.rerun()

                totals = svc.quote_totals(int(active_id))
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Subtotal", f"${totals['subtotal']:,.2f}")
                m2.metric("Discount", f"-${totals['discount_amount']:,.2f}")
                m3.metric("Tax", f"${totals['tax_amount']:,.2f}")
                m4.metric("Grand total", f"${totals['grand_total']:,.2f}")

                x1, x2, x3 = st.columns(3)
                with x1:
                    st.download_button(
                        "⬇️ Quote Excel",
                        svc.export_quote_excel(int(active_id)),
                        f"{quote.get('quote_number')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                with x2:
                    qpdf = svc.export_quote_pdf(int(active_id))
                    st.download_button(
                        "⬇️ Quote PDF",
                        qpdf,
                        f"{quote.get('quote_number')}.pdf"
                        if qpdf[:4] == b"%PDF"
                        else f"{quote.get('quote_number')}.txt",
                    )
                with x3:
                    if st.button("🗑 Delete quote"):
                        svc.delete_quote(int(active_id))
                        st.session_state.pop("active_quote", None)
                        st.rerun()

                st.markdown("##### Add from master")
                sq = st.text_input("Find item", key="qfind")
                hits = svc.search(sq, limit=30) if sq.strip() else pd.DataFrame()
                if not hits.empty:
                    st.dataframe(
                        hits[
                            [
                                c
                                for c in [
                                    "id",
                                    "vendor",
                                    "part_number",
                                    "description",
                                    "species",
                                    "base_price",
                                    "adjusted_price",
                                ]
                                if c in hits.columns
                            ]
                        ].head(15),
                        use_container_width=True,
                        column_config=money_cols(hits),
                    )
                    hid = st.number_input(
                        "Add pricebook id",
                        min_value=1,
                        value=int(hits.iloc[0]["id"]),
                        key="qhid",
                    )
                    hqty = st.number_input("Qty", 0.1, 999.0, 1.0, key="qhqty")
                    if st.button("Add to quote", type="primary"):
                        svc.add_quote_line_from_id(
                            int(active_id), int(hid), qty=float(hqty)
                        )
                        st.success("Line added.")
                        st.rerun()

                with st.expander("Custom line (not in book)"):
                    cd = st.text_input("Description", key="qcd")
                    cr = st.number_input("Unit retail $", 0.0, 1_000_000.0, 0.0, key="qcr")
                    cq = st.number_input("Qty", 0.1, 999.0, 1.0, key="qcq")
                    if st.button("Add custom") and cd:
                        svc.add_custom_quote_line(
                            int(active_id),
                            description=cd,
                            unit_retail=cr,
                            qty=cq,
                        )
                        st.rerun()

# ---------------------------------------------------------------------------
# VENDORS
# ---------------------------------------------------------------------------
with tab_vendors:
    st.subheader("Vendors & multipliers")
    summary = svc.vendor_summary()
    if summary.empty:
        st.info("No vendors in master yet.")
    else:
        st.dataframe(summary, use_container_width=True)

    st.markdown("##### Set / recompute multiplier")
    vlist = svc.list_vendors()
    if vlist:
        vv = st.selectbox("Vendor", vlist, key="vv")
        cur = svc.get_vendor_multiplier(vv)
        nm = st.number_input("Multiplier", 0.1, 20.0, float(cur), 0.1, key="vm")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Save multiplier"):
                svc.set_vendor_multiplier(vv, float(nm))
                st.success(f"Saved {vv} → {nm:g}")
        with c2:
            if st.button("Recompute this vendor retail"):
                n = svc.reapply_multiplier(float(nm), vendor=vv)
                svc.set_vendor_multiplier(vv, float(nm))
                st.success(f"Updated {n:,} rows")
        with c3:
            if st.button("Delete vendor from master", type="secondary"):
                n = svc.delete_by_vendor(vv)
                st.warning(f"Deleted {n:,} rows for {vv}")

    st.markdown("##### Saved settings table")
    st.dataframe(svc.list_vendor_settings(), use_container_width=True)

# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------
with tab_admin:
    st.subheader("Admin / data quality")
    st.json(svc.stats())
    st.caption(f"Database: `{svc.path}`")

    st.markdown("##### Duplicates")
    if st.button("Scan duplicate groups"):
        dups = svc.find_duplicates(50)
        if dups.empty:
            st.success("No duplicate identity groups.")
        else:
            st.dataframe(dups, use_container_width=True)
            st.session_state["dups_df"] = True

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Dry-run cleanup (keep newest)"):
            report = svc.cleanup_duplicates(dry_run=True)
            st.write(report)
    with c2:
        if st.button("⚠️ Execute cleanup", type="primary"):
            report = svc.cleanup_duplicates(dry_run=False)
            st.success(report)

    st.markdown("##### Source files in master")
    sources = svc.list_source_files()
    if sources:
        src = st.selectbox("Source file", sources)
        if st.button("Delete all rows from this source"):
            n = svc.delete_by_source(src)
            st.warning(f"Removed {n:,} rows")

    st.markdown("##### CLI cheat sheet")
    st.code(
        """
source ~/FAF-pricebook/.venv/bin/activate
python -m backend.cli stats
python -m backend.cli search "oak nightstand"
python -m backend.cli import-xlsx FILE --vendor NAME --use-markup --mode upsert
python -m backend.cli batch FOLDER --excel-only --mode upsert
python -m backend.cli dups
        """.strip()
    )

st.caption(
    "FAF Price Book v2.0 · Search · Import · Batch · Quotes · Vendors · Admin · "
    "backend.PriceBookService"
)
