"""
setup.py — FRIDAY launcher
Run this file (F5 or python setup.py) to install all dependencies and start FRIDAY.
"""
import sys
import subprocess
from pathlib import Path

REQUIREMENTS = Path(__file__).parent / "requirements.txt"


def install_dependencies():
    print("=" * 50)
    print("  FRIDAY — Checking dependencies...")
    print("=" * 50)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        )
        print("\n  ✅ All dependencies installed.\n")
    except subprocess.CalledProcessError:
        print("\n  ⚠️  Some packages failed. Trying one by one...\n")
        with open(REQUIREMENTS, "r") as f:
            packages = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        for pkg in packages:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                print(f"  ✅ {pkg}")
            except subprocess.CalledProcessError:
                print(f"  ❌ Failed: {pkg} (install manually if needed)")

    # Install Playwright browser
    print("  Installing Playwright browser (chromium)...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
        )
        print("  ✅ Playwright chromium installed.\n")
    except subprocess.CalledProcessError:
        print("  ⚠️  Playwright install failed. Run manually: playwright install chromium\n")


def launch():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main", Path(__file__).parent / "main.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


if __name__ == "__main__":
    install_dependencies()
    launch()