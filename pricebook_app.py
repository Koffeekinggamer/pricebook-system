"""
Price Book System — Streamlit UI (full product)

Tabs: Search · Drop files · Vendors · Admin
All logic via backend.PriceBookService

Run:  streamlit run pricebook_app.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from backend import PriceBookService
from backend.auth import check_login
from backend.config import APP_DIR, DEFAULT_MULTIPLIER, DEFAULT_SEARCH_LIMIT

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_FAVICON = APP_DIR / "assets" / "favicon.png"
_LOGO = APP_DIR / "assets" / "logo.png"

st.set_page_config(
    page_title="FAF Price Book",
    page_icon=str(_FAVICON) if _FAVICON.is_file() else "🪵",
    layout="wide",
    initial_sidebar_state="collapsed",  # floor default: full-width search; open « for sign-out/stats
)

# Brand mark in the sidebar (horse & buggy wordmark)
if _LOGO.is_file():
    st.logo(str(_LOGO), size="large")

# iPad / phone-friendly density
st.markdown(
    """
    <style>
      /* Larger tap targets on touch devices */
      @media (max-width: 900px) {
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
          min-height: 2.6rem;
          font-size: 1.05rem !important;
        }
        div[data-testid="stDataFrame"] { font-size: 0.95rem; }
        .block-container { padding-top: 1rem; padding-left: 0.8rem; padding-right: 0.8rem; }
        button { min-height: 2.5rem; }
      }
      /* Favorite chip row */
      .faf-fav-row button { margin-right: 0.25rem; margin-bottom: 0.25rem; }
      /* Sidebar brand */
      [data-testid="stSidebar"] img { max-width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _favorites_path() -> Path:
    """Prefer project file locally; fall back to home (Streamlit Cloud is often read-only)."""
    local = APP_DIR / ".floor_favorites.json"
    if local.parent.exists() and os.access(str(APP_DIR), os.W_OK):
        return local
    home = Path.home() / ".faf_pricebook"
    home.mkdir(parents=True, exist_ok=True)
    return home / "floor_favorites.json"

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
          <div style="font-size:2rem;font-weight:700;color:#2d4a30;">FAF Price Book</div>
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


@st.cache_data(ttl=120, show_spinner=False)
def _wood_dropdown_options(vendor_key: str) -> list:
    """Cached wood list for the Search Wood selectbox (never empty)."""
    svc = get_service()
    v = None if not vendor_key or vendor_key == "All" else vendor_key
    try:
        woods = list(svc.list_species(vendor=v) or [])
    except Exception:
        woods = []
    # Guaranteed baseline so the dropdown always populates
    if not woods:
        woods = [
            "Oak",
            "Red Oak",
            "White Oak",
            "Brown Maple",
            "Hard Maple",
            "Cherry",
            "Walnut",
            "Hickory",
            "Elm",
            "QSWO",
            "Rustic Cherry",
            "Wormy Maple",
        ]
    return woods


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


def _auto_col_widths(
    df: pd.DataFrame,
    *,
    min_px: int = 80,
    max_px: int = 640,
    char_px: float = 8.6,
    pad_px: int = 40,
    overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    """Pixel widths sized to the longest value (and header) in each column."""
    overrides = overrides or {}
    widths: dict[str, int] = {}
    for col in df.columns:
        if col in overrides:
            widths[col] = overrides[col]
            continue
        header_len = len(str(col))
        if df.empty:
            max_len = header_len
        else:
            # Full frame is fine — search is capped at DEFAULT_SEARCH_LIMIT
            max_len = max(
                header_len,
                int(df[col].astype(str).fillna("").str.len().max() or 0),
            )
        widths[col] = min(max_px, max(min_px, int(max_len * char_px) + pad_px))
    return widths


def _dataframe_column_config(
    df: pd.DataFrame,
    *,
    money_cols: set[str] | None = None,
    number_formats: dict[str, str] | None = None,
    help_text: dict[str, str] | None = None,
    overrides: dict[str, int] | None = None,
) -> dict:
    """Build st.column_config with content-based widths so cells aren't clipped."""
    money_cols = money_cols or set()
    number_formats = number_formats or {}
    help_text = help_text or {}
    widths = _auto_col_widths(df, overrides=overrides)
    cfg: dict = {}
    for col, w in widths.items():
        if col in money_cols:
            cfg[col] = st.column_config.NumberColumn(
                col,
                format=number_formats.get(col, "$%.2f"),
                width=w,
                help=help_text.get(col),
            )
        elif col in number_formats:
            cfg[col] = st.column_config.NumberColumn(
                col,
                format=number_formats[col],
                width=w,
                help=help_text.get(col),
            )
        else:
            cfg[col] = st.column_config.TextColumn(
                col,
                width=w,
                help=help_text.get(col),
            )
    return cfg


def _last_backup_hint() -> str:
    try:
        from scripts.backup_db import list_backups
    except Exception:
        backup_dir = Path.home() / "Documents" / "FAF-pricebook-backups"
        if not backup_dir.is_dir():
            return "No backup yet"
        files = sorted(
            backup_dir.glob("master_pricebook-*.db"),
            key=lambda p: p.stat().st_mtime,
        )
        if not files:
            return "No backup yet"
        latest = files[-1]
    else:
        files = list_backups(1)
        if not files:
            return "No backup yet"
        latest = files[0]
    age = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%b %d %I:%M %p")
    return f"{latest.name} · {age}"


def _viztech_state_path() -> Path:
    return Path.home() / "Documents" / "FAF-pricebook-backups" / "viztech_sync_state.json"


def _viztech_sync_hint() -> str:
    """Human-readable last Viztech sync status (Admin only)."""
    path = _viztech_state_path()
    if not path.is_file():
        return "Never run — use Install 30-day schedule or Run full sync below."
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        return f"State file issue ({type(exc).__name__}) — run Check Viztech login to refresh."
    if not isinstance(data, dict):
        return "State file empty — run Check Viztech login to refresh."
    when = data.get("last_success") or data.get("last_check") or data.get("last_run") or "?"
    # ISO → short display
    try:
        if isinstance(when, str) and "T" in when:
            when = when.replace("Z", "+00:00")
            # Python 3.9: fromisoformat may not like all offsets; strip micros if needed
            dt = datetime.fromisoformat(when)
            when = dt.strftime("%b %d %Y %I:%M %p UTC")
    except Exception:
        pass
    mode = data.get("mode") or ""
    summary = data.get("summary") or {}
    stats = summary.get("stats") or {}
    bits = [f"Last: {when}"]
    if mode:
        bits.append(f"mode={mode}")
    if summary:
        bits.append(
            f"ok={summary.get('ok', '?')} err={summary.get('err', '?')} "
            f"skip={summary.get('skip', '?')}"
        )
    if stats.get("rows"):
        bits.append(f"book={stats.get('rows'):,} rows / {stats.get('vendors')} builders")
    if data.get("builders_seen"):
        bits.append(f"builders seen={data['builders_seen']}")
    return " · ".join(bits)


def _load_favorites() -> list[str]:
    path = _favorites_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def _save_favorites(names: list[str]) -> None:
    clean = []
    seen = set()
    for n in names:
        n = str(n).strip()
        if n and n not in seen:
            seen.add(n)
            clean.append(n)
    path = _favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("FAF Price Book")
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
# Viztech sync status lives under Admin only (hidden from floor sidebar)

# ---------------------------------------------------------------------------
# Home dashboard strip
# ---------------------------------------------------------------------------

d1, d2, d3 = st.columns([1, 1, 2.2])
d1.metric("Price rows", f"{stats['rows']:,}")
d2.metric("Builders", f"{stats['vendors']}")
with d3:
    # metric() truncates long labels; plain text shows the full store name
    st.caption("Store")
    st.markdown(
        "<div style='font-size:1.35rem;font-weight:600;line-height:1.3;"
        "color:inherit;padding-top:0.15rem;'>Foothills Amish Furniture</div>",
        unsafe_allow_html=True,
    )

# ===========================================================================
# TABS
# ===========================================================================

tab_search, tab_import, tab_vendors, tab_admin = st.tabs(
    [
        "Search",
        "Drop files",
        "Vendors",
        "Admin",
    ]
)

# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Find a price")

    # Apply pin selection BEFORE any widgets with keys sq/sv/sf exist
    # (Streamlit forbids changing those keys after the widgets are created)
    _pending_pin = st.session_state.pop("_pin_select", None)
    if _pending_pin is not None:
        st.session_state["sq"] = ""
        st.session_state["sv"] = _pending_pin
        st.session_state["sf"] = "finished"

    all_vendors = svc.list_vendors()
    favorites = [v for v in _load_favorites() if v in all_vendors]

    # Two-column floor layout: search (left) | pinned builders list (right)
    search_col, pin_col = st.columns([3.4, 1.15], gap="large")

    with search_col:
        st.caption(
            "**Boolean search** across every pricelist field (part #, description, "
            "collection, wood, builder, …).  \n"
            "`oak nightstand` = AND · `oak OR maple` · `nightstand NOT dust` · "
            '`"bar stool"` phrase · `(oak OR cherry) chair` · SKUs rank first.'
        )

        q = st.text_input(
            "Search the master book",
            placeholder='VECG  ·  oak nightstand  ·  oak OR maple  ·  "bar stool"  ·  chair NOT dust',
            key="sq",
            label_visibility="collapsed",
        )

        vendors = ["All"] + all_vendors
        # Put favorites first after All for faster floor pick in dropdown only
        if favorites:
            rest = [v for v in all_vendors if v not in favorites]
            vendors = ["All"] + favorites + rest

        f1, f2, f3, f4 = st.columns([1.45, 1.25, 0.95, 0.85])
        with f1:
            vf = st.selectbox("Builder", vendors, key="sv")
        with f2:
            # Wood — selectable species for every builder (cached; always has options)
            wood_list = _wood_dropdown_options(vf if vf else "All")
            wood_opts = ["All"] + [w for w in wood_list if w and w != "All"]
            # Keep session value valid for this option set (before widget binds)
            if "sw" in st.session_state and st.session_state["sw"] not in wood_opts:
                st.session_state["sw"] = "All"
            wf = st.selectbox(
                "Wood",
                options=wood_opts,
                key="sw",
                help="Select one wood for any builder. Multi-wood price tiers "
                "(Elm / Cherry / Maple) match when they include that wood.",
            )
        with f3:
            # Floor default: finished only
            finish_opts = ["finished", "All", "unfinished"]
            ff = st.selectbox("Finish", finish_opts, index=0, key="sf")
        with f4:
            st.write("")  # align with selectboxes
            st.write("")
            if vf != "All":
                if vf in favorites:
                    if st.button("Unpin", key="unpin_builder", use_container_width=True):
                        _save_favorites([x for x in favorites if x != vf])
                        st.rerun()
                else:
                    if st.button(
                        "Pin builder", key="pin_builder", use_container_width=True
                    ):
                        _save_favorites(favorites + [vf])
                        st.rerun()

        # Don't dump the whole book when search is empty — unless a builder is chosen
        if not (q or "").strip() and vf == "All":
            results = pd.DataFrame()
            empty_reason = "type"
        else:
            try:
                results = svc.search(
                    q,
                    vendor=None if vf == "All" else vf,
                    collection=None,  # Collection filter hidden on floor UI
                    finish_state=None if ff == "All" else ff,
                    species=None if wf == "All" else wf,
                    limit=DEFAULT_SEARCH_LIMIT,
                )
                empty_reason = "none" if results.empty else ""
            except Exception as exc:
                results = pd.DataFrame()
                empty_reason = "error"
                st.error(f"Search failed: {exc}")
        display = results.copy()
        # With a wood filter, show that wood (not the full multi-wood tier string)
        if not display.empty and wf and wf != "All" and "species" in display.columns:
            display = display.copy()
            display["species"] = wf

        # Floor table emphasizes RETAIL
        if display.empty:
            if empty_reason == "type":
                st.info(
                    "Type a part number or product words above — or pick a **Builder** "
                    "to browse (or use **Pinned** on the right)."
                )
            elif empty_reason == "error":
                pass  # error already shown
            else:
                if ff == "finished" and vf != "All":
                    st.info(
                        "No **finished** hits for this builder — try **Finish → All** "
                        "(or **unfinished**), or clear the search box."
                    )
                else:
                    st.info(
                        "No hits — try fewer words, Boolean **OR**, or check "
                        "**Builder** / **Finish** filters."
                    )
        else:
            hit_note = f"**{len(display):,}** hits"
            if len(display) >= DEFAULT_SEARCH_LIMIT:
                hit_note += f" (showing first {DEFAULT_SEARCH_LIMIT})"
            st.markdown(
                f"{hit_note} · "
                f"<span style='color:#2d4a30;font-weight:700'>Retail is what the customer pays</span>",
                unsafe_allow_html=True,
            )
            # Floor view: retail only (wholesale/mult managed on Vendors tab)
            show_cols = [
                c
                for c in [
                    "collection",
                    "part_number",
                    "description",
                    "vendor",
                    "species",
                    "finish_state",
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
                    "species": "Wood",
                    "finish_state": "Finish",
                    "adjusted_price": "RETAIL",
                }
            )
            if wf and wf != "All":
                st.caption(
                    f"Wood filter: **{wf}** · multi-wood tiers that include this wood use the same retail price."
                )
            # Content-based widths so headers + values fully show (scrolls if needed)
            st.dataframe(
                view,
                use_container_width=True,
                hide_index=True,
                column_config=_dataframe_column_config(
                    view,
                    money_cols={"RETAIL"},
                    number_formats={"RETAIL": "$%.0f"},
                    help_text={
                        "RETAIL": "Customer price — wholesale × mult, rolled up to next even dollar",
                        "Wood": "Wood species / option — use the Wood dropdown above to pick one",
                    },
                    overrides={
                        "Part #": 110,
                        "Wood": 160,
                        "Finish": 100,
                        "RETAIL": 100,
                    },
                ),
                height=480,
            )

    # ---- Separate pinned-builders column (not under the search bar) ----
    with pin_col:
        st.markdown("##### Pinned builders")
        st.caption("Tap to filter search · pin from the Builder menu")
        if not favorites:
            st.info("No pins yet. Choose a **Builder**, then **Pin builder**.")
        else:
            for i, name in enumerate(favorites[:24]):
                active = (
                    st.session_state.get("sv") == name
                    and not (st.session_state.get("sq") or "").strip()
                )
                label = f"● {name}" if active else name
                if st.button(
                    label,
                    key=f"fav_pick_{i}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    # Defer widget key updates to next run (before widgets instantiate)
                    st.session_state["_pin_select"] = name
                    st.rerun()
            if st.button("Clear pins", key="clear_all_pins", use_container_width=True):
                _save_favorites([])
                st.rerun()

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

    commit_mode = "replace_vendor"
    prefer_wb_markup = st.checkbox(
        "Prefer workbook Markup sheet when mult not set manually",
        value=False,
        key="drop_use_wb_markup",
        help="If unchecked, uses each builder’s saved mult, else 2.7 (Genuine Oak usually 1.7 saved).",
    )

    def _clear_drop_widget_state() -> None:
        for k in list(st.session_state.keys()):
            if isinstance(k, str) and (
                k.startswith("drop_vend_")
                or k.startswith("drop_mult_")
                or k.startswith("drop_wb_")
                or k.startswith("m27_")
                or k.startswith("m17_")
            ):
                del st.session_state[k]

    def _apply_vendor_mult(rows: list, vendor: str, mult: float, source: str) -> list:
        """Return deep-copied rows with vendor/mult/retail applied (never mutate cache)."""
        out = []
        for src in rows:
            r = dict(src)
            r["vendor"] = vendor
            r["source_file"] = source
            r["multiplier"] = mult
            bp = r.get("base_price")
            if bp is not None:
                try:
                    from backend.pricing import retail_from_wholesale

                    r["adjusted_price"] = retail_from_wholesale(bp, mult)
                except (TypeError, ValueError):
                    pass
            out.append(r)
        return out

    # Flash message after load (survives rerun so sidebar stats refresh)
    if st.session_state.get("drop_load_msg"):
        st.success(st.session_state.pop("drop_load_msg"))
        log = st.session_state.pop("drop_load_log", None)
        if log:
            st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)

    if not uploads:
        st.info("Drop one or more builder price files above to begin.")
    else:
        # Signature: names + sizes + markup preference. Index keys stay stable while
        # this set is unchanged. Do not use filename as widget key (special chars).
        upload_sig = (
            tuple((f.name, int(getattr(f, "size", 0) or 0)) for f in uploads),
            bool(prefer_wb_markup),
        )
        cache_key = "drop_parse_cache"

        if st.session_state.get("drop_file_keys") != upload_sig:
            _clear_drop_widget_state()
            parsed: list[dict] = []
            progress = st.progress(0.0, text="Reading files…")
            n_up = max(len(uploads), 1)
            for i, up in enumerate(uploads):
                progress.progress(i / n_up, text=f"Parsing {up.name}…")
                try:
                    data = _bytes(up)
                    prepared = svc.prepare_drop_file(
                        data,
                        filename=up.name,
                        vendor="",
                        multiplier=None,
                        use_workbook_markup=prefer_wb_markup,
                    )
                except Exception as exc:
                    prepared = {
                        "filename": up.name,
                        "vendor": Path(up.name).stem,
                        "multiplier": float(DEFAULT_MULTIPLIER),
                        "detected_markup": None,
                        "rows": [],
                        "notes": "",
                        "error": f"Parse failed: {exc}"[:400],
                        "row_count": 0,
                        "kind": "pdf"
                        if up.name.lower().endswith(".pdf")
                        else "excel",
                    }
                # Keep only what we need; never store raw bytes in session
                parsed.append(
                    {
                        "filename": up.name,
                        "vendor": prepared.get("vendor") or Path(up.name).stem,
                        "multiplier": float(
                            prepared.get("multiplier") or DEFAULT_MULTIPLIER
                        ),
                        "detected_markup": prepared.get("detected_markup"),
                        "rows": list(prepared.get("rows") or []),
                        "notes": prepared.get("notes") or "",
                        "error": prepared.get("error") or "",
                        "row_count": int(prepared.get("row_count") or 0),
                        "kind": prepared.get("kind") or "excel",
                    }
                )
            progress.progress(1.0, text="Done parsing")
            st.session_state[cache_key] = parsed
            st.session_state["drop_file_keys"] = upload_sig

        parsed_list: list = st.session_state.get(cache_key) or []
        # Align list length with current uploads if cache is stale/partial
        if len(parsed_list) != len(uploads):
            st.session_state.pop(cache_key, None)
            st.session_state.pop("drop_file_keys", None)
            st.warning("Parse cache out of sync — re-reading files…")
            st.rerun()

        st.markdown("### Per-file builder & multiplier")
        st.caption(
            "Set the retail multiplier **per builder**. "
            "Example: Genuine Oak **1.7**, most others **2.7**."
        )

        ready_payloads = []

        for i, up in enumerate(uploads):
            prep = parsed_list[i] if i < len(parsed_list) else {}
            name = up.name
            default_vend = (prep.get("vendor") or Path(name).stem).strip()
            saved = svc.get_vendor_multiplier(
                default_vend, default=float(DEFAULT_MULTIPLIER)
            )
            default_mult = float(
                prep.get("multiplier") or saved or DEFAULT_MULTIPLIER
            )

            vend_key = f"drop_vend_{i}"
            mult_key = f"drop_mult_{i}"
            # Init session defaults once — never pass value= with an existing key
            if vend_key not in st.session_state:
                st.session_state[vend_key] = default_vend
            if mult_key not in st.session_state:
                st.session_state[mult_key] = float(default_mult)

            with st.container(border=True):
                h1, h2 = st.columns([2, 1])
                with h1:
                    st.markdown(f"**{name}**")
                    if prep.get("error") and not prep.get("row_count"):
                        st.error(str(prep["error"]))
                    elif prep.get("notes"):
                        st.caption(str(prep.get("notes", ""))[:200])
                with h2:
                    kind = (prep.get("kind") or "excel").upper()
                    st.metric(
                        "Parsed rows", f"{int(prep.get('row_count') or 0):,}"
                    )
                    st.caption(kind)

                c1, c2, c3 = st.columns([1.6, 1.0, 1.0])
                with c1:
                    vend_edit = st.text_input(
                        "Builder name",
                        key=vend_key,
                        help="One catalog per builder name",
                    )
                with c2:
                    mult_edit = st.number_input(
                        "Multiplier for this builder",
                        min_value=0.1,
                        max_value=20.0,
                        step=0.1,
                        key=mult_key,
                        help="Retail = wholesale × this number",
                    )
                with c3:
                    detected = prep.get("detected_markup")
                    if detected is not None:
                        try:
                            det_f = float(detected)
                        except (TypeError, ValueError):
                            det_f = None
                    else:
                        det_f = None
                    if det_f is not None:
                        st.caption(f"Workbook markup sheet: **{det_f:g}**")
                        if st.button(
                            f"Use workbook {det_f:g}",
                            key=f"drop_wb_{i}",
                        ):
                            st.session_state[mult_key] = float(det_f)
                            st.rerun()
                    else:
                        st.caption("No markup sheet found")
                    b_a, b_b = st.columns(2)
                    with b_a:
                        if st.button("2.7", key=f"m27_{i}"):
                            st.session_state[mult_key] = 2.7
                            st.rerun()
                    with b_b:
                        if st.button("1.7", key=f"m17_{i}"):
                            st.session_state[mult_key] = 1.7
                            st.rerun()

                vend_final = (vend_edit or default_vend).strip()
                mult_final = float(mult_edit)
                cached_rows = list(prep.get("rows") or [])
                rows = _apply_vendor_mult(
                    cached_rows, vend_final, mult_final, name
                )

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
                            "Wholesale": st.column_config.NumberColumn(
                                format="$%.2f"
                            ),
                            "RETAIL": st.column_config.NumberColumn(
                                format="$%.0f",
                                help="Rolled up to next even dollar",
                            ),
                            "Mult": st.column_config.NumberColumn(format="%.2f"),
                        },
                    )
                    try:
                        rets = [
                            float(r["adjusted_price"])
                            for r in rows
                            if r.get("adjusted_price") is not None
                        ]
                        if rets:
                            st.caption(
                                f"Retail range after x{mult_final:g} (even $): "
                                f"**${min(rets):,.0f}** – **${max(rets):,.0f}** · "
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
                    st.warning(
                        "This file will be skipped until it parses cleanly."
                    )

        st.divider()
        st.markdown("### Load into master price book")
        if not ready_payloads:
            st.warning("No files with parsed rows yet.")
        else:
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
                f"Standardize & load {len(by_vendor)} builder(s) into master",
                type="primary",
                use_container_width=True,
                key="drop_load_master",
            ):
                results_log = []
                bar = st.progress(0.0, text="Loading…")
                items = list(by_vendor.values())
                for i, p in enumerate(items):
                    bar.progress(
                        i / max(len(items), 1),
                        text=f"Loading {p['vendor']}…",
                    )
                    try:
                        result = svc.add_rows(p["rows"], mode=commit_mode)
                        svc.set_vendor_multiplier(
                            p["vendor"],
                            float(p["multiplier"]),
                            notes=f"Set from drop import of {p['filename']}",
                        )
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
                                "Status": "ok",
                            }
                        )
                    except Exception as exc:
                        results_log.append(
                            {
                                "Builder": p["vendor"],
                                "File": p["filename"],
                                "Mult": p["multiplier"],
                                "Inserted": 0,
                                "Updated": 0,
                                "Removed old": 0,
                                "Total": 0,
                                "Status": f"error: {exc}"[:120],
                            }
                        )
                bar.progress(1.0, text="Done")
                ok_n = sum(1 for r in results_log if r.get("Status") == "ok")
                st.session_state.pop(cache_key, None)
                st.session_state.pop("drop_file_keys", None)
                _clear_drop_widget_state()
                st.session_state["drop_load_msg"] = (
                    f"Loaded **{ok_n}** of **{len(items)}** builder(s). "
                    f"Master now has **{svc.row_count():,}** rows."
                )
                st.session_state["drop_load_log"] = results_log
                # Rerun so sidebar metrics reflect the new master row count
                st.rerun()

# ---------------------------------------------------------------------------
# VENDORS — edit multipliers
# ---------------------------------------------------------------------------
with tab_vendors:
    st.subheader("Modify builder multipliers")

    summary = svc.vendor_summary()
    if summary.empty:
        st.info("No builders in master yet — import files under **Drop files** first.")
    else:
        edit_df = summary[
            [
                c
                for c in [
                    "vendor",
                    "phone",
                    "rows",
                    "collections",
                    "saved_mult",
                    "avg_mult",
                ]
                if c in summary.columns
            ]
        ].copy()
        if "phone" not in edit_df.columns:
            edit_df["phone"] = ""
        edit_df["phone"] = (
            edit_df["phone"].fillna("").astype(str).replace({"nan": "", "None": ""})
        )
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
                "phone": "Phone",
                "rows": "Items",
                "collections": "Collections",
            }
        )
        show_cols = [
            c
            for c in [
                "Builder",
                "Phone",
                "Items",
                "Collections",
                "Multiplier",
            ]
            if c in edit_df.columns
        ]
        edited = st.data_editor(
            edit_df[show_cols],
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            # Lock stats columns; Phone + Multiplier are editable
            disabled=["Builder", "Items", "Collections"],
            column_config={
                "Builder": st.column_config.TextColumn(disabled=True),
                "Phone": st.column_config.TextColumn(
                    "Phone",
                    help="Builder main phone — edit then Save",
                    width="medium",
                    max_chars=40,
                ),
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
            },
            key="vendor_mult_editor",
        )

        st.caption(
            "Quick tips: set **2.7** for most Amish builders · **1.7** for Genuine Oak "
            "(or whatever deal you run). **Phone** is next to each builder for the floor."
        )

        b1, b2, b3 = st.columns([1.4, 1.0, 1.0])
        with b1:
            if st.button(
                "Save phone & multipliers · update retail",
                type="primary",
                use_container_width=True,
            ):
                updated_builders = 0
                updated_rows = 0
                for _, r in edited.iterrows():
                    builder = str(r["Builder"])
                    phone = str(r.get("Phone") or "").strip()
                    mult = float(r["Multiplier"])
                    if mult <= 0:
                        continue
                    svc.set_vendor_phone(builder, phone)
                    svc.set_vendor_multiplier(
                        builder,
                        mult,
                        notes="Updated from Vendors tab",
                    )
                    n = svc.reapply_multiplier(mult, vendor=builder)
                    updated_builders += 1
                    updated_rows += int(n or 0)
                st.success(
                    f"Saved phone + mult for **{updated_builders}** builders · "
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
    st.caption(f"Viztech sync: {_viztech_sync_hint()}")

    st.markdown("##### Viztech monthly update")
    st.caption(
        "Every **~30 days** this Mac downloads builder pricelists from "
        "**viztechfurniture.com** and updates the book "
        "(keeps builders Viztech doesn’t have · FN Chair = Level One only)."
    )
    st.info(_viztech_sync_hint())
    vz1, vz2, vz3 = st.columns(3)
    with vz1:
        if st.button("Check Viztech login", use_container_width=True):
            import subprocess

            py = APP_DIR / ".venv" / "bin" / "python"
            script = APP_DIR / "scripts" / "viztech_sync.py"
            with st.spinner("Logging into Viztech…"):
                proc = subprocess.run(
                    [str(py), str(script), "--dry-run"],
                    cwd=str(APP_DIR),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            if proc.returncode == 0:
                st.success("Viztech login OK — builders listed.")
                get_service.clear()
            else:
                st.error("Check failed — see logs below.")
            if proc.stdout:
                st.code(proc.stdout[-2500:])
            if proc.stderr:
                st.code(proc.stderr[-1500:])
    with vz2:
        if st.button(
            "Run full Viztech sync now",
            type="primary",
            use_container_width=True,
            help="Downloads all pricelists and re-imports (can take 10–30+ minutes)",
        ):
            import subprocess

            py = APP_DIR / ".venv" / "bin" / "python"
            script = APP_DIR / "scripts" / "viztech_sync.py"
            with st.spinner(
                "Syncing Viztech → FAF (download + import). Leave this tab open…"
            ):
                proc = subprocess.run(
                    [str(py), str(script)],
                    cwd=str(APP_DIR),
                    capture_output=True,
                    text=True,
                    timeout=14400,
                )
            if proc.returncode == 0:
                get_service.clear()
                st.success("Viztech sync finished. Reloading stats…")
                st.rerun()
            else:
                st.error("Sync failed — check output / viztech-sync.err")
            if proc.stdout:
                st.code(proc.stdout[-4000:])
            if proc.stderr:
                st.code(proc.stderr[-2000:])
    with vz3:
        if st.button("Install 30-day schedule", use_container_width=True):
            import subprocess

            install = (
                Path(__file__).resolve().parent
                / "scripts"
                / "install_viztech_monthly_sync.sh"
            )
            rc = subprocess.call(["/bin/zsh", str(install)])
            if rc == 0:
                st.success("LaunchAgent installed — runs every ~30 days.")
            else:
                st.error(
                    "Install failed — run scripts/install_viztech_monthly_sync.sh in Terminal."
                )

    st.markdown("##### Backup DB")
    st.caption(
        "Saves a snapshot under **Documents/FAF-pricebook-backups**. "
        "Weekly auto-backup: run `scripts/install_weekly_backup.sh` once on this Mac."
    )
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("Backup DB now", type="primary", use_container_width=True):
            try:
                from scripts.backup_db import backup_now

                dest = backup_now()
                st.success(f"Saved `{dest.name}`")
            except Exception as exc:
                st.error(f"Backup failed: {exc}")
    with b2:
        if st.button("Install weekly backup (Sunday 6 AM)", use_container_width=True):
            import subprocess
            import sys

            install = Path(__file__).resolve().parent / "scripts" / "install_weekly_backup.sh"
            rc = subprocess.call(["/bin/zsh", str(install)])
            if rc == 0:
                st.success("Weekly LaunchAgent installed (Sunday 6:00 AM).")
            else:
                st.error("Install failed — run scripts/install_weekly_backup.sh in Terminal.")
    try:
        from scripts.backup_db import list_backups, restore_from

        backups = list_backups(30)
    except Exception:
        backups = []

    if backups:
        st.markdown("##### Restore from backup")
        labels = [
            f"{p.name}  ·  {datetime.fromtimestamp(p.stat().st_mtime).strftime('%b %d %I:%M %p')}"
            for p in backups
        ]
        pick = st.selectbox("Backup file", labels, key="restore_pick")
        confirm = st.checkbox(
            "I understand restore replaces the live price book",
            key="restore_confirm",
        )
        if st.button("Restore selected backup", type="secondary"):
            if not confirm:
                st.warning("Check the confirmation box first.")
            else:
                idx = labels.index(pick)
                try:
                    live = restore_from(backups[idx], also_backup_current=True)
                    # Clear cached service so next load reopens DB connection state
                    get_service.clear()
                    st.success(
                        f"Restored `{backups[idx].name}` → `{live.name}`. "
                        "Reloading…"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Restore failed: {exc}")
    else:
        st.caption("No backups yet — click **Backup DB now**.")

    st.markdown("##### Maintenance")
    m1, m2, m3 = st.columns(3)
    with m1:
        if st.button("Re-standardize master"):
            report = svc.standardize_master()
            st.write(report)
            st.success("Standardize complete")
    with m2:
        if st.button("Scan duplicates"):
            dups = svc.find_duplicates(50)
            if dups.empty:
                st.success("No duplicate identity groups.")
            else:
                st.dataframe(dups, use_container_width=True)
    with m3:
        if st.button("Dry-run cleanup"):
            report = svc.cleanup_duplicates(dry_run=True)
            st.write(report)

    if st.button("Execute cleanup (keep newest)", type="primary"):
        report = svc.cleanup_duplicates(dry_run=False)
        st.success(report)
        st.rerun()

    st.markdown("##### Source files in master")
    sources = svc.list_source_files()
    if sources:
        src = st.selectbox("Source file", sources)
        if st.button("Delete all rows from this source"):
            n = svc.delete_by_source(src)
            st.warning(f"Removed {n:,} rows")

    st.markdown("##### Deploy")
    st.caption(
        "Permanent hosting: Streamlit Community Cloud from GitHub "
        "`Koffeekinggamer/pricebook-system` · main file `pricebook_app.py`. "
        "See **DEPLOY.md**. Public tunnel (this Mac on): `scripts/public_tunnel.sh`."
    )

    st.markdown("##### CLI")
    st.code(
        """
source ~/FAF-pricebook/.venv/bin/activate
python -m backend.cli stats
python -m backend.cli search "oak nightstand"
python scripts/backup_db.py backup
python scripts/backup_db.py list
python scripts/backup_db.py restore --file master_pricebook-YYYYMMDD-HHMMSS.db
python scripts/viztech_sync.py --dry-run
python scripts/viztech_sync.py
        """.strip()
    )

st.caption(
    "FAF Price Book · Search · Drop files · Vendors · Admin · "
    "one builder = one catalog · Viztech sync every ~30 days"
)
