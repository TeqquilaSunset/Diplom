from enum import Enum
from pathlib import Path


class ProjectType(Enum):
    PYTHON = "python"
    CSHARP = "csharp"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    MIXED = "mixed"
    UNKNOWN = "unknown"


PROJECT_MARKERS = {
    ProjectType.PYTHON: {
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
    },
    ProjectType.CSHARP: {".csproj", ".sln", "project.json", "global.json"},
    ProjectType.JAVASCRIPT: {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"},
    ProjectType.TYPESCRIPT: {"tsconfig.json", "tsconfig.base.json"},
}


def detect_project_type(path: Path | None = None) -> ProjectType:
    """Detect project type based on marker files in directory."""
    if path is None:
        path = Path.cwd()
    elif isinstance(path, str):
        path = Path(path)

    detected: set[ProjectType] = set()

    for project_type, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if (path / marker).exists():
                detected.add(project_type)
                break

    if not detected:
        return ProjectType.UNKNOWN

    if len(detected) == 1:
        return detected.pop()

    return ProjectType.MIXED


def detect_project_root(start_path: Path | None = None) -> Path | None:
    """Find project root by traversing up looking for any project marker."""
    if start_path is None:
        start_path = Path.cwd()
    elif isinstance(start_path, str):
        start_path = Path(start_path)

    current = start_path.resolve()
    all_markers = set()
    for markers in PROJECT_MARKERS.values():
        all_markers.update(markers)

    while current != current.parent:
        for marker in all_markers:
            if (current / marker).exists():
                return current
        current = current.parent

    for marker in all_markers:
        if (current / marker).exists():
            return current

    return None


def get_project_languages(path: Path | None = None) -> list[str]:
    """Get list of detected languages for a project."""
    project_type = detect_project_type(path)

    if project_type == ProjectType.UNKNOWN:
        return []

    if project_type == ProjectType.MIXED:
        return ["python", "csharp", "javascript", "typescript"]

    return [project_type.value]
