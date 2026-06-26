import json
import platform
from pathlib import Path

def get_os() -> str:
    return platform.system()

def is_windows() -> bool:
    return platform.system() == "Windows"

def is_mac() -> bool:
    return platform.system() == "Darwin"

def is_linux() -> bool:
    return platform.system() == "Linux"

_CONFIG_PATH = Path(__file__).parent / "api_keys.json"
_DEFAULTS = {
    "gemini_api_key": "",
    "elevenlabs_api_key": "",
    "os_system": "windows",
    "assistant_name": "FRIDAY",
    "voice_enabled": True,
    "camera_index": 0,
    "wake_word": "friday",
}

# ── Keyring helpers (graceful fallback to JSON) ───────────────────────────────
try:
    import keyring as _kr
    _KEYRING = True
except ImportError:
    _KEYRING = False

_KR_SERVICE = "FRIDAY"
_SECURE_KEYS = {"gemini_api_key", "elevenlabs_api_key"}


def _kr_get(key: str) -> str:
    if not _KEYRING:
        return ""
    try:
        return _kr.get_password(_KR_SERVICE, key) or ""
    except Exception:
        return ""


def _kr_set(key: str, value: str) -> bool:
    if not _KEYRING:
        return False
    try:
        _kr.set_password(_KR_SERVICE, key, value)
        return True
    except Exception:
        return False


def get_config() -> dict:
    if not _CONFIG_PATH.exists():
        _CONFIG_PATH.write_text(
            json.dumps({k: v for k, v in _DEFAULTS.items() if k not in _SECURE_KEYS}, indent=2),
            encoding="utf-8",
        )
        return _DEFAULTS.copy()
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k, v in _DEFAULTS.items():
        data.setdefault(k, v)
    # Overlay secure keys from keyring
    for k in _SECURE_KEYS:
        kr_val = _kr_get(k)
        if kr_val:
            data[k] = kr_val
        # else leave whatever is in JSON (migration path)
    return data


def save_config(data: dict):
    # Always write everything including API keys to local JSON
    _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Also store in keyring if available (bonus security layer)
    for k in _SECURE_KEYS:
        if k in data and data[k]:
            _kr_set(k, data[k])


def get_api_key() -> str:
    # Check JSON file first — if key is there, use it
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if data.get("gemini_api_key"):
                return data["gemini_api_key"]
        except Exception:
            pass
    # Fallback to keyring
    kr = _kr_get("gemini_api_key")
    if kr:
        return kr
    return ""


def get_wake_word() -> str:
    return get_config().get("wake_word", "friday").lower()


def get_assistant_name() -> str:
    return get_config().get("assistant_name", "FRIDAY")