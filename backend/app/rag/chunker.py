"""
backend/app/rag/chunker.py

AST-Aware Code Chunker for Phase 9a.
Extracts semantic code chunks (functions, classes, methods) using Python's AST
with size caps and line tracking, preserving architectural metadata.
Falls back safely to sliding-window chunks for non-Python or unparsable files.
"""

import ast
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CodeChunk(BaseModel):
    """
    Semantic chunk of source code with architectural and lexical metadata.
    """
    chunk_id: str = Field(..., description="Unique deterministic identifier for the chunk")
    project_id: str = Field(..., description="ID of the parent project")
    file_path: str = Field(..., description="Relative repository file path")
    symbol_name: Optional[str] = Field(None, description="Function, class, or method name")
    entity_type: str = Field(..., description="'function', 'method', 'class', 'module', or 'raw_block'")
    start_line: int = Field(..., description="1-indexed starting line number")
    end_line: int = Field(..., description="1-indexed ending line number")
    language: str = Field(default="python", description="Programming language")
    content: str = Field(..., description="Source code text of the chunk")
    parent_name: Optional[str] = Field(None, description="Enclosing class name if a method")
    char_count: int = Field(default=0, description="Character count of content")
    token_estimate: int = Field(default=0, description="Estimated token count (approx char_count / 3.8)")


class ASTChunker:
    """
    AST-aware source code chunker that extracts one chunk per function/class/method
    with configurable size capping.
    """

    def __init__(
        self,
        size_cap_chars: int = 1500,
        subchunk_overlap_chars: int = 200,
    ):
        """
        :param size_cap_chars: Maximum characters allowed per chunk before splitting into subchunks.
        :param subchunk_overlap_chars: Overlap character count when splitting oversized functions.
        """
        self.size_cap_chars = size_cap_chars
        self.subchunk_overlap_chars = subchunk_overlap_chars

    def _generate_chunk_id(
        self,
        project_id: str,
        file_path: str,
        symbol: Optional[str],
        start_line: int,
        part_idx: int = 0,
    ) -> str:
        """Create a deterministic unique chunk ID."""
        raw_key = f"{project_id}:{file_path}:{symbol or 'block'}:{start_line}:{part_idx}"
        hash_suffix = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
        clean_sym = (symbol or "block").replace(".", "_")
        return f"{clean_sym}_{start_line}_{hash_suffix}"

    def chunk_python_code(
        self,
        code: str,
        file_path: str,
        project_id: str = "default",
    ) -> List[CodeChunk]:
        """
        Parse Python source code via AST and generate semantic chunks for functions,
        methods, and classes.
        """
        if not code or not code.strip():
            return []

        lines = code.splitlines(keepends=True)
        total_lines = len(lines)

        try:
            tree = ast.parse(code, filename=file_path)
        except (SyntaxError, ValueError) as err:
            logger.warning("AST parse error in %s: %s. Using sliding-window fallback.", file_path, err)
            return self.chunk_raw_text(
                text=code,
                file_path=file_path,
                project_id=project_id,
                language="python",
            )

        chunks: List[CodeChunk] = []

        # 1. Top-Level Module Header (docstring or top-level imports)
        module_docstring = ast.get_docstring(tree)
        if module_docstring:
            # Capture initial module docstring
            doc_lines = module_docstring.splitlines()
            end_doc_line = min(total_lines, len(doc_lines) + 4)
            doc_content = "".join(lines[:end_doc_line]).strip()
            if doc_content:
                chunks.append(
                    CodeChunk(
                        chunk_id=self._generate_chunk_id(project_id, file_path, "module_doc", 1),
                        project_id=project_id,
                        file_path=file_path,
                        symbol_name=Path(file_path).stem,
                        entity_type="module",
                        start_line=1,
                        end_line=end_doc_line,
                        language="python",
                        content=doc_content,
                        parent_name=None,
                        char_count=len(doc_content),
                        token_estimate=max(1, len(doc_content) // 4),
                    )
                )

        # 2. Iterate AST top-level nodes
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunks.extend(
                    self._chunk_function_node(
                        node=node,
                        lines=lines,
                        file_path=file_path,
                        project_id=project_id,
                        parent_name=None,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                chunks.extend(
                    self._chunk_class_node(
                        node=node,
                        lines=lines,
                        file_path=file_path,
                        project_id=project_id,
                    )
                )

        # 3. If no functions or classes were found (e.g. script-like code with only top-level statements)
        if not chunks:
            return self.chunk_raw_text(
                text=code,
                file_path=file_path,
                project_id=project_id,
                language="python",
            )

        return chunks

    def _chunk_function_node(
        self,
        node: ast.AST,
        lines: List[str],
        file_path: str,
        project_id: str,
        parent_name: Optional[str] = None,
    ) -> List[CodeChunk]:
        """Extract a function or method node into one or more chunks."""
        fn_name = getattr(node, "name", "anonymous")
        qualified_name = f"{parent_name}.{fn_name}" if parent_name else fn_name
        entity_type = "method" if parent_name else "function"

        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        # Extract source code lines
        fn_lines = lines[start_line - 1 : end_line]
        fn_content = "".join(fn_lines).rstrip()

        # If function fits within size cap, return as single semantic chunk
        if len(fn_content) <= self.size_cap_chars:
            chunk_id = self._generate_chunk_id(project_id, file_path, qualified_name, start_line)
            return [
                CodeChunk(
                    chunk_id=chunk_id,
                    project_id=project_id,
                    file_path=file_path,
                    symbol_name=qualified_name,
                    entity_type=entity_type,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    content=fn_content,
                    parent_name=parent_name,
                    char_count=len(fn_content),
                    token_estimate=max(1, len(fn_content) // 4),
                )
            ]

        # Oversized function: split into capped subchunks while preserving signature context
        return self._split_oversized_code(
            content=fn_content,
            symbol_name=qualified_name,
            entity_type=entity_type,
            file_path=file_path,
            project_id=project_id,
            start_line=start_line,
            parent_name=parent_name,
        )

    def _chunk_class_node(
        self,
        node: ast.ClassDef,
        lines: List[str],
        file_path: str,
        project_id: str,
    ) -> List[CodeChunk]:
        """Extract a class definition into class header and method chunks."""
        class_name = node.name
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        chunks: List[CodeChunk] = []

        # Find first method line to extract class header
        methods: List[ast.AST] = []
        first_method_line = end_line + 1

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item)
                item_line = getattr(item, "lineno", end_line)
                if item_line < first_method_line:
                    first_method_line = item_line

        # Class header chunk (class signature, docstring, class attributes)
        header_end = min(end_line, first_method_line - 1) if methods else end_line
        header_lines = lines[start_line - 1 : header_end]
        header_content = "".join(header_lines).rstrip()

        if header_content.strip():
            header_chunk_id = self._generate_chunk_id(project_id, file_path, class_name, start_line)
            chunks.append(
                CodeChunk(
                    chunk_id=header_chunk_id,
                    project_id=project_id,
                    file_path=file_path,
                    symbol_name=class_name,
                    entity_type="class",
                    start_line=start_line,
                    end_line=header_end,
                    language="python",
                    content=header_content,
                    parent_name=None,
                    char_count=len(header_content),
                    token_estimate=max(1, len(header_content) // 4),
                )
            )

        # Individual method chunks
        for method_node in methods:
            chunks.extend(
                self._chunk_function_node(
                    node=method_node,
                    lines=lines,
                    file_path=file_path,
                    project_id=project_id,
                    parent_name=class_name,
                )
            )

        return chunks

    def _split_oversized_code(
        self,
        content: str,
        symbol_name: str,
        entity_type: str,
        file_path: str,
        project_id: str,
        start_line: int,
        parent_name: Optional[str] = None,
    ) -> List[CodeChunk]:
        """Split oversized code snippet into subchunks of size cap."""
        subchunks: List[CodeChunk] = []
        lines = content.splitlines(keepends=True)

        current_lines: List[str] = []
        current_chars = 0
        current_start_line = start_line
        part_idx = 1

        for idx, line in enumerate(lines):
            line_len = len(line)
            if current_chars + line_len > self.size_cap_chars and current_lines:
                chunk_text = f"# [{symbol_name} - part {part_idx}]\n" + "".join(current_lines).rstrip()
                chunk_end_line = current_start_line + len(current_lines) - 1

                subchunks.append(
                    CodeChunk(
                        chunk_id=self._generate_chunk_id(
                            project_id, file_path, symbol_name, current_start_line, part_idx
                        ),
                        project_id=project_id,
                        file_path=file_path,
                        symbol_name=f"{symbol_name} (part {part_idx})",
                        entity_type=entity_type,
                        start_line=current_start_line,
                        end_line=chunk_end_line,
                        language="python",
                        content=chunk_text,
                        parent_name=parent_name,
                        char_count=len(chunk_text),
                        token_estimate=max(1, len(chunk_text) // 4),
                    )
                )

                # Overlap: keep last few lines
                overlap_lines = current_lines[-3:] if len(current_lines) >= 3 else []
                current_lines = list(overlap_lines)
                current_chars = sum(len(l) for l in current_lines)
                current_start_line = chunk_end_line - len(overlap_lines) + 1
                part_idx += 1

            current_lines.append(line)
            current_chars += line_len

        if current_lines:
            chunk_text = f"# [{symbol_name} - part {part_idx}]\n" + "".join(current_lines).rstrip()
            chunk_end_line = current_start_line + len(current_lines) - 1
            subchunks.append(
                CodeChunk(
                    chunk_id=self._generate_chunk_id(
                        project_id, file_path, symbol_name, current_start_line, part_idx
                    ),
                    project_id=project_id,
                    file_path=file_path,
                    symbol_name=f"{symbol_name} (part {part_idx})",
                    entity_type=entity_type,
                    start_line=current_start_line,
                    end_line=chunk_end_line,
                    language="python",
                    content=chunk_text,
                    parent_name=parent_name,
                    char_count=len(chunk_text),
                    token_estimate=max(1, len(chunk_text) // 4),
                )
            )

        return subchunks

    def chunk_raw_text(
        self,
        text: str,
        file_path: str,
        project_id: str = "default",
        language: str = "text",
        lines_per_chunk: int = 50,
        overlap_lines: int = 10,
    ) -> List[CodeChunk]:
        """Sliding window chunking for non-Python or unparsable files."""
        if not text or not text.strip():
            return []

        all_lines = text.splitlines(keepends=True)
        total = len(all_lines)
        chunks: List[CodeChunk] = []
        step = max(1, lines_per_chunk - overlap_lines)

        for i in range(0, total, step):
            slice_lines = all_lines[i : i + lines_per_chunk]
            if not slice_lines:
                break
            content = "".join(slice_lines).rstrip()
            start_line = i + 1
            end_line = min(total, i + len(slice_lines))
            part_idx = (i // step) + 1

            chunk_id = self._generate_chunk_id(
                project_id, file_path, "block", start_line, part_idx
            )
            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    project_id=project_id,
                    file_path=file_path,
                    symbol_name=f"{Path(file_path).stem}_L{start_line}",
                    entity_type="raw_block",
                    start_line=start_line,
                    end_line=end_line,
                    language=language,
                    content=content,
                    parent_name=None,
                    char_count=len(content),
                    token_estimate=max(1, len(content) // 4),
                )
            )

        return chunks


def chunk_file(
    file_path: Path,
    repo_root: Path,
    project_id: str,
    size_cap_chars: int = 1500,
) -> List[CodeChunk]:
    """Helper to read and chunk a single file from the repository."""
    chunker = ASTChunker(size_cap_chars=size_cap_chars)
    rel_path = str(file_path.relative_to(repo_root))

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_path, e)
        return []

    if file_path.suffix.lower() == ".py":
        return chunker.chunk_python_code(content, rel_path, project_id=project_id)
    else:
        return chunker.chunk_raw_text(
            content,
            rel_path,
            project_id=project_id,
            language=file_path.suffix.lstrip(".").lower() or "text",
        )
