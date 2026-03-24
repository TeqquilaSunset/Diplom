from pathlib import Path
from typing import Optional
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from .base import BaseParser
from ..models import ParsedFile, FileInfo, Symbol, Inheritance, Reference


class PythonParser(BaseParser):
    language = "python"
    extensions = [".py", ".pyw"]

    def __init__(self):
        self._parser: Optional[Parser] = None
        self._language: Optional[Language] = None

    def _ensure_parser(self):
        if self._parser is None:
            self._language = Language(tspython.language())
            self._parser = Parser(self._language)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.extensions

    def parse(self, file_path: Path, content: bytes) -> ParsedFile:
        self._ensure_parser()

        tree = self._parser.parse(content)
        root = tree.root_node

        file_info = FileInfo(
            path=str(file_path.resolve()),
            language="python",
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
        """Walk the tree and extract symbols."""
        node_type = node.type

        if node_type == "class_definition":
            self._process_class(node, source, file_path, symbols, inheritances, scope)
        elif node_type == "function_definition":
            self._process_function(node, source, file_path, symbols, parent, scope)
        else:
            for child in node.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, parent, scope)

    def _process_class(
        self, node, source: bytes, file_path: str, symbols: list, inheritances: list, scope: str
    ):
        """Process a class definition."""
        name = self._get_name(node, source)
        if not name:
            return

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        signature = self._get_class_signature(node, source)

        symbols.append(
            Symbol(
                name=name,
                kind="class",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=signature,
                docstring=self._get_docstring(node, source),
                parent=None,
                scope=scope,
            )
        )

        arg_list = self._find_child_by_type(node, "argument_list")
        if arg_list:
            for arg in arg_list.children:
                if arg.type == "identifier" or arg.type == "attribute":
                    parent_name = self._get_text(arg, source)
                    inheritances.append(
                        Inheritance(
                            child_symbol=name,
                            child_file=file_path,
                            parent_symbol=parent_name,
                            parent_file=None,
                            kind="extends",
                        )
                    )

        body = self._find_child_by_type(node, "block")
        if body:
            new_scope = f"{scope}.{name}" if scope else name
            for child in body.children:
                self._walk_tree(child, source, file_path, symbols, inheritances, name, new_scope)

    def _process_function(
        self, node, source: bytes, file_path: str, symbols: list, parent: str, scope: str
    ):
        """Process a function definition."""
        name = self._get_name(node, source)
        if not name:
            return

        kind = "method" if parent else "function"
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        signature = self._get_function_signature(node, source)

        symbols.append(
            Symbol(
                name=name,
                kind=kind,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=signature,
                docstring=self._get_docstring(node, source),
                parent=parent,
                scope=scope,
            )
        )

    def _get_name(self, node, source: bytes) -> Optional[str]:
        """Get the name of a definition node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_text(child, source)
        return None

    def _find_child_by_type(self, node, child_type: str):
        """Find a child node by type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _get_text(self, node, source: bytes) -> str:
        """Get text content of a node."""
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _get_class_signature(self, node, source: bytes) -> str:
        """Get class signature including bases."""
        parts = ["class"]
        name = self._get_name(node, source)
        if name:
            parts.append(name)

        arg_list = self._find_child_by_type(node, "argument_list")
        if arg_list:
            parts.append("(" + self._get_text(arg_list, source)[1:-1] + ")")

        return " ".join(parts)

    def _get_function_signature(self, node, source: bytes) -> str:
        """Get function signature including params and return type."""
        parts = ["def"]
        name = self._get_name(node, source)
        if name:
            parts.append(name)

        params = self._find_child_by_type(node, "parameters")
        if params:
            parts.append(self._get_text(params, source))

        ret_type = self._find_child_by_type(node, "type")
        if ret_type:
            parts.append("-> " + self._get_text(ret_type, source))

        return " ".join(parts)

    def _get_docstring(self, node, source: bytes) -> Optional[str]:
        """Extract docstring from a node's body."""
        body = self._find_child_by_type(node, "block")
        if not body:
            return None

        for child in body.children:
            if child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "string":
                        return self._get_text(expr_child, source)
        return None
