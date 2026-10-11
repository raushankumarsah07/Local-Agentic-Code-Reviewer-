"""
Projects API router: Handles repository uploads, ZIP decompression,
repository scanning, project metadata, and file listings.
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import crud
from app.db.session import get_db
from app.ingestion.scanner import ScanSummary, detect_language, scan_repository
from app.ingestion.zip_handler import (
    ExtractionResult,
    ZipBombError,
    ZipExtractionError,
    ZipSlipError,
    safe_extract_zip,
)
from app.parsing.base import ParsedFile
from app.parsing.python_parser import PythonParser

router = APIRouter(prefix="/projects", tags=["Projects"])


# --- Pydantic Request & Response Schemas ---

class ProjectUploadResponse(BaseModel):
    """Response returned upon successful ZIP upload, extraction, and repository scanning."""
    project_id: str = Field(..., description="Unique identifier for the uploaded project")
    project_name: str = Field(..., description="Original name of the uploaded project archive")
    file_count: int = Field(..., description="Number of valid code and text files scanned")
    total_lines: int = Field(..., description="Total line count across all scanned files")
    skipped_count: int = Field(..., description="Number of ignored files (binaries, node_modules, etc.)")
    languages: Dict[str, int] = Field(default_factory=dict, description="File counts grouped by language")
    target_directory: str = Field(..., description="Path where repository is saved on disk")
    message: str = Field(..., description="Status message")


class ProjectFileItem(BaseModel):
    """Metadata schema for an individual file within a project."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    language: str
    size_bytes: int
    line_count: int
    created_at: Optional[datetime] = None


class ProjectFilesListResponse(BaseModel):
    """Response schema for listing files of a project."""
    project_id: str
    total_files: int
    total_lines: int
    languages: Dict[str, int]
    count: int
    files: List[ProjectFileItem]


class SourceLine(BaseModel):
    """Single line of source code with 1-indexed line number."""
    line_number: int
    content: str


class SourceFileResponse(BaseModel):
    """Source file contents with line-by-line numbering and metadata."""
    project_id: str
    file_path: str
    language: str
    total_lines: int
    size_bytes: int
    lines: List[SourceLine]
    raw_content: str


class ProjectDetail(BaseModel):
    """Detailed summary of a project."""
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    name: str
    path: str
    total_files: int
    total_lines: int
    total_size_bytes: int
    created_at: datetime
    languages: Dict[str, int] = Field(default_factory=dict)


# --- API Endpoints ---

@router.post(
    "/upload",
    response_model=ProjectUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and scan a ZIP repository",
    description=(
        "Accepts a ZIP file, verifies security (anti-zip-slip, size limits), "
        "extracts code to workspace, executes the repository scanner, "
        "and persists all file metadata to the database."
    ),
)
async def upload_project(
    file: UploadFile = File(..., description="ZIP archive of the software project"),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ProjectUploadResponse:
    """
    Handle project ZIP upload:
    1. Validate filename has .zip extension.
    2. Assign a unique project_id.
    3. Safely extract files using safe_extract_zip().
    4. Run repository scanner to extract file paths, languages, sizes, and line counts.
    5. Save project and file records to the database.
    6. Return project summary.
    """
    filename = file.filename or "unknown.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .zip archives are supported.",
        )

    # Generate a collision-free project identifier
    project_id = uuid.uuid4().hex[:12]
    target_dir = (settings.WORKSPACE_DIR / project_id).resolve()

    try:
        extraction_result: ExtractionResult = safe_extract_zip(
            zip_source=file.file,
            destination_dir=target_dir,
            project_id=project_id,
            max_size_bytes=settings.max_upload_size_bytes,
            max_file_count=settings.MAX_FILE_COUNT,
        )
    except ZipSlipError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Violation (Zip-Slip): {str(e)}",
        )
    except ZipBombError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Archive Safety Limit Exceeded: {str(e)}",
        )
    except ZipExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract ZIP: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during project extraction: {str(e)}",
        )

    clean_name = Path(filename).stem

    # Phase 2: Execute repository scanner on unpacked workspace
    scan_summary: ScanSummary = scan_repository(target_dir, project_id)

    # Persist project and file metadata in database
    crud.create_project(
        db=db,
        project_id=project_id,
        name=clean_name,
        path=str(target_dir),
        total_files=scan_summary.total_files,
        total_lines=scan_summary.total_lines,
        total_size_bytes=scan_summary.total_size_bytes,
    )

    files_payload = [
        {
            "path": f.path,
            "language": f.language,
            "size_bytes": f.size_bytes,
            "line_count": f.line_count,
        }
        for f in scan_summary.files
    ]
    crud.save_project_files(db=db, project_id=project_id, files_data=files_payload)

    return ProjectUploadResponse(
        project_id=project_id,
        project_name=clean_name,
        file_count=scan_summary.total_files,
        total_lines=scan_summary.total_lines,
        skipped_count=extraction_result.skipped_files_count,
        languages=scan_summary.languages,
        target_directory=str(target_dir),
        message="Repository uploaded, extracted, and scanned successfully.",
    )


@router.get(
    "",
    response_model=List[ProjectDetail],
    summary="List all registered projects",
)
async def list_projects(db: Session = Depends(get_db)) -> List[ProjectDetail]:
    """Retrieve all projects stored in the database with their metadata and language distributions."""
    projects = crud.list_projects(db)
    result = []
    for p in projects:
        languages = crud.get_project_language_stats(db, p.id)
        result.append(
            ProjectDetail(
                project_id=p.id,
                name=p.name,
                path=p.path,
                total_files=p.total_files,
                total_lines=p.total_lines,
                total_size_bytes=p.total_size_bytes,
                created_at=p.created_at,
                languages=languages,
            )
        )
    return result


@router.get(
    "/{project_id}",
    response_model=ProjectDetail,
    summary="Get project overview by ID",
)
async def get_project_details(project_id: str, db: Session = Depends(get_db)) -> ProjectDetail:
    """Retrieve details and metrics for a specific project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )
    languages = crud.get_project_language_stats(db, project_id)
    return ProjectDetail(
        project_id=project.id,
        name=project.name,
        path=project.path,
        total_files=project.total_files,
        total_lines=project.total_lines,
        total_size_bytes=project.total_size_bytes,
        created_at=project.created_at,
        languages=languages,
    )


@router.get(
    "/{project_id}/files",
    response_model=ProjectFilesListResponse,
    summary="List files in a project",
    description="Retrieve scanned files with language, size, and line count. Supports language filtering and pagination.",
)
async def list_project_files(
    project_id: str,
    language: Optional[str] = Query(None, description="Filter by language (e.g. Python, Markdown)"),
    limit: int = Query(500, ge=1, le=2000, description="Max files to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> ProjectFilesListResponse:
    """Retrieve all scanned files for a project, optionally filtered by language."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    files, total_filtered = crud.get_project_files(
        db=db,
        project_id=project_id,
        language=language,
        limit=limit,
        offset=offset,
    )
    language_stats = crud.get_project_language_stats(db, project_id)

    return ProjectFilesListResponse(
        project_id=project.id,
        total_files=project.total_files,
        total_lines=project.total_lines,
        languages=language_stats,
        count=len(files),
        files=[ProjectFileItem.model_validate(f) for f in files],
    )


@router.get(
    "/{project_id}/files/{file_path:path}",
    response_model=SourceFileResponse,
    summary="Get source code file with line numbers",
    description="Returns source code broken down into 1-indexed line numbers. Strictly prevents directory and path traversal attacks.",
)
@router.get(
    "/{project_id}/source",
    response_model=SourceFileResponse,
    summary="Get source code file via path query parameter",
    description="Alternative endpoint accepting file path via ?path= query param to prevent client-side path normalization.",
)
async def get_source_file(
    project_id: str,
    file_path: Optional[str] = None,
    path: Optional[str] = Query(None, description="Path to file within project"),
    db: Session = Depends(get_db),
) -> SourceFileResponse:
    """
    Retrieve source file content line-by-line with safe boundary checking.
    Guards against path traversal attacks like ../../etc/passwd or absolute paths.
    """
    target_param = file_path if file_path is not None else path
    if not target_param:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File path must be specified.",
        )

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path).resolve()

    # Security: Normalize path and prevent directory traversal
    clean_rel = target_param.lstrip("/\\")
    try:
        resolved_file = (project_root / clean_rel).resolve()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path provided.",
        )

    # Strictly verify target file is a child of project_root (Anti-Path Traversal)
    try:
        if not resolved_file.is_relative_to(project_root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security Violation: Path traversal attempt detected. Access denied.",
            )
    except AttributeError:
        if not str(resolved_file).startswith(str(project_root) + os.sep) and resolved_file != project_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security Violation: Path traversal attempt detected. Access denied.",
            )

    if not resolved_file.exists() or not resolved_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_path}' does not exist in project '{project_id}'.",
        )

    try:
        with open(resolved_file, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}",
        )

    split_lines = raw_text.splitlines()
    lines = [
        SourceLine(line_number=idx + 1, content=line)
        for idx, line in enumerate(split_lines)
    ]

    rel_display_path = resolved_file.relative_to(project_root).as_posix()
    size_bytes = resolved_file.stat().st_size
    language = detect_language(resolved_file)

    return SourceFileResponse(
        project_id=project.id,
        file_path=rel_display_path,
        language=language,
        total_lines=len(split_lines),
        size_bytes=size_bytes,
        lines=lines,
        raw_content=raw_text,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a project",
)
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Delete a project from the database and remove its workspace files from disk."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    # Delete disk directory
    project_dir = Path(project.path)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    # Delete database record (cascades to files)
    crud.delete_project(db, project_id)

    return {"message": f"Project '{project_id}' successfully deleted."}


# --- Phase 3: AST Parsing Endpoints ---

class ProjectParseSummaryResponse(BaseModel):
    """Summary of AST parsing results for a project."""
    project_id: str
    parsed_files_count: int
    unparsable_files_count: int
    total_classes: int
    total_functions: int
    total_methods: int
    total_imports: int
    total_calls: int
    unparsable_files: List[Dict[str, str]] = Field(default_factory=list)


class EntityItemResponse(BaseModel):
    """Extracted code entity metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    entity_type: str
    name: str
    parent_name: Optional[str] = None
    start_line: int
    end_line: int
    details: Optional[str] = None


@router.post(
    "/{project_id}/parse",
    response_model=ProjectParseSummaryResponse,
    summary="Run AST parser on project Python files",
    description="Parses all Python source files using PythonParser, extracts classes, functions, calls, and imports, and stores entities in the database.",
)
async def parse_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProjectParseSummaryResponse:
    """Parse all Python files in the project workspace and persist AST entities."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    # Fetch all Python files recorded in database for this project
    py_files, _ = crud.get_project_files(db=db, project_id=project_id, language="Python")
    parser = PythonParser()
    project_root = Path(project.path)

    parsed_count = 0
    unparsable_count = 0
    unparsable_info = []

    total_classes = 0
    total_functions = 0
    total_methods = 0
    total_imports = 0
    total_calls = 0

    entities_to_save: List[dict] = []

    for file_record in py_files:
        full_path = project_root / file_record.path
        parsed: ParsedFile = parser.parse_file(full_path, project_root=project_root)

        if not parsed.is_parsable:
            unparsable_count += 1
            unparsable_info.append({"file": file_record.path, "error": parsed.error_message or "Unknown error"})
            continue

        parsed_count += 1
        total_classes += len(parsed.classes)
        total_functions += len(parsed.functions)
        total_imports += len(parsed.imports)
        total_calls += len(parsed.calls)

        # 1. Classes & their methods
        for cls in parsed.classes:
            entities_to_save.append({
                "file_path": file_record.path,
                "entity_type": "class",
                "name": cls.name,
                "parent_name": None,
                "start_line": cls.start_line,
                "end_line": cls.end_line,
                "details": json.dumps({
                    "bases": cls.bases,
                    "decorators": cls.decorators,
                    "docstring": cls.docstring,
                    "methods_count": len(cls.methods),
                }),
            })

            total_methods += len(cls.methods)
            for m in cls.methods:
                entities_to_save.append({
                    "file_path": file_record.path,
                    "entity_type": "method",
                    "name": m.name,
                    "parent_name": cls.name,
                    "start_line": m.start_line,
                    "end_line": m.end_line,
                    "details": json.dumps({
                        "params": m.params,
                        "return_type": m.return_type,
                        "decorators": m.decorators,
                        "calls": m.calls,
                        "docstring": m.docstring,
                    }),
                })

        # 2. Top-level functions
        for fn in parsed.functions:
            entities_to_save.append({
                "file_path": file_record.path,
                "entity_type": "function",
                "name": fn.name,
                "parent_name": None,
                "start_line": fn.start_line,
                "end_line": fn.end_line,
                "details": json.dumps({
                    "params": fn.params,
                    "return_type": fn.return_type,
                    "decorators": fn.decorators,
                    "calls": fn.calls,
                    "docstring": fn.docstring,
                }),
            })

        # 3. Imports
        for imp in parsed.imports:
            entities_to_save.append({
                "file_path": file_record.path,
                "entity_type": "import",
                "name": imp.imported_name,
                "parent_name": None,
                "start_line": imp.line_number,
                "end_line": imp.line_number,
                "details": json.dumps({
                    "module": imp.module,
                    "alias": imp.alias,
                    "is_relative": imp.is_relative,
                    "level": imp.level,
                }),
            })

    # Clear prior entities if re-parsing
    db.query(crud.CodeEntity).filter(crud.CodeEntity.project_id == project_id).delete()
    db.commit()

    # Bulk persist entities
    if entities_to_save:
        crud.save_code_entities(db=db, project_id=project_id, entities_data=entities_to_save)

    return ProjectParseSummaryResponse(
        project_id=project_id,
        parsed_files_count=parsed_count,
        unparsable_files_count=unparsable_count,
        total_classes=total_classes,
        total_functions=total_functions,
        total_methods=total_methods,
        total_imports=total_imports,
        total_calls=total_calls,
        unparsable_files=unparsable_info,
    )


@router.get(
    "/{project_id}/ast",
    response_model=ParsedFile,
    summary="Get AST extraction JSON for a specific file",
    description="Parses the specified file and returns functions, classes, bases, imports, and calls in JSON format.",
)
async def get_file_ast(
    project_id: str,
    file_path: str = Query(..., description="Relative path of file inside project, e.g. calculator.py"),
    db: Session = Depends(get_db),
) -> ParsedFile:
    """Parse and return structured AST for a single file."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    target_file = Path(project.path) / file_path
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_path}' does not exist in project '{project_id}'.",
        )

    parser = PythonParser()
    return parser.parse_file(target_file, project_root=Path(project.path))


@router.get(
    "/{project_id}/entities",
    response_model=List[EntityItemResponse],
    summary="Get stored AST entities for a project",
    description="Returns stored classes, functions, methods, and imports from the database.",
)
async def list_project_entities(
    project_id: str,
    entity_type: Optional[str] = Query(None, description="Filter by type (class, function, method, import)"),
    db: Session = Depends(get_db),
) -> List[EntityItemResponse]:
    """List code entities extracted by AST parser and persisted in the database."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    entities = crud.get_project_entities(db=db, project_id=project_id, entity_type=entity_type)
    return [EntityItemResponse.model_validate(e) for e in entities]
