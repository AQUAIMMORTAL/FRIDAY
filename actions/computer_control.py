"""
computer_control.py — Mouse, keyboard, clipboard, window & process control for FRIDAY
"""
import time
import subprocess
import sys
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _CLIP = True
except ImportError:
    _CLIP = False

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require(lib: str, name: str):
    if not lib:
        raise RuntimeError(f"{name} not installed. Run: pip install {name.lower()}")


def _parse_int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ── Mouse ─────────────────────────────────────────────────────────────────────

def mouse_move(x: int, y: int, duration: float = 0.3) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse moved to ({x}, {y})"


def mouse_click(x: int | None = None, y: int | None = None,
                button: str = "left", clicks: int = 1) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks, interval=0.1)
    else:
        pyautogui.click(button=button, clicks=clicks, interval=0.1)
    pos = f"({x},{y})" if x is not None else "current position"
    return f"{button.title()} click ×{clicks} at {pos}"


def mouse_scroll(direction: str = "down", amount: int = 3) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    delta = -amount if direction.lower() == "down" else amount
    pyautogui.scroll(delta)
    return f"Scrolled {direction} by {amount}"


def mouse_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    pyautogui.mouseDown(x1, y1)
    pyautogui.moveTo(x2, y2, duration=duration)
    pyautogui.mouseUp()
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


# ── Keyboard ──────────────────────────────────────────────────────────────────

def keyboard_type(text: str, interval: float = 0.03) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}"


def keyboard_hotkey(*keys: str) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def keyboard_press(key: str) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    pyautogui.press(key)
    return f"Key pressed: {key}"


# ── Clipboard ─────────────────────────────────────────────────────────────────

def clipboard_write(text: str) -> str:
    _require(_CLIP, "pyperclip")
    pyperclip.copy(text)
    return "Copied to clipboard"


def clipboard_read() -> str:
    _require(_CLIP, "pyperclip")
    content = pyperclip.paste()
    if not content:
        return "Clipboard is empty"
    preview = content[:300] + ("..." if len(content) > 300 else "")
    return f"Clipboard: {preview}"


# ── Screenshot ────────────────────────────────────────────────────────────────

def take_screenshot(save_path: str | None = None) -> str:
    _require(_PYAUTOGUI, "pyautogui")
    if not save_path:
        save_path = str(Path.home() / "Desktop" / f"friday_ss_{int(time.time())}.png")
    pyautogui.screenshot(save_path)
    return f"Screenshot saved: {save_path}"


# ── System / Process ──────────────────────────────────────────────────────────

def open_application(name_or_path: str) -> str:
    try:
        subprocess.Popen(name_or_path, shell=True)
        return f"Launched: {name_or_path}"
    except Exception as e:
        return f"Failed to launch {name_or_path}: {e}"


def close_application(name: str) -> str:
    if not _PSUTIL:
        # fallback
        subprocess.run(f"taskkill /F /IM {name}", shell=True, capture_output=True)
        return f"Sent kill to {name}"
    killed = []
    for proc in psutil.process_iter(["pid", "name"]):
        if name.lower() in proc.info["name"].lower():
            proc.kill()
            killed.append(proc.info["name"])
    return f"Closed: {', '.join(killed)}" if killed else f"No process matching '{name}' found"


def list_running_apps() -> str:
    if not _PSUTIL:
        return "psutil not installed"
    names = sorted({p.name() for p in psutil.process_iter(["name"])
                    if p.name() and not p.name().startswith("svchost")})
    return "Running apps:\n" + "\n".join(f"  • {n}" for n in names[:40])


def run_command(cmd: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if out:
            return out[:800]
        if err:
            return f"[stderr] {err[:400]}"
        return f"Command executed (exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Command error: {e}"


def get_screen_size() -> str:
    if _PYAUTOGUI:
        w, h = pyautogui.size()
        return f"Screen size: {w}×{h}"
    return "pyautogui not installed"


# ── Main dispatcher ───────────────────────────────────────────────────────────

def computer_control(parameters: dict, **_) -> str:
    """
    Unified dispatcher for all computer control actions.
    parameters:
        action: str  — one of the actions below
        + action-specific keys
    """
    action = parameters.get("action", "").lower().replace("-", "_")

    try:
        if action == "mouse_move":
            return mouse_move(_parse_int(parameters.get("x")),
                              _parse_int(parameters.get("y")))

        elif action == "mouse_click":
            return mouse_click(
                x=parameters.get("x"),
                y=parameters.get("y"),
                button=parameters.get("button", "left"),
                clicks=_parse_int(parameters.get("clicks", 1), 1),
            )

        elif action == "mouse_scroll":
            return mouse_scroll(parameters.get("direction", "down"),
                                _parse_int(parameters.get("amount", 3), 3))

        elif action == "mouse_drag":
            return mouse_drag(
                _parse_int(parameters.get("x1")), _parse_int(parameters.get("y1")),
                _parse_int(parameters.get("x2")), _parse_int(parameters.get("y2")),
            )

        elif action == "keyboard_type":
            return keyboard_type(parameters.get("text", ""))

        elif action == "keyboard_hotkey":
            keys = parameters.get("keys", [])
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split("+")]
            return keyboard_hotkey(*keys)

        elif action == "keyboard_press":
            return keyboard_press(parameters.get("key", "enter"))

        elif action == "clipboard_write":
            return clipboard_write(parameters.get("text", ""))

        elif action == "clipboard_read":
            return clipboard_read()

        elif action == "take_screenshot":
            return take_screenshot(parameters.get("path"))

        elif action == "open_app":
            return open_application(parameters.get("app", ""))

        elif action == "close_app":
            return close_application(parameters.get("app", ""))

        elif action == "list_apps":
            return list_running_apps()

        elif action == "run_command":
            return run_command(parameters.get("command", ""),
                               _parse_int(parameters.get("timeout", 15), 15))

        elif action == "screen_size":
            return get_screen_size()

        elif action == "sleep":
            secs = float(parameters.get("seconds", 1))
            time.sleep(secs)
            return f"Waited {secs}s"

        else:
            return (f"Unknown action: '{action}'. Available: mouse_move, mouse_click, "
                    "mouse_scroll, mouse_drag, keyboard_type, keyboard_hotkey, keyboard_press, "
                    "clipboard_write, clipboard_read, take_screenshot, open_app, close_app, "
                    "list_apps, run_command, screen_size, sleep")

    except Exception as e:
        return f"[ComputerControl Error] {e}"
