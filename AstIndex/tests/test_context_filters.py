import pytest
from ast_index.context_filters import should_exclude_context, filter_extension_methods


def test_exclude_xml_documentation():
    line = '/// <summary>This is a summary</summary>'
    assert should_exclude_context(line, 3, "summary") == True


def test_exclude_inside_attribute():
    line = '[Obsolete("Do not use")]'
    # Проверим позицию внутри Obsolete
    col_start = line.find('Obsolete')
    assert should_exclude_context(line, col_start, "Obsolete") == True


def test_not_exclude_normal_code():
    line = 'var user = new User();'
    col_start = line.find('User')
    assert should_exclude_context(line, col_start, "User") == False


def test_exclude_string_interpolation():
    line = 'var message = $"User: {user.Name}";'
    # user.Name внутри интерполяции
    user_col = line.find('user')
    name_col = line.find('Name')
    assert should_exclude_context(line, user_col, "user") == True
    assert should_exclude_context(line, name_col, "Name") == True


def test_filter_linq_extension_methods():
    line = 'users.Where(u => u.Id > 0).ToList()'

    # Where - extension method
    where_col = line.find('Where')
    assert filter_extension_methods("Where", line, set()) == True

    # ToList - extension method
    tolist_col = line.find('ToList')
    assert filter_extension_methods("ToList", line, set()) == True

    # Id - не extension method
    id_col = line.find('Id')
    assert filter_extension_methods("Id", line, set()) == False


def test_filter_custom_extension_methods():
    line = 'items.MyCustomExtension()'

    # Если MyCustomExtension в known_extensions
    known_extensions = {'MyCustomExtension'}
    custom_col = line.find('MyCustomExtension')
    assert filter_extension_methods("MyCustomExtension", line, known_extensions) == True