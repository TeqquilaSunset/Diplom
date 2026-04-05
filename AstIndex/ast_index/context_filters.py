"""
Контекст-зависимая фильтрация ссылок для C#.
"""
import re
from typing import Set


# C#-специфичные паттерны для фильтрации
_CSHARP_XML_DOC_PATTERN = re.compile(r'///\s*<')
_CSHARP_ATTRIBUTE_PATTERN = re.compile(r'\[(.*)\]')
_CSHARP_INTERPOLATION_PATTERN = re.compile(r'\$"?[^"]*\{[^}]*\}[^"]*"?')


def should_exclude_context(line: str, col_start: int, symbol_name: str) -> bool:
    """
    Проверить, следует ли исключить символ на основе контекста.

    Случаи для исключения:
    - Внутри XML комментариев (/// <summary>)
    - Внутри атрибута [AttributeName]
    - Внутри string interpolation ($"{var}")

    Args:
        line: Строка кода
        col_start: Начальная позиция символа
        symbol_name: Имя символа

    Returns:
        True если следует исключить
    """
    # Проверка на XML документацию
    if _CSHARP_XML_DOC_PATTERN.search(line):
        return True

    # Проверка на нахождение внутри атрибута
    attr_match = _CSHARP_ATTRIBUTE_PATTERN.search(line)
    if attr_match:
        attr_start = attr_match.start()
        attr_end = attr_match.end()
        if attr_start <= col_start < attr_end:
            return True

    # Проверка на string interpolation
    # $"{User.Name}" - User и Name должны исключаться
    if '$"' in line:
        # Найдем начало интерполяции
        interpolation_start = line.find('$"')
        if interpolation_start != -1:
            # Ищем все {...} внутри строки
            brace_count = 0
            in_interpolation = False
            for i in range(interpolation_start, len(line)):
                if line[i] == '{':
                    brace_count = 1
                    in_interpolation = True
                    start_pos = i + 1
                elif line[i] == '}' and in_interpolation:
                    brace_count -= 1
                    if brace_count == 0:
                        in_interpolation = False
                        # Проверяем, находится ли col_start внутри этих скобок
                        if start_pos <= col_start <= i:
                            return True
                elif line[i] == '{' and in_interpolation:
                    brace_count += 1

    return False


def filter_extension_methods(
    symbol_name: str,
    line: str,
    known_extensions: Set[str]
) -> bool:
    """
    Фильтрация extension methods.

    Extension methods вызываются как instance methods:
        list.Where(x => x.Id > 0)  // Where - extension method

    Args:
        symbol_name: Имя символа
        line: Строка кода
        known_extensions: Известные extension methods

    Returns:
        True если это extension method (оставить)
    """
    # Проверка на распространённые LINQ extension methods
    common_linq_extensions = {
        'Where', 'Select', 'SelectMany', 'OrderBy', 'OrderByDescending',
        'ThenBy', 'ThenByDescending', 'GroupBy', 'Join', 'GroupJoin',
        'First', 'FirstOrDefault', 'Last', 'LastOrDefault', 'Single',
        'SingleOrDefault', 'Any', 'All', 'Count', 'LongCount', 'Sum',
        'Average', 'Min', 'Max', 'Aggregate', 'Contains', 'ToList',
        'ToArray', 'ToDictionary', 'ToLookup', 'Distinct', 'Union',
        'Intersect', 'Except', 'Skip', 'SkipWhile', 'Take', 'TakeWhile',
        'Reverse', 'SequenceEqual', 'Concat', 'Zip', 'Cast', 'OfType'
    }

    all_extensions = common_linq_extensions | known_extensions

    if symbol_name in all_extensions:
        # Проверка паттерна: something.Method(
        # Точка перед именем символа
        col_pos = line.find(symbol_name)
        if col_pos > 0 and line[col_pos - 1] == '.':
            return True

    return False