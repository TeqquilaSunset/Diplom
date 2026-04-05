import pytest
import tempfile
import os
from ast_index.database import Database
from ast_index.models import NamespaceMapping


@pytest.fixture
def temp_db():
    """Создать временную базу данных."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(path)
    db._create_tables()

    yield db

    os.unlink(path)


def test_save_and_get_usings(temp_db):
    """Тест сохранения и получения usings."""
    mapping = NamespaceMapping(
        file_path="test.cs",
        aliases={"App": "MyNamespace.App"},
        imports={"System", "System.Collections.Generic"},
        static_imports={"System.Math"}
    )

    temp_db.save_usings("test.cs", mapping)

    retrieved = temp_db.get_usings_for_file("test.cs")

    assert "App" in retrieved.aliases
    assert retrieved.aliases["App"] == "MyNamespace.App"
    assert "System" in retrieved.imports
    assert "System.Math" in retrieved.static_imports


def test_delete_usings(temp_db):
    """Тест удаления usings."""
    mapping = NamespaceMapping(
        file_path="test.cs",
        imports={"System"}
    )

    temp_db.save_usings("test.cs", mapping)
    temp_db.delete_usings_for_file("test.cs")

    retrieved = temp_db.get_usings_for_file("test.cs")
    assert len(retrieved.imports) == 0


def test_update_usings(temp_db):
    """Тест обновления usings (старые удаляются)."""
    # Первое сохранение
    mapping1 = NamespaceMapping(
        file_path="test.cs",
        imports={"System", "Collections"}
    )
    temp_db.save_usings("test.cs", mapping1)

    # Второе сохранение (должно заменить первое)
    mapping2 = NamespaceMapping(
        file_path="test.cs",
        imports={"System.IO"}
    )
    temp_db.save_usings("test.cs", mapping2)

    retrieved = temp_db.get_usings_for_file("test.cs")
    assert "System.IO" in retrieved.imports
    assert "System" not in retrieved.imports
    assert "Collections" not in retrieved.imports