from pathlib import Path
from typing import Optional
import tree_sitter_c_sharp as tscs
from tree_sitter import Language, Parser

from .base import BaseParser
from ..models import ParsedFile, FileInfo, Symbol, Inheritance, Reference


class CSharpParser(BaseParser):
    language = "csharp"
    extensions = [".cs"]

    def __init__(self):
        self._parser: Optional[Parser] = None
        self._language: Optional[Language] = None

    def _ensure_parser(self):
        if self._parser is None:
            self._language = Language(tscs.language())
            self._parser = Parser(self._language)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.extensions

    def parse(self, file_path: Path, content: bytes) -> ParsedFile:
        self._ensure_parser()

        tree = self._parser.parse(content)
        root = tree.root_node

        file_info = FileInfo(
            path=str(file_path.resolve()),
            language="csharp",
            content_hash="",
            last_modified=0.0,
            size=len(content),
        )

        symbols: list[Symbol] = []
        inheritances: list[Inheritance] = []

        self._walk_tree(root, content, str(file_path), symbols, inheritances)

        # Extract references using the universal method
        content_str = content.decode("utf-8", errors="replace")
        references = self.extract_references(
            content=content_str,
            file_path=str(file_path),
            defined_symbols=symbols
        )

        return ParsedFile(
            file_info=file_info,
            symbols=symbols,
            inheritances=inheritances,
            references=references,
        )

    def _walk_tree(
        self,
        node,
        source: bytes,
        file_path: str,
        symbols: list,
        inheritances: list,
        parent: str = None,
        scope: str = None,
    ):
        node_type = node.type

        if node_type == "class_declaration":
            self._process_class(node, source, file_path, symbols, inheritances, scope)
        elif node_type == "interface_declaration":
            self._process_interface(node, source, file_path, symbols, inheritances, scope)
        elif node_type == "struct_declaration":
            self._process_struct(node, source, file_path, symbols, inheritances, scope)
        elif node_type == "enum_declaration":
            self._process_enum(node, source, file_path, symbols, scope)
        elif node_type == "method_declaration":
            self._process_method(node, source, file_path, symbols, parent, scope)
        elif node_type == "property_declaration":
            self._process_property(node, source, file_path, symbols, parent, scope)
        elif node_type == "field_declaration":
            self._process_field(node, source, file_path, symbols, parent, scope)
        else:
            for child in node.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, parent, scope)

    def _process_class(
        self, node, source: bytes, file_path: str, symbols: list, inheritances: list, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="class",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_type_signature(node, source, "class"),
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

        self._process_inheritance(node, source, file_path, name, inheritances)
        self._process_body(node, source, file_path, symbols, inheritances, name, scope)

    def _process_interface(
        self, node, source: bytes, file_path: str, symbols: list, inheritances: list, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="interface",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_type_signature(node, source, "interface"),
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

        self._process_inheritance(node, source, file_path, name, inheritances)
        self._process_body(node, source, file_path, symbols, inheritances, name, scope)

    def _process_struct(
        self, node, source: bytes, file_path: str, symbols: list, inheritances: list, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="class",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_type_signature(node, source, "struct"),
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

        self._process_inheritance(node, source, file_path, name, inheritances)
        self._process_body(node, source, file_path, symbols, inheritances, name, scope)

    def _process_enum(self, node, source: bytes, file_path: str, symbols: list, scope: str):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="enum",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=f"enum {name}",
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

    def _process_method(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="method",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_method_signature(node, source),
                docstring=None,
                parent=parent,
                scope=scope,
            )
        )

    def _process_property(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind="property",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_property_signature(node, source),
                docstring=None,
                parent=parent,
                scope=scope,
            )
        )

    def _process_field(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        var_decl = self._find_child_by_type(node, "variable_declaration")
        if not var_decl:
            return

        for decl in var_decl.children:
            if decl.type == "variable_declarator":
                name = self._get_identifier_name(decl, source)
                if name:
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1

                    symbols.append(
                        Symbol(
                            name=name,
                            kind="field",
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            col_start=node.start_point[1],
                            col_end=node.end_point[1],
                            signature=self._get_text(var_decl, source),
                            docstring=None,
                            parent=parent,
                            scope=scope,
                        )
                    )

    def _process_inheritance(
        self, node, source: bytes, file_path: str, child_name: str, inheritances: list
    ):
        base_list = self._find_child_by_type(node, "base_list")
        if not base_list:
            return

        for child in base_list.children:
            if child.type == "identifier" or child.type == "qualified_name":
                parent_name = self._get_text(child, source)
                inheritances.append(
                    Inheritance(
                        child_symbol=child_name,
                        child_file=file_path,
                        parent_symbol=parent_name,
                        parent_file=None,
                        kind="extends",
                    )
                )

    def _process_body(
        self,
        node,
        source: bytes,
        file_path: str,
        symbols: list,
        inheritances: list,
        parent: str,
        scope: str,
    ):
        body = self._find_child_by_type(node, "declaration_list")
        if body:
            new_scope = f"{scope}.{parent}" if scope else parent
            for child in body.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, parent, new_scope)

    def _get_identifier_name(self, node, source: bytes) -> Optional[str]:
        for child in node.children:
            if child.type == "identifier":
                return self._get_text(child, source)
        return None

    def _find_child_by_type(self, node, child_type: str):
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _get_text(self, node, source: bytes) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _get_type_signature(self, node, source: bytes, type_kind: str) -> str:
        modifiers = []
        for child in node.children:
            if child.type == "modifier":
                modifiers.append(self._get_text(child, source))

        name = self._get_identifier_name(node, source) or ""
        sig = f"{type_kind} {name}"

        base_list = self._find_child_by_type(node, "base_list")
        if base_list:
            bases = self._get_text(base_list, source)
            sig += f" : {bases}"

        return sig

    def _get_method_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        params = self._find_child_by_type(node, "parameter_list")
        ret_type = self._find_child_by_type(node, "type")

        sig = name
        if params:
            sig += self._get_text(params, source)
        if ret_type:
            sig += f" : {self._get_text(ret_type, source)}"

        return sig

    def _get_property_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        prop_type = self._find_child_by_type(node, "type")

        if prop_type:
            return f"{self._get_text(prop_type, source)} {name}"
        return name
