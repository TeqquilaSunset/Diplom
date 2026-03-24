import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import FileInfo, Symbol, Inheritance, Reference


class Database:
    SCHEMA_VERSION = 1

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._create_triggers()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                last_modified REAL NOT NULL,
                size INTEGER NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                col_start INTEGER DEFAULT 0,
                col_end INTEGER DEFAULT 0,
                signature TEXT,
                docstring TEXT,
                parent TEXT,
                scope TEXT,
                FOREIGN KEY (file_path) REFERENCES files(path)
            );
            
            CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
                name,
                content='symbols',
                content_rowid='id'
            );
            
            CREATE TABLE IF NOT EXISTS inheritance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_symbol TEXT NOT NULL,
                child_file TEXT NOT NULL,
                parent_symbol TEXT NOT NULL,
                parent_file TEXT,
                kind TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_name TEXT NOT NULL,
                symbol_file TEXT NOT NULL,
                ref_file TEXT NOT NULL,
                ref_line INTEGER NOT NULL,
                ref_col INTEGER NOT NULL,
                ref_kind TEXT NOT NULL,
                context TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
            CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_inheritance_child ON inheritance(child_symbol);
            CREATE INDEX IF NOT EXISTS idx_inheritance_parent ON inheritance(parent_symbol);
            CREATE INDEX IF NOT EXISTS idx_refs_symbol ON refs(symbol_name);
            CREATE INDEX IF NOT EXISTS idx_refs_file ON refs(ref_file);
        """)

    def _create_triggers(self):
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
                INSERT INTO symbols_fts(rowid, name) VALUES (new.id, new.name);
            END;
            
            CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
                INSERT INTO symbols_fts(symbols_fts, rowid, name) VALUES('delete', old.id, old.name);
            END;
            
            CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
                INSERT INTO symbols_fts(symbols_fts, rowid, name) VALUES('delete', old.id, old.name);
                INSERT INTO symbols_fts(rowid, name) VALUES (new.id, new.name);
            END;
        """)

    @contextmanager
    def transaction(self):
        self._conn.execute("BEGIN TRANSACTION")
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def insert_file(self, file_info: FileInfo) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO files (path, language, content_hash, last_modified, size)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                file_info.path,
                file_info.language,
                file_info.content_hash,
                file_info.last_modified,
                file_info.size,
            ),
        )

    def get_file(self, path: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
        return dict(row) if row else None

    def delete_file(self, path: str) -> None:
        self._conn.execute("DELETE FROM files WHERE path = ?", (path,))

    def get_all_files(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self._conn.execute("SELECT * FROM files")]

    def insert_symbol(self, symbol: Symbol) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO symbols (name, kind, file_path, line_start, line_end, 
                                 col_start, col_end, signature, docstring, parent, scope)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                symbol.name,
                symbol.kind,
                symbol.file_path,
                symbol.line_start,
                symbol.line_end,
                symbol.col_start,
                symbol.col_end,
                symbol.signature,
                symbol.docstring,
                symbol.parent,
                symbol.scope,
            ),
        )
        return cursor.lastrowid

    def insert_symbols(self, symbols: List[Symbol]) -> None:
        for symbol in symbols:
            self.insert_symbol(symbol)

    def delete_symbols_for_file(self, file_path: str) -> None:
        self._conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))

    def search_symbols(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT s.* FROM symbols s
            JOIN symbols_fts fts ON s.id = fts.rowid
            WHERE symbols_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (query, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_symbols_by_name(self, name: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM symbols WHERE name = ?", (name,)).fetchall()
        return [dict(row) for row in rows]

    def get_symbols_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM symbols WHERE kind = ?", (kind,)).fetchall()
        return [dict(row) for row in rows]

    def insert_inheritance(self, inheritance: Inheritance) -> None:
        self._conn.execute(
            """
            INSERT INTO inheritance (child_symbol, child_file, parent_symbol, parent_file, kind)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                inheritance.child_symbol,
                inheritance.child_file,
                inheritance.parent_symbol,
                inheritance.parent_file,
                inheritance.kind,
            ),
        )

    def insert_inheritances(self, inheritances: List[Inheritance]) -> None:
        for inh in inheritances:
            self.insert_inheritance(inh)

    def delete_inheritance_for_file(self, file_path: str) -> None:
        self._conn.execute("DELETE FROM inheritance WHERE child_file = ?", (file_path,))

    def get_children(self, parent_symbol: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM inheritance WHERE parent_symbol = ?", (parent_symbol,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_parents(self, child_symbol: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM inheritance WHERE child_symbol = ?", (child_symbol,)
        ).fetchall()
        return [dict(row) for row in rows]

    def insert_reference(self, reference: Reference) -> None:
        self._conn.execute(
            """
            INSERT INTO refs (symbol_name, symbol_file, ref_file, ref_line, ref_col, ref_kind, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                reference.symbol_name,
                reference.symbol_file,
                reference.ref_file,
                reference.ref_line,
                reference.ref_col,
                reference.ref_kind,
                reference.context,
            ),
        )

    def insert_references(self, references: List[Reference]) -> None:
        for ref in references:
            self.insert_reference(ref)

    def delete_refs_for_file(self, file_path: str) -> None:
        self._conn.execute("DELETE FROM refs WHERE ref_file = ?", (file_path,))

    def get_usages(self, symbol_name: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM refs WHERE symbol_name = ?", (symbol_name,)
        ).fetchall()
        return [dict(row) for row in rows]

    def set_metadata(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
        )

    def get_metadata(self, key: str) -> Optional[str]:
        row = self._conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def get_stats(self) -> Dict[str, int]:
        return {
            "files": self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
            "symbols": self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0],
            "inheritances": self._conn.execute("SELECT COUNT(*) FROM inheritance").fetchone()[0],
            "references": self._conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0],
        }

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
