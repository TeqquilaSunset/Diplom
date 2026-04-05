"""Parser modules for different programming languages."""

from . import csharp, javascript, python, typescript
from .base import BaseParser


def get_parser(language: str):
    return BaseParser.get_parser(language)


def get_supported_languages():
    return BaseParser.get_supported_languages()


__all__ = ["BaseParser", "get_parser", "get_supported_languages"]
