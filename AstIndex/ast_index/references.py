"""
Модуль для извлечения ссылок (references/usages) из исходного кода.

Использует regex-based подход с фильтрацией для поиска использований символов.
"""

from typing import Set, List, Optional
import re
from dataclasses import dataclass
from functools import lru_cache

from .models import Reference
from .reference_keywords import get_keywords, get_standard_types


# Module-level cached regex patterns for performance
_CAMELCASE_PATTERN = None
_FUNCTION_CALL_PATTERN = None


def _get_camelcase_pattern() -> re.Pattern:
    """Get cached CamelCase regex pattern."""
    global _CAMELCASE_PATTERN
    if _CAMELCASE_PATTERN is None:
        # Supports Unicode letters in identifiers
        _CAMELCASE_PATTERN = re.compile(r'\b([A-Z][a-zA-Z0-9_$]*)\b')
    return _CAMELCASE_PATTERN


def _get_function_call_pattern() -> re.Pattern:
    """Get cached function call regex pattern."""
    global _FUNCTION_CALL_PATTERN
    if _FUNCTION_CALL_PATTERN is None:
        # Supports Unicode letters in identifiers
        _FUNCTION_CALL_PATTERN = re.compile(r'\b([a-z][a-zA-Z0-9_$]*)\s*\(')
    return _FUNCTION_CALL_PATTERN


def strip_comments(content: str, language: str) -> str:
    """
    Удалить комментарии из кода.

    Поддерживает:
    - C-style комментарии (//, /* */)
    - Python комментарии (#)
    - Python docstrings (тройные кавычки)

    Args:
        content: Исходный код
        language: Язык программирования (python, csharp, javascript, typescript)

    Returns:
        Код без комментариев
    """
    if not content:
        return content

    language_lower = language.lower() if language else ""
    is_python = language_lower == "python"

    # State machine states
    NORMAL = 0
    SINGLE_LINE_COMMENT = 1  # Python # or C-style //
    MULTI_LINE_COMMENT = 2   # /* */
    PYTHON_DOCSTRING = 3     # """ or '''

    result = []
    i = 0
    n = len(content)
    state = NORMAL
    docstring_char = None  # '"' or "' for docstrings

    while i < n:
        if state == NORMAL:
            # Check for single-line comments
            if is_python and content[i] == '#':
                state = SINGLE_LINE_COMMENT
                i += 1
                continue
            elif not is_python and i + 1 < n and content[i:i+2] == '//':
                state = SINGLE_LINE_COMMENT
                i += 2
                continue
            # Check for multi-line comments (C-style)
            elif not is_python and i + 1 < n and content[i:i+2] == '/*':
                state = MULTI_LINE_COMMENT
                i += 2
                continue
            # Check for Python docstrings
            elif is_python and i + 2 < n:
                if content[i:i+3] in ('"""', "'''"):
                    state = PYTHON_DOCSTRING
                    docstring_char = content[i]
                    i += 3
                    continue
            # Normal character - add to result
            result.append(content[i])
            i += 1

        elif state == SINGLE_LINE_COMMENT:
            # Skip until end of line
            if content[i] in ('\n', '\r'):
                result.append(content[i])
                state = NORMAL
            i += 1

        elif state == MULTI_LINE_COMMENT:
            # Skip until */
            if i + 1 < n and content[i:i+2] == '*/':
                state = NORMAL
                i += 2
            else:
                i += 1

        elif state == PYTHON_DOCSTRING:
            # Skip until closing triple quotes
            if i + 2 < n and content[i:i+3] in ('"""', "'''"):
                if content[i] == docstring_char:
                    state = NORMAL
                    docstring_char = None
                    i += 3
                    continue
            i += 1

    return ''.join(result)


def remove_string_literals(content: str) -> str:
    """
    Заменить строковые литералы на пробелы.

    Это предотвращает нахождение ссылок в строках:
    UserRepository в строке не должно быть ссылкой.

    Поддерживает:
    - Одинарные и двойные кавычки
    - Экранированные кавычки
    - Многострочные строки (C# verbatim, Python triple quotes)

    Args:
        content: Исходный код

    Returns:
        Код с заменёнными строковыми литералами
    """
    if not content:
        return content

    result = []
    i = 0
    n = len(content)

    # States
    NORMAL = 0
    IN_DOUBLE_QUOTE = 1
    IN_SINGLE_QUOTE = 2
    IN_CSHARP_VERBATIM = 3  # @"..."
    IN_PYTHON_TRIPLE_DOUBLE = 4  # """..."""
    IN_PYTHON_TRIPLE_SINGLE = 5  # '''...'''

    state = NORMAL
    escape_next = False

    while i < n:
        char = content[i]

        if state == NORMAL:
            # Check for C# verbatim string
            if i + 1 < n and char == '@' and content[i+1] == '"':
                result.append('@@')  # Keep length
                state = IN_CSHARP_VERBATIM
                i += 2
                continue
            # Check for Python triple quotes
            elif i + 2 < n and content[i:i+3] == '"""':
                result.append('   ')  # Keep length
                state = IN_PYTHON_TRIPLE_DOUBLE
                i += 3
                continue
            elif i + 2 < n and content[i:i+3] == "'''":
                result.append('   ')  # Keep length
                state = IN_PYTHON_TRIPLE_SINGLE
                i += 3
                continue
            # Check for regular strings
            elif char == '"':
                result.append(' ')  # Replace opening quote with space
                state = IN_DOUBLE_QUOTE
                i += 1
                continue
            elif char == "'":
                result.append(' ')  # Replace opening quote with space
                state = IN_SINGLE_QUOTE
                i += 1
                continue
            else:
                result.append(char)
                i += 1

        elif state == IN_DOUBLE_QUOTE:
            if escape_next:
                result.append(' ')  # Replace escaped char with space
                escape_next = False
                i += 1
                continue
            elif char == '\\':
                result.append(' ')
                escape_next = True
                i += 1
                continue
            elif char == '"':
                result.append(' ')  # Replace closing quote with space
                state = NORMAL
                i += 1
                continue
            else:
                result.append(' ')
                i += 1

        elif state == IN_SINGLE_QUOTE:
            if escape_next:
                result.append(' ')  # Replace escaped char with space
                escape_next = False
                i += 1
                continue
            elif char == '\\':
                result.append(' ')
                escape_next = True
                i += 1
                continue
            elif char == "'":
                result.append(' ')  # Replace closing quote with space
                state = NORMAL
                i += 1
                continue
            else:
                result.append(' ')
                i += 1

        elif state == IN_CSHARP_VERBATIM:
            # In C# verbatim strings, only "" is an escape sequence
            if i + 1 < n and char == '"' and content[i+1] == '"':
                result.append('  ')  # Two quotes -> two spaces
                i += 2
                continue
            elif char == '"':
                result.append(' ')  # Replace closing quote with space
                state = NORMAL
                i += 1
                continue
            else:
                result.append(' ')
                i += 1

        elif state == IN_PYTHON_TRIPLE_DOUBLE:
            if i + 2 < n and content[i:i+3] == '"""':
                result.append('   ')  # Replace closing quotes with spaces
                state = NORMAL
                i += 3
                continue
            else:
                result.append(' ')
                i += 1

        elif state == IN_PYTHON_TRIPLE_SINGLE:
            if i + 2 < n and content[i:i+3] == "'''":
                result.append('   ')  # Replace closing quotes with spaces
                state = NORMAL
                i += 3
                continue
            else:
                result.append(' ')
                i += 1

    return ''.join(result)


def is_excluded_symbol(
    name: str,
    keywords: Set[str],
    standard_types: Set[str],
    defined_symbols: Set[str],
    line: str = ""
) -> bool:
    """
    Проверить, следует ли исключить символ из ссылок.

    Исключает:
    - Ключевые слова языка (if, else, while)
    - Стандартные типы (String, Int, List)
    - Локально определённые символы
    - Опционально: import/package строки

    Args:
        name: Имя символа
        keywords: Ключевые слова языка
        standard_types: Стандартные типы языка
        defined_symbols: Локально определённые символы
        line: Строка кода (для опциональной фильтрации)

    Returns:
        True если символ следует исключить
    """
    # Check if it's a keyword
    if name in keywords:
        return True

    # Check if it's a standard type
    if name in standard_types:
        return True

    # Check if it's a locally defined symbol
    if name in defined_symbols:
        return True

    # Optional: Check if line is an import/using/package statement
    if line:
        stripped_line = line.strip()
        # Skip import/using/package lines
        if (stripped_line.startswith("import ") or
            stripped_line.startswith("using ") or
            stripped_line.startswith("package ") or
            stripped_line.startswith("from ") or
            stripped_line.startswith("#import ") or
            stripped_line.startswith("#using ")):
            return True

    # Don't exclude
    return False


def extract_references_universal(
    content: str,
    file_path: str,
    language: str,
    defined_symbols: Set[str]
) -> List[Reference]:
    """
    Универсальный метод извлечения ссылок.

    Алгоритм:
    1. Удалить комментарии и строковые литералы
    2. Разбить по строкам
    3. Для каждой строки:
       - Пропустить если > 2000 символов
       - Пропустить если import/using/package
       - Найти CamelCase идентификаторы
       - Найти вызовы функций
       - Отфильтровать исключения
    4. Вернуть список Reference

    Args:
        content: Исходный код
        file_path: Путь к файлу
        language: Язык программирования
        defined_symbols: Множество определённых символов

    Returns:
        Список найденных ссылок
    """
    if not content:
        return []

    # Get language-specific keywords and standard types
    # Handle None language gracefully
    language = language or ""
    keywords = get_keywords(language)
    standard_types = get_standard_types(language)

    # Preprocess content
    content_without_comments = strip_comments(content, language)
    content_without_strings = remove_string_literals(content_without_comments)

    # Get cached regex patterns
    camelcase_pattern = _get_camelcase_pattern()
    function_call_pattern = _get_function_call_pattern()

    references = []
    seen_refs = set()  # For deduplication

    lines = content_without_strings.split('\n')

    for line_num, line in enumerate(lines, start=1):
        # Skip long lines (minified code)
        if len(line) > 2000:
            continue

        # Get original line for context (from original content)
        original_lines = content.split('\n')
        original_line = original_lines[line_num - 1] if line_num <= len(original_lines) else line

        # Find CamelCase identifiers
        for match in camelcase_pattern.finditer(line):
            symbol_name = match.group(1)
            col_start = match.start(1)

            # Skip if excluded
            if is_excluded_symbol(symbol_name, keywords, standard_types,
                                 defined_symbols, line):
                continue

            # Create unique key for deduplication
            ref_key = (symbol_name, file_path, line_num, col_start)
            if ref_key in seen_refs:
                continue
            seen_refs.add(ref_key)

            # Create reference
            context = original_line[:500] if original_line else None
            references.append(Reference(
                symbol_name=symbol_name,
                symbol_file="",  # Will be filled by caller
                ref_file=file_path,
                ref_line=line_num,
                ref_col=col_start,
                ref_kind="reference",
                context=context
            ))

        # Find function calls
        for match in function_call_pattern.finditer(line):
            symbol_name = match.group(1)
            col_start = match.start(1)

            # Skip if excluded
            if is_excluded_symbol(symbol_name, keywords, standard_types,
                                 defined_symbols, line):
                continue

            # Create unique key for deduplication
            ref_key = (symbol_name, file_path, line_num, col_start)
            if ref_key in seen_refs:
                continue
            seen_refs.add(ref_key)

            # Create reference
            context = original_line[:500] if original_line else None
            references.append(Reference(
                symbol_name=symbol_name,
                symbol_file="",  # Will be filled by caller
                ref_file=file_path,
                ref_line=line_num,
                ref_col=col_start,
                ref_kind="call",
                context=context
            ))

    return references
