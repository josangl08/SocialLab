"""Supabase en memoria con filtros reales (eq, neq, gte, in_) para tests de servicios."""
from typing import Any, Dict, List
from unittest.mock import MagicMock


class _Query:
    def __init__(self, store: Dict[str, List[Dict[str, Any]]], table: str):
        self.store, self.table = store, table
        self.filters: List = []
        self.op = "select"
        self.payload: Any = None
        self.on_conflict: str = ""

    def select(self, *_a, **_kw): self.op = "select"; return self
    def insert(self, data): self.op, self.payload = "insert", data; return self
    def update(self, data): self.op, self.payload = "update", data; return self
    def delete(self): self.op = "delete"; return self

    def upsert(self, data, on_conflict: str = ""):
        self.op, self.payload, self.on_conflict = "upsert", data, on_conflict
        return self

    def eq(self, col, val): self.filters.append(lambda r: r.get(col) == val); return self
    def neq(self, col, val): self.filters.append(lambda r: r.get(col) != val); return self
    def gte(self, col, val): self.filters.append(lambda r: str(r.get(col)) >= str(val)); return self
    def in_(self, col, vals): self.filters.append(lambda r: r.get(col) in vals); return self
    def order(self, *_a, **_kw): return self
    def limit(self, _n): return self

    def _match(self, row): return all(f(row) for f in self.filters)

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.op == "insert":
            new = {"id": len(rows) + 1, **self.payload}
            rows.append(new)
            return MagicMock(data=[new])
        if self.op == "upsert":
            keys = [k.strip() for k in self.on_conflict.split(",") if k.strip()]
            for row in rows:
                if keys and all(row.get(k) == self.payload.get(k) for k in keys):
                    row.update(self.payload)
                    return MagicMock(data=[row])
            new = {"id": len(rows) + 1, **self.payload}
            rows.append(new)
            return MagicMock(data=[new])
        matched = [r for r in rows if self._match(r)]
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
        elif self.op == "delete":
            self.store[self.table] = [r for r in rows if not self._match(r)]
        return MagicMock(data=[dict(r) for r in matched])


class FakeSupabase:
    def __init__(self, tables: Dict[str, List[Dict[str, Any]]]):
        self.store = {k: [dict(r) for r in v] for k, v in tables.items()}

    def table(self, name: str) -> _Query:
        return _Query(self.store, name)
