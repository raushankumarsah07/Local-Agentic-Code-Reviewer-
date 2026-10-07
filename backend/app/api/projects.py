"""
Projects API router: Handles repository uploads, ZIP decompression, and project listing.
"""

import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.ingestion.zip_handler import (
    ExtractionResult,
    ZipBombError,
    ZipExtractionError,
    ZipSlipError,
    safe_extract_zip,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectUploadResponse(BaseModel):
    """Response returned upon successful ZIP upload and extraction."""
    project_id: str = Field(..., description="Unique identifier for the uploaded project")
    project_name: str = Field(..., description="Original name of the uploaded ZIP file")
    file_count: int = Field(..., description="Number of valid code/text files extracted")
    skipped_count: int = Field(..., description="Number of ignored files (binaries, .git, etc.)")
    target_directory: str = Field(..., description="Path where repository is saved on disk")
    message: str = Field(..., description="Status message")


class ProjectSummary(BaseModel):
    """Brief metadata summary for an existing project folder."""
    project_id: str
    exists: bool
    path: str


@router.post(
    "/upload",
    response_model=ProjectUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a ZIP repository",
    description="Accepts a ZIP file, verifies security (anti-zip-slip, size limits), and extracts code to the workspace directory.",
)
async def upload_project(
    file: UploadFile = File(..., description="ZIP archive of the software project"),
    settings: Settings = Depends(get_settings),
) -> ProjectUploadResponse:
    """
    Handle project ZIP upload:
    1. Validate filename has .zip extension.
    2. Assign a unique project_id.
    3. Safely extract files using safe_extract_zip().
    4. Return project_id and file count.
    """
    filename = file.filename or "unknown.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .zip archives are supported.",
        )

    # Generate a clean, collision-free project identifier
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

    # Derive clean project display name (stripping .zip extension)
    clean_name = Path(filename).stem

    return ProjectUploadResponse(
        project_id=project_id,
        project_name=clean_name,
        file_count=extraction_result.extracted_files_count,
        skipped_count=extraction_result.skipped_files_count,
        target_directory=str(target_dir),
        message="Repository uploaded and safely extracted.",
    )


@router.get(
    "",
    response_model=List[ProjectSummary],
    summary="List all local workspace projects",
)
async def list_projects(settings: Settings = Depends(get_settings)) -> List[ProjectSummary]:
    """List all extracted project directories currently residing in the workspace."""
    workspace = settings.WORKSPACE_DIR.resolve()
    if not workspace.exists():
        return []

    projects = []
    for item in workspace.iterdir():
        if item.is_dir():
            projects.append(
                ProjectSummary(
                    project_id=item.name,
                    exists=True,
                    path=str(item),
                )
            )
    return projects
