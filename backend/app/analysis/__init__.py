"""
Static analysis and code quality package.
Provides modular analyzers for cyclomatic complexity, dead code, dependency cycles, and security.
"""

from app.analysis.complexity import ComplexityAnalyzer, ComplexityThresholds

__all__ = ["ComplexityAnalyzer", "ComplexityThresholds"]
