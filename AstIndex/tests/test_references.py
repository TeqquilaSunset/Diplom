"""
Тесты для модуля references.py

Проверяют функциональность извлечения ссылок из исходного кода.
"""

import pytest
from ast_index.references import (
    strip_comments,
    remove_string_literals,
    is_excluded_symbol,
    extract_references_universal,
)
from ast_index.reference_keywords import PYTHON_KEYWORDS, PYTHON_STANDARD_TYPES


class TestStripComments:
    """Тесты для функции strip_comments."""

    def test_strip_comments_python_single_line(self):
        """Тест удаления Python однострочных комментариев."""
        content = "def hello():  # This is a comment\n    pass"
        result = strip_comments(content, "python")
        assert "This is a comment" not in result
        assert "def hello():" in result
        assert "pass" in result

    def test_strip_comments_python_docstring(self):
        """Тест удаления Python docstrings."""
        content = 'def hello():\n    """This is a docstring"""\n    pass'
        result = strip_comments(content, "python")
        assert "This is a docstring" not in result
        assert "def hello():" in result

    def test_strip_comments_python_docstring_single_quotes(self):
        """Тест удаления Python docstrings с одинарными кавычками."""
        content = "def hello():\n    '''This is a docstring'''\n    pass"
        result = strip_comments(content, "python")
        assert "This is a docstring" not in result

    def test_strip_comments_cstyle_single_line(self):
        """Тест удаления C-style однострочных комментариев."""
        content = "int x = 5;  // This is a comment\nint y = 10;"
        result = strip_comments(content, "csharp")
        assert "This is a comment" not in result
        assert "int x = 5;" in result

    def test_strip_comments_cstyle_multi_line(self):
        """Тест удаления C-style многострочных комментариев."""
        content = "int x = 5; /* This is a\nmulti-line comment */ int y = 10;"
        result = strip_comments(content, "csharp")
        assert "This is a" not in result
        assert "multi-line comment" not in result
        assert "int x = 5;" in result
        assert "int y = 10;" in result

    def test_strip_comments_empty_content(self):
        """Тест с пустым содержимым."""
        assert strip_comments("", "python") == ""
        assert strip_comments(None, "python") == None

    def test_strip_comments_preserves_code(self):
        """Тест что код без комментариев не изменяется."""
        content = "def hello():\n    pass"
        result = strip_comments(content, "python")
        assert result == content


class TestRemoveStringLiterals:
    """Тесты для функции remove_string_literals."""

    def test_remove_double_quoted_strings(self):
        """Тест удаления строк в двойных кавычках."""
        content = 'var x = "UserRepository";'
        result = remove_string_literals(content)
        assert "UserRepository" not in result
        assert "var x =" in result

    def test_remove_single_quoted_strings(self):
        """Тест удаления строк в одинарных кавычках."""
        content = "var x = 'UserRepository';"
        result = remove_string_literals(content)
        assert "UserRepository" not in result
        assert "var x =" in result

    def test_remove_escaped_quotes(self):
        """Тест обработки экранированных кавычек."""
        content = 'var x = "Test \\"escaped\\" string";'
        result = remove_string_literals(content)
        assert "Test" not in result
        assert "escaped" not in result
        assert "var x =" in result

    def test_remove_csharp_verbatim_string(self):
        """Тест обработки C# verbatim strings."""
        content = 'var x = @"This is a verbatim string";'
        result = remove_string_literals(content)
        assert "This is a verbatim string" not in result
        assert "var x =" in result

    def test_remove_python_triple_quotes(self):
        """Тест обработки Python triple quotes."""
        content = 'x = """This is a docstring"""'
        result = remove_string_literals(content)
        assert "This is a docstring" not in result
        assert "x =" in result

    def test_remove_python_triple_single_quotes(self):
        """Тест обработки Python triple single quotes."""
        content = "x = '''This is a docstring'''"
        result = remove_string_literals(content)
        assert "This is a docstring" not in result
        assert "x =" in result

    def test_remove_string_preserves_non_strings(self):
        """Тест что код без строк не изменяется."""
        content = "var x = UserRepository;"
        result = remove_string_literals(content)
        assert result == content


class TestIsExcludedSymbol:
    """Тесты для функции is_excluded_symbol."""

    def test_excludes_keywords(self):
        """Тест что ключевые слова исключаются."""
        assert is_excluded_symbol("if", PYTHON_KEYWORDS, set(), set())
        assert is_excluded_symbol("else", PYTHON_KEYWORDS, set(), set())
        assert is_excluded_symbol("while", PYTHON_KEYWORDS, set(), set())

    def test_excludes_standard_types(self):
        """Тест что стандартные типы исключаются."""
        assert is_excluded_symbol("str", set(), PYTHON_STANDARD_TYPES, set())
        assert is_excluded_symbol("int", set(), PYTHON_STANDARD_TYPES, set())
        assert is_excluded_symbol("list", set(), PYTHON_STANDARD_TYPES, set())

    def test_excludes_defined_symbols(self):
        """Тест что локально определённые символы исключаются."""
        assert is_excluded_symbol("MyClass", set(), set(), {"MyClass"})
        assert is_excluded_symbol("myFunction", set(), set(), {"myFunction"})

    def test_does_not_exclude_valid_symbols(self):
        """Тест что валидные символы не исключаются."""
        assert not is_excluded_symbol("ExternalClass", set(), set(), set())
        assert not is_excluded_symbol("externalFunction", set(), set(), set())

    def test_excludes_import_lines(self):
        """Тест что import строки исключаются."""
        line = "import os"
        assert is_excluded_symbol("os", set(), set(), set(), line)

        line = "from typing import List"
        assert is_excluded_symbol("List", set(), set(), set(), line)

        line = "using System;"
        assert is_excluded_symbol("System", set(), set(), set(), line)


class TestExtractReferencesUniversal:
    """Тесты для функции extract_references_universal."""

    def test_extract_references_csharp(self):
        """Тест извлечения ссылок из C# кода."""
        content = """
        public class UserService {
            public void GetUser() {
                var repo = new UserRepository();
                repo.GetData();
            }
        }
        """
        refs = extract_references_universal(content, "test.cs", "csharp",
                                            {"UserService", "GetUser"})
        assert len(refs) == 2
        assert any(r.symbol_name == "UserRepository" for r in refs)
        assert any(r.symbol_name == "GetData" for r in refs)

    def test_extract_references_python(self):
        """Тест извлечения ссылок из Python кода."""
        content = """
class UserService:
    def get_user(self):
        repo = UserRepository()
        repo.get_data()
"""
        refs = extract_references_universal(content, "test.py", "python",
                                            {"UserService", "get_user"})
        # Should find both UserRepository (CamelCase) and get_data (function call)
        assert len(refs) == 2
        assert any(r.symbol_name == "UserRepository" for r in refs)
        assert any(r.symbol_name == "get_data" for r in refs)

    def test_extract_references_javascript(self):
        """Тест извлечения ссылок из JavaScript кода."""
        content = """
        class UserService {
            getUser() {
                const repo = new UserRepository();
                repo.getData();
            }
        }
        """
        refs = extract_references_universal(content, "test.js", "javascript",
                                            {"UserService", "getUser"})
        assert len(refs) == 2
        assert any(r.symbol_name == "UserRepository" for r in refs)
        assert any(r.symbol_name == "getData" for r in refs)

    def test_excludes_keywords_in_code(self):
        """Тест что ключевые слова исключаются из ссылок."""
        content = """
        if (condition) {
            return value;
        }
        """
        refs = extract_references_universal(content, "test.py", "python", set())
        assert not any(r.symbol_name == "if" for r in refs)
        assert not any(r.symbol_name == "return" for r in refs)

    def test_includes_context(self):
        """Тест что контекст сохраняется в ссылках."""
        content = 'var repo = new UserRepository();'
        refs = extract_references_universal(content, "test.cs", "csharp", set())
        assert len(refs) == 1
        assert refs[0].context is not None
        assert "UserRepository" in refs[0].context
        assert len(refs[0].context) <= 500

    def test_skips_long_lines(self):
        """Тест что длинные строки пропускаются."""
        long_line = "var x = " + "A" * 2500 + ";"
        refs = extract_references_universal(long_line, "test.js", "javascript", set())
        assert len(refs) == 0

    def test_deduplicates_references(self):
        """Тест что дубликаты удаляются."""
        content = """
        UserRepository repo1 = new UserRepository();
        UserRepository repo2 = new UserRepository();
        """
        refs = extract_references_universal(content, "test.cs", "csharp", set())
        # Should have unique references based on (symbol_name, file_path, line_num, col_start)
        assert len(refs) <= 6  # Maximum 6 occurrences (3 per line * 2 lines, but deduplicated)

    def test_empty_content(self):
        """Тест с пустым содержимым."""
        refs = extract_references_universal("", "test.py", "python", set())
        assert len(refs) == 0

    def test_content_with_only_comments(self):
        """Тест с содержимым только из комментариев."""
        content = "# This is a comment\n# Another comment"
        refs = extract_references_universal(content, "test.py", "python", set())
        assert len(refs) == 0

    def test_references_have_correct_positions(self):
        """Тест что позиции ссылок определены правильно."""
        content = "var repo = new UserRepository();"
        refs = extract_references_universal(content, "test.cs", "csharp", set())
        assert len(refs) == 1
        assert refs[0].ref_line == 1
        assert refs[0].ref_col >= 0
        assert refs[0].ref_file == "test.cs"
