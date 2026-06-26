"""
screen_processor.py — Screen & webcam capture for FRIDAY
Captures screen or webcam, sends image to Gemini for analysis.
"""
import io
import sys
import json
from pathlib import Path

try:
    import mss
    _MSS = True
except ImportError:
    _MSS = False

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    from google import genai
    from google.genai import types as gtypes
    _GENAI = True
except ImportError:
    _GENAI = False

_IMG_MAX_W = 1280
_IMG_MAX_H = 720


def _load_config() -> dict:
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def _get_api_key() -> str:
    key = _load_config().get("gemini_api_key", "")
    if not key:
        raise RuntimeError("Gemini API key not set. Run setup first.")
    return key


def _resize_bytes(img_bytes: bytes) -> bytes:
    if not _PIL:
        return img_bytes
    img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _capture_screen() -> bytes:
    if not _MSS:
        raise RuntimeError("mss not installed. Run: pip install mss")
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        shot = sct.grab(monitor)
        buf = io.BytesIO()
        if _PIL:
            img = PIL.Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            img.save(buf, format="JPEG", quality=85)
        else:
            mss.tools.to_png(shot.rgb, shot.size, output=buf)
        return _resize_bytes(buf.getvalue())


def _get_camera_index() -> int:
    return int(_load_config().get("camera_index", 0))


def _capture_webcam() -> bytes:
    if not _CV2:
        raise RuntimeError("opencv-python not installed. Run: pip install opencv-python")
    idx = _get_camera_index()
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        raise RuntimeError(f"Camera index {idx} not available.")
    for _ in range(5):
        cap.read()  # warmup frames
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture webcam frame.")
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return _resize_bytes(bytes(buf))


def _ask_gemini(img_bytes: bytes, question: str) -> str:
    if not _GENAI:
        raise RuntimeError("google-genai not installed.")
    client = genai.Client(api_key=_get_api_key())
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            gtypes.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            question,
        ],
    )
    return response.text.strip()


def screen_processor(parameters: dict, **_) -> str:
    """
    Captures screen or webcam and optionally asks Gemini a question about it.
    parameters:
        source: "screen" | "webcam"  (default: "screen")
        question: str  (what to ask about the image)
    """
    source   = parameters.get("source", "screen").lower()
    question = parameters.get("question", "Describe what you see in detail.")

    try:
        if source == "webcam":
            img_bytes = _capture_webcam()
        else:
            img_bytes = _capture_screen()
        return _ask_gemini(img_bytes, question)
    except Exception as e:
        return f"[Screen Processor Error] {e}"
