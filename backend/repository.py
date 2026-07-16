"""Data access for pricebook + vendors tables."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union  # noqa: F401 — Optional used throughout

import pandas as pd

from backend.config import DEFAULT_MULTIPLIER, DEFAULT_SEARCH_LIMIT, IDENTITY_FIELDS
from backend.db import get_connection
from backend.models import PRICEBOOK_COLS, SELECT_COLS


def _norm_key_val(v) -> str:
    if v is None:
        return ""
    s = str(v).strip().lower()
    if s in {"none", "nan", "null"}:
        return ""
    return s


def identity_key(row: dict) -> tuple:
    return tuple(_norm_key_val(row.get(f)) for f in IDENTITY_FIELDS)


class PriceBookRepository:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = db_path

    def _conn(self):
        return get_connection(self.db_path)

    # ------------------------------------------------------------------ stats
    def row_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM pricebook").fetchone()[0]

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM pricebook").fetchone()[0]
            vendors = conn.execute(
                "SELECT COUNT(DISTINCT vendor) FROM pricebook "
                "WHERE vendor IS NOT NULL AND vendor != ''"
            ).fetchone()[0]
            collections = conn.execute(
                "SELECT COUNT(DISTINCT collection) FROM pricebook "
                "WHERE collection IS NOT NULL AND collection != ''"
            ).fetchone()[0]
            sources = conn.execute(
                "SELECT COUNT(DISTINCT source_file) FROM pricebook "
                "WHERE source_file IS NOT NULL AND source_file != ''"
            ).fetchone()[0]
        return {
            "rows": total,
            "vendors": vendors,
            "collections": collections,
            "source_files": sources,
        }

    # ------------------------------------------------------------------ lists
    def list_vendors(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT vendor FROM pricebook "
                "WHERE vendor IS NOT NULL AND vendor != '' "
                "ORDER BY vendor"
            ).fetchall()
        return [r[0] for r in rows]

    def list_collections(self, vendor: Optional[str] = None) -> list[str]:
        with self._conn() as conn:
            if vendor:
                rows = conn.execute(
                    "SELECT DISTINCT collection FROM pricebook "
                    "WHERE collection IS NOT NULL AND collection != '' "
                    "AND vendor = ? ORDER BY collection",
                    (vendor,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT collection FROM pricebook "
                    "WHERE collection IS NOT NULL AND collection != '' "
                    "ORDER BY collection"
                ).fetchall()
        return [r[0] for r in rows]

    def list_source_files(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT source_file FROM pricebook "
                "WHERE source_file IS NOT NULL AND source_file != '' "
                "ORDER BY source_file"
            ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ search
    def search(
        self,
        query: str = "",
        *,
        collection: Optional[str] = None,
        vendor: Optional[str] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> pd.DataFrame:
        clauses: list[str] = []
        params: list = []

        if query and query.strip():
            for token in query.strip().split():
                like = f"%{token}%"
                clauses.append(
                    "(vendor LIKE ? OR collection LIKE ? OR part_number LIKE ? "
                    "OR description LIKE ? OR species LIKE ? OR dimensions LIKE ? "
                    "OR notes LIKE ? OR source_file LIKE ? OR finish_state LIKE ?)"
                )
                params.extend([like] * 9)

        if collection and collection != "All":
            clauses.append("collection = ?")
            params.append(collection)
        if vendor and vendor != "All":
            clauses.append("vendor = ?")
            params.append(vendor)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        cols = ", ".join(SELECT_COLS)
        sql = f"""
            SELECT {cols}
            FROM pricebook
            {where}
            ORDER BY vendor, collection, part_number, species_tier, description
            LIMIT ?
        """
        params.append(int(limit))

        with self._conn() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # ------------------------------------------------------------------ write
    def insert_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        placeholders = ",".join("?" * len(PRICEBOOK_COLS))
        sql = (
            f"INSERT INTO pricebook ({','.join(PRICEBOOK_COLS)}) "
            f"VALUES ({placeholders})"
        )
        values = [tuple(r.get(c) for c in PRICEBOOK_COLS) for r in rows]
        with self._conn() as conn:
            conn.executemany(sql, values)
            conn.commit()
            return len(values)

    def delete_by_source(self, source_file: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM pricebook WHERE source_file = ?", (source_file,)
            )
            conn.commit()
            return cur.rowcount

    def delete_by_vendor(self, vendor: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM pricebook WHERE vendor = ?", (vendor,))
            conn.commit()
            return cur.rowcount

    def upsert_rows(self, rows: list[dict]) -> dict:
        """
        Insert new configs; update base_price/multiplier/adjusted when identity matches.

        Identity = vendor + collection + part_number + species + finish_state
                    + option_key + dimensions (null-safe).

        Returns counts: inserted, updated, skipped.
        """
        if not rows:
            return {"inserted": 0, "updated": 0, "skipped": 0, "total": 0}

        # Load existing keys for vendors present in batch (scoped for speed)
        vendors = {r.get("vendor") for r in rows if r.get("vendor")}
        existing: dict[tuple, int] = {}
        with self._conn() as conn:
            if vendors:
                for vend in vendors:
                    cur = conn.execute(
                        f"SELECT id, {', '.join(IDENTITY_FIELDS)} FROM pricebook "
                        "WHERE vendor = ?",
                        (vend,),
                    )
                    for row in cur.fetchall():
                        d = {f: row[f] for f in IDENTITY_FIELDS}
                        d["id"] = row["id"]
                        existing[identity_key(d)] = row["id"]
            else:
                cur = conn.execute(
                    f"SELECT id, {', '.join(IDENTITY_FIELDS)} FROM pricebook"
                )
                for row in cur.fetchall():
                    d = {f: row[f] for f in IDENTITY_FIELDS}
                    existing[identity_key(d)] = row["id"]

            to_insert = []
            updated = 0
            skipped = 0
            for r in rows:
                key = identity_key(r)
                # require at least part or description + price
                if r.get("base_price") is None and not (
                    r.get("part_number") or r.get("description")
                ):
                    skipped += 1
                    continue
                if key in existing and any(key):  # empty key still inserts
                    # all-empty identity → always insert to avoid mass collision
                    if not any(key):
                        to_insert.append(r)
                        continue
                    rid = existing[key]
                    conn.execute(
                        """
                        UPDATE pricebook SET
                            description = COALESCE(?, description),
                            base_price = ?,
                            price_basis = COALESCE(?, price_basis),
                            multiplier = ?,
                            adjusted_price = ?,
                            unit = COALESCE(?, unit),
                            notes = COALESCE(?, notes),
                            source_file = ?,
                            imported_at = ?,
                            species_tier = COALESCE(?, species_tier)
                        WHERE id = ?
                        """,
                        (
                            r.get("description"),
                            r.get("base_price"),
                            r.get("price_basis"),
                            r.get("multiplier"),
                            r.get("adjusted_price"),
                            r.get("unit"),
                            r.get("notes"),
                            r.get("source_file"),
                            r.get("imported_at"),
                            r.get("species_tier"),
                            rid,
                        ),
                    )
                    updated += 1
                else:
                    to_insert.append(r)
                    # prevent dupes within same batch
                    if any(key):
                        existing[key] = -1

            inserted = 0
            if to_insert:
                placeholders = ",".join("?" * len(PRICEBOOK_COLS))
                sql = (
                    f"INSERT INTO pricebook ({','.join(PRICEBOOK_COLS)}) "
                    f"VALUES ({placeholders})"
                )
                values = [tuple(r.get(c) for c in PRICEBOOK_COLS) for r in to_insert]
                conn.executemany(sql, values)
                inserted = len(values)

            conn.commit()

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "total": inserted + updated,
        }

    def find_duplicate_groups(self, limit: int = 100) -> pd.DataFrame:
        """Groups sharing the same identity key with count > 1."""
        fields = ", ".join(IDENTITY_FIELDS)
        coalesce_parts = [
            f"COALESCE(LOWER(TRIM({f})), '')" for f in IDENTITY_FIELDS
        ]
        group_expr = " || '|' || ".join(coalesce_parts)
        sql = f"""
            SELECT {fields}, COUNT(*) AS dup_count
            FROM pricebook
            GROUP BY {group_expr}
            HAVING COUNT(*) > 1
            ORDER BY dup_count DESC
            LIMIT ?
        """
        with self._conn() as conn:
            return pd.read_sql_query(sql, conn, params=(limit,))

    def cleanup_duplicates(self, *, dry_run: bool = True) -> dict:
        """
        Keep newest imported_at (then highest id) per identity group; delete rest.

        Returns counts and optional sample of deleted ids when dry_run.
        """
        fields = ", ".join(IDENTITY_FIELDS)
        coalesce_parts = [
            f"COALESCE(LOWER(TRIM({f})), '')" for f in IDENTITY_FIELDS
        ]
        group_expr = " || '|' || ".join(coalesce_parts)

        with self._conn() as conn:
            groups = conn.execute(
                f"""
                SELECT {group_expr} AS gkey, COUNT(*) AS c
                FROM pricebook
                GROUP BY gkey
                HAVING c > 1
                """
            ).fetchall()

            to_delete: list[int] = []
            for g in groups:
                # empty identity keys — skip mass delete
                if not g["gkey"] or set(g["gkey"].split("|")) <= {""}:
                    continue
                rows = conn.execute(
                    f"""
                    SELECT id, imported_at FROM pricebook
                    WHERE {group_expr} = ?
                    ORDER BY
                        CASE WHEN imported_at IS NULL OR imported_at = '' THEN 0 ELSE 1 END DESC,
                        imported_at DESC,
                        id DESC
                    """,
                    (g["gkey"],),
                ).fetchall()
                # keep first
                for r in rows[1:]:
                    to_delete.append(int(r["id"]))

            if dry_run:
                return {
                    "dry_run": True,
                    "groups": len(groups),
                    "would_delete": len(to_delete),
                    "sample_ids": to_delete[:30],
                }

            deleted = 0
            # chunk deletes
            chunk = 500
            for i in range(0, len(to_delete), chunk):
                batch = to_delete[i : i + chunk]
                placeholders = ",".join("?" * len(batch))
                cur = conn.execute(
                    f"DELETE FROM pricebook WHERE id IN ({placeholders})", batch
                )
                deleted += cur.rowcount
            conn.commit()
            return {
                "dry_run": False,
                "groups": len(groups),
                "deleted": deleted,
            }

    def get_row_by_id(self, row_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT {', '.join(SELECT_COLS)} FROM pricebook WHERE id = ?",
                (row_id,),
            ).fetchone()
            return dict(row) if row else None

    def vendor_summary(self) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql_query(
                """
                SELECT
                    p.vendor,
                    COUNT(*) AS rows,
                    COUNT(DISTINCT p.collection) AS collections,
                    COUNT(DISTINCT p.source_file) AS source_files,
                    MIN(p.base_price) AS min_base,
                    MAX(p.base_price) AS max_base,
                    AVG(p.multiplier) AS avg_mult,
                    v.multiplier AS saved_mult,
                    v.updated_at AS mult_updated
                FROM pricebook p
                LEFT JOIN vendors v ON v.name = p.vendor
                WHERE p.vendor IS NOT NULL AND p.vendor != ''
                GROUP BY p.vendor
                ORDER BY rows DESC
                """,
                conn,
            )

    # ------------------------------------------------------------------ pricing bulk
    def reapply_multiplier(
        self,
        new_mult: float,
        *,
        vendor: Optional[str] = None,
    ) -> int:
        with self._conn() as conn:
            if vendor:
                cur = conn.execute(
                    """
                    UPDATE pricebook
                    SET multiplier = ?, adjusted_price = ROUND(base_price * ?, 2)
                    WHERE base_price IS NOT NULL AND vendor = ?
                    """,
                    (new_mult, new_mult, vendor),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE pricebook
                    SET multiplier = ?, adjusted_price = ROUND(base_price * ?, 2)
                    WHERE base_price IS NOT NULL
                    """,
                    (new_mult, new_mult),
                )
            conn.commit()
            return cur.rowcount

    def recompute_adjusted(self, vendor: Optional[str] = None) -> int:
        """Recompute retail from each row's own multiplier."""
        with self._conn() as conn:
            if vendor:
                cur = conn.execute(
                    """
                    UPDATE pricebook
                    SET adjusted_price = ROUND(base_price * multiplier, 2)
                    WHERE base_price IS NOT NULL AND multiplier IS NOT NULL
                      AND vendor = ?
                    """,
                    (vendor,),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE pricebook
                    SET adjusted_price = ROUND(base_price * multiplier, 2)
                    WHERE base_price IS NOT NULL AND multiplier IS NOT NULL
                    """
                )
            conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------------ vendors table
    def get_vendor_multiplier(
        self, vendor: str, default: float = DEFAULT_MULTIPLIER
    ) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT multiplier FROM vendors WHERE name = ?", (vendor,)
            ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
        return default

    def set_vendor_multiplier(
        self, vendor: str, multiplier: float, notes: str = ""
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO vendors (name, multiplier, notes, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    multiplier = excluded.multiplier,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (vendor, multiplier, notes or None, now),
            )
            conn.commit()

    def list_vendor_settings(self) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql_query(
                "SELECT name, multiplier, notes, updated_at FROM vendors ORDER BY name",
                conn,
            )
