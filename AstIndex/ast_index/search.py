from typing import Any

from .config import Config, load_config
from .database import Database
from .symbol_resolution import SymbolResolver


class SearchEngine:
    def __init__(self, db_path: str | None = None, config: Config | None = None):
        if config:
            self.db = Database(config.db_path)
        elif db_path:
            self.db = Database(db_path)
        else:
            config = load_config()
            self.db = Database(config.db_path)

        self._resolver = None  # Lazy initialization

    def _get_resolver(self) -> SymbolResolver:
        """Get or create SymbolResolver instance."""
        if self._resolver is None:
            self._resolver = SymbolResolver(self.db)
        return self._resolver

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

    def search_definition(
        self,
        symbol_name: str,
        reference_file: str | None = None
    ) -> dict[str, Any] | None:
        """
        Найти определение символа с разрешением импортов.

        Args:
            symbol_name: Имя символа
            reference_file: Опционально: файл, где используется символ

        Returns:
            Словарь с информацией о символе или None
        """
        # Если указан файл - используем резолвер
        if reference_file:
            resolver = self._get_resolver()
            return resolver.resolve_symbol(symbol_name, reference_file)

        # Иначе - ищем все символы с таким именем
        symbols = self.db.get_symbols_by_name(symbol_name)

        if not symbols:
            return None

        # Если один символ - возвращаем его
        if len(symbols) == 1:
            return symbols[0]

        # Если несколько - возвращаем первый (class/interface приоритет)
        for symbol in symbols:
            if symbol["kind"] in ("class", "interface"):
                return symbol

        return symbols[0]

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
