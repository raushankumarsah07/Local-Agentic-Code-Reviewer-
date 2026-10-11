"""
Python AST Parser module using Python's standard library `ast` module.
Deterministically extracts classes, functions, inheritance, imports, calls,
and decorators without external dependencies or cloud calls.
Guarantees robust error handling: syntax errors will never crash execution.
"""

import ast
from pathlib import Path
from typing import Any, List, Optional

from app.parsing.base import (
    BaseParser,
    CallEntity,
    ClassEntity,
    FunctionEntity,
    ImportEntity,
    ParsedFile,
)


def _safe_unparse(node: Optional[ast.AST]) -> Optional[str]:
    """Safely convert an AST expression node back to readable source text."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return str(node)


def _resolve_callee_name(node: ast.AST) -> str:
    """
    Recursively extract the qualified name of a called function or method.
    Examples:
        validate_number(...)   -> 'validate_number'
        self.format_result(...) -> 'self.format_result'
        math.sqrt(...)         -> 'math.sqrt'
        a.b.c(...)             -> 'a.b.c'
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parent = _resolve_callee_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    elif isinstance(node, ast.Call):
        return _resolve_callee_name(node.func)
    else:
        return _safe_unparse(node) or "<anonymous>"


class _ASTVisitor(ast.NodeVisitor):
    """
    Traverses the Python AST tree, maintaining lexical scope to accurately
    associate calls with their enclosing functions or classes.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.classes: List[ClassEntity] = []
        self.functions: List[FunctionEntity] = []
        self.imports: List[ImportEntity] = []
        self.calls: List[CallEntity] = []
        self.top_level_statements: List[str] = []

        # Scope tracker: stack of names, e.g. ['module', 'Calculator', 'add']
        self._scope_stack: List[str] = ["module"]
        self._current_class: Optional[str] = None

    @property
    def current_context(self) -> str:
        """Returns the qualified name of the current scope, e.g. 'Calculator.add'."""
        if len(self._scope_stack) == 1:
            return self._scope_stack[0]
        return ".".join(self._scope_stack[1:])

    def visit_Import(self, node: ast.Import) -> None:
        """Extract 'import x', 'import x.y as z'."""
        for alias in node.names:
            self.imports.append(
                ImportEntity(
                    module=alias.name,
                    imported_name=alias.name,
                    alias=alias.asname,
                    is_relative=False,
                    level=0,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Extract 'from x import y', 'from .utils import z'."""
        is_rel = node.level > 0
        mod_name = node.module
        for alias in node.names:
            self.imports.append(
                ImportEntity(
                    module=mod_name,
                    imported_name=alias.name,
                    alias=alias.asname,
                    is_relative=is_rel,
                    level=node.level,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class definition, inheritance bases, and decorators."""
        # 1. Extract inheritance bases
        bases: List[str] = []
        for base in node.bases:
            base_repr = _safe_unparse(base)
            if base_repr:
                bases.append(base_repr)

        # 2. Extract decorators
        decorators = [_safe_unparse(d) for d in node.decorator_list if _safe_unparse(d)]

        # 3. Extract docstring
        docstring = ast.get_docstring(node)

        # 4. Push scope and collect methods
        previous_class = self._current_class
        self._current_class = node.name
        self._scope_stack.append(node.name)

        class_methods: List[FunctionEntity] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_entity = self._extract_function(item, is_method=True, class_name=node.name)
                class_methods.append(method_entity)
                # Also record method in the global visitor
                self.visit(item)
            else:
                self.visit(item)

        self._scope_stack.pop()
        self._current_class = previous_class

        class_entity = ClassEntity(
            name=node.name,
            bases=bases,
            methods=class_methods,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            decorators=decorators,
            has_docstring=docstring is not None,
            docstring=docstring,
        )
        self.classes.append(class_entity)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract standard synchronous function."""
        self._handle_function_node(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract asynchronous function (async def)."""
        self._handle_function_node(node, is_async=True)

    def _extract_function(
        self,
        node: ast.AST,
        is_method: bool = False,
        class_name: Optional[str] = None,
        is_async: bool = False,
    ) -> FunctionEntity:
        """Helper to create a FunctionEntity from a FunctionDef or AsyncFunctionDef."""
        # Extract parameter names with optional type hints
        params: List[str] = []
        for arg in node.args.args:
            annotation = _safe_unparse(arg.annotation)
            if annotation:
                params.append(f"{arg.arg}: {annotation}")
            else:
                params.append(arg.arg)

        # Variadic args (*args, **kwargs)
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")

        # Return type annotation
        return_type = _safe_unparse(getattr(node, "returns", None))

        # Decorators
        decorators = [_safe_unparse(d) for d in node.decorator_list if _safe_unparse(d)]

        # Docstring
        docstring = ast.get_docstring(node)

        # Collect calls inside the function body
        function_calls: List[str] = []
        for body_node in ast.walk(node):
            if isinstance(body_node, ast.Call):
                function_calls.append(_resolve_callee_name(body_node.func))

        return FunctionEntity(
            name=node.name,
            params=params,
            return_type=return_type,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            decorators=decorators,
            has_docstring=docstring is not None,
            docstring=docstring,
            is_async=is_async,
            is_method=is_method,
            class_name=class_name,
            calls=function_calls,
        )

    def _handle_function_node(self, node: ast.AST, is_async: bool = False) -> None:
        """Traverse into function body while updating the scope stack."""
        is_method = self._current_class is not None
        # Top-level functions are recorded in self.functions (methods are also in class.methods)
        if not is_method:
            func_entity = self._extract_function(
                node, is_method=False, class_name=None, is_async=is_async
            )
            self.functions.append(func_entity)

        # Push function name into scope stack and visit child expressions/calls
        self._scope_stack.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """Extract function/method invocation along with caller context."""
        callee = _resolve_callee_name(node.func)
        self.calls.append(
            CallEntity(
                caller_context=self.current_context,
                callee=callee,
                line_number=node.lineno,
            )
        )
        self.generic_visit(node)


class PythonParser(BaseParser):
    """
    Python AST Parser implementing the BaseParser interface.
    Uses Python's built-in `ast` module.
    """

    def parse_code(self, code: str, file_path: str = "") -> ParsedFile:
        """
        Parses Python source code into a structured ParsedFile.
        Gracefully intercepts syntax errors, returning is_parsable=False.
        """
        if not code.strip():
            # Empty file is valid and parsable
            return ParsedFile(file_path=file_path, is_parsable=True)

        try:
            tree = ast.parse(code, filename=file_path)
        except (SyntaxError, IndentationError) as e:
            line_no = e.lineno or 0
            offset = e.offset or 0
            return ParsedFile(
                file_path=file_path,
                is_parsable=False,
                error_message=f"SyntaxError on line {line_no}:{offset} - {e.msg}",
            )
        except Exception as e:
            return ParsedFile(
                file_path=file_path,
                is_parsable=False,
                error_message=f"Failed to parse AST: {str(e)}",
            )

        # Extract AST entities using visitor
        visitor = _ASTVisitor(file_path=file_path)
        visitor.visit(tree)

        # Record top-level statements
        top_level_stmts = [type(stmt).__name__ for stmt in tree.body]

        return ParsedFile(
            file_path=file_path,
            is_parsable=True,
            error_message=None,
            classes=visitor.classes,
            functions=visitor.functions,
            imports=visitor.imports,
            calls=visitor.calls,
            top_level_statements=top_level_stmts,
        )

    @staticmethod
    def dump_ast(code: str) -> str:
        """
        Helper utility to return a clean indented string dump of the raw Python AST.
        Useful for education, debugging, and visualization.
        """
        tree = ast.parse(code)
        return ast.dump(tree, indent=2)
