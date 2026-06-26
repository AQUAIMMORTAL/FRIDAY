"""
ui.py — FRIDAY UI
"""
import sys
import re
import math
import time
import random
import threading
import subprocess
import platform
import psutil
from datetime import datetime
from pathlib import Path

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


# ── Background system metrics (non-blocking daemon thread) ────────────────────

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0
        self.gpu  = -1.0
        self.tmp  = -1.0
        self._lock       = threading.Lock()
        self._last_net   = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running    = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()
        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass
        if _OS == "Linux":
            try:
                r = subprocess.run(["rocm-smi", "--showuse", "--csv"], capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz", "cpu-thermal", "zenpower", "it8688"):
                if key in temps and temps[key]:
                    return temps[key][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        if _OS == "Darwin":
            try:
                r = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {"cpu": self.cpu, "mem": self.mem, "net": self.net, "gpu": self.gpu, "tmp": self.tmp}


_metrics = _SysMetrics()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QDialog, QFormLayout,
    QFrame, QSizePolicy, QFileDialog, QScrollArea
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal, QObject, QPointF, QRectF, QSize, QSizeF
from PyQt6.QtGui   import (
    QColor, QTextCursor, QPainter, QPen, QBrush, QFont,
    QLinearGradient, QRadialGradient, QConicalGradient,
    QPainterPath, QFontDatabase, QPixmap, QDragEnterEvent, QDropEvent,
    QShortcut, QKeySequence
)

from config import get_config, save_config

C_BG       = "#020b12"
C_PANEL    = "#010d14"
C_PANEL2   = "#010f18"
C_BORDER   = "#0d3347"
C_BORDER_B = "#1a5c7a"
C_BORDER_A = "#0f4060"
C_CYAN     = "#00e5ff"
C_CYAN_DIM = "#007a99"
C_CYAN_GHO = "#001f2e"
C_CYAN_DARK= "#003344"
C_ACC      = "#ff6b00"
C_ACC2     = "#ffcc00"
C_GREEN    = "#00ff88"
C_GREEN_D  = "#00aa55"
C_AMBER    = "#ffaa00"
C_RED      = "#ff3355"
C_TEXT     = "#a0d8e8"
C_TEXT_DIM = "#3a6070"
C_TEXT_MED = "#5ab8cc"
C_WHITE    = "#d8f8ff"
C_DARK     = "#000d14"
C_BAR_BG   = "#011520"


class C:
    """Jarvis-style palette alias — same colors as the C_* constants above."""
    BG       = C_BG
    PANEL    = C_PANEL
    PANEL2   = C_PANEL2
    BORDER   = C_BORDER
    BORDER_B = C_BORDER_B
    BORDER_A = C_BORDER_A
    PRI      = C_CYAN
    PRI_DIM  = C_CYAN_DIM
    PRI_GHO  = C_CYAN_GHO
    ACC      = C_ACC
    ACC2     = C_ACC2
    GREEN    = C_GREEN
    GREEN_D  = C_GREEN_D
    RED      = C_RED
    MUTED_C  = C_RED
    TEXT     = C_TEXT
    TEXT_DIM = C_TEXT_DIM
    TEXT_MED = C_TEXT_MED
    WHITE    = C_WHITE
    DARK     = C_DARK
    BAR_BG   = C_BAR_BG


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


STYLE = f"""
* {{ font-family: 'Consolas', 'Courier New', monospace; }}
QMainWindow, QWidget#root {{ background-color: {C_BG}; }}
QWidget#panel {{ background: rgba(0,18,28,210); border: 1px solid {C_CYAN_DIM}; }}
QTextEdit#logArea {{
    background: transparent; color: {C_TEXT}; border: none;
    font-size: 12px; font-family: 'Consolas', monospace;
    selection-background-color: rgba(0,229,255,40);
}}
QLineEdit#cmdInput {{
    background: rgba(0,15,25,200); color: {C_CYAN};
    border: 1px solid {C_CYAN_DIM}; border-radius: 0px;
    padding: 8px 12px; font-size: 13px; font-family: 'Consolas', monospace;
    selection-background-color: rgba(0,229,255,60);
}}
QLineEdit#cmdInput:focus {{ border: 1px solid {C_CYAN}; background: rgba(0,229,255,8); }}
QPushButton#sendBtn {{
    background: rgba(0,229,255,15); color: {C_CYAN};
    border: 1px solid {C_CYAN_DIM}; border-radius: 0px;
    padding: 8px 14px; font-size: 14px; font-family: 'Consolas', monospace; font-weight: bold;
}}
QPushButton#sendBtn:hover {{ background: rgba(0,229,255,30); border-color: {C_CYAN}; }}
QPushButton#muteBtn {{
    background: rgba(0,255,136,12); color: {C_GREEN};
    border: 1px solid rgba(0,255,136,60);
    padding: 6px 16px; font-size: 11px; font-family: 'Consolas', monospace; letter-spacing: 1px;
}}
QPushButton#muteBtn:hover {{ background: rgba(0,255,136,25); }}
QPushButton#muteBtn:checked {{ background: rgba(255,50,80,15); color: {C_RED}; border-color: rgba(255,50,80,80); }}
QPushButton#settingsBtn {{
    background: transparent; color: {C_TEXT_DIM};
    border: 1px solid {C_TEXT_DIM}; padding: 4px 10px; font-size: 10px; letter-spacing: 1px;
}}
QPushButton#settingsBtn:hover {{ color: {C_CYAN}; border-color: {C_CYAN}; }}
QPushButton#uploadBtn {{
    background: rgba(0,229,255,8); color: {C_CYAN_DIM};
    border: 1px dashed {C_CYAN_DIM}; padding: 20px; font-size: 11px; letter-spacing: 1px;
}}
QPushButton#uploadBtn:hover {{ background: rgba(0,229,255,15); color: {C_CYAN}; border-color: {C_CYAN}; }}
QLabel {{ color: {C_TEXT}; }}
QLabel#sectionTitle {{ color: {C_CYAN}; font-size: 10px; letter-spacing: 2px; font-weight: bold; padding: 2px 0px; }}
QLabel#statLabel    {{ color: {C_TEXT_DIM}; font-size: 10px; letter-spacing: 1px; }}
QLabel#statValue    {{ color: {C_CYAN}; font-size: 10px; font-weight: bold; }}
QLabel#timeLabel    {{ color: {C_CYAN}; font-size: 22px; font-weight: bold; letter-spacing: 2px; }}
QLabel#dateLabel    {{ color: {C_CYAN_DIM}; font-size: 10px; letter-spacing: 1px; }}
QLabel#titleMain    {{ color: {C_CYAN}; font-size: 22px; font-weight: bold; letter-spacing: 8px; }}
QLabel#titleSub     {{ color: {C_CYAN_DIM}; font-size: 9px; letter-spacing: 3px; }}
QLabel#statusOrb    {{ color: {C_GREEN}; font-size: 11px; letter-spacing: 3px; font-weight: bold; }}
QLabel#fileLabel    {{ color: {C_TEXT_DIM}; font-size: 10px; font-style: italic; }}
QLabel#fileStatus {{ color: {C_TEXT_DIM}; font-size: 9px; font-style: italic; padding: 2px 0; }}
QScrollBar:vertical {{ background: transparent; width: 4px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C_CYAN_DIM}; border-radius: 2px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QDialog {{ background: {C_BG}; }}
QLineEdit#settingsInput {{
    background: rgba(0,15,25,200); color: {C_CYAN};
    border: 1px solid {C_CYAN_DIM}; padding: 7px 12px;
    font-size: 13px; font-family: 'Consolas', monospace;
}}
"""


# ── Orb widget ────────────────────────────────────────────────────────────────

class OrbWidget(QWidget):
    """Video orb with QGraphicsScene glow overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 340)
        self._state     = "OFFLINE"
        self._muted     = False
        self._amp       = 0.0
        self._pulse     = 0.0
        self._pulse_dir = 1
        # layout geometry — initialised to safe defaults so _tick never crashes
        self._cx = 0.0
        self._cy = 0.0
        self._r  = 0.0

        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
        from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView
        from PyQt6.QtCore import QUrl
        from pathlib import Path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scene = QGraphicsScene(self)
        self._view  = QGraphicsView(self._scene)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setStyleSheet("background:black; border:none;")
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self._view)

        # Video layer (z=0)
        self._video_item = QGraphicsVideoItem()
        self._scene.addItem(self._video_item)

        # Glow layer (z=10)
        glow_path = QPainterPath()
        glow_path.addEllipse(0, 0, 100, 100)
        self._glow_item = self._scene.addPath(
            glow_path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.BrushStyle.NoBrush))
        self._glow_item.setZValue(10)

        # Ring layer (z=11)
        self._ring_item = self._scene.addEllipse(
            QRectF(0, 0, 100, 100),
            QPen(QColor(200, 100, 255, 0), 3),
            QBrush(Qt.BrushStyle.NoBrush))
        self._ring_item.setZValue(11)

        # Media player
        self._player = QMediaPlayer()
        self._audio  = QAudioOutput()
        self._audio.setVolume(0)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_item)
        video_path = Path(__file__).parent / "Friday.mp4"
        self._player.setSource(QUrl.fromLocalFile(str(video_path)))
        self._player.setLoops(-1)
        self._player.play()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def showEvent(self, event):
        """Ensure layout is computed on first show."""
        super().showEvent(event)
        self._update_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()

    def _update_layout(self):
        w, h = self._view.width(), self._view.height()
        if w == 0 or h == 0:
            return
        self._scene.setSceneRect(0, 0, w, h)
        self._video_item.setSize(QSizeF(w, h))
        self._video_item.setPos(0, 0)
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.45
        self._cx, self._cy, self._r = cx, cy, r
        path = QPainterPath()
        path.addEllipse(cx - r * 1.5, cy - r * 1.5, r * 3, r * 3)
        self._glow_item.setPath(path)
        self._ring_item.setRect(QRectF(cx - r, cy - r, r * 2, r * 2))

    def set_state(self, state: str):
        self._state = state

    def set_muted(self, muted: bool):
        self._muted = muted

    def _tick(self):
        target = 1.0 if self._state == "SPEAKING" else 0.0
        self._amp += (target - self._amp) * 0.07
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:  self._pulse_dir = -1
        elif self._pulse <= 0.0: self._pulse_dir = 1

        # Safe: _cx/_cy/_r initialised to 0.0 but skip draw if radius not set
        if self._r == 0.0:
            return

        amp = self._amp
        pr  = self._r * (1.02 + 0.04 * self._pulse)
        path = QPainterPath()
        path.addEllipse(self._cx - self._r * 1.5, self._cy - self._r * 1.5, self._r * 3, self._r * 3)
        self._glow_item.setPath(path)
        self._glow_item.setPen(QPen(Qt.PenStyle.NoPen))

        if self._muted:
            g = QRadialGradient(self._cx, self._cy, self._r * 1.5)
            g.setColorAt(0.0, QColor(255, 0, 0, 0))
            g.setColorAt(0.4, QColor(200, 0, 0, 35))
            g.setColorAt(0.75,QColor(150, 0, 0, 55))
            g.setColorAt(1.0, QColor(100, 0, 0, 0))
            self._glow_item.setBrush(QBrush(g))
            self._ring_item.setRect(QRectF(self._cx - pr, self._cy - pr, pr * 2, pr * 2))
            self._ring_item.setPen(QPen(QColor(255, 60, 60, int(100 + 60 * self._pulse)), 1.5))
        else:
            g = QRadialGradient(self._cx, self._cy, self._r * 1.5)
            g.setColorAt(0.0, QColor(180, 0, 255, 0))
            g.setColorAt(0.4, QColor(140, 0, 220, int(50 * amp)))
            g.setColorAt(0.75,QColor(100, 0, 180, int(80 * amp)))
            g.setColorAt(1.0, QColor(60,  0, 120, 0))
            self._glow_item.setBrush(QBrush(g))
            self._ring_item.setRect(QRectF(self._cx - pr, self._cy - pr, pr * 2, pr * 2))
            self._ring_item.setPen(QPen(QColor(200, 100, 255, int(180 * amp)), 2 + amp * 3))


# ── Stat bar ──────────────────────────────────────────────────────────────────

class StatBar(QWidget):
    def __init__(self, label: str, color: str = C_CYAN, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = QColor(color)
        self._value = 0.0
        self.setFixedHeight(22)
        self.setMinimumWidth(120)

    def set_value(self, v: float):
        self._value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(QColor(C_TEXT_DIM))
        p.setFont(QFont("Consolas", 9))
        p.drawText(0, 0, 35, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        pct = int(self._value * 100)
        col = self._color
        if pct > 80:   col = QColor(C_RED)
        elif pct > 60: col = QColor(C_AMBER)
        p.setPen(col)
        p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        p.drawText(w - 38, 0, 38, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{pct}%")

        bar_x, bar_w, bar_h = 38, w - 80, 3
        bar_y = (h - bar_h) // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C_CYAN_DARK))
        p.drawRect(bar_x, bar_y, bar_w, bar_h)
        fill = QColor(col); fill.setAlpha(200)
        p.setBrush(fill)
        p.drawRect(bar_x, bar_y, int(bar_w * self._value), bar_h)
        p.end()


# ── History graph panel ───────────────────────────────────────────────────────

class _GraphPanel(QWidget):
    """Scrolling bar-chart history panel."""

    def __init__(self, label: str, color: str = C_CYAN, unit: str = "%", parent=None):
        super().__init__(parent)
        self._label   = label
        self._color   = QColor(color)
        self._unit    = unit
        self._history = [0.0] * 48
        self._current = 0.0
        self.setFixedHeight(80)
        self.setMinimumWidth(120)
        self.setStyleSheet(f"background: rgba(0,10,18,180); border: 1px solid {C_CYAN_DIM};")

    def push(self, value: float):
        self._current = value
        self._history.append(max(0.0, min(100.0, value)))
        if len(self._history) > 48:
            self._history.pop(0)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(QPen(QColor(C_CYAN_DARK), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            p.drawLine(0, y, w, y)

        p.setPen(QColor(C_CYAN_DIM))
        p.setFont(QFont("Consolas", 8))
        p.drawText(4, 0, w - 8, 14, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        val = self._current
        col = QColor(C_RED) if val > 80 else QColor(C_AMBER) if val > 60 else self._color
        p.setPen(col)
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        if self._unit == "%":
            val_str = f"{val:.0f}%"
        elif self._unit == "MB/s":
            val_str = f"{val:.1f}" if val < 10 else f"{val:.0f}"
        else:
            val_str = f"{val:.0f}"
        p.drawText(4, 0, w - 8, 14, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_str)

        chart_top    = 16
        chart_height = h - chart_top - 2
        n            = len(self._history)
        if n == 0:
            p.end()
            return
        bar_w = max(1, (w - 2) // n)
        # FIX: safe gap calculation avoids ZeroDivisionError when n==1
        gap   = max(0, (w - 2 - bar_w * n) // max(1, n - 1)) if n > 1 else 0

        for i, v in enumerate(self._history):
            bh  = max(1, int(v / 100 * chart_height))
            x   = 1 + i * (bar_w + gap)
            y   = chart_top + chart_height - bh
            alpha = int(80 + 140 * (v / 100))
            fill = QColor(col if v > 80 else (QColor(C_AMBER) if v > 60 else self._color))
            fill.setAlpha(alpha)
            p.fillRect(x, y, bar_w, bh, fill)

        p.end()
# ── Log widget (typewriter activity log) ──────────────────────────────────────

class LogWidget(QTextEdit):
    """Activity log with character-by-character typewriter animation.
    Dialogue lines (YOU/FRIDAY) get role headers + body colors; system,
    error, and file-event lines are auto-tagged and colored like Jarvis
    (SYS=amber/yellow, ERR=red, FILE=green)."""

    _sig = pyqtSignal(str, str)  # (role, text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logArea")
        self.setReadOnly(True)
        self._queue: list[tuple[str, str]] = []
        self._typing = False
        self._role   = ""
        self._tag    = "sys"
        self._text   = ""
        self._pos    = 0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, role: str, text: str):
        if not text.strip():
            return
        self._sig.emit(role, text)

    def _enqueue(self, role: str, text: str):
        self._queue.append((role, text))
        if not self._typing:
            self._next()

    def _detect_tag(self, role: str, text: str) -> str:
        """Classify a line for coloring: you / ai / sys / err / file."""
        tl = text.strip().lower()
        if role == "YOU":
            return "you"
        if role == "FRIDAY":
            if tl.startswith("sys:"):
                if "err" in tl or "error" in tl or "fail" in tl:
                    return "err"
                if tl.startswith("sys: file") or "file loaded" in tl or "file:" in tl:
                    return "file"
                return "sys"
            if "err" in tl or "error" in tl:
                return "err"
            return "ai"
        return "sys"

    def _prefix_text(self, tag: str) -> tuple[str, QColor] | None:
        """Inline label prefix shown before the body text, e.g. 'You: '."""
        if tag == "you":
            return ("You: ", QColor(C_CYAN_DIM))
        elif tag == "ai":
            return ("Friday: ", QColor(C_CYAN))
        return None

    def _body_color(self, tag: str) -> QColor:
        return {
            "you":  QColor(C_TEXT),
            "ai":   QColor(C_CYAN),
            "sys":  QColor(C_ACC2),   # amber/yellow
            "err":  QColor(C_RED),
            "file": QColor(C_GREEN),
        }.get(tag, QColor(C_TEXT))

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        role, self._text = self._queue.pop(0)
        self._tag  = self._detect_tag(role, self._text)
        self._role = role
        self._pos  = 0

        # Start a fresh line for this entry (skip for the very first line)
        if self.toPlainText() != "":
            cur = self.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)

        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)

        prefix = self._prefix_text(self._tag)
        if prefix:
            text, col = prefix
            fmt = cur.charFormat()
            fmt.setForeground(QBrush(col))
            fmt.setFontWeight(QFont.Weight.Bold)
            cur.insertText(text, fmt)

        fmt = cur.charFormat()
        fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setForeground(QBrush(self._body_color(self._tag)))
        cur.setCharFormat(fmt)
        self.setTextCursor(cur)

        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            fmt.setForeground(QBrush(self._body_color(self._tag)))
            cur.movePosition(QTextCursor.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)




class _Bridge(QObject):
    state_signal = pyqtSignal(str)


# ── Wave bar (voice activity visualiser) ─────────────────────────────────────

class _WaveBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars  = [0.0] * 32
        self._state = "OFFLINE"
        # FIX: random imported once at module level (not inside 16Hz tick)
        self._t     = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(60)

    def set_state(self, s: str): self._state = s

    def _tick(self):
        speaking = self._state == "SPEAKING"
        for i in range(len(self._bars)):
            target = random.uniform(0.1, 1.0) if speaking else random.uniform(0.0, 0.08)
            self._bars[i] += (target - self._bars[i]) * 0.35
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h  = self.width(), self.height()
        n     = len(self._bars)
        bw    = max(1, w // n - 1)
        gap   = (w - bw * n) // max(1, n - 1)
        col   = QColor(C_CYAN)
        for i, v in enumerate(self._bars):
            bh  = max(1, int(v * h * 0.9))
            x   = i * (bw + gap)
            y   = (h - bh) // 2
            col.setAlpha(int(60 + 160 * v))
            p.fillRect(x, y, bw, bh, col)
        p.end()


# ── Drop zone (Jarvis-style FileDropZone) ────────────────────────────────────

_qcol = qcol  # alias used by drop-zone painting code

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                    "pdf"),
    **dict.fromkeys(["doc","docx"],                                             "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                       "excel"),
    **dict.fromkeys(["ppt","pptx"],                                             "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],  "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                  "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                   "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                 "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_dropped = pyqtSignal(str)  # same signal name as old _DropZone for compatibility

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering   = False
        self._drag_over  = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for FRIDAY", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_dropped.emit(path)  # emit on same signal name


class _DropCanvas(QWidget):
    def __init__(self, zone: "FileDropZone"):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = _qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C_BG))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._drag_over:    border_col = _qcol(C_CYAN, 230)
        elif z._hovering:   border_col = _qcol(C_CYAN_DIM, 200)
        else:               border_col = _qcol(C_CYAN_DARK, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        # FIX: FILE UPLOAD stays constant/idle so multiple files can be
        # dropped/browsed in sequence — the loaded-file card now renders
        # in the FILE panel above (see FridayWindow._on_file_dropped).
        if z._drag_over:    self._paint_drag_over(p, W, H)
        else:               self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = _qcol(C_CYAN_DIM if not hover else C_CYAN)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(_qcol(C_CYAN_DIM if not hover else C_TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(_qcol(C_CYAN_DARK), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(_qcol(C_CYAN), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(_qcol(C_CYAN), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def mousePressEvent(self, e):
        self._z.mousePressEvent(e)


# ── File card (loaded-file display, shown in the FILE panel) ─────────────────

class FileCardWidget(QWidget):
    """Rich file card for ONE file: icon, name, type · size, path, ✕ to clear."""

    clear_requested = pyqtSignal()

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path = Path(path)
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        pad  = 4
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        p.setBrush(QBrush(_qcol(C_BG))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        pen = QPen(_qcol(C_GREEN, 200), 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(self._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        path = self.path
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size) if path.exists() else "?"
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(_qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(_qcol(C_TEXT), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(_qcol(C_TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(_qcol(C_CYAN_DARK), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(_qcol(C_RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        if e.pos().x() > self.width() - 34:
            self.clear_requested.emit()


class FileQueueWidget(QWidget):
    """Scrollable stack of FileCardWidgets — holds multiple loaded files."""

    files_changed = pyqtSignal(list)  # list[str] of current paths

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self._scroll.viewport().setStyleSheet("background: transparent;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(4)
        self._vbox.addStretch()
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        self._empty_lbl = QLabel("No file loaded")
        self._empty_lbl.setObjectName("fileLabel")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setMinimumHeight(70)
        outer.addWidget(self._empty_lbl)

        self._cards: list[FileCardWidget] = []
        self._update_visibility()

    def _update_visibility(self):
        has_files = bool(self._cards)
        self._scroll.setVisible(has_files)
        self._empty_lbl.setVisible(not has_files)

    def add_file(self, path: str):
        # avoid duplicate entries for the same path
        if any(c.path == Path(path) for c in self._cards):
            return
        card = FileCardWidget(path)
        card.clear_requested.connect(lambda c=card: self._remove(c))
        self._vbox.insertWidget(self._vbox.count() - 1, card)
        self._cards.append(card)
        self._update_visibility()
        self.files_changed.emit(self.paths())

    def _remove(self, card: "FileCardWidget"):
        self._cards.remove(card)
        self._vbox.removeWidget(card)
        card.deleteLater()
        self._update_visibility()
        self.files_changed.emit(self.paths())

    def clear_all(self):
        for card in self._cards:
            self._vbox.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._update_visibility()
        self.files_changed.emit(self.paths())

    def paths(self) -> list[str]:
        return [str(c.path) for c in self._cards]


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FRIDAY — SETTINGS")
        self.setMinimumWidth(440)
        self.setStyleSheet(STYLE)
        cfg = get_config()

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("◈  SYSTEM CONFIGURATION")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        lbl = QLabel("GEMINI API KEY:"); lbl.setObjectName("statLabel")
        self._key_input = QLineEdit(cfg.get("gemini_api_key", ""))
        self._key_input.setObjectName("settingsInput")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza...")
        form.addRow(lbl, self._key_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        save_btn   = QPushButton("SAVE");   save_btn.setObjectName("sendBtn");    save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("CANCEL"); cancel_btn.setObjectName("settingsBtn"); cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self):
        cfg = get_config()
        cfg["gemini_api_key"] = self._key_input.text().strip()
        save_config(cfg)
        self.accept()


class SetupOverlay(QWidget):
    """First-boot overlay — shown when no API key found in local config."""
    done = pyqtSignal(str, str)  # (api_key, os_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(2, 11, 18, 248);
                border: 1px solid {C_CYAN_DIM};
                border-radius: 4px;
            }}
        """)

        detected = {"Darwin": "mac", "Windows": "windows"}.get(_OS, "linux")
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(8)

        def _lbl(txt, size=9, bold=False, color=C_CYAN,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure FRIDAY before first boot.", 9, color=C_CYAN_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C_CYAN_DIM};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C_CYAN_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C_CYAN};
                border: 1px solid {C_CYAN_DIM}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C_CYAN}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C_CYAN_DIM};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C_CYAN_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C_GREEN,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict = {}
        for key, label in [("windows", "⊞  Windows"), ("mac", "  macOS"), ("linux", "🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_CYAN};
                border: 1px solid {C_CYAN_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: rgba(0,229,255,15); border: 1px solid {C_CYAN};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

        self._err_lbl = _lbl("", 8, color=C_RED)
        layout.addWidget(self._err_lbl)

    def _sel(self, key: str):
        self._sel_os = key
        colors = {
            "windows": (C_CYAN,   "#001a22"),
            "mac":     ("#ffcc00", "#1a1400"),
            "linux":   (C_GREEN,  "#001a0d"),
        }
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = colors[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C_CYAN_DIM};
                        border: 1px solid {C_CYAN_DIM}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C_CYAN}; border: 1px solid {C_CYAN}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._err_lbl.setText("⚠  API key required.")
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C_RED}; }}"
            )
            return
        if len(key) < 20:
            self._err_lbl.setText("⚠  Key too short.")
            return
        self._err_lbl.setText("")
        self.done.emit(key, self._sel_os)

    def resizeEvent(self, e):
        """Centre overlay in parent."""
        if self.parent():
            pw, ph = self.parent().width(), self.parent().height()
            # FIX: use minimumSizeHint for reliable pre-layout height
            hint = self.minimumSizeHint()
            w = min(480, pw - 40)
            h = max(hint.height(), self.sizeHint().height()) + 20
            self.setGeometry((pw - w) // 2, (ph - h) // 2, w, h)
        super().resizeEvent(e)


# ── Main window ───────────────────────────────────────────────────────────────

class FridayWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("F.R.I.D.A.Y")
        self.resize(1280, 780)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE)
        self.muted          = False
        self._agent         = None
        self._bridge        = _Bridge()
        self._current_state = "OFFLINE"
        self._bridge.state_signal.connect(self._on_state)

        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        main = QHBoxLayout(body)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        outer.addWidget(body, stretch=1)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget(); left.setObjectName("panel"); left.setFixedWidth(160)
        ll = QVBoxLayout(left); ll.setContentsMargins(8, 8, 8, 8); ll.setSpacing(3)

        sys_title = QLabel("◈ SYS MONITOR"); sys_title.setObjectName("sectionTitle")
        ll.addWidget(sys_title); ll.addSpacing(2)

        self._cpu_bar = StatBar("CPU"); self._cpu_bar.setVisible(False)
        self._mem_bar = StatBar("MEM", C_AMBER); self._mem_bar.setVisible(False)
        self._gpu_bar = StatBar("GPU", C_CYAN);  self._gpu_bar.setVisible(False)
        self._net_label = QLabel("NET   0 B/s"); self._net_label.setObjectName("statLabel")
        self._net_label.setVisible(False)

        self._cpu_graph = _GraphPanel("CPU", C_CYAN);             self._cpu_graph.setFixedHeight(62)
        self._mem_graph = _GraphPanel("MEM", C_AMBER);            self._mem_graph.setFixedHeight(62)
        self._net_graph = _GraphPanel("NET", C_CYAN_DIM, "KB/s"); self._net_graph.setFixedHeight(62)
        self._gpu_graph = _GraphPanel("GPU", C_CYAN);             self._gpu_graph.setFixedHeight(62)
        ll.addWidget(self._cpu_graph)
        ll.addWidget(self._mem_graph)
        ll.addWidget(self._net_graph)
        ll.addWidget(self._gpu_graph)

        self._tmp_label = QLabel("TMP   N/A"); self._tmp_label.setObjectName("statLabel")
        ll.addWidget(self._tmp_label)

        ll.addSpacing(4)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_CYAN_DIM};"); ll.addWidget(div); ll.addSpacing(3)

        self._uptime_label = QLabel("UP   0:00"); self._uptime_label.setObjectName("statLabel")
        self._proc_label   = QLabel("PROC  0");   self._proc_label.setObjectName("statLabel")
        os_name = {"Windows": "WIN", "Darwin": "MAC", "Linux": "LNX"}.get(_OS, "N/A")
        os_lbl  = QLabel(f"OS   {os_name}");      os_lbl.setObjectName("statLabel")
        ll.addWidget(self._uptime_label); ll.addWidget(self._proc_label); ll.addWidget(os_lbl)
        ll.addStretch()

        for txt, col in [("AI CORE\nACTIVE", C_GREEN), ("SEC\nCLEARED", C_CYAN)]:
            chip = QLabel(txt); chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setFixedHeight(40)
            chip.setStyleSheet(
                f"color:{col}; border:1px solid {col}; padding:3px 4px;"
                f"font-size:9px; letter-spacing:1px;"
            )
            ll.addWidget(chip)
        main.addWidget(left)

        # ── Centre panel ──────────────────────────────────────────────────────
        centre = QWidget()
        cl = QVBoxLayout(centre); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet(f"background:rgba(0,18,28,200);border-bottom:1px solid {C_CYAN_DIM};")
        tb = QHBoxLayout(title_bar); tb.setContentsMargins(12, 4, 12, 4); tb.setSpacing(0)

        spacer_l = QWidget(); spacer_l.setFixedWidth(80)
        tb.addWidget(spacer_l)
        tb.addStretch(1)

        ct = QVBoxLayout(); ct.setSpacing(0); ct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QLabel("F.R.I.D.A.Y"); brand.setObjectName("titleMain")
        brand.setStyleSheet(f"color:{C_CYAN}; font-size:22px; font-weight:bold; letter-spacing:9px;")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub   = QLabel("[Friendly Rapid Intelligence Digital Autonomous Yielder]")
        sub.setObjectName("titleSub")
        sub.setStyleSheet(f"color:{C_CYAN_DIM}; font-size:8px; letter-spacing:1px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ct.addWidget(brand); ct.addWidget(sub)
        tb.addLayout(ct)
        tb.addStretch(1)

        rt = QVBoxLayout(); rt.setSpacing(0); rt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_label = QLabel(); self._time_label.setObjectName("timeLabel")
        self._time_label.setStyleSheet(f"color:{C_CYAN}; font-size:14px; font-weight:bold; letter-spacing:2px;")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date_label = QLabel(); self._date_label.setObjectName("dateLabel")
        self._date_label.setStyleSheet(f"color:{C_CYAN_DIM}; font-size:9px; letter-spacing:1px;")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        rt.addWidget(self._time_label); rt.addWidget(self._date_label)
        tb.addLayout(rt)
        cl.addWidget(title_bar)

        self._orb = OrbWidget()
        self._orb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cl.addWidget(self._orb, stretch=1)

        sb_w = QWidget()
        sb_w.setFixedHeight(34)
        sb_w.setStyleSheet(f"background:rgba(0,18,28,200);border-top:1px solid {C_CYAN_DIM};")
        sb = QHBoxLayout(sb_w); sb.setContentsMargins(10, 4, 10, 4); sb.setSpacing(6)

        self._mute_btn = QPushButton("🎤  MICROPHONE ACTIVE")
        self._mute_btn.setObjectName("muteBtn"); self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedHeight(26)
        self._mute_btn.clicked.connect(self._toggle_mute)

        self._state_label = QLabel("○  OFFLINE"); self._state_label.setObjectName("statusOrb")

        clear_btn    = QPushButton("CLEAR LOG");  clear_btn.setObjectName("settingsBtn");    clear_btn.clicked.connect(self._clear_log)
        settings_btn = QPushButton("⚙ SETTINGS"); settings_btn.setObjectName("settingsBtn"); settings_btn.clicked.connect(self._open_settings)
        self._fs_btn = QPushButton("⛶ FULLSCREEN [F11]"); self._fs_btn.setObjectName("settingsBtn"); self._fs_btn.clicked.connect(self._toggle_fullscreen)

        sb.addWidget(self._mute_btn)
        sb.addStretch()
        sb.addWidget(self._state_label)
        sb.addStretch()
        sb.addWidget(clear_btn); sb.addWidget(settings_btn); sb.addWidget(self._fs_btn)
        cl.addWidget(sb_w)
        main.addWidget(centre, stretch=1)

        # ── Right panel ───────────────────────────────────────────────────────
        right = QWidget(); right.setObjectName("panel"); right.setFixedWidth(310)
        rl = QVBoxLayout(right); rl.setContentsMargins(10, 10, 10, 10); rl.setSpacing(6)

        log_title = QLabel("◈ ACTIVITY LOG"); log_title.setObjectName("sectionTitle")
        rl.addWidget(log_title)
        self._log = LogWidget()
        rl.addWidget(self._log, stretch=2)

        self._wave_bar = _WaveBar(); self._wave_bar.setFixedHeight(36)
        rl.addWidget(self._wave_bar)

        div1 = QFrame(); div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet(f"color:{C_CYAN_DIM};"); rl.addWidget(div1)

        # FILE preview panel — shows currently-loaded file content/thumbnail
        file_prev_title = QLabel("◈ FILE"); file_prev_title.setObjectName("sectionTitle")
        rl.addWidget(file_prev_title)

        self._file_queue = FileQueueWidget()
        self._file_queue.files_changed.connect(self._on_files_changed)
        rl.addWidget(self._file_queue, stretch=1)

        div2 = QFrame(); div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"color:{C_CYAN_DIM};"); rl.addWidget(div2)

        file_title = QLabel("◈ FILE UPLOAD"); file_title.setObjectName("sectionTitle")
        rl.addWidget(file_title)

        self._upload_btn = FileDropZone()
        self._upload_btn.file_dropped.connect(self._on_file_dropped)
        rl.addWidget(self._upload_btn)

        self._file_status = QLabel("")
        self._file_status.setObjectName("fileStatus")
        self._file_status.setWordWrap(True)
        self._file_status.setVisible(False)
        rl.addWidget(self._file_status)

        div3 = QFrame(); div3.setFrameShape(QFrame.Shape.HLine)
        div3.setStyleSheet(f"color:{C_CYAN_DIM};"); rl.addWidget(div3)

        cmd_title = QLabel("◈ COMMAND INPUT"); cmd_title.setObjectName("sectionTitle")
        rl.addWidget(cmd_title)
        cmd_row = QHBoxLayout(); cmd_row.setSpacing(0)
        self._input = QLineEdit(); self._input.setObjectName("cmdInput")
        self._input.setPlaceholderText("Type a command or question...")
        self._input.returnPressed.connect(self._send)
        self._send_btn = QPushButton("▶"); self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedWidth(36); self._send_btn.clicked.connect(self._send)
        cmd_row.addWidget(self._input); cmd_row.addWidget(self._send_btn)
        rl.addLayout(cmd_row)

        main.addWidget(right)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(22)
        footer.setStyleSheet(f"background:{C_DARK};border-top:1px solid {C_CYAN_DIM};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(14, 0, 14, 0)

        def _flabel(txt, color=C_CYAN):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color:{color}; background:transparent;")
            return l

        fl.addWidget(_flabel("[F4] Mute  ·  [F11] Fullscreen"))
        fl.addStretch()
        fl.addWidget(_flabel("Ankit  ·  FRIDAY  ·  CLASSIFIED"))
        fl.addStretch()
        fl.addWidget(_flabel("© ANKIT", C_CYAN))
        outer.addWidget(footer)

        # ── Timers ────────────────────────────────────────────────────────────
        self._clock_timer = QTimer(self); self._clock_timer.timeout.connect(self._update_clock); self._clock_timer.start(1000)
        self._update_clock()
        self._sys_timer = QTimer(self); self._sys_timer.timeout.connect(self._update_sys); self._sys_timer.start(2000)
        self._update_sys()

        # FIX: check API key after window is shown (avoids Qt signal race on startup)
        if not get_config().get("gemini_api_key"):
            QTimer.singleShot(400, self._prompt_api_key)

        # ── Shortcuts ─────────────────────────────────────────────────────────
        QShortcut(QKeySequence("F4"), self).activated.connect(self._toggle_mute_shortcut)

    def _toggle_mute_shortcut(self):
        self._mute_btn.setChecked(not self._mute_btn.isChecked())
        self._toggle_mute()

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _update_clock(self):
        now = datetime.now()
        self._time_label.setText(now.strftime("%H:%M:%S"))
        self._date_label.setText(now.strftime("%a %d %b %Y"))

    # ── System stats ──────────────────────────────────────────────────────────

    def _update_sys(self):
        snap = _metrics.snapshot()

        self._cpu_bar.set_value(snap["cpu"] / 100)
        self._mem_bar.set_value(snap["mem"] / 100)

        self._cpu_graph.push(snap["cpu"])
        self._mem_graph.push(snap["mem"])

        net = snap["net"]
        net_kb = net * 1024
        self._net_graph.push(min(net_kb, 100))
        if net >= 1.0:     net_str = f"{net:.1f} MB/s"
        elif net >= 0.001: net_str = f"{net_kb:.0f} KB/s"
        else:              net_str = "0 B/s"
        self._net_label.setText(f"NET   {net_str}")

        gpu = snap["gpu"]
        if gpu >= 0:
            self._gpu_bar.set_value(gpu / 100)
            self._gpu_graph.push(gpu)
        else:
            self._gpu_graph.push(0)

        tmp = snap["tmp"]
        if tmp >= 0:
            self._tmp_label.setText(f"TMP   {tmp:.0f}°C")
        else:
            self._tmp_label.setText("TMP   N/A")

        try:
            self._proc_label.setText(f"PROC  {len(psutil.pids())}")
        except Exception:
            pass

        try:
            boot     = datetime.fromtimestamp(psutil.boot_time())
            delta_up = datetime.now() - boot
            hrs  = int(delta_up.total_seconds() // 3600)
            mins = int((delta_up.total_seconds() % 3600) // 60)
            self._uptime_label.setText(f"UP   {hrs}:{mins:02d}")
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def append_log(self, role: str, text: str):
        self._log.append_log(role, text)

    def set_state(self, state: str):
        self._bridge.state_signal.emit(state)

    def set_agent(self, agent):
        self._agent = agent

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_state(self, state: str):
        # FIX: always update _current_state regardless of mute, so unmute restores correct state
        self._current_state = state
        self._orb.set_state(state)
        self._wave_bar.set_state(state)
        if self.muted:
            return
        self._apply_state_label(state)

    def _apply_state_label(self, state: str):
        colors = {"LISTENING": C_GREEN, "SPEAKING": "#a090ff", "THINKING": C_AMBER, "OFFLINE": C_RED}
        col = colors.get(state, C_CYAN)
        self._state_label.setText(f"○  {state}")
        self._state_label.setStyleSheet(f"color:{col};font-size:11px;letter-spacing:3px;font-weight:bold;")

    def _send(self):
        text = self._input.text().strip()
        if not text or not self._agent: return
        self._input.clear()
        self.append_log("YOU", text)
        self._agent.send_text(text)

    def _toggle_mute(self):
        self.muted = self._mute_btn.isChecked()
        self._mute_btn.setText("🔇  MICROPHONE MUTED" if self.muted else "🎤  MICROPHONE ACTIVE")
        self._orb.set_muted(self.muted)
        if self.muted:
            self._state_label.setText("○  MUTED")
            self._state_label.setStyleSheet(f"color:{C_RED}; font-size:11px; letter-spacing:3px; font-weight:bold;")
        else:
            # FIX: restore using _current_state (which is now always up-to-date)
            self._apply_state_label(self._current_state)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self._fs_btn.setText("⛶ FULLSCREEN  [F11]")
        else:
            self.showFullScreen()
            self._fs_btn.setText("⛶ EXIT FULLSCREEN  [ESC]")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            self._fs_btn.setText("⛶ FULLSCREEN  [F11]")
        else:
            super().keyPressEvent(event)

    def _clear_log(self):
        self._log._tmr.stop()
        self._log._queue.clear()
        self._log._typing = False
        self._log.clear()
        self.append_log("FRIDAY", "SYS: Log cleared.")

    def _open_settings(self):
        SettingsDialog(self).exec()

    def _prompt_api_key(self):
        self.append_log("FRIDAY", "SYS: No API key found. Initialisation required.")
        self._show_setup_overlay()

    def _show_setup_overlay(self):
        self._setup_overlay = SetupOverlay(self)
        self._setup_overlay.done.connect(self._on_setup_done)
        self._setup_overlay.show()
        self._setup_overlay.raise_()
        pw, ph = self.width(), self.height()
        w = min(480, pw - 40)
        hint = self._setup_overlay.sizeHint()
        h = hint.height() + 20
        self._setup_overlay.setGeometry((pw - w) // 2, (ph - h) // 2, w, h)

    def _on_setup_done(self, api_key: str, os_name: str):
        cfg = get_config()
        cfg["gemini_api_key"] = api_key
        cfg["os_system"]      = os_name
        save_config(cfg)
        self._setup_overlay.hide()
        self._setup_overlay.deleteLater()
        self.append_log("FRIDAY", "SYS: Configuration saved. Starting agent...")
        from agent import start_live_agent
        self._agent = start_live_agent(self)

    def _on_file_dropped(self, path: str):
        p = Path(path)
        icon, _ = _FILE_ICONS.get(_file_category(p), _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)

        self._file_queue.add_file(path)
        self.append_log("FRIDAY", f"SYS: File loaded — {p.name} ({size}).")
        self._file_status.setText(f"{icon}  {p.name}  ·  {size}  ·  Sent to FRIDAY")
        self._file_status.setVisible(True)

        # FIX: proactively notify the agent so FRIDAY acknowledges the
        # upload immediately, e.g. "I see you've uploaded 'README.md'
        # (17 B). What would you like to do with it?"
        if self._agent:
            notice = f"[The user just uploaded a file: '{p.name}' ({size}).]"
            self._agent.send_text_with_file(notice, path)

    def _on_files_changed(self, paths: list):
        if not paths:
            self._file_status.setVisible(False)
            self._file_status.setText("")


# ── Public API wrapper ────────────────────────────────────────────────────────

class _RootShim:
    """Mimics a Tk-style root object for code expecting .mainloop()/.protocol()."""

    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class FridayUI:
    """Thin convenience facade over FridayWindow, mirroring JarvisUI's API."""

    def __init__(self):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = FridayWindow()
        self._win.show()
        self.root = _RootShim(self._app)

        from config import get_api_key
        if get_api_key():
            from agent.live_agent import start_live_agent
            agent = start_live_agent(self._win)
            self._win.set_agent(agent)

    @property
    def muted(self) -> bool:
        return self._win.muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win.muted:
            self._win._toggle_mute()

    @property
    def current_files(self) -> list[str]:
        return self._win._file_queue.paths()

    @property
    def current_file(self) -> str | None:
        paths = self.current_files
        return paths[0] if paths else None

    def set_state(self, state: str):
        self._win.set_state(state)

    def write_log(self, role: str, text: str):
        self._win.append_log(role, text)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def run(self):
        self.root.mainloop()


# ── Entry ─────────────────────────────────────────────────────────────────────

def run_ui():
    ui = FridayUI()
    sys.exit(ui._app.exec())