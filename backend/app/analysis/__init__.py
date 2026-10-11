"""
Static analysis and code quality package.
Provides modular analyzers for cyclomatic complexity, dead code, dependency cycles, and security.
"""

from app.analysis.architecture import ArchitectureAnalyzer
from app.analysis.complexity import ComplexityAnalyzer, ComplexityThresholds
from app.analysis.dead_code import DeadCodeAnalyzer
from app.analysis.security import SecurityAnalyzer, SecurityASTVisitor, normalize_severity, ensure_potential_label

__all__ = [
    "ArchitectureAnalyzer",
    "ComplexityAnalyzer",
    "ComplexityThresholds",
    "DeadCodeAnalyzer",
    "SecurityAnalyzer",
    "SecurityASTVisitor",
    "normalize_severity",
    "ensure_potential_label",
]
