from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ParsedFile, Reference, Symbol
from ..references import extract_references_universal


class BaseParser(ABC):
    """Abstract base class for language parsers."""

    language: str = ""
    extensions: list[str] = []

    _registry: dict[str, type["BaseParser"]] = {}

    def __init_subclass__(cls, **kwargs):
        """Register subclasses automatically."""
        super().__init_subclass__(**kwargs)
        if cls.language:
            cls._registry[cls.language] = cls

    @classmethod
    def get_parser(cls, language: str) -> type["BaseParser"] | None:
        """Get parser class for a language."""
        return cls._registry.get(language)

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """Get list of supported languages."""
        return list(cls._registry.keys())

    @abstractmethod
    def parse(self, file_path: Path, content: bytes) -> ParsedFile:
        """Parse a file and return extracted symbols."""
        pass

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        pass

    def extract_references(
        self,
        content: str,
        file_path: str,
        defined_symbols: list[Symbol]
    ) -> list[Reference]:
        """
        Извлечь ссылки на символы (usages).

        По умолчанию использует универсальный regex метод.
        Может быть переопределён в subclass для языковой специфики.

        Args:
            content: Исходный код
            file_path: Путь к файлу
            defined_symbols: Список определённых символов

        Returns:
            Список найденных ссылок
        """
        defined_names = {sym.name for sym in defined_symbols}
        return extract_references_universal(
            content=content,
            file_path=file_path,
            language=self.language,
            defined_symbols=defined_names
        )

    def _get_text(self, node, source: bytes) -> str:
        """Get text content of a node."""
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _get_line_col(self, node) -> tuple:
        """Get line and column for a node."""
        return (node.start_point[0] + 1, node.start_point[1])
