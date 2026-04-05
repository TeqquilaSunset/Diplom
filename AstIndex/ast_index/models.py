from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
from pathlib import Path


@dataclass
class FileInfo:
    path: str
    language: str
    content_hash: str
    last_modified: float
    size: int


@dataclass
class Symbol:
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    col_start: int = 0
    col_end: int = 0
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None
    scope: Optional[str] = None


@dataclass
class Inheritance:
    child_symbol: str
    child_file: str
    parent_symbol: str
    parent_file: Optional[str]
    kind: str


@dataclass
class Reference:
    symbol_name: str
    symbol_file: str
    ref_file: str
    ref_line: int
    ref_col: int
    ref_kind: str
    context: Optional[str] = None


@dataclass
class ParsedFile:
    file_info: FileInfo
    symbols: List[Symbol] = field(default_factory=list)
    inheritances: List[Inheritance] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)


@dataclass
class UsingDirective:
    """Представляет using директиву в C# файле."""
    file_path: str
    alias: Optional[str] = None      # для using App = MyNamespace.App
    namespace: str = ""              # System.Collections.Generic
    is_static: bool = False          # для using static Math


@dataclass
class NamespaceMapping:
    """Картирование namespace для файла."""
    file_path: str
    aliases: Dict[str, str] = field(default_factory=dict)    # {alias: namespace}
    imports: Set[str] = field(default_factory=set)           # {namespace}
    static_imports: Set[str] = field(default_factory=set)    # {static_type}
