"""
Hierarchical Documentation Generator (Map-Reduce Style).
Generates architectural and code-level documentation:
1. Map: Per-file summaries (AST structure, functions, classes, dependencies).
2. Reduce: Module/package summaries (directory groupings, boundaries, coupling).
3. Reduce: Repository overview (architectural topology, component catalog, entry points, findings).
4. Export: Formatted Markdown report exported to disk and database.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def generate_file_summary(
    file_record: Dict[str, Any],
    entities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate an AST-grounded summary for an individual file (Map step).
    """
    file_path = file_record.get("path", "")
    language = file_record.get("language", "Unknown")
    line_count = file_record.get("line_count", 0)
    size_bytes = file_record.get("size_bytes", 0)

    classes: List[Dict[str, Any]] = []
    functions: List[Dict[str, Any]] = []
    imports: List[str] = []

    for ent in entities:
        ent_type = ent.get("entity_type", "")
        name = ent.get("name", "")
        if ent_type == "class":
            classes.append({
                "name": name,
                "start_line": ent.get("start_line", 0),
                "end_line": ent.get("end_line", 0),
            })
        elif ent_type == "function":
            functions.append({
                "name": name,
                "start_line": ent.get("start_line", 0),
                "end_line": ent.get("end_line", 0),
            })
        elif ent_type == "import":
            imports.append(name)

    # Heuristic purpose description from symbols
    purpose = f"Provides implementation for {', '.join([c['name'] for c in classes] + [f['name'] for f in functions])}" if (classes or functions) else "Source code file or configuration"

    return {
        "file_path": file_path,
        "language": language,
        "line_count": line_count,
        "size_bytes": size_bytes,
        "classes": classes,
        "functions": functions,
        "imports": sorted(list(set(imports))),
        "purpose": purpose,
        "classes_count": len(classes),
        "functions_count": len(functions),
    }


def generate_module_summaries(
    file_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Aggregate per-file summaries into directory/package module summaries (Reduce step).
    """
    modules_map: Dict[str, List[Dict[str, Any]]] = {}

    for f_sum in file_summaries:
        p = Path(f_sum["file_path"])
        module_name = p.parent.as_posix() if str(p.parent) != "." else "root"
        modules_map.setdefault(module_name, []).append(f_sum)

    module_summaries: List[Dict[str, Any]] = []
    for mod_name, files in sorted(modules_map.items()):
        total_lines = sum(f.get("line_count", 0) for f in files)
        all_classes = [c["name"] for f in files for c in f.get("classes", [])]
        all_funcs = [fn["name"] for f in files for fn in f.get("functions", [])]
        all_imports = sorted(list({imp for f in files for imp in f.get("imports", [])}))

        role = "Core root application entry & scripts" if mod_name == "root" else f"Subsystem handling {mod_name} utilities and business components"

        module_summaries.append({
            "module_name": mod_name,
            "role": role,
            "file_count": len(files),
            "total_lines": total_lines,
            "files": [f["file_path"] for f in files],
            "exported_classes": all_classes,
            "exported_functions": all_funcs,
            "external_dependencies": all_imports,
        })

    return module_summaries


def generate_repository_overview(
    project_name: str,
    file_summaries: List[Dict[str, Any]],
    module_summaries: List[Dict[str, Any]],
    graph_metrics: Optional[Dict[str, Any]] = None,
    findings_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synthesize high-level repository overview from module summaries and graph metrics (Final Reduce).
    """
    total_files = len(file_summaries)
    total_lines = sum(f.get("line_count", 0) for f in file_summaries)
    total_classes = sum(f.get("classes_count", 0) for f in file_summaries)
    total_functions = sum(f.get("functions_count", 0) for f in file_summaries)

    # Detect likely entry points (e.g. main.py, app.py, run, main)
    entry_points = []
    for f in file_summaries:
        p_lower = f["file_path"].lower()
        if "main.py" in p_lower or "app.py" in p_lower or "run.py" in p_lower or "index.py" in p_lower:
            entry_points.append(f["file_path"])
        else:
            for fn in f.get("functions", []):
                if fn["name"].lower() in ("main", "run", "entry"):
                    entry_points.append(f"{f['file_path']}:{fn['name']}")

    graph_metrics = graph_metrics or {}
    findings_summary = findings_summary or {}

    return {
        "project_name": project_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": total_files,
        "total_lines": total_lines,
        "total_modules": len(module_summaries),
        "total_classes": total_classes,
        "total_functions": total_functions,
        "entry_points": sorted(list(set(entry_points))),
        "graph_nodes": graph_metrics.get("nodes_count", total_files),
        "graph_edges": graph_metrics.get("edges_count", 0),
        "findings_total": findings_summary.get("total", 0),
        "findings_by_severity": findings_summary.get("by_severity", {}),
    }


def export_markdown_documentation(
    repo_overview: Dict[str, Any],
    module_summaries: List[Dict[str, Any]],
    file_summaries: List[Dict[str, Any]],
    findings_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate clean, structured GitHub-Flavored Markdown documentation.
    """
    project_name = repo_overview.get("project_name", "Repository")
    timestamp = repo_overview.get("generated_at", "")
    total_files = repo_overview.get("total_files", 0)
    total_lines = repo_overview.get("total_lines", 0)
    total_classes = repo_overview.get("total_classes", 0)
    total_functions = repo_overview.get("total_functions", 0)
    entry_points = repo_overview.get("entry_points", [])

    findings_summary = findings_summary or {}
    total_findings = findings_summary.get("total", 0)
    by_sev = findings_summary.get("by_severity", {})

    lines: List[str] = [
        f"# Architecture & Repository Documentation: {project_name}",
        "",
        f"> **Generated automatically by Local Agentic Code Reviewer**  ",
        f"> *Timestamp: {timestamp}*  ",
        "",
        "## 1. Executive Overview",
        "",
        f"- **Project Name:** `{project_name}`",
        f"- **Total Scanned Files:** {total_files}",
        f"- **Total Source Lines:** {total_lines:,}",
        f"- **Classes Identified:** {total_classes}",
        f"- **Functions & Methods:** {total_functions}",
        f"- **Identified Entry Points:** {', '.join([f'`{ep}`' for ep in entry_points]) if entry_points else '*(None explicitly detected)*'}",
        "",
        "## 2. Architecture & Subsystem Modules",
        "",
        "The repository is structured into the following architectural modules:",
        "",
        "| Module / Directory | Role & Responsibility | Files | Lines | Exported Symbols |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for mod in module_summaries:
        mod_name = mod["module_name"]
        role = mod["role"]
        f_count = mod["file_count"]
        m_lines = mod["total_lines"]
        symbols = ", ".join([f"`{s}`" for s in (mod.get("exported_classes", []) + mod.get("exported_functions", []))[:4]])
        if not symbols:
            symbols = "—"
        lines.append(f"| `{mod_name}` | {role} | {f_count} | {m_lines:,} | {symbols} |")

    lines.extend([
        "",
        "## 3. Detailed Component Catalog",
        "",
    ])

    for f in file_summaries:
        f_path = f["file_path"]
        lang = f["language"]
        f_lines = f["line_count"]
        purpose = f["purpose"]
        classes = f.get("classes", [])
        functions = f.get("functions", [])
        imports = f.get("imports", [])

        lines.append(f"### `{f_path}`")
        lines.append(f"- **Language:** {lang} | **Lines:** {f_lines}")
        lines.append(f"- **Summary:** {purpose}")

        if classes:
            class_str = ", ".join([f"`{c['name']}` (L{c['start_line']}-{c['end_line']})" for c in classes])
            lines.append(f"- **Classes:** {class_str}")

        if functions:
            fn_str = ", ".join([f"`{fn['name']}` (L{fn['start_line']}-{fn['end_line']})" for fn in functions])
            lines.append(f"- **Functions:** {fn_str}")

        if imports:
            lines.append(f"- **Dependencies / Imports:** {', '.join([f'`{imp}`' for imp in imports[:8]])}")

        lines.append("")

    lines.extend([
        "## 4. Code Quality & Security Posture",
        "",
        f"- **Total Static Findings:** {total_findings}",
    ])

    if by_sev:
        for sev, count in sorted(by_sev.items()):
            lines.append(f"  - **{sev}:** {count}")
    else:
        lines.append("  - *No static defects flagged.*")

    lines.extend([
        "",
        "---",
        "*Report compiled deterministically via AST extraction and LangGraph agent workflow.*",
    ])

    return "\n".join(lines)


def save_markdown_documentation(project_path: Path, markdown_content: str) -> Path:
    """
    Persist generated Markdown documentation to the repository docs directory.
    """
    docs_dir = project_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    target_file = docs_dir / "ARCHITECTURE.md"
    target_file.write_text(markdown_content, encoding="utf-8")
    return target_file
