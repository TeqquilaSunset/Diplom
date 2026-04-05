from typing import Any

from .config import Config, load_config
from .database import Database


class SearchEngine:
    def __init__(self, db_path: str | None = None, config: Config | None = None):
        if config:
            self.db = Database(config.db_path)
        elif db_path:
            self.db = Database(db_path)
        else:
            config = load_config()
            self.db = Database(config.db_path)

    def search(self, query: str, limit: int = 50, level: str = "prefix") -> list[dict[str, Any]]:
        if level == "exact":
            return self.db.get_symbols_by_name(query)[:limit]
        elif level == "prefix":
            fts_query = f'"{query}"*'
            return self.db.search_symbols(fts_query, limit)
        else:
            return self._fuzzy_search(query, limit)

    def _fuzzy_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        cursor = self.db._conn.execute(
            "SELECT * FROM symbols WHERE name LIKE ? ORDER BY name LIMIT ?", (pattern, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def search_class(self, name: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self.db._conn.execute(
            "SELECT * FROM symbols WHERE name LIKE ? AND kind IN ('class', 'interface') ORDER BY name LIMIT ?",
            (f"%{name}%", limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def search_usages(self, symbol_name: str, limit: int = 100) -> dict[str, Any]:
        usages = self.db.get_usages(symbol_name)[:limit]
        definitions = self.db.get_symbols_by_name(symbol_name)
        return {
            "symbol": symbol_name,
            "definitions": definitions,
            "references": usages,
        }

    def search_inheritance(self, symbol_name: str, direction: str = "children") -> dict[str, Any]:
        result = {
            "symbol": symbol_name,
            "children": [],
            "parents": [],
        }
        if direction in ("children", "both"):
            result["children"] = self.db.get_children(symbol_name)
        if direction in ("parents", "both"):
            result["parents"] = self.db.get_parents(symbol_name)
        return result

    def search_by_kind(self, kind: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.get_symbols_by_kind(kind)[:limit]

    def search_in_file(self, file_path: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.db._conn.execute(
            "SELECT * FROM symbols WHERE file_path = ? ORDER BY line_start LIMIT ?",
            (file_path, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
