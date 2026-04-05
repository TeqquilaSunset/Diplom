from pathlib import Path

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser

from ..models import FileInfo, Inheritance, ParsedFile, Symbol
from .base import BaseParser


class JavaScriptParser(BaseParser):
    language = "javascript"
    extensions = [".js", ".jsx", ".mjs", ".cjs"]

    def __init__(self):
        self._parser: Parser | None = None
        self._language: Language | None = None

    def _ensure_parser(self):
        if self._parser is None:
            self._language = Language(tsjs.language())
            self._parser = Parser(self._language)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.extensions

    def parse(self, file_path: Path, content: bytes) -> ParsedFile:
        self._ensure_parser()

        tree = self._parser.parse(content)
        root = tree.root_node

        file_info = FileInfo(
            path=str(file_path.resolve()),
            language="javascript",
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
        elif node_type == "function_declaration":
            self._process_function(node, source, file_path, symbols, parent, scope, "function")
        elif node_type == "arrow_function":
            self._process_arrow_function(node, source, file_path, symbols, parent, scope)
        elif node_type == "method_definition":
            self._process_method(node, source, file_path, symbols, parent, scope)
        elif node_type == "variable_declarator":
            self._process_variable_declarator(node, source, file_path, symbols, parent, scope)
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
                for heritage_child in child.children:
                    if heritage_child.type == "identifier":
                        parent_name = self._get_text(heritage_child, source)
                        inheritances.append(
                            Inheritance(
                                child_symbol=name,
                                child_file=file_path,
                                parent_symbol=parent_name,
                                parent_file=None,
                                kind="extends",
                            )
                        )
                    elif heritage_child.type == "member_expression":
                        parent_name = self._get_text(heritage_child, source)
                        inheritances.append(
                            Inheritance(
                                child_symbol=name,
                                child_file=file_path,
                                parent_symbol=parent_name,
                                parent_file=None,
                                kind="extends",
                            )
                        )

        body = self._find_child_by_type(node, "class_body")
        if body:
            new_scope = f"{scope}.{name}" if scope else name
            for child in body.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, name, new_scope)

    def _process_function(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str, kind: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        symbols.append(
            Symbol(
                name=name,
                kind=kind,
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

    def _process_arrow_function(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        pass

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

    def _process_variable_declarator(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        name = self._get_identifier_name(node, source)
        if not name:
            return

        value = self._find_child_by_type(node, "arrow_function")
        if value:
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
                    signature=self._get_arrow_function_signature(name, value, source),
                    docstring=None,
                    parent=parent,
                    scope=scope,
                )
            )

    def _get_identifier_name(self, node, source: bytes) -> str | None:
        for child in node.children:
            if child.type == "identifier":
                return self._get_text(child, source)
        return None

    def _get_property_name(self, node, source: bytes) -> str | None:
        for child in node.children:
            if child.type == "property_identifier":
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

        for child in node.children:
            if child.type == "class_heritage":
                heritage = self._get_text(child, source)
                sig += f" {heritage}"

        return sig

    def _get_function_signature(self, node, source: bytes) -> str:
        name = self._get_identifier_name(node, source) or ""
        params = self._find_child_by_type(node, "formal_parameters")

        sig = f"function {name}"
        if params:
            sig += self._get_text(params, source)

        return sig

    def _get_method_signature(self, node, source: bytes) -> str:
        name = self._get_property_name(node, source) or ""
        params = self._find_child_by_type(node, "formal_parameters")

        sig = name
        if params:
            sig += self._get_text(params, source)

        return sig

    def _get_arrow_function_signature(self, name: str, node, source: bytes) -> str:
        params = self._find_child_by_type(node, "formal_parameters")

        sig = f"{name} = "
        if params:
            sig += self._get_text(params, source)
        else:
            child = node.child(0)
            if child and child.type == "identifier":
                sig += f"({self._get_text(child, source)})"
        sig += " => { ... }"

        return sig
