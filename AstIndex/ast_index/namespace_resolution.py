"""
Модуль для разрешения пространств имен в C#.
"""
import re

from .models import NamespaceMapping


def extract_using_directives(content: str, file_path: str) -> NamespaceMapping:
    """
    Извлечь все using директивы из C# файла.

    Примеры:
        using System;
        using System.Collections.Generic;
        using static System.Math;
        using App = MyNamespace.App;

    Args:
        content: Исходный код C#
        file_path: Путь к файлу

    Returns:
        NamespaceMapping с извлечёнными директивами
    """
    aliases = {}
    imports = set()
    static_imports = set()
    in_skipped_block = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Обработка директив препроцессора
        if stripped.startswith('#'):
            if stripped.startswith('#define'):
                # Пропускаем define, но не влияет на блоки
                continue
            elif stripped.startswith('#if ') or stripped.startswith('#elif '):
                # Простая проверка для #if DEBUG, #if true, #if false
                condition = stripped[3:].strip()
                if condition.lower() in ('false', '0', 'null', '""') or condition == 'DEBUG':
                    in_skipped_block = True
                else:
                    in_skipped_block = False
            elif stripped.startswith('#else'):
                in_skipped_block = not in_skipped_block
            elif stripped.startswith('#endif'):
                in_skipped_block = False
            continue

        # Пропуск комментариев и строк в заблокированных областях
        if not stripped or stripped.startswith('//') or in_skipped_block:
            continue

        # Проверка на static import
        static_match = re.match(r'using\s+static\s+([A-Za-z0-9_.]+)\s*;', stripped)
        if static_match:
            static_imports.add(static_match.group(1))
            continue

        # Проверка на alias
        alias_match = re.match(r'using\s+([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_.]+)\s*;', stripped)
        if alias_match:
            alias, namespace = alias_match.groups()
            aliases[alias] = namespace
            continue

        # Обычный using
        using_match = re.match(r'using\s+([A-Za-z0-9_.]+)\s*;', stripped)
        if using_match:
            namespace = using_match.group(1)
            imports.add(namespace)
            continue

    return NamespaceMapping(
        file_path=file_path,
        aliases=aliases,
        imports=imports,
        static_imports=static_imports
    )
