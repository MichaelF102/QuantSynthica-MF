"""Partitioned Parquet store for NAV observations: <root>/year=YYYY/nav.parquet.

Columns: amfi_code (str), date (date32), nav (float64), source (str). Key: (amfi_code, date).
Upserts are idempotent: re-writing the same rows leaves the store unchanged. Writes are atomic (tmp + rename).
"""
from __future__ import annotations

import fcntl
import os
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = pa.schema([("amfi_code", pa.string()), ("date", pa.date32()), ("nav", pa.float64()), ("source", pa.string())])


# Rows are written sorted by (amfi_code, date) in groups of this size, so a read of a few funds can skip nearly every group
# using the min/max statistics instead of decompressing a whole year (which needs ~130 MB).
ROW_GROUP = 50_000


class NavStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, year: int) -> Path:
        return self.root / f"year={year}" / "nav.parquet"

    @contextmanager
    def _lock(self):
        """Exclusive cross-process lock: upserts are read-modify-write and must not interleave."""
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / ".lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def upsert(self, rows: Iterable[tuple[str, date, float, str]]) -> dict[str, int]:
        """Insert or replace by (amfi_code, date). Returns counts of {inserted, updated, unchanged}."""
        by_year: dict[int, dict[tuple[str, date], tuple[float, str]]] = defaultdict(dict)
        for code, d, nav, src in rows:
            by_year[d.year][(code, d)] = (nav, src)
        with self._lock():
            return self._upsert_locked(by_year)

    def _upsert_locked(self, by_year) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        for year, new in by_year.items():
            path = self._path(year)
            existing: dict[tuple[str, date], tuple[float, str]] = {}
            if path.exists():
                t = pq.read_table(path).to_pydict()
                existing = {(c, d): (n, s) for c, d, n, s in zip(t["amfi_code"], t["date"], t["nav"], t["source"])}
            changed = False
            for key, val in new.items():
                if key not in existing:
                    counts["inserted"] += 1
                    changed = True
                elif existing[key][0] != val[0]:
                    counts["updated"] += 1
                    changed = True
                else:
                    counts["unchanged"] += 1
                    continue
                existing[key] = val
            if not changed:
                continue
            keys = sorted(existing)
            table = pa.table(
                {"amfi_code": [k[0] for k in keys], "date": [k[1] for k in keys],
                 "nav": [existing[k][0] for k in keys], "source": [existing[k][1] for k in keys]},
                schema=SCHEMA,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"nav.{uuid.uuid4().hex}.tmp")
            pq.write_table(table, tmp, compression="zstd", row_group_size=ROW_GROUP)
            os.replace(tmp, path)
        return counts

    def compact(self) -> int:
        """Rewrite existing year files with small row groups (one-off for stores written before ROW_GROUP existed). Returns files rewritten."""
        n = 0
        with self._lock():
            for part in sorted(self.root.glob("year=*/nav.parquet")):
                if pq.ParquetFile(part).metadata.num_row_groups > 1 and pq.ParquetFile(part).metadata.row_group(0).num_rows <= ROW_GROUP:
                    continue
                table = pq.read_table(part).sort_by([("amfi_code", "ascending"), ("date", "ascending")])
                tmp = part.with_name(f"nav.{uuid.uuid4().hex}.tmp")
                pq.write_table(table, tmp, compression="zstd", row_group_size=ROW_GROUP)
                os.replace(tmp, part)
                n += 1
        return n

    def read(self, codes: Iterable[str] | None = None, start: date | None = None, end: date | None = None) -> Mapping[str, list[tuple[date, float]]]:
        wanted = sorted(set(codes)) if codes is not None else None
        out: dict[str, list[tuple[date, float]]] = defaultdict(list)
        if not self.root.exists() or wanted == []:
            return out
        filters = []
        if wanted is not None:
            filters.append(("amfi_code", "in", wanted))  # pushed down to Parquet row groups
        if start is not None:
            filters.append(("date", ">=", start))
        if end is not None:
            filters.append(("date", "<=", end))
        for part in sorted(self.root.glob("year=*/nav.parquet")):
            year = int(part.parent.name.split("=")[1])
            if (start and year < start.year) or (end and year > end.year):
                continue
            t = pq.read_table(part, columns=["amfi_code", "date", "nav"], filters=filters or None).to_pydict()
            for c, d, n in zip(t["amfi_code"], t["date"], t["nav"]):
                out[c].append((d, n))
        for v in out.values():
            v.sort()
        return out

    def read_frames(self, codes: Iterable[str]) -> dict:
        """{code: pandas Series of NAV indexed by Timestamp}. Reads one year file at a time and converts columnar data directly,
        so peak memory stays near the size of the requested series (the tuple-based `read` costs ~10x more)."""
        import pandas as pd

        wanted = sorted(set(codes))
        if not self.root.exists() or not wanted:
            return {}
        parts = []
        for part in sorted(self.root.glob("year=*/nav.parquet")):
            t = pq.read_table(part, columns=["amfi_code", "date", "nav"], filters=[("amfi_code", "in", wanted)])  # prunes row groups by statistics
            if t.num_rows:
                df = t.to_pandas()
                df["date"] = pd.to_datetime(df["date"])
                parts.append(df)
            del t
        pa.default_memory_pool().release_unused()
        if not parts:
            return {}
        df = pd.concat(parts, ignore_index=True)
        out = {}
        for code, g in df.groupby("amfi_code", sort=False):
            out[code] = pd.Series(g["nav"].to_numpy(dtype=float), index=pd.DatetimeIndex(g["date"])).sort_index()
        return out

    def summary(self, codes: Iterable[str] | None = None) -> dict[str, tuple[date, date, int]]:
        """(first date, last date, observation count) per code, streamed partition by partition."""
        wanted = set(codes) if codes is not None else None
        out: dict[str, list] = {}
        for part in sorted(self.root.glob("year=*/nav.parquet")) if self.root.exists() else []:
            t = pq.read_table(part, columns=["amfi_code", "date"]).to_pydict()
            for c, d in zip(t["amfi_code"], t["date"]):
                if wanted is not None and c not in wanted:
                    continue
                cur = out.get(c)
                if cur is None:
                    out[c] = [d, d, 1]
                else:
                    cur[0] = min(cur[0], d)
                    cur[1] = max(cur[1], d)
                    cur[2] += 1
        return {c: (v[0], v[1], v[2]) for c, v in out.items()}

    def row_count(self) -> int:
        return sum(pq.ParquetFile(p).metadata.num_rows for p in self.root.glob("year=*/nav.parquet")) if self.root.exists() else 0
