"""
Price Book System — Streamlit UI (full product)

Tabs: Search · Drop files · Batch · Vendors · Admin
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
from backend.auth import check_login, credentials_source_hint
from backend.config import DEFAULT_MULTIPLIER

st.set_page_config(
    page_title="FAF Price Book",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Login gate
# ---------------------------------------------------------------------------


def _require_login() -> bool:
    """Show login form until authenticated. Returns True when logged in."""
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        """
        <div style="max-width:420px;margin:4rem auto 1rem auto;text-align:center;">
          <div style="font-size:2rem;font-weight:700;color:#2d4a30;">🔥 FAF Price Book</div>
          <div style="color:#555;margin-top:0.25rem;">Foothills Amish Furniture · sign in to continue</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        with st.form("login_form", clear_on_submit=False):
            user = st.text_input("Username", autocomplete="username")
            pw = st.text_input(
                "Password", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button(
                "Sign in", type="primary", use_container_width=True
            )
            if submitted:
                if check_login(user, pw):
                    st.session_state["authenticated"] = True
                    st.session_state["auth_user"] = user.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
        st.caption(
            f"Credentials source: **{credentials_source_hint()}** · "
            "edit `.streamlit/secrets.toml` to change."
        )
    return False


if not _require_login():
    st.stop()

# ---------------------------------------------------------------------------
# Service (after login)
# ---------------------------------------------------------------------------


@st.cache_resource
def get_service() -> PriceBookService:
    svc = PriceBookService()
    svc.init()
    return svc


svc = get_service()

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


def _last_backup_hint() -> str:
    backup_dir = Path.home() / "Documents" / "FAF-pricebook-backups"
    if not backup_dir.is_dir():
        return "No backup yet"
    files = sorted(backup_dir.glob("master_pricebook-*.db"), key=lambda p: p.stat().st_mtime)
    if not files:
        return "No backup yet"
    latest = files[-1]
    age = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%b %d %I:%M %p")
    return f"{latest.name} · {age}"


def money_cols(df: pd.DataFrame):
    return {
        "base_price": st.column_config.NumberColumn("Wholesale", format="$%.2f"),
        "adjusted_price": st.column_config.NumberColumn(
            "RETAIL", format="$%.2f", help="What the customer pays (base × mult)"
        ),
        "unit_retail": st.column_config.NumberColumn("Each $", format="$%.2f"),
        "line_total": st.column_config.NumberColumn("Line $", format="$%.2f"),
        "multiplier": st.column_config.NumberColumn("Mult", format="%.2f"),
        "qty": st.column_config.NumberColumn("Qty", min_value=0.1, step=1.0),
        "line_discount_pct": st.column_config.NumberColumn(
            "Disc %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
        ),
    }


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
        ["replace_vendor", "upsert", "append"],
        format_func=lambda m: {
            "replace_vendor": "Replace this builder (recommended — one catalog per builder)",
            "upsert": "Upsert (smart update, no full replace)",
            "append": "Append always (can create duplicates)",
        }[m],
        horizontal=True,
        key=f"mode_{source_name}",
        index=0,
    )
    st.caption(
        "Policy: **one builder = one vendor**. Re-importing Premier replaces all Premier rows."
    )
    if st.button("➕ Commit to master", type="primary", key=f"go_{source_name}"):
        result = svc.add_rows(rows, mode=mode)
        vend = vendor_hint or (rows[0].get("vendor") if rows else "")
        if vend and rows:
            svc.set_vendor_multiplier(
                vend,
                float(rows[0].get("multiplier") or DEFAULT_MULTIPLIER),
            )
        st.success(
            f"Done · total {result.get('total', 0):,} · "
            f"in {result.get('inserted', 0):,} · up {result.get('updated', 0):,} · "
            f"del {result.get('deleted', 0):,}"
        )
        st.balloons()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🔥 FAF Price Book")
st.sidebar.caption("Foothills Amish Furniture")
who = st.session_state.get("auth_user") or "user"
st.sidebar.caption(f"Signed in as **{who}**")
if st.sidebar.button("Sign out"):
    for k in ("authenticated", "auth_user"):
        st.session_state.pop(k, None)
    st.rerun()

stats = svc.stats()
st.sidebar.metric("Master rows", f"{stats['rows']:,}")
st.sidebar.caption(
    f"{stats['vendors']} vendors · {stats['collections']} collections"
)

st.sidebar.caption(
    "Multipliers: set per builder on the **Vendors** tab "
    f"(default for new imports: {DEFAULT_MULTIPLIER:g})."
)

st.sidebar.divider()
if st.sidebar.button("Recompute ALL retail from Vendors mults"):
    total = 0
    for v in svc.list_vendors():
        m = svc.get_vendor_multiplier(v, default=DEFAULT_MULTIPLIER)
        total += int(svc.reapply_multiplier(float(m), vendor=v) or 0)
    st.sidebar.success(f"Updated {total:,} rows from each builder’s mult")

if st.sidebar.button("💾 Backup price book DB"):
    import subprocess
    import sys

    script = Path(__file__).resolve().parent / "scripts" / "backup_db.py"
    rc = subprocess.call([sys.executable, str(script)])
    if rc == 0:
        st.sidebar.success("Saved → Documents/FAF-pricebook-backups")
    else:
        st.sidebar.error("Backup failed — see terminal")
st.sidebar.caption(f"Last backup: {_last_backup_hint()}")

# ---------------------------------------------------------------------------
# Home dashboard strip
# ---------------------------------------------------------------------------

vsum = svc.vendor_summary()
top_vendors = ""
if not vsum.empty:
    top = vsum.head(3)
    top_vendors = " · ".join(
        f"{r['vendor']} ({int(r['rows']):,})" for _, r in top.iterrows()
    )

d1, d2, d3 = st.columns(3)
d1.metric("Price rows", f"{stats['rows']:,}")
d2.metric("Builders", f"{stats['vendors']}")
d3.metric(
    "Last backup",
    _last_backup_hint().split("·")[-1].strip()
    if "·" in _last_backup_hint()
    else _last_backup_hint(),
)
if top_vendors:
    st.caption(f"Largest books: {top_vendors}")

# ===========================================================================
# TABS
# ===========================================================================

tab_search, tab_import, tab_batch, tab_vendors, tab_admin = st.tabs(
    [
        "🔎 Search",
        "📥 Drop files",
        "📁 Batch folder",
        "🏭 Vendors",
        "⚙️ Admin",
    ]
)

# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Find a price")
    st.caption(
        "Type a **part number** or words · exact SKU ranks first · "
        "dust covers sink when you type a short code (VECG before VECG-DC)."
    )

    q = st.text_input(
        "Search the master book",
        placeholder="VECG   ·   GO-AVNNS   ·   oak nightstand   ·   Abe bar stool",
        key="sq",
        label_visibility="collapsed",
    )

    vendors = ["All"] + svc.list_vendors()
    f1, f2, f3, f4 = st.columns([1.3, 1.5, 1.2, 0.8])
    with f1:
        vf = st.selectbox("Builder", vendors, key="sv")
    with f2:
        coll_src = svc.list_collections(vendor=None if vf == "All" else vf)
        collections = ["All"] + coll_src
        cf = st.selectbox("Collection", collections, key="sc")
    with f3:
        # Floor default: finished only
        finish_opts = ["finished", "All", "unfinished"]
        ff = st.selectbox("Finish", finish_opts, index=0, key="sf")
    with f4:
        lim = st.number_input("Max rows", 50, 5000, 150, 50, key="sl")

    # Don't dump the whole book when search is empty — unless a builder is chosen
    if not (q or "").strip() and vf == "All":
        results = pd.DataFrame()
        empty_reason = "type"
    else:
        results = svc.search(
            q,
            vendor=None if vf == "All" else vf,
            collection=None if cf == "All" else cf,
            finish_state=None if ff == "All" else ff,
            limit=int(lim),
        )
        empty_reason = "none" if results.empty else ""
    display = results.copy()

    # Floor table emphasizes RETAIL
    if display.empty:
        if empty_reason == "type":
            st.info(
                "Type a part number or product words above — or pick a **Builder** to browse."
            )
        else:
            st.info(
                "No hits — try fewer words, or check **Builder** / **Finish** filters."
            )
    else:
        st.markdown(
            f"**{len(display):,}** hits · "
            f"<span style='color:#2d4a30;font-weight:700'>Retail is what the customer pays</span>",
            unsafe_allow_html=True,
        )
        show_cols = [
            c
            for c in [
                "part_number",
                "description",
                "vendor",
                "collection",
                "species",
                "finish_state",
                "dimensions",
                "base_price",
                "multiplier",
                "adjusted_price",
            ]
            if c in display.columns
        ]
        view = display[show_cols].rename(
            columns={
                "part_number": "Part #",
                "description": "Description",
                "vendor": "Builder",
                "collection": "Collection",
                "species": "Wood / option",
                "finish_state": "Finish",
                "dimensions": "Dims",
                "base_price": "Wholesale",
                "multiplier": "Mult",
                "adjusted_price": "RETAIL",
            }
        )
        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wholesale": st.column_config.NumberColumn(format="$%.2f"),
                "RETAIL": st.column_config.NumberColumn(
                    "RETAIL", format="$%.2f", help="Customer price"
                ),
                "Mult": st.column_config.NumberColumn(format="%.2f"),
            },
            height=480,
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        e1, e2, e3 = st.columns(3)
        export_df = display.drop(columns=["id"], errors="ignore")
        with e1:
            st.download_button(
                "⬇️ Excel",
                svc.export_excel(export_df),
                f"pricebook_{stamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with e2:
            st.download_button(
                "⬇️ CSV",
                svc.export_csv(export_df),
                f"pricebook_{stamp}.csv",
                "text/csv",
            )
        with e3:
            pdf = svc.export_pdf(display.head(200), "FAF Price Book Export")
            st.download_button(
                "⬇️ PDF (200)",
                pdf,
                f"pricebook_{stamp}.pdf" if pdf[:4] == b"%PDF" else f"pricebook_{stamp}.txt",
            )

# ---------------------------------------------------------------------------
# IMPORT — multi-file drop with per-builder multiplier
# ---------------------------------------------------------------------------
with tab_import:
    st.subheader("Drop builder price lists")
    st.markdown(
        """
Upload one or many **Excel** (`.xlsx` / `.xls` / `.xlsm`) or **PDF** files.

For **each file** you set:
1. **Builder name** (auto-detected from filename — edit if needed)
2. **Multiplier** for that builder only (saved on the vendor; used for retail)

The system will **standardize** rows (long-form: SKU × wood/option × finish) and
**replace that builder’s catalog** so you never get duplicate builders.
        """
    )

    uploads = st.file_uploader(
        "Drop Excel or PDF price lists here",
        type=["xlsx", "xls", "xlsm", "pdf"],
        accept_multiple_files=True,
        key="drop_files",
        help="You can select multiple files at once.",
    )

    # Always replace each builder’s catalog (one builder = one book)
    commit_mode = "replace_vendor"
    prefer_wb_markup = st.checkbox(
        "Prefer workbook Markup sheet when mult not set manually",
        value=False,
        key="drop_use_wb_markup",
        help="If unchecked, uses each builder’s saved mult, else 2.7 (Genuine Oak usually 1.7 saved).",
    )

    if not uploads:
        st.info("Drop one or more builder price files above to begin.")
    else:
        # Parse once per unique filename into session so mult edits re-render cleanly
        file_keys = (tuple(sorted(f.name for f in uploads)), bool(prefer_wb_markup))
        cache_key = "drop_parse_cache"
        if (
            cache_key not in st.session_state
            or st.session_state.get("drop_file_keys") != file_keys
        ):
            parsed = {}
            progress = st.progress(0.0, text="Reading files…")
            for i, up in enumerate(uploads):
                progress.progress(
                    (i) / max(len(uploads), 1),
                    text=f"Parsing {up.name}…",
                )
                data = _bytes(up)
                prepared = svc.prepare_drop_file(
                    data,
                    filename=up.name,
                    vendor="",
                    multiplier=None,
                    use_workbook_markup=prefer_wb_markup,
                )
                prepared["_bytes"] = data
                parsed[up.name] = prepared
            progress.progress(1.0, text="Done parsing")
            st.session_state[cache_key] = parsed
            st.session_state["drop_file_keys"] = file_keys

        parsed_map: dict = st.session_state.get(cache_key, {})

        st.markdown("### Per-file builder & multiplier")
        st.caption(
            "Set the retail multiplier **per builder**. "
            "Example: Genuine Oak **1.7**, most others **2.7**."
        )

        ready_payloads = []  # list of {vendor, mult, rows, filename}

        for up in uploads:
            name = up.name
            prep = parsed_map.get(name) or {}
            with st.container(border=True):
                h1, h2 = st.columns([2, 1])
                with h1:
                    st.markdown(f"**📄 {name}**")
                    if prep.get("error") and not prep.get("row_count"):
                        st.error(prep["error"])
                    elif prep.get("notes"):
                        st.caption(prep.get("notes", "")[:200])
                with h2:
                    kind = (prep.get("kind") or "excel").upper()
                    st.metric("Parsed rows", f"{int(prep.get('row_count') or 0):,}")
                    st.caption(kind)

                c1, c2, c3 = st.columns([1.6, 1.0, 1.0])
                default_vend = prep.get("vendor") or Path(name).stem
                # Saved mult for this builder, else parsed default
                saved = svc.get_vendor_multiplier(
                    default_vend, default=float(DEFAULT_MULTIPLIER)
                )
                default_mult = float(prep.get("multiplier") or saved or DEFAULT_MULTIPLIER)

                with c1:
                    vend_edit = st.text_input(
                        "Builder name",
                        value=default_vend,
                        key=f"drop_vend_{name}",
                        help="One catalog per builder name",
                    )
                with c2:
                    mult_edit = st.number_input(
                        "Multiplier for this builder",
                        min_value=0.1,
                        max_value=20.0,
                        value=float(default_mult),
                        step=0.1,
                        key=f"drop_mult_{name}",
                        help="Retail = wholesale × this number",
                    )
                with c3:
                    detected = prep.get("detected_markup")
                    if detected:
                        st.caption(f"Workbook markup sheet: **{detected:g}**")
                        if st.button(
                            f"Use workbook {detected:g}",
                            key=f"drop_wb_{name}",
                        ):
                            st.session_state[f"drop_mult_{name}"] = float(detected)
                            st.rerun()
                    else:
                        st.caption("No markup sheet found")
                    # Suggest common mults
                    b_a, b_b = st.columns(2)
                    with b_a:
                        if st.button("2.7", key=f"m27_{name}"):
                            st.session_state[f"drop_mult_{name}"] = 2.7
                            st.rerun()
                    with b_b:
                        if st.button("1.7", key=f"m17_{name}"):
                            st.session_state[f"drop_mult_{name}"] = 1.7
                            st.rerun()

                # Re-apply mult + vendor on rows for this file
                rows = list(prep.get("rows") or [])
                vend_final = (vend_edit or default_vend).strip()
                mult_final = float(mult_edit)
                for r in rows:
                    r["vendor"] = vend_final
                    r["source_file"] = name
                    r["multiplier"] = mult_final
                    bp = r.get("base_price")
                    if bp is not None:
                        try:
                            r["adjusted_price"] = round(float(bp) * mult_final, 2)
                        except (TypeError, ValueError):
                            pass

                # Sample retail after mult
                if rows:
                    sample = pd.DataFrame(rows[:6])
                    show = [
                        c
                        for c in [
                            "vendor",
                            "part_number",
                            "description",
                            "species",
                            "finish_state",
                            "base_price",
                            "multiplier",
                            "adjusted_price",
                        ]
                        if c in sample.columns
                    ]
                    st.dataframe(
                        sample[show].rename(
                            columns={
                                "base_price": "Wholesale",
                                "adjusted_price": "RETAIL",
                                "multiplier": "Mult",
                                "part_number": "Part #",
                                "species": "Wood / option",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Wholesale": st.column_config.NumberColumn(format="$%.2f"),
                            "RETAIL": st.column_config.NumberColumn(format="$%.2f"),
                            "Mult": st.column_config.NumberColumn(format="%.2f"),
                        },
                    )
                    # Retail range hint
                    try:
                        rets = [
                            float(r["adjusted_price"])
                            for r in rows
                            if r.get("adjusted_price") is not None
                        ]
                        if rets:
                            st.caption(
                                f"Retail range after ×{mult_final:g}: "
                                f"**${min(rets):,.2f}** – **${max(rets):,.2f}** · "
                                f"{len(rows):,} sellable rows"
                            )
                    except Exception:
                        pass

                    ready_payloads.append(
                        {
                            "filename": name,
                            "vendor": vend_final,
                            "multiplier": mult_final,
                            "rows": rows,
                        }
                    )
                elif prep.get("error"):
                    st.warning("This file will be skipped until it parses cleanly.")

        st.divider()
        st.markdown("### Load into master price book")
        if not ready_payloads:
            st.warning("No files with parsed rows yet.")
        else:
            # Collapse duplicate builders in the same drop (last file wins)
            by_vendor: dict = {}
            for p in ready_payloads:
                by_vendor[p["vendor"]] = p
            if len(by_vendor) < len(ready_payloads):
                st.warning(
                    "Two or more files map to the **same builder name**. "
                    "Only the last file for each builder will be kept "
                    "(one catalog per builder)."
                )

            summary_rows = [
                {
                    "Builder": p["vendor"],
                    "File": p["filename"],
                    "Rows": len(p["rows"]),
                    "Multiplier": p["multiplier"],
                }
                for p in by_vendor.values()
            ]
            st.caption(
                "Loading **replaces each builder’s whole catalog** "
                "(one builder = one book)."
            )
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Multiplier": st.column_config.NumberColumn(format="%.2f"),
                    "Rows": st.column_config.NumberColumn(format="%d"),
                },
            )

            if st.button(
                f"🚀 Standardize & load {len(by_vendor)} builder(s) into master",
                type="primary",
                use_container_width=True,
            ):
                results_log = []
                bar = st.progress(0.0, text="Loading…")
                items = list(by_vendor.values())
                for i, p in enumerate(items):
                    bar.progress(
                        i / max(len(items), 1),
                        text=f"Loading {p['vendor']}…",
                    )
                    result = svc.add_rows(p["rows"], mode=commit_mode)
                    svc.set_vendor_multiplier(
                        p["vendor"],
                        float(p["multiplier"]),
                        notes=f"Set from drop import of {p['filename']}",
                    )
                    # Ensure retail matches saved mult
                    svc.reapply_multiplier(
                        float(p["multiplier"]), vendor=p["vendor"]
                    )
                    results_log.append(
                        {
                            "Builder": p["vendor"],
                            "File": p["filename"],
                            "Mult": p["multiplier"],
                            "Inserted": result.get("inserted", 0),
                            "Updated": result.get("updated", 0),
                            "Removed old": result.get("deleted", 0),
                            "Total": result.get("total", 0),
                        }
                    )
                bar.progress(1.0, text="Done")
                st.success(
                    f"Loaded **{len(items)}** builder(s). "
                    f"Master now has **{svc.row_count():,}** rows."
                )
                st.dataframe(
                    pd.DataFrame(results_log),
                    use_container_width=True,
                    hide_index=True,
                )
                st.balloons()
                # Clear parse cache so a re-drop re-reads
                st.session_state.pop(cache_key, None)
                st.session_state.pop("drop_file_keys", None)

# ---------------------------------------------------------------------------
# BATCH
# ---------------------------------------------------------------------------
with tab_batch:
    st.subheader("Batch import a folder of price lists")
    st.caption(
        "Excel preferred. Default mode **replaces each builder** (one catalog per builder). "
        "Builder name is derived from the filename."
    )

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
    mode = st.selectbox(
        "Mode",
        ["replace_vendor", "upsert", "append"],
        format_func=lambda m: {
            "replace_vendor": "Replace each builder (recommended — no duplicates)",
            "upsert": "Upsert only",
            "append": "Append (not recommended)",
        }[m],
        key="bm",
        index=0,
    )
    st.caption(
        "Batch maps filenames to **one name per builder** (e.g. MWS 2023 + Millers 2026 → "
        "Millers Woodshop only). Only one file per builder is imported."
    )
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
                    multiplier=float(DEFAULT_MULTIPLIER),
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
# VENDORS — edit multipliers
# ---------------------------------------------------------------------------
with tab_vendors:
    st.subheader("Modify builder multipliers")
    st.markdown(
        """
**Retail = wholesale × multiplier.**  
Each builder has its own mult (e.g. Genuine Oak **1.7**, most others **2.7**).

1. Edit the **Multiplier** column below  
2. Click **Save multipliers & update retail prices**
        """
    )

    summary = svc.vendor_summary()
    if summary.empty:
        st.info("No builders in master yet — import files under **Drop files** first.")
    else:
        edit_df = summary[
            [
                c
                for c in [
                    "vendor",
                    "rows",
                    "collections",
                    "saved_mult",
                    "avg_mult",
                    "min_base",
                    "max_base",
                ]
                if c in summary.columns
            ]
        ].copy()
        # Prefer saved_mult; fall back to avg_mult
        edit_df["Multiplier"] = edit_df.apply(
            lambda r: float(
                r["saved_mult"]
                if pd.notna(r.get("saved_mult"))
                else (r.get("avg_mult") or DEFAULT_MULTIPLIER)
            ),
            axis=1,
        )
        edit_df = edit_df.rename(
            columns={
                "vendor": "Builder",
                "rows": "Items",
                "collections": "Collections",
                "min_base": "Min wholesale",
                "max_base": "Max wholesale",
            }
        )
        show_cols = [
            c
            for c in [
                "Builder",
                "Items",
                "Collections",
                "Multiplier",
                "Min wholesale",
                "Max wholesale",
            ]
            if c in edit_df.columns
        ]
        edited = st.data_editor(
            edit_df[show_cols],
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Builder": st.column_config.TextColumn(disabled=True),
                "Items": st.column_config.NumberColumn(format="%d", disabled=True),
                "Collections": st.column_config.NumberColumn(
                    format="%d", disabled=True
                ),
                "Multiplier": st.column_config.NumberColumn(
                    "Multiplier",
                    min_value=0.1,
                    max_value=20.0,
                    step=0.1,
                    format="%.2f",
                    help="Edit this — then click Save below",
                    disabled=False,
                ),
                "Min wholesale": st.column_config.NumberColumn(
                    format="$%.0f", disabled=True
                ),
                "Max wholesale": st.column_config.NumberColumn(
                    format="$%.0f", disabled=True
                ),
            },
            key="vendor_mult_editor",
        )

        st.caption(
            "Quick tips: set **2.7** for most Amish builders · **1.7** for Genuine Oak "
            "(or whatever deal you run)."
        )

        b1, b2, b3 = st.columns([1.4, 1.0, 1.0])
        with b1:
            if st.button(
                "💾 Save multipliers & update retail prices",
                type="primary",
                use_container_width=True,
            ):
                updated_builders = 0
                updated_rows = 0
                for _, r in edited.iterrows():
                    builder = str(r["Builder"])
                    mult = float(r["Multiplier"])
                    if mult <= 0:
                        continue
                    svc.set_vendor_multiplier(
                        builder,
                        mult,
                        notes="Updated from Vendors tab",
                    )
                    n = svc.reapply_multiplier(mult, vendor=builder)
                    updated_builders += 1
                    updated_rows += int(n or 0)
                st.success(
                    f"Saved **{updated_builders}** builders · "
                    f"recomputed **{updated_rows:,}** retail prices"
                )
                st.rerun()
        with b2:
            if st.button("Set all to 2.7", use_container_width=True):
                for v in svc.list_vendors():
                    svc.set_vendor_multiplier(v, 2.7, notes="Bulk set 2.7")
                    svc.reapply_multiplier(2.7, vendor=v)
                st.success("All builders set to 2.7")
                st.rerun()
        with b3:
            if st.button("Genuine Oak → 1.7", use_container_width=True):
                if "Genuine Oak" in svc.list_vendors():
                    svc.set_vendor_multiplier(
                        "Genuine Oak", 1.7, notes="Typical Genuine Oak deal"
                    )
                    n = svc.reapply_multiplier(1.7, vendor="Genuine Oak")
                    st.success(f"Genuine Oak → 1.7 ({n:,} rows)")
                    st.rerun()
                else:
                    st.warning("Genuine Oak not in master.")

        # Example: show one SKU before/after for selected builder
        st.markdown("##### Check a price after mult change")
        vlist = svc.list_vendors()
        cv1, cv2 = st.columns([1.2, 2])
        with cv1:
            check_v = st.selectbox("Builder", vlist, key="vcheck")
        with cv2:
            sample = svc.search("", vendor=check_v, finish_state="finished", limit=5)
            if sample.empty:
                sample = svc.search("", vendor=check_v, limit=5)
            if not sample.empty:
                s = sample.iloc[0]
                st.write(
                    f"**{s.get('part_number')}** · {s.get('description') or ''} · "
                    f"{s.get('species') or ''}  \n"
                    f"Wholesale **${float(s.get('base_price') or 0):,.2f}** × "
                    f"**{float(s.get('multiplier') or 0):.2f}** = "
                    f"Retail **${float(s.get('adjusted_price') or 0):,.2f}**"
                )

        st.divider()
        st.markdown("##### Remove a builder from the book")
        vv = st.selectbox("Builder to remove", vlist, key="vv_del")
        if st.button("Remove builder from book", type="secondary"):
            n = svc.delete_by_vendor(vv)
            st.warning(f"Deleted {n:,} rows for {vv}")
            st.rerun()

# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------
with tab_admin:
    st.subheader("Admin / data quality")
    s1, s2 = st.columns(2)
    s1.metric("Rows", f"{stats['rows']:,}")
    s2.metric("Builders", stats["vendors"])
    st.caption(f"Database: `{svc.path}`")
    st.caption(f"Last backup: {_last_backup_hint()}")

    st.markdown("##### Maintenance")
    m1, m2, m3 = st.columns(3)
    with m1:
        if st.button("💾 Backup DB now"):
            import subprocess
            import sys

            script = Path(__file__).resolve().parent / "scripts" / "backup_db.py"
            rc = subprocess.call([sys.executable, str(script)])
            st.success("Backup saved") if rc == 0 else st.error("Backup failed")
    with m2:
        if st.button("✨ Re-standardize master"):
            report = svc.standardize_master()
            st.write(report)
            st.success("Standardize complete")
    with m3:
        if st.button("Scan duplicates"):
            dups = svc.find_duplicates(50)
            if dups.empty:
                st.success("No duplicate identity groups.")
            else:
                st.dataframe(dups, use_container_width=True)

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
python -m backend.cli import-xlsx FILE --vendor NAME --mode replace_vendor
python -m backend.cli batch FOLDER --excel-only --mode replace_vendor
python -m backend.cli backup-db
python -m backend.cli standardize
        """.strip()
    )

st.caption(
    "FAF Price Book · Foothills Amish Furniture · "
    "Search · Drop files · Vendors · one builder = one catalog"
)
