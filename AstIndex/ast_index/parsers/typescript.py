from pathlib import Path
from typing import Optional
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

from .base import BaseParser
from ..models import ParsedFile, FileInfo, Symbol, Inheritance, Reference


class TypeScriptParser(BaseParser):
    language = "typescript"
    extensions = [".ts", ".tsx"]

    def __init__(self):
        self._parser: Optional[Parser] = None
        self._language: Optional[Language] = None

    def _ensure_parser(self):
        if self._parser is None:
            self._language = Language(tstypescript.language_typescript())
            self._parser = Parser(self._language)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.extensions

    def parse(self, file_path: Path, content: bytes) -> ParsedFile:
        self._ensure_parser()

        tree = self._parser.parse(content)
        root = tree.root_node

        file_info = FileInfo(
            path=str(file_path.resolve()),
            language="typescript",
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
        elif node_type == "enum_declaration":
            self._process_enum(node, source, file_path, symbols, scope)
        elif node_type == "type_alias_declaration":
            self._process_type_alias(node, source, file_path, symbols, scope)
        elif node_type == "function_declaration":
            self._process_function(node, source, file_path, symbols, parent, scope)
        elif node_type == "method_definition":
            self._process_method(node, source, file_path, symbols, parent, scope)
        elif node_type in ("public_field_definition", "field_definition"):
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
                signature=self._get_class_signature(node, source),
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

        for child in node.children:
            if child.type == "class_heritage":
                self._process_heritage(child, source, file_path, name, inheritances)

        body = self._find_child_by_type(node, "class_body")
        if body:
            new_scope = f"{scope}.{name}" if scope else name
            for child in body.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, name, new_scope)

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
                signature=self._get_interface_signature(node, source),
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

        for child in node.children:
            if child.type in ("extends_clause", "heritage_clause"):
                for ext_child in child.children:
                    if ext_child.type in ("identifier", "type_identifier", "generic_type"):
                        parent_name = self._get_text(ext_child, source)
                        inheritances.append(
                            Inheritance(
                                child_symbol=name,
                                child_file=file_path,
                                parent_symbol=parent_name,
                                parent_file=None,
                                kind="extends",
                            )
                        )

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

    def _process_type_alias(self, node, source: bytes, file_path: str, symbols: list, scope: str):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        type_value = self._find_child_by_type(node, "object_type")
        if not type_value:
            type_value = self._find_child_by_type(node, "union_type")
        if not type_value:
            type_value = self._find_child_by_type(node, "type")

        signature = f"type {name}"
        if type_value:
            signature += f" = {self._get_text(type_value, source)}"

        symbols.append(
            Symbol(
                name=name,
                kind="type_alias",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=signature,
                docstring=None,
                parent=None,
                scope=scope,
            )
        )

    def _process_function(
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
                kind="function",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=self._get_function_signature(node, source),
                docstring=None,
                parent=parent,
                scope=scope,
            )
        )

    def _process_method(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        name = self._get_property_name(node, source)
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

    def _process_field(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        name = self._get_property_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        type_node = self._find_child_by_type(node, "type_annotation")
        signature = name
        if type_node:
            signature += self._get_text(type_node, source)

        symbols.append(
            Symbol(
                name=name,
                kind="field",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=signature,
                docstring=None,
                parent=parent,
                scope=scope,
            )
        )

    def _process_heritage(
        self, node, source: bytes, file_path: str, child_name: str, inheritances: list
    ):
        for child in node.children:
            if child.type == "extends_clause":
                for ext_child in child.children:
                    if ext_child.type in ("identifier", "type_identifier", "generic_type"):
                        parent_name = self._get_text(ext_child, source)
                        inheritances.append(
                            Inheritance(
                                child_symbol=child_name,
                                child_file=file_path,
                                parent_symbol=parent_name,
                                parent_file=None,
                                kind="extends",
                            )
                        )
            elif child.type == "implements_clause":
                for impl_child in child.children:
                    if impl_child.type in ("identifier", "type_identifier", "generic_type"):
                        parent_name = self._get_text(impl_child, source)
                        inheritances.append(
                            Inheritance(
                                child_symbol=child_name,
                                child_file=file_path,
                                parent_symbol=parent_name,
                                parent_file=None,
                                kind="implements",
                            )
                        )

    def _get_identifier_name(self, node, source: bytes) -> Optional[str]:
        for child in node.children:
            if child.type in ("identifier", "type_identifier"):
                return self._get_text(child, source)
        return None

    def _get_property_name(self, node, source: bytes) -> Optional[str]:
        for child in node.children:
            if child.type in ("property_identifier", "identifier"):
                return self._get_text(child, source)
        return None

    def _find_child_by_type(self, node, child_type: str):
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _get_class_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        sig = f"class {name}"

        heritage = self._find_child_by_type(node, "class_heritage")
        if heritage:
            sig += f" {self._get_text(heritage, source)}"

        return sig

    def _get_interface_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        return f"interface {name}"

    def _get_function_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        params = self._find_child_by_type(node, "formal_parameters")
        ret_type = self._find_child_by_type(node, "type_annotation")

        sig = f"function {name}"
        if params:
            sig += self._get_text(params, source)
        if ret_type:
            sig += f": {self._get_text(ret_type, source)}"

        return sig

    def _get_method_signature(self, node, source: bytes) -> str:
        name = self._get_property_name(node, source) or ""
        params = self._find_child_by_type(node, "formal_parameters")
        ret_type = self._find_child_by_type(node, "type_annotation")

        sig = name
        if params:
            sig += self._get_text(params, source)
        if ret_type:
            sig += f": {self._get_text(ret_type, source)}"

        return sig
