"""
Wide species-matrix Excel import → long-form sellable rows.

Builders ship:
  Item # | Description | Dims | Oak/BM | Rustic tier | Cherry tier | Walnut | …

We store:
  one row per (part × species_tier × finish_state) with base_price.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional, Union

import pandas as pd

# ---------------------------------------------------------------------------
# Species / finish detection
# ---------------------------------------------------------------------------

WOOD_TOKENS = (
    "oak", "maple", "cherry", "walnut", "hickory", "elm", "qswo", "pswo",
    "wormy", "rustic", "birch", "ash", "poplar", "pine", "alder", "beech",
    "mahogany", "sap cherry", "brown maple", "hard maple", "white oak",
    "red oak", "quarter", "1/4 sawn", "rough sawn", "ruff sawn", "barnwood",
    "species", "wood",
)

FINISH_TOKENS = ("finished", "unfinished", "glazed", "fin.", "unf.", "fin ", "unf ")

ID_TOKENS = (
    "item", "part", "sku", "model", "code", "style", "catalog", "stock",
    "item #", "item#", "part #", "part#", "model #", "sku #",
)

DESC_TOKENS = ("description", "descr", "desc.", "name", "product", "title", "item name")

DIM_TOKENS = (
    "dimension", "dims", "size", "w x d x h", "w×d×h", 'h"', 'w"', 'd"',
    "width", "height", "depth", "overall", "wxdxh",
)

SKIP_SHEET_RE = re.compile(
    r"""(?ix)
    ^(markup|mark\s*up|multiplier|multipliers|instructions?|cover|index|index_?|
      settings?|information(\s*sheet)?|customer\s*letter|notes?|toc|
      table\s*of\s*contents|percentage|controls?|options?\s*&\s*portal|
      title\s*page|dealer\s*info.*)$
    """
)

MARKUP_SHEET_RE = re.compile(r"(?i)mark\s*up|multiplier|multipliers")

MONEY_CELL_RE = re.compile(r"^\$?\s*[\d,]+(?:\.\d{1,2})?$")


def _norm(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = str(s).replace("\n", " ").replace("\r", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _norm_key(s) -> str:
    return _norm(s).lower()


def _to_float(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        # Excel serials / huge junk
        f = float(val)
        if f <= 0 or f > 5_000_000:
            # allow small prices like 15; reject obvious non-prices later elsewhere
            if f <= 0:
                return None
        return f
    s = _norm(val)
    if not s or s.lower() in {"nan", "none", "-", "n/a", "na", "n\\a", "#n/a", "#value!", "#ref!"}:
        return None
    if re.fullmatch(r"N/?A", s, re.I):
        return None
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    try:
        f = float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        f = float(m.group())
    if f <= 0 or f > 5_000_000:
        return None
    return f


def looks_like_species_header(col: str) -> bool:
    k = _norm_key(col)
    if not k or k.startswith("unnamed"):
        return False
    # pure finish without wood → not a species tier alone
    if any(t in k for t in WOOD_TOKENS):
        return True
    # column that is only "Finished"/"Unfinished" handled separately
    return False


def looks_like_finish_header(col: str) -> bool:
    k = _norm_key(col)
    return any(t in k for t in FINISH_TOKENS) and not any(
        w in k for w in ("finishing cost", "finish est", "est. finishing", "estimated finishing")
    )


def looks_like_id_header(col: str) -> bool:
    k = _norm_key(col)
    if k in {"item", "item #", "item#", "item number", "item no", "item no.",
             "part", "part #", "part#", "part number", "part no", "sku", "model",
             "model #", "code", "style", "style #", "catalog #", "stock #",
             "item name", "search all items"}:
        return True
    # FVWW-style: long header containing "search all items"
    if "search all items" in k or k.endswith(" items"):
        return True
    return any(k == t or k.startswith(t + " ") or k.endswith(" " + t) for t in ID_TOKENS) and len(k) < 40


def looks_like_desc_header(col: str) -> bool:
    k = _norm_key(col)
    return any(t in k for t in DESC_TOKENS) or k in {"description", "descr.", "desc"}


def looks_like_dim_header(col: str) -> bool:
    k = _norm_key(col)
    if k in {"h", "w", "d", 'h"', 'w"', 'd"', "h'", "w'", "d'"}:
        return True
    return any(t in k for t in DIM_TOKENS)


def classify_column(col: str) -> str:
    """Return: id | desc | dim | species | finish | finish_est | price | other | skip."""
    k = _norm_key(col)
    if not k or k.startswith("unnamed"):
        return "skip"
    if re.search(r"finish(ing)?\s*(cost|est|estimate)", k) or "estimated finishing" in k:
        return "finish_est"
    if looks_like_id_header(col):
        return "id"
    if looks_like_desc_header(col):
        return "desc"
    if looks_like_dim_header(col):
        return "dim"
    if looks_like_species_header(col):
        return "species"
    if looks_like_finish_header(col):
        return "finish"
    if k in {"price", "wholesale", "retail", "cost", "amount", "net", "dealer",
             "whsl. price", "whsl price", "list price", "regular"}:
        return "price"
    if k in {"unit", "uom", "notes", "note", "collection", "series"}:
        return "meta"
    # Multi-line wood blobs often contain newlines already normalized
    wood_hits = sum(1 for t in WOOD_TOKENS if t in k)
    if wood_hits >= 2:
        return "species"
    if wood_hits == 1 and len(k) < 80:
        return "species"
    return "other"


def is_price_column(series: pd.Series, min_hits: int = 3) -> bool:
    """True if a solid share of non-empty cells look like money (not labels)."""
    hits = 0
    nonempty = 0
    for v in series.head(50):
        s = _norm(v)
        if not s:
            continue
        nonempty += 1
        if _to_float(v) is not None:
            hits += 1
    if hits < min_hits:
        return False
    if nonempty == 0:
        return False
    return (hits / nonempty) >= 0.45


# ---------------------------------------------------------------------------
# Header detection & sheet loading
# ---------------------------------------------------------------------------

def find_header_row(raw: pd.DataFrame, max_scan: int = 20) -> int:
    """Pick row with best mix of id/desc/species labels or most wood-token cells."""
    best_i, best_score = 0, -1
    for i in range(min(max_scan, len(raw))):
        row = raw.iloc[i]
        cells = [_norm(v) for v in row.tolist()]
        nonempty = [c for c in cells if c]
        if len(nonempty) < 2:
            continue
        score = 0
        for c in nonempty:
            kind = classify_column(c)
            if kind == "id":
                score += 5
            elif kind == "desc":
                score += 4
            elif kind == "species":
                score += 6
            elif kind == "finish":
                score += 3
            elif kind == "dim":
                score += 2
            elif kind == "price":
                score += 3
            # penalty for pure address/phone junk
            if re.search(r"@|phone|fax|http|township|road|street", c, re.I):
                score -= 4
        # prefer rows with multiple species-like headers
        species_like = sum(1 for c in nonempty if classify_column(c) == "species")
        if species_like >= 2:
            score += 8
        if score > best_score:
            best_score = score
            best_i = i
    return best_i


def dataframe_from_sheet(
    data: bytes,
    sheet_name: Union[str, int],
    engine: Optional[str] = None,
) -> pd.DataFrame:
    bio = io.BytesIO(data)
    kwargs = {"sheet_name": sheet_name, "header": None}
    if engine:
        kwargs["engine"] = engine
    try:
        raw = pd.read_excel(bio, **kwargs)
    except Exception:
        bio.seek(0)
        raw = pd.read_excel(bio, sheet_name=sheet_name, header=None)

    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return raw

    # Reset index after drop
    raw = raw.reset_index(drop=True)
    hdr_i = find_header_row(raw)
    headers = []
    seen = {}
    for j, v in enumerate(raw.iloc[hdr_i].tolist()):
        name = _norm(v) or f"col_{j}"
        # de-dupe
        base = name
        if base in seen:
            seen[base] += 1
            name = f"{base} ({seen[base]})"
        else:
            seen[base] = 1
        headers.append(name)
    body = raw.iloc[hdr_i + 1 :].copy()
    body.columns = headers
    body = body.dropna(how="all")
    return body.reset_index(drop=True)


def list_excel_sheets(data: bytes) -> list[str]:
    bio = io.BytesIO(data)
    try:
        xl = pd.ExcelFile(bio, engine="openpyxl")
    except Exception:
        bio.seek(0)
        try:
            xl = pd.ExcelFile(bio, engine="xlrd")
        except Exception:
            bio.seek(0)
            xl = pd.ExcelFile(bio)
    return list(xl.sheet_names)


def detect_markup_from_workbook(data: bytes, sheet_names: list[str]) -> Optional[float]:
    """Scan Markup sheets for a plausible multiplier (0.5–20 or percent 50–2000)."""
    for name in sheet_names:
        if not MARKUP_SHEET_RE.search(str(name)):
            continue
        try:
            bio = io.BytesIO(data)
            df = pd.read_excel(bio, sheet_name=name, header=None)
        except Exception:
            continue
        candidates = []
        for v in df.to_numpy().ravel()[:200]:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                f = float(v)
                if 1.0 <= f <= 10.0:
                    candidates.append(f)
                elif 100 <= f <= 400:  # percent form e.g. 270
                    candidates.append(f / 100.0)
        # also labeled cells nearby
        for i in range(min(30, len(df))):
            for j in range(min(10, df.shape[1])):
                cell = _norm_key(df.iat[i, j])
                if "markup" in cell or "multiplier" in cell or "mark up" in cell:
                    # look right / below
                    for di, dj in ((0, 1), (1, 0), (0, 2), (1, 1)):
                        ii, jj = i + di, j + dj
                        if 0 <= ii < len(df) and 0 <= jj < df.shape[1]:
                            f = _to_float(df.iat[ii, jj])
                            if f is not None and 0.5 <= f <= 20:
                                candidates.append(f)
                            elif f is not None and 50 <= f <= 400:
                                candidates.append(f / 100.0)
        if candidates:
            # prefer values near 2.7 or 1.7
            candidates.sort(key=lambda x: min(abs(x - 2.7), abs(x - 1.7), abs(x - 1.0)))
            return candidates[0]
    return None


# ---------------------------------------------------------------------------
# Layout classification & unpivot
# ---------------------------------------------------------------------------

@dataclass
class SheetLayout:
    sheet_name: str
    layout: str  # wide_species | wide_finish | long_flat | unknown | skip
    id_col: Optional[str] = None
    desc_col: Optional[str] = None
    dim_cols: list[str] = field(default_factory=list)
    species_cols: list[str] = field(default_factory=list)
    finish_cols: list[str] = field(default_factory=list)
    price_cols: list[str] = field(default_factory=list)
    finish_est_col: Optional[str] = None
    notes: str = ""


def classify_sheet(df: pd.DataFrame, sheet_name: str) -> SheetLayout:
    if SKIP_SHEET_RE.match(str(sheet_name).strip()):
        return SheetLayout(sheet_name, "skip", notes="Non-product sheet")

    if df is None or df.empty or len(df.columns) < 2:
        return SheetLayout(sheet_name, "unknown", notes="Empty sheet")

    kinds = {c: classify_column(c) for c in df.columns}
    # promote "other" columns that are mostly prices
    for c, k in list(kinds.items()):
        if k in ("other", "skip", "meta") and is_price_column(df[c], min_hits=4):
            # if header has wood → species; else price
            if looks_like_species_header(c) or sum(1 for t in WOOD_TOKENS if t in _norm_key(c)) >= 1:
                kinds[c] = "species"
            elif not looks_like_id_header(c) and not looks_like_desc_header(c):
                kinds[c] = "price"

    id_cols = [c for c, k in kinds.items() if k == "id"]
    desc_cols = [c for c, k in kinds.items() if k == "desc"]
    dim_cols = [c for c, k in kinds.items() if k == "dim"]
    species_cols = [c for c, k in kinds.items() if k == "species"]
    finish_cols = [c for c, k in kinds.items() if k == "finish"]
    price_cols = [c for c, k in kinds.items() if k == "price"]
    finish_est = next((c for c, k in kinds.items() if k == "finish_est"), None)

    # If multiple species-like price columns, it's wide_species
    pricey_species = [c for c in species_cols if is_price_column(df[c], min_hits=2)]
    if len(pricey_species) >= 2:
        layout = "wide_species"
        species_cols = pricey_species
    elif len(finish_cols) >= 2 and any(is_price_column(df[c], min_hits=2) for c in finish_cols):
        layout = "wide_finish"
    elif (id_cols or desc_cols) and price_cols:
        layout = "long_flat"
    elif (id_cols or desc_cols) and len(pricey_species) == 1:
        layout = "long_flat"
        price_cols = pricey_species
        species_cols = []
    else:
        # last chance: numeric columns without labels — require a real id column
        numericish = [
            c for c in df.columns
            if kinds.get(c) in ("other", "price", "species") and is_price_column(df[c], min_hits=4)
        ]
        guessed_id = _guess_id_from_values(df)
        if len(numericish) >= 2 and (id_cols or guessed_id):
            layout = "wide_species"
            species_cols = numericish
            if not id_cols and guessed_id:
                id_cols = [guessed_id]
        elif len(numericish) == 1 and (id_cols or desc_cols or guessed_id):
            layout = "long_flat"
            price_cols = numericish
            if not id_cols and guessed_id:
                id_cols = [guessed_id]
        else:
            layout = "unknown"

    return SheetLayout(
        sheet_name=sheet_name,
        layout=layout,
        id_col=id_cols[0] if id_cols else None,
        desc_col=desc_cols[0] if desc_cols else None,
        dim_cols=dim_cols,
        species_cols=species_cols,
        finish_cols=[c for c in finish_cols if is_price_column(df[c], min_hits=2)],
        price_cols=price_cols,
        finish_est_col=finish_est,
        notes=f"kinds: id={len(id_cols)} desc={len(desc_cols)} species={len(species_cols)} finish={len(finish_cols)} price={len(price_cols)}",
    )


def _guess_id_from_values(df: pd.DataFrame) -> Optional[str]:
    """Pick first column that looks like part numbers."""
    for c in df.columns:
        sample = [_norm(v) for v in df[c].head(25).tolist() if _norm(v)]
        if len(sample) < 3:
            continue
        # codes like A591-Q, 100K, SU-BT10, 5885
        hits = sum(
            1 for s in sample
            if re.match(r"^[A-Z0-9][A-Z0-9\-_/]{1,20}$", s, re.I) and not MONEY_CELL_RE.match(s)
        )
        if hits >= 3 and not looks_like_species_header(c):
            return c
    return None


def _combine_dims(row: pd.Series, dim_cols: list[str]) -> Optional[str]:
    if not dim_cols:
        return None
    parts = []
    for c in dim_cols:
        v = _norm(row.get(c))
        if v:
            # label short dim cols
            label = _norm(c)
            if label.lower() in {'h"', 'w"', 'd"', "h", "w", "d"}:
                parts.append(f"{label}{v}" if v[-1] in '"\'' else f"{label}:{v}")
            else:
                parts.append(v)
    if not parts:
        return None
    return " × ".join(parts) if len(parts) > 1 else parts[0]


def _section_collection(row_vals: list, prev: Optional[str]) -> Optional[str]:
    """If a row is a section header (single text cell, no prices), treat as collection."""
    texts = [_norm(v) for v in row_vals if _norm(v)]
    if not texts:
        return prev
    # header-like: 1-3 text cells, no money
    moneys = [v for v in texts if _to_float(v) is not None]
    if moneys:
        return prev
    joined = texts[0]
    if len(texts) <= 2 and 3 <= len(joined) <= 60:
        if re.search(r"(?i)collection|series|bedroom|dining|chairs?|tables?|suite", joined):
            return joined
        # Title Case short phrase
        if joined[0].isupper() and not re.match(r"^[A-Z0-9][A-Z0-9\-_/]{1,16}$", joined):
            return joined
    return prev


def unpivot_wide_species(
    df: pd.DataFrame,
    layout: SheetLayout,
    *,
    default_collection: str = "",
    vendor: str = "",
) -> pd.DataFrame:
    """Expand species columns into long rows."""
    rows = []
    current_collection = default_collection or None
    id_col = layout.id_col or _guess_id_from_values(df)
    desc_col = layout.desc_col
    # if no desc, sometimes description is second text col
    if not desc_col:
        for c in df.columns:
            if c != id_col and classify_column(c) in ("desc", "other"):
                if not is_price_column(df[c], min_hits=5):
                    desc_col = c
                    break

    species_cols = layout.species_cols
    if not species_cols:
        return pd.DataFrame()

    for _, row in df.iterrows():
        vals = row.tolist()
        # section header?
        part = _norm(row[id_col]) if id_col and id_col in row.index else ""
        desc = _norm(row[desc_col]) if desc_col and desc_col in row.index else ""
        any_price = any(_to_float(row[c]) is not None for c in species_cols if c in row.index)

        if not any_price:
            current_collection = _section_collection(vals, current_collection)
            continue

        if not part and not desc:
            continue
        # skip if part looks like a header repeated
        if part and classify_column(part) == "species":
            continue

        dims = _combine_dims(row, layout.dim_cols)
        finish_est = None
        if layout.finish_est_col and layout.finish_est_col in row.index:
            finish_est = _to_float(row[layout.finish_est_col])

        for tier_i, col in enumerate(species_cols, start=1):
            if col not in row.index:
                continue
            price = _to_float(row[col])
            if price is None:
                continue
            notes_parts = []
            if finish_est is not None:
                notes_parts.append(f"finish_est={finish_est}")
            rows.append({
                "vendor": vendor or None,
                "collection": current_collection,
                "part_number": part or None,
                "description": desc or None,
                "dimensions": dims,
                "option_key": None,
                "species": _norm(col),
                "species_tier": tier_i,
                "finish_state": "finished",  # default for species-only matrices
                "base_price": price,
                "price_basis": "wholesale",
                "unit": None,
                "notes": "; ".join(notes_parts) if notes_parts else None,
            })

    return pd.DataFrame(rows)


def unpivot_wide_finish(
    df: pd.DataFrame,
    layout: SheetLayout,
    *,
    default_collection: str = "",
    vendor: str = "",
) -> pd.DataFrame:
    """
    Finished/Unfinished columns — optionally interleaved under species groups.
    Heuristic: pair consecutive Fin/Unf columns; if only finish cols, species unknown.
    """
    rows = []
    current_collection = default_collection or None
    id_col = layout.id_col or _guess_id_from_values(df)
    desc_col = layout.desc_col
    cols = layout.finish_cols or [
        c for c in df.columns if is_price_column(df[c], min_hits=2) and looks_like_finish_header(c)
    ]
    if not cols:
        return pd.DataFrame()

    for _, row in df.iterrows():
        part = _norm(row[id_col]) if id_col and id_col in row.index else ""
        desc = _norm(row[desc_col]) if desc_col and desc_col in row.index else ""
        any_price = any(_to_float(row[c]) is not None for c in cols if c in row.index)
        if not any_price:
            current_collection = _section_collection(row.tolist(), current_collection)
            continue
        if not part and not desc:
            continue
        dims = _combine_dims(row, layout.dim_cols)

        for col in cols:
            price = _to_float(row[col]) if col in row.index else None
            if price is None:
                continue
            k = _norm_key(col)
            if "unf" in k or "unfinished" in k:
                finish_state = "unfinished"
            elif "glaz" in k:
                finish_state = "glazed"
            else:
                finish_state = "finished"
            # species may be encoded in multi-line header above — keep column name
            species = _norm(col)
            rows.append({
                "vendor": vendor or None,
                "collection": current_collection,
                "part_number": part or None,
                "description": desc or None,
                "dimensions": dims,
                "option_key": None,
                "species": species,
                "species_tier": None,
                "finish_state": finish_state,
                "base_price": price,
                "price_basis": "wholesale",
                "unit": None,
                "notes": None,
            })

    return pd.DataFrame(rows)


def extract_long_flat(
    df: pd.DataFrame,
    layout: SheetLayout,
    *,
    default_collection: str = "",
    vendor: str = "",
) -> pd.DataFrame:
    rows = []
    current_collection = default_collection or None
    id_col = layout.id_col or _guess_id_from_values(df)
    desc_col = layout.desc_col
    price_col = layout.price_cols[0] if layout.price_cols else None
    if not price_col:
        # single species col used as price
        for c in layout.species_cols:
            if is_price_column(df[c], min_hits=2):
                price_col = c
                break
    if not price_col:
        for c in df.columns:
            if is_price_column(df[c], min_hits=3) and c != id_col and c != desc_col:
                price_col = c
                break
    if not price_col:
        return pd.DataFrame()

    for _, row in df.iterrows():
        part = _norm(row[id_col]) if id_col and id_col in row.index else ""
        desc = _norm(row[desc_col]) if desc_col and desc_col in row.index else ""
        price = _to_float(row[price_col]) if price_col in row.index else None
        if price is None:
            current_collection = _section_collection(row.tolist(), current_collection)
            continue
        if not part and not desc:
            continue
        dims = _combine_dims(row, layout.dim_cols)
        rows.append({
            "vendor": vendor or None,
            "collection": current_collection,
            "part_number": part or None,
            "description": desc or part or None,
            "dimensions": dims,
            "option_key": None,
            "species": None,
            "species_tier": None,
            "finish_state": None,
            "base_price": price,
            "price_basis": "wholesale",
            "unit": None,
            "notes": None,
        })
    return pd.DataFrame(rows)


def _clean_long_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove info-sheet debris and empty configs."""
    if df.empty:
        return df
    out = df.copy()
    # require a price
    out = out[out["base_price"].notna()]
    # drop absurd micro-prices without a part number (lead-time weeks, etc.)
    has_part = out["part_number"].notna() & (out["part_number"].astype(str).str.strip() != "")
    tiny = out["base_price"] < 20
    out = out[~(tiny & ~has_part)]
    # drop rows where description is clearly instructional
    if "description" in out.columns:
        bad = out["description"].astype(str).str.contains(
            r"(?i)subject to change|purchase order|lead time|please note|table of contents",
            na=False,
        )
        out = out[~bad]
    return out.reset_index(drop=True)


@dataclass
class WorkbookImportResult:
    sheets_tried: list[dict]
    long_df: pd.DataFrame
    detected_markup: Optional[float]
    sheet_names: list[str]
    notes: str = ""


def import_workbook(
    data: bytes,
    *,
    vendor: str = "",
    default_collection: str = "",
    sheet_filter: Optional[list[str]] = None,
    filename: str = "",
) -> WorkbookImportResult:
    """
    Read all product sheets from an Excel workbook, unpivot wide matrices,
    return long-form DataFrame ready for master insert.
    """
    names = list_excel_sheets(data)
    markup = detect_markup_from_workbook(data, names)
    frames = []
    tried = []

    for name in names:
        if sheet_filter is not None and name not in sheet_filter:
            continue
        if SKIP_SHEET_RE.match(str(name).strip()) and (
            sheet_filter is None or name not in (sheet_filter or [])
        ):
            tried.append({"sheet": name, "layout": "skip", "rows": 0, "note": "skipped"})
            continue
        try:
            df = dataframe_from_sheet(data, name)
        except Exception as e:
            tried.append({"sheet": name, "layout": "error", "rows": 0, "note": str(e)})
            continue
        if df.empty:
            tried.append({"sheet": name, "layout": "empty", "rows": 0, "note": ""})
            continue

        layout = classify_sheet(df, name)
        long = pd.DataFrame()
        if layout.layout == "wide_species":
            long = unpivot_wide_species(
                df, layout, default_collection=default_collection or name, vendor=vendor
            )
        elif layout.layout == "wide_finish":
            long = unpivot_wide_finish(
                df, layout, default_collection=default_collection or name, vendor=vendor
            )
        elif layout.layout == "long_flat":
            long = extract_long_flat(
                df, layout, default_collection=default_collection or name, vendor=vendor
            )
        elif layout.layout == "skip":
            tried.append({"sheet": name, "layout": "skip", "rows": 0, "note": layout.notes})
            continue
        else:
            # Conservative fallback: only if we can identify part numbers
            guessed = _guess_id_from_values(df)
            numericish = [c for c in df.columns if is_price_column(df[c], min_hits=4)]
            if guessed and len(numericish) >= 2:
                layout_try = SheetLayout(
                    name, "wide_species",
                    id_col=layout.id_col or guessed,
                    desc_col=layout.desc_col,
                    dim_cols=layout.dim_cols,
                    species_cols=numericish,
                )
                long = unpivot_wide_species(
                    df, layout_try, default_collection=default_collection or name, vendor=vendor
                )
            elif guessed and len(numericish) == 1:
                layout_try = SheetLayout(
                    name, "long_flat",
                    id_col=layout.id_col or guessed,
                    desc_col=layout.desc_col,
                    price_cols=numericish,
                )
                long = extract_long_flat(
                    df, layout_try, default_collection=default_collection or name, vendor=vendor
                )

        # Drop obvious junk rows (tiny prices with no SKU on info pages)
        if long is not None and not long.empty:
            long = _clean_long_rows(long)

        n = len(long) if long is not None and not long.empty else 0
        tried.append({
            "sheet": name,
            "layout": layout.layout,
            "rows": n,
            "note": layout.notes,
            "species_cols": layout.species_cols[:8],
            "id_col": layout.id_col,
            "desc_col": layout.desc_col,
        })
        if n > 0:
            # if collection empty, use sheet name
            if "collection" in long.columns:
                long["collection"] = long["collection"].fillna(name)
                long.loc[long["collection"].astype(str).str.strip() == "", "collection"] = name
            frames.append(long)

    if frames:
        out = pd.concat(frames, ignore_index=True)
    else:
        out = pd.DataFrame(columns=[
            "vendor", "collection", "part_number", "description", "dimensions",
            "option_key", "species", "species_tier", "finish_state", "base_price",
            "price_basis", "unit", "notes",
        ])

    # attach vendor default
    if vendor and not out.empty:
        out["vendor"] = out["vendor"].fillna(vendor)
        out.loc[out["vendor"].isna() | (out["vendor"].astype(str).str.strip() == ""), "vendor"] = vendor

    note = f"{len(names)} sheets · {len(out)} long rows · markup={markup}"
    if filename:
        note = f"{filename}: " + note

    return WorkbookImportResult(
        sheets_tried=tried,
        long_df=out,
        detected_markup=markup,
        sheet_names=names,
        notes=note,
    )
