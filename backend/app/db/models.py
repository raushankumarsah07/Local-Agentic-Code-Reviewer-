"""
SQLAlchemy ORM models.
Implements the complete database schema for the application:
1. projects: Uploaded repositories and overall statistics
2. project_files: Files discovered during scanning
3. entities: Classes, functions, methods, and imports from AST
4. edges: Dependency relationships between files/modules
5. findings: Deterministic static analysis warnings and defects
6. chunks_meta: Semantic code chunks for vector indexing & RAG
7. chat_messages: History of user conversations with citations
8. analysis_runs: Progress and execution tracking for pipeline runs
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class Project(Base):
    """
    Represents an uploaded and extracted software repository.
    """
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    path = Column(String(1024), nullable=False)
    total_files = Column(Integer, default=0, nullable=False)
    total_lines = Column(Integer, default=0, nullable=False)
    total_size_bytes = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Cascading relationships
    files = relationship(
        "ProjectFile",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectFile.path",
    )
    entities = relationship(
        "CodeEntity",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    edges = relationship(
        "GraphEdge",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    findings = relationship(
        "Finding",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    chunks = relationship(
        "ChunkMeta",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    chat_messages = relationship(
        "ChatMessage",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    analysis_runs = relationship(
        "AnalysisRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project(id='{self.id}', name='{self.name}', files={self.total_files})>"


class ProjectFile(Base):
    """
    Represents an individual code or documentation file discovered during repository scanning.
    """
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path = Column(String(1024), nullable=False, index=True)  # Relative path e.g. "src/main.py"
    language = Column(String(64), nullable=False, index=True)  # e.g. "Python", "Markdown"
    size_bytes = Column(Integer, nullable=False, default=0)
    line_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="files")

    def __repr__(self) -> str:
        return f"<ProjectFile(id={self.id}, project_id='{self.project_id}', path='{self.path}', lang='{self.language}')>"


class CodeEntity(Base):
    """
    Represents an extracted code entity (function, class, method, or import) from AST parsing.
    """
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(1024), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # 'class', 'function', 'method', 'import'
    name = Column(String(255), nullable=False, index=True)
    parent_name = Column(String(255), nullable=True)  # Enclosing class name if method
    start_line = Column(Integer, nullable=False, default=0)
    end_line = Column(Integer, nullable=False, default=0)
    details = Column(Text, nullable=True)  # JSON-encoded metadata (parameters, bases, etc.)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="entities")

    def __repr__(self) -> str:
        return f"<CodeEntity(id={self.id}, type='{self.entity_type}', name='{self.name}', file='{self.file_path}')>"


class GraphEdge(Base):
    """
    Represents a directed dependency edge between files or external libraries.
    """
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(1024), nullable=False, index=True)
    target = Column(String(1024), nullable=False, index=True)
    edge_type = Column(String(32), default="import", nullable=False)  # 'import', 'call', 'inheritance'
    is_external = Column(Boolean, default=False, nullable=False)
    imported_symbols = Column(Text, nullable=True)  # JSON list of symbols
    line_number = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="edges")

    def __repr__(self) -> str:
        return f"<GraphEdge(id={self.id}, {self.source}->{self.target})>"


class Finding(Base):
    """
    Represents a static analysis finding (complexity, dead code, circular dependency, security).
    """
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(64), nullable=False, index=True)  # 'complexity', 'dead_code', 'security', 'cycle', 'coupling'
    severity = Column(String(32), nullable=False, index=True)  # 'Critical', 'High', 'Medium', 'Low', 'Info'
    title = Column(String(512), nullable=False)
    file = Column(String(1024), nullable=False, index=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    evidence_snippet = Column(Text, nullable=True)
    source_tool = Column(String(64), nullable=False)  # 'mccabe', 'vulture', 'ast_security', 'tarjan'
    explanation = Column(Text, nullable=True)  # Grounded LLM explanation or recommendations
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="findings")

    def __repr__(self) -> str:
        return f"<Finding(id={self.id}, severity='{self.severity}', title='{self.title[:30]}')>"


class ChunkMeta(Base):
    """
    Metadata for indexed code chunks in ChromaDB vector store.
    """
    __tablename__ = "chunks_meta"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(String(128), nullable=False, index=True)
    file_path = Column(String(1024), nullable=False, index=True)
    symbol_name = Column(String(255), nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    language = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<ChunkMeta(id={self.id}, chunk_id='{self.chunk_id}', file='{self.file_path}')>"


class ChatMessage(Base):
    """
    Conversation message for repository Q&A (RAG chat).
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)  # JSON-encoded array of file:line citations
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role='{self.role}')>"


class AnalysisRun(Base):
    """
    Execution run and progress tracker for background agent analysis pipeline.
    """
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), default="pending", nullable=False)  # 'pending', 'running', 'completed', 'failed'
    step = Column(String(64), default="initialized", nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="analysis_runs")

    def __repr__(self) -> str:
        return f"<AnalysisRun(id={self.id}, status='{self.status}', progress={self.progress_percent}%)>"
