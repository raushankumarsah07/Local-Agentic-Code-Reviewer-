"""
Base parser interface and data schemas for Abstract Syntax Tree (AST) extraction.
Designed as an extensible interface so Tree-sitter or other language parsers
can be plugged in without changing the analysis pipeline.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ImportEntity(BaseModel):
    """Represents an imported module or symbol."""
    model_config = ConfigDict(from_attributes=True)

    module: Optional[str] = Field(None, description="Module imported from, e.g. 'utils.helpers'")
    imported_name: str = Field(..., description="Name of the imported symbol or '*'")
    alias: Optional[str] = Field(None, description="Import alias if any, e.g. 'np'")
    is_relative: bool = Field(False, description="True if imported with relative syntax like from . import x")
    level: int = Field(0, description="Relative import level (1 for ., 2 for .., etc.)")
    line_number: int = Field(..., description="Source code line number of import")


class CallEntity(BaseModel):
    """Represents a function or method invocation."""
    model_config = ConfigDict(from_attributes=True)

    caller_context: str = Field("module", description="Enclosing scope (function, method, or 'module')")
    callee: str = Field(..., description="Qualified or simple function/method name called")
    line_number: int = Field(..., description="Source code line number where call occurs")


class FunctionEntity(BaseModel):
    """Represents a function or class method."""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Function or method name")
    params: List[str] = Field(default_factory=list, description="List of parameter names")
    return_type: Optional[str] = Field(None, description="Annotated return type if present")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    decorators: List[str] = Field(default_factory=list, description="Names of applied decorators")
    has_docstring: bool = Field(False, description="Whether function contains a docstring")
    docstring: Optional[str] = Field(None, description="Extracted docstring text")
    is_async: bool = Field(False, description="True if defined with async def")
    is_method: bool = Field(False, description="True if function belongs to a class")
    class_name: Optional[str] = Field(None, description="Parent class name if this is a method")
    calls: List[str] = Field(default_factory=list, description="List of callees invoked inside function body")


class ClassEntity(BaseModel):
    """Represents a class definition and its inheritance."""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Class name")
    bases: List[str] = Field(default_factory=list, description="Base class names (inheritance)")
    methods: List[FunctionEntity] = Field(default_factory=list, description="Methods defined in the class")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    decorators: List[str] = Field(default_factory=list, description="Decorators on the class")
    has_docstring: bool = Field(False, description="Whether class contains a docstring")
    docstring: Optional[str] = Field(None, description="Extracted docstring text")


class ParsedFile(BaseModel):
    """Complete AST extraction payload for a single source file."""
    model_config = ConfigDict(from_attributes=True)

    file_path: str = Field(..., description="Relative path of file within repository")
    is_parsable: bool = Field(True, description="False if file contained fatal syntax/parse errors")
    error_message: Optional[str] = Field(None, description="Error message if is_parsable is False")
    classes: List[ClassEntity] = Field(default_factory=list, description="All classes defined in the file")
    functions: List[FunctionEntity] = Field(default_factory=list, description="Top-level functions in the file")
    imports: List[ImportEntity] = Field(default_factory=list, description="All import statements")
    calls: List[CallEntity] = Field(default_factory=list, description="All function calls across file")
    top_level_statements: List[str] = Field(
        default_factory=list, description="Kinds of top-level statements (e.g. Assign, Expr, If)"
    )


class BaseParser(ABC):
    """
    Abstract base parser interface.
    Allows swappable language parsers (PythonParser, TreeSitterParser, etc.).
    """

    @abstractmethod
    def parse_code(self, code: str, file_path: str = "") -> ParsedFile:
        """
        Parse raw source code string into a structured ParsedFile.
        Must never raise syntax exceptions; captures errors into ParsedFile.error_message.
        """
        pass

    def parse_file(self, file_path: Path, project_root: Optional[Path] = None) -> ParsedFile:
        """
        Read and parse a file from disk.
        """
        rel_path = (
            file_path.relative_to(project_root).as_posix()
            if project_root and file_path.is_relative_to(project_root)
            else file_path.as_posix()
        )
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            return self.parse_code(code, file_path=rel_path)
        except Exception as e:
            return ParsedFile(
                file_path=rel_path,
                is_parsable=False,
                error_message=f"I/O or reading error: {str(e)}",
            )
