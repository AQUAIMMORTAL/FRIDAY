"""
file_handler.py — File system operations for FRIDAY
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

_TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".csv",
    ".xml", ".sql", ".sh", ".bat", ".ps1", ".log", ".rst"
}
_MAX_READ = 8000  # characters


def _safe_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def read_file(parameters: dict, **_) -> str:
    path = _safe_path(parameters.get("path", ""))
    if not path.exists():
        return f"File not found: {path}"
    if not path.is_file():
        return f"Not a file: {path}"

    if path.suffix.lower() not in _TEXT_EXTS:
        size = path.stat().st_size
        return f"Binary file: {path.name} ({size:,} bytes) — can't read as text."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_READ:
            content = content[:_MAX_READ] + f"\n\n[...truncated at {_MAX_READ} chars]"
        return f"Content of {path.name}:\n\n{content}"
    except Exception as e:
        return f"Read error: {e}"


def write_file(parameters: dict, **_) -> str:
    path    = _safe_path(parameters.get("path", ""))
    content = parameters.get("content", "")
    append  = parameters.get("append", False)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        path.write_text(content, encoding="utf-8") if not append else \
            open(path, "a", encoding="utf-8").write(content)
        action = "Appended to" if append else "Written"
        return f"{action} {path} ({len(content):,} chars)"
    except Exception as e:
        return f"Write error: {e}"


def list_directory(parameters: dict, **_) -> str:
    path  = _safe_path(parameters.get("path", "."))
    depth = int(parameters.get("depth", 1))

    if not path.exists():
        return f"Path not found: {path}"
    if not path.is_dir():
        return f"Not a directory: {path}"

    lines = [f"📁 {path}"]

    def _walk(p: Path, level: int):
        if level > depth:
            return
        try:
            entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            lines.append("  " * level + "  [Permission denied]")
            return
        for entry in entries[:50]:
            icon = "📄" if entry.is_file() else "📁"
            size = f" ({entry.stat().st_size:,}B)" if entry.is_file() else ""
            lines.append("  " * level + f"{icon} {entry.name}{size}")
            if entry.is_dir():
                _walk(entry, level + 1)

    _walk(path, 1)
    return "\n".join(lines)


def delete_file(parameters: dict, **_) -> str:
    path    = _safe_path(parameters.get("path", ""))
    confirm = parameters.get("confirmed", False)

    if not path.exists():
        return f"Not found: {path}"
    if not confirm:
        return (f"⚠️ About to delete: {path}\n"
                "Set confirmed=true to proceed.")
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return f"Deleted directory: {path}"
        else:
            path.unlink()
            return f"Deleted file: {path}"
    except Exception as e:
        return f"Delete error: {e}"


def copy_file(parameters: dict, **_) -> str:
    src = _safe_path(parameters.get("src", ""))
    dst = _safe_path(parameters.get("dst", ""))
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return f"Copied {src.name} → {dst}"
    except Exception as e:
        return f"Copy error: {e}"


def move_file(parameters: dict, **_) -> str:
    src = _safe_path(parameters.get("src", ""))
    dst = _safe_path(parameters.get("dst", ""))
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved {src.name} → {dst}"
    except Exception as e:
        return f"Move error: {e}"


def search_files(parameters: dict, **_) -> str:
    directory = _safe_path(parameters.get("directory", "."))
    pattern   = parameters.get("pattern", "*")
    recursive = parameters.get("recursive", True)

    try:
        glob_fn = directory.rglob if recursive else directory.glob
        matches = list(glob_fn(pattern))[:30]
        if not matches:
            return f"No files matching '{pattern}' in {directory}"
        lines = [f"Found {len(matches)} match(es) for '{pattern}':"]
        for m in matches:
            size = f" ({m.stat().st_size:,}B)" if m.is_file() else " [dir]"
            lines.append(f"  {m}{size}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def file_info(parameters: dict, **_) -> str:
    path = _safe_path(parameters.get("path", ""))
    if not path.exists():
        return f"Not found: {path}"
    st = path.stat()
    return (
        f"Name:     {path.name}\n"
        f"Type:     {'Directory' if path.is_dir() else 'File'}\n"
        f"Size:     {st.st_size:,} bytes\n"
        f"Modified: {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}\n"
        f"Full path:{path}"
    )


# ── Main dispatcher ───────────────────────────────────────────────────────────

def file_handler(parameters: dict, **_) -> str:
    action = parameters.get("action", "").lower().replace("-", "_")
    dispatch = {
        "read":    read_file,
        "write":   write_file,
        "list":    list_directory,
        "delete":  delete_file,
        "copy":    copy_file,
        "move":    move_file,
        "search":  search_files,
        "info":    file_info,
    }
    fn = dispatch.get(action)
    if not fn:
        return f"Unknown file action: '{action}'. Available: {', '.join(dispatch)}"
    return fn(parameters)
