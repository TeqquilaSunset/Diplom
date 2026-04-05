import time
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .constants import BATCH_SIZE
from .database import Database
from .models import ParsedFile
from .parsers import get_parser
from .utils.file_utils import djb2_hash, get_file_info, scan_files
from .utils.logging import get_logger

logger = get_logger(__name__)


class Indexer:
    def __init__(self, config: Config | None = None, root: Path | None = None):
        if config:
            self.config = config
        else:
            self.config = load_config(root or Path.cwd())

        self.db = Database(self.config.db_path)
        self._parsers: dict[str, Any] = {}

    def _get_parser(self, language: str):
        if language not in self._parsers:
            parser_cls = get_parser(language)
            if parser_cls:
                self._parsers[language] = parser_cls()
        return self._parsers.get(language)

    def index(self) -> dict[str, int]:
        logger.info(f"Starting full index of {self.config.root}")
        start_time = time.time()

        stats = {
            "files_indexed": 0,
            "symbols_indexed": 0,
            "inheritances_indexed": 0,
            "references_indexed": 0,
            "errors": 0,
        }

        files_batch: list[tuple] = []

        for file_path, language in scan_files(
            self.config.root,
            self.config.includes,
            self.config.excludes,
        ):
            files_batch.append((file_path, language))

            if len(files_batch) >= BATCH_SIZE:
                batch_stats = self._process_batch(files_batch)
                self._merge_stats(stats, batch_stats)
                files_batch = []

        if files_batch:
            batch_stats = self._process_batch(files_batch)
            self._merge_stats(stats, batch_stats)

        self.db.set_metadata("last_index_time", str(time.time()))
        self.db.set_metadata("schema_version", "1")

        elapsed = time.time() - start_time
        logger.info(f"Indexing complete in {elapsed:.2f}s: {stats}")

        return stats

    def update(self) -> dict[str, int]:
        logger.info(f"Starting incremental update of {self.config.root}")
        start_time = time.time()

        stats = {
            "files_added": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "symbols_indexed": 0,
            "inheritances_indexed": 0,
            "errors": 0,
        }

        existing_files = {f["path"]: f for f in self.db.get_all_files()}
        current_files = set()

        files_to_process: list[tuple] = []

        for file_path, language in scan_files(
            self.config.root,
            self.config.includes,
            self.config.excludes,
        ):
            path_str = str(file_path.resolve())
            current_files.add(path_str)

            existing = existing_files.get(path_str)
            if existing:
                stat = file_path.stat()
                if stat.st_mtime > existing["last_modified"] or stat.st_size != existing["size"]:
                    files_to_process.append((file_path, language, "modified"))
            else:
                files_to_process.append((file_path, language, "added"))

        deleted_paths = set(existing_files.keys()) - current_files
        for path_str in deleted_paths:
            self._delete_file(path_str)
            stats["files_deleted"] += 1

        batch: list[tuple] = []
        for item in files_to_process:
            if len(item) == 3:
                file_path, language, change_type = item
            else:
                file_path, language = item
                change_type = "added"

            batch.append((file_path, language, change_type))

            if len(batch) >= BATCH_SIZE:
                added_count = sum(1 for _, _, ct in batch if ct == "added")
                modified_count = len(batch) - added_count
                batch_stats = self._process_batch([(fp, lang) for fp, lang, _ in batch])
                self._merge_stats(stats, batch_stats)
                stats["files_added"] += added_count
                stats["files_modified"] += modified_count
                batch = []

        if batch:
            added_count = sum(1 for _, _, ct in batch if ct == "added")
            modified_count = len(batch) - added_count
            batch_stats = self._process_batch([(fp, lang) for fp, lang, _ in batch])
            self._merge_stats(stats, batch_stats)
            stats["files_added"] += added_count
            stats["files_modified"] += modified_count

        elapsed = time.time() - start_time
        logger.info(f"Update complete in {elapsed:.2f}s: {stats}")

        return stats

    def rebuild(self) -> dict[str, int]:
        logger.info(f"Rebuilding index for {self.config.root}")

        self._clear_all()

        return self.index()

    def _process_batch(self, files: list[tuple]) -> dict[str, int]:
        stats = {
            "files_indexed": 0,
            "symbols_indexed": 0,
            "inheritances_indexed": 0,
            "references_indexed": 0,
            "errors": 0,
        }

        with self.db.transaction():
            for file_path, language in files:
                try:
                    parsed = self._parse_file(file_path, language)
                    if parsed:
                        self._store_parsed_file(parsed)
                        stats["files_indexed"] += 1
                        stats["symbols_indexed"] += len(parsed.symbols)
                        stats["inheritances_indexed"] += len(parsed.inheritances)
                        stats["references_indexed"] += len(parsed.references)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    stats["errors"] += 1

        return stats

    def _parse_file(self, file_path: Path, language: str) -> ParsedFile | None:
        parser = self._get_parser(language)
        if not parser:
            logger.warning(f"No parser for language: {language}")
            return None

        if not parser.can_parse(file_path):
            return None

        try:
            content = file_path.read_bytes()

            file_info = get_file_info(file_path, language)
            file_info.content_hash = djb2_hash(content)

            parsed = parser.parse(file_path, content)
            parsed.file_info = file_info

            return parsed
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def _store_parsed_file(self, parsed: ParsedFile):
        file_info = parsed.file_info

        self.db.delete_symbols_for_file(file_info.path)
        self.db.delete_inheritance_for_file(file_info.path)
        self.db.delete_refs_for_file(file_info.path)

        self.db.insert_file(file_info)

        self.db.insert_symbols(parsed.symbols)

        self.db.insert_inheritances(parsed.inheritances)

        self.db.insert_references(parsed.references)

        # Save usings if available (C# specific)
        if hasattr(parsed, 'namespace_mapping') and parsed.namespace_mapping:
            self.db.save_usings(file_info.path, parsed.namespace_mapping)

    def _delete_file(self, path: str):
        self.db.delete_symbols_for_file(path)
        self.db.delete_inheritance_for_file(path)
        self.db.delete_refs_for_file(path)
        self.db.delete_file(path)

    def _clear_all(self):
        all_files = self.db.get_all_files()
        for f in all_files:
            self._delete_file(f["path"])

    def _merge_stats(self, stats: dict[str, int], batch_stats: dict[str, int]):
        for key, value in batch_stats.items():
            if key in stats:
                stats[key] += value
            else:
                stats[key] = value

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
