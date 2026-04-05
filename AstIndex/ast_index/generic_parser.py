"""
Модуль для анализа generic типов в C#.
"""
import re
from dataclasses import dataclass


@dataclass
class GenericType:
    """Представляет generic тип."""
    base_type: str           # List, Dictionary, etc.
    type_arguments: list[str]  # [string, int] for Dictionary<string, int>
    full_name: str           # List<string>




def _find_generic_types_manually(content: str) -> list[tuple]:
    """Manually find generic types with proper nested handling."""
    # Remove spaces around angle brackets to handle mixed spacing
    content = re.sub(r'\s*<\s*', '<', content)
    content = re.sub(r'\\s*>\s*', '>', content)

    results = []
    i = 0
    n = len(content)

    while i < n:
        # Look for potential generic start (capital letter followed by lowercase)
        if i < n and content[i].isupper():
            # Found potential start of a type name
            j = i
            while j < n and content[j].isalpha():
                j += 1

            # Check if followed by <
            if j < n and content[j] == '<':
                start_bracket = j
                depth = 1
                k = j + 1

                # Find matching closing bracket
                while k < n and depth > 0:
                    if content[k] == '<':
                        depth += 1
                    elif content[k] == '>':
                        depth -= 1
                    k += 1

                if depth == 0:
                    # Found complete generic type
                    base_type = content[i:j]
                    type_args_str = content[start_bracket+1:k-1]
                    results.append((base_type, type_args_str))
                    i = k
                    continue
                else:
                    # Unbalanced brackets, skip
                    i = j
                    continue
            else:
                # No generic, continue
                i += 1
        else:
            i += 1

    return results


def extract_generic_types(
    content: str,
    file_path: str,
    line_number: int
) -> list[GenericType]:
    """
    Извлечь generic типы из строки кода.

    Примеры:
        List<string> → GenericType(base_type="List", type_arguments=["string"])
        Dictionary<int, string> → GenericType(base_type="Dictionary", type_arguments=["int", "string"])

    Args:
        content: Строка кода
        file_path: Путь к файлу
        line_number: Номер строки

    Returns:
        Список найденных generic типов
    """
    generics = []

    # Use manual parsing for better nested generic handling
    generic_matches = _find_generic_types_manually(content)

    for base_type, type_args_str in generic_matches:
        # Skip empty generic type arguments
        if not type_args_str.strip():
            continue

        # Парсинг type arguments (учитывая вложенные generic)
        type_args = _parse_type_arguments(type_args_str)

        generics.append(GenericType(
            base_type=base_type,
            type_arguments=type_args,
            full_name=f"{base_type}<{type_args_str}>"
        ))

    return generics


def _parse_type_arguments(type_args_str: str) -> list[str]:
    """
    Распарсить строку type arguments.

    Args:
        type_args_str: "int, string" или "List<int>, Dictionary<string, int>"

    Returns:
        Список type arguments
    """
    args = []
    current_arg = []
    depth = 0  # для nested generics

    for char in type_args_str:
        if char == '<':
            depth += 1
            current_arg.append(char)
        elif char == '>':
            depth -= 1
            current_arg.append(char)
        elif char == ',' and depth == 0:
            # Разделитель верхнего уровня
            args.append(''.join(current_arg).strip())
            current_arg = []
        else:
            current_arg.append(char)

    # Добавить последний аргумент
    if current_arg:
        args.append(''.join(current_arg).strip())

    return args


def get_generic_reference_candidates(
    generic_type: GenericType
) -> list[str]:
    """
    Получить кандидатов в символы для generic типа.

    Для List<string> вернёт ["List", "string"]
    Для Dictionary<int, User> вернёт ["Dictionary", "int", "User"]

    Args:
        generic_type: Generic type для анализа

    Returns:
        Список потенциальных ссылок на символы
    """
    candidates = [generic_type.base_type]

    for type_arg in generic_type.type_arguments:
        # Извлечь имя типа из аргумента
        nested_generics = extract_generic_types(type_arg, "", 0)

        if nested_generics:
            for nested in nested_generics:
                candidates.extend(get_generic_reference_candidates(nested))
        else:
            # Не-generic тип
            clean_type = type_arg.strip()
            if clean_type and not clean_type.startswith('?'):
                # Возьмём только имя (без namespace)
                candidates.append(clean_type.split('.')[-1])

    return candidates
