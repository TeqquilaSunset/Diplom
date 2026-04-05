from enum import Enum


class Language(Enum):
    PYTHON = "python"
    CSHARP = "csharp"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


class SymbolKind(Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    ENUM = "enum"
    TYPE_ALIAS = "type_alias"
    PROPERTY = "property"
    FIELD = "field"
    IMPORT = "import"


class InheritanceKind(Enum):
    EXTENDS = "extends"
    IMPLEMENTS = "implements"


BATCH_SIZE = 500
MAX_FILE_SIZE = 10 * 1024 * 1024
