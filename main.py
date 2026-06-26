"""
main.py — FRIDAY entry point
"""
import sys
import os
from pathlib import Path

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

_IMPORT_TO_PKG = {
    "google.generativeai": "google-genai  (also run: pip uninstall google-generativeai -y)",
    "google.genai":        "google-genai",
    "google":              "google-genai",
    "cv2":                 "opencv-python",
    "bs4":                 "beautifulsoup4",
    "PIL":                 "pillow",
    "win32api":            "pywin32",
    "duckduckgo_search":   "duckduckgo-search",
}


def _pip_fix(err: str) -> str:
    for key, pkg in _IMPORT_TO_PKG.items():
        if key in err:
            return f"pip install {pkg}"
    mod = err.split("'")[-2] if "'" in err else err.split()[-1]
    return f"pip install {mod.split('.')[0]}"


def main():
    try:
        from ui import run_ui
        run_ui()
    except ImportError as e:
        fix = _pip_fix(str(e))
        print(f"\n[Error] {e}")
        print(f"  Fix : {sys.executable} -m {fix}")
        print( "  Or  : python setup.py\n")
        sys.exit(1)


if __name__ == "__main__":
    main()