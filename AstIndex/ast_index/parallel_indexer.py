"""
Параллельный индексатор для многопоточной обработки файлов.

Использует ThreadPoolExecutor для ускорения индексации
за счёт параллельного парсинга файлов.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .database import Database
from .models import ParsedFile
from .parsers import get_parser
from .utils.file_utils import djb2_hash, get_file_info
from .utils.logging import get_logger

logger = get_logger(__name__)


class ParallelIndexer:
    """Параллельный индексатор с поддержкой прогресс-бара."""

    def __init__(
        self,
        config: Config,
        max_workers: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None
    ):
        """
        Initialize parallel indexer.

        Args:
            config: Конфигурация проекта
            max_workers: Максимальное количество потоков (default: os.cpu_count())
            progress_callback: Функция для отображения прогресса (current, total)
        """
        self.config = config
        self.max_workers = max_workers or os.cpu_count() or 4
        self.progress_callback = progress_callback

        # Кеш парсеров (ленивая инициализация)
        self._parsers: dict[str, Any] = {}
        # Локальное хранилище для thread-local database connections
        self._db_path = config.db_path

    def index_files_parallel(
        self,
        files: list[tuple[Path, str]]
    ) -> dict[str, int]:
        """
        Индексировать файлы параллельно.

        Args:
            files: Список кортежей (file_path, language)

        Returns:
            Статистика индексации
        """
        stats = {
            "files_indexed": 0,
            "symbols_indexed": 0,
            "inheritances_indexed": 0,
            "references_indexed": 0,
            "errors": 0,
        }

        total_files = len(files)
        logger.info(f"Starting parallel indexing of {total_files} files with {self.max_workers} workers")

        # Обрабатываем файлы параллельно
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Отправляем задачи на выполнение
            future_to_file = {
                executor.submit(self._parse_file_with_db, file_path, language): (file_path, language)
                for file_path, language in files
            }

            # Собираем результаты по мере завершения
            completed = 0
            for future in as_completed(future_to_file):
                (file_path, language) = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        self._merge_stats(stats, result)
                        completed += 1

                        # Вызываем callback для прогресс-бара
                        if self.progress_callback:
                            self.progress_callback(completed, total_files)

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    stats["errors"] += 1
                    completed += 1

        return stats

    def _parse_file_with_db(
        self,
        file_path: Path,
        language: str
    ) -> dict[str, int] | None:
        """
        Парсить файл с собственным DB соединением для thread-safety.

        Args:
            file_path: Путь к файлу
            language: Язык программирования

        Returns:
            Статистика обработки файла или None при ошибке
        """
        # Создаём отдельное соединение для каждого потока
        db = Database(self._db_path)
        try:
            # Парсим файл
            parsed = self._parse_file(file_path, language)
            if not parsed:
                return None

            # Сохраняем в базу
            self._store_parsed_file(db, parsed)

            return {
                "files_indexed": 1,
                "symbols_indexed": len(parsed.symbols),
                "inheritances_indexed": len(parsed.inheritances),
                "references_indexed": len(parsed.references),
            }
        except Exception as e:
            logger.error(f"Error in thread processing {file_path}: {e}")
            return None
        finally:
            # Закрываем соединение
            db.close()

    def _parse_file(self, file_path: Path, language: str) -> ParsedFile | None:
        """Parse file (thread-safe)."""
        parser = self._get_parser(language)
        if not parser:
            return None

        if not parser.can_parse(file_path):
            return None

        content = file_path.read_bytes()
        file_info = get_file_info(file_path, language)
        file_info.content_hash = djb2_hash(content)

        parsed = parser.parse(file_path, content)
        parsed.file_info = file_info

        return parsed

    def _store_parsed_file(self, db: Database, parsed: ParsedFile):
        """Store parsed file in database (thread-safe)."""
        file_info = parsed.file_info

        # Don't use transaction in parallel mode to avoid locking
        # Delete old data
        db.delete_symbols_for_file(file_info.path)
        db.delete_inheritance_for_file(file_info.path)
        db.delete_refs_for_file(file_info.path)

        # Insert new data
        db.insert_file(file_info)
        db.insert_symbols(parsed.symbols)
        db.insert_inheritances(parsed.inheritances)
        db.insert_references(parsed.references)

        # Save usings if available (C# specific)
        if hasattr(parsed, 'namespace_mapping') and parsed.namespace_mapping:
            db.save_usings(file_info.path, parsed.namespace_mapping)

    def _get_parser(self, language: str):
        """Get parser for language (thread-safe)."""
        if language not in self._parsers:
            parser_cls = get_parser(language)
            if parser_cls:
                self._parsers[language] = parser_cls()
        return self._parsers.get(language)

    def _merge_stats(self, total: dict, partial: dict | None):
        """Merge partial stats into total."""
        if partial:
            total["files_indexed"] += partial.get("files_indexed", 0)
            total["symbols_indexed"] += partial.get("symbols_indexed", 0)
            total["inheritances_indexed"] += partial.get("inheritances_indexed", 0)
            total["references_indexed"] += partial.get("references_indexed", 0)
            total["errors"] += partial.get("errors", 0)
