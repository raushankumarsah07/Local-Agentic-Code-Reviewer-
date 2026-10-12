"""
Seed Sample Projects into Database & Workspace.

Ingests and automatically executes full agentic analysis for 4 diverse projects
ranging from basic to advanced:
1. Basic: Simple Calculator & Math Engine (CLI, arithmetic, stack history)
2. Intermediate: Auth & Identity Microservice (JWT, PBKDF2/SHA-256, session tokens)
3. Advanced: High-Throughput ETL Data Pipeline (Stream extractor, transformer, batch loader)
4. Advanced Full-Stack: ApexCommerce Order & Payment API (E-commerce saga, inventory locking, Stripe/PayPal mock)
"""

import os
import sys
import shutil
import uuid
from pathlib import Path

# Add backend directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.db import crud
from app.db.session import SessionLocal, init_db
from app.db.models import Project, ProjectFile, CodeEntity, GraphEdge, Finding, ProjectDoc
from app.ingestion.scanner import scan_repository
from app.agent.runner import execute_analysis_sync

PROJECTS_TO_SEED = [
    {
        "name": "simple-calculator",
        "display_name": "Simple Calculator & Math Utility",
        "source_dir": REPO_ROOT / "sample_repos" / "sample_calculator",
        "description": "Basic arithmetic CLI, scientific operations, calculation history stack, and formatters.",
        "difficulty": "Basic / Beginner",
    },
    {
        "name": "auth-identity-service",
        "display_name": "JWT Auth & Identity Microservice",
        "source_dir": REPO_ROOT / "sample_repos" / "sample_auth_service",
        "description": "Intermediate authentication service with JWT token issuance, password crypto, session management, and validation.",
        "difficulty": "Intermediate",
    },
    {
        "name": "streaming-data-pipeline",
        "display_name": "High-Throughput ETL Data Pipeline",
        "source_dir": REPO_ROOT / "sample_repos" / "sample_data_pipeline",
        "description": "Advanced multi-stage data engineering pipeline with batch extraction, stream transformation, and metrics telemetry.",
        "difficulty": "Advanced",
    },
    {
        "name": "apex-ecommerce-api",
        "display_name": "ApexCommerce Orders & Payment Microservice",
        "source_dir": REPO_ROOT / "sample_repos" / "sample_ecommerce_api",
        "description": "Enterprise e-commerce backend coordinating inventory reservation locks, idempotency payments, and order state machines.",
        "difficulty": "Advanced Enterprise",
    },
]


def seed_project(project_info: dict, settings) -> str:
    source_dir = project_info["source_dir"]
    if not source_dir.exists():
        raise FileNotFoundError(f"Source repo directory not found: {source_dir}")

    project_name = project_info["name"]

    with SessionLocal() as db:
        # Check if project with this name already exists; if so, clean up old records first
        existing = db.query(Project).filter_by(name=project_name).first()
        if existing:
            print(f"[*] Project '{project_name}' already exists (ID: {existing.id}). Re-indexing...")
            project_id = existing.id
            target_dir = Path(existing.path)
        else:
            project_id = uuid.uuid4().hex[:12]
            target_dir = (settings.WORKSPACE_DIR / project_id).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            crud.create_project(
                db=db,
                project_id=project_id,
                name=project_name,
                path=str(target_dir),
                total_files=0,
                total_lines=0,
                total_size_bytes=0,
            )

    # Copy files into workspace target
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    # Scan files
    scan_summary = scan_repository(target_dir, project_id)

    with SessionLocal() as db:
        db_proj = db.query(Project).filter_by(id=project_id).first()
        if db_proj:
            db_proj.total_files = scan_summary.total_files
            db_proj.total_lines = scan_summary.total_lines
            db_proj.total_size_bytes = scan_summary.total_size_bytes
            db.commit()

        # Save files metadata
        files_payload = [
            {
                "path": f.path,
                "language": f.language,
                "size_bytes": f.size_bytes,
                "line_count": f.line_count,
            }
            for f in scan_summary.files
        ]
        # Remove old files if any
        db.query(ProjectFile).filter_by(project_id=project_id).delete()
        db.commit()
        crud.save_project_files(db=db, project_id=project_id, files_data=files_payload)

    print(f"[+] Ingested '{project_name}' ({scan_summary.total_files} files, {scan_summary.total_lines} lines).")
    print(f"    Executing full agentic analysis pipeline (AST, Graph, Checks, Vector Index, Docs)...")

    # Execute full agent pipeline
    analysis_result = execute_analysis_sync(project_id)
    print(f"    Status: {analysis_result.get('status')}")

    # Inspect resulting stats
    with SessionLocal() as db:
        p_files = db.query(ProjectFile).filter_by(project_id=project_id).count()
        p_ents = db.query(CodeEntity).filter_by(project_id=project_id).count()
        p_edges = db.query(GraphEdge).filter_by(project_id=project_id).count()
        p_finds = db.query(Finding).filter_by(project_id=project_id).count()
        p_docs = db.query(ProjectDoc).filter_by(project_id=project_id).count()
        print(f"    Summary in DB -> Files: {p_files} | Entities: {p_ents} | Edges: {p_edges} | Findings: {p_finds} | Docs: {p_docs}")

    return project_id


def main():
    print("=" * 70)
    print("SEEDING BASIC-TO-ADVANCED PROJECTS INTO POSTGRESQL DATABASE")
    print("=" * 70)

    settings = get_settings()
    init_db()

    seeded = []
    for info in PROJECTS_TO_SEED:
        print(f"\n--- Seeding [{info['difficulty']}]: {info['display_name']} ---")
        pid = seed_project(info, settings)
        seeded.append((info["name"], pid, info["difficulty"]))

    print("\n" + "=" * 70)
    print("ALL SAMPLE PROJECTS SUCCESSFULLY SEEDED & ANALYZED IN POSTGRESQL!")
    print("=" * 70)
    for name, pid, diff in seeded:
        print(f" - [{diff:20}] {name:25} (ID: {pid})")
    print("=" * 70)


if __name__ == "__main__":
    main()
