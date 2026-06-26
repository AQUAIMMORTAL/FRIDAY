"""
voice_engine.py — TTS and STT for FRIDAY (Windows)
pyttsx3 is COM-based on Windows — must live on its own dedicated thread.
"""
import threading
import queue

try:
    import pyttsx3
    _TTS = True
except ImportError:
    _TTS = False

try:
    import speech_recognition as sr
    _STT = True
except ImportError:
    _STT = False


# ── TTS ───────────────────────────────────────────────────────────────────────

class _TTSThread(threading.Thread):
    """Dedicated thread that owns the pyttsx3 engine for its full lifetime."""

    def __init__(self):
        super().__init__(daemon=True, name="FRIDAY-TTS")
        self._queue  = queue.Queue()
        self._ready  = threading.Event()
        self.start()
        self._ready.wait(timeout=5)   # wait until engine is initialised

    def run(self):
        if not _TTS:
            self._ready.set()
            return

        engine = pyttsx3.init()

        # Prefer Microsoft Zira (female) on Windows
        for v in engine.getProperty("voices"):
            if "zira" in v.name.lower():
                engine.setProperty("voice", v.id)
                break

        engine.setProperty("rate",   170)
        engine.setProperty("volume", 1.0)
        self._ready.set()

        while True:
            text = self._queue.get()
            if text is None:          # shutdown signal
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[TTS Error] {e}")

    def speak(self, text: str):
        self._queue.put(text)

    def stop(self):
        self._queue.put(None)


_tts_thread: _TTSThread | None = None
_tts_lock = threading.Lock()


def _get_tts() -> "_TTSThread":
    global _tts_thread
    with _tts_lock:
        if _tts_thread is None or not _tts_thread.is_alive():
            _tts_thread = _TTSThread()
    return _tts_thread


def speak(text: str):
    if not _TTS:
        print(f"[FRIDAY] {text}")
        return
    _get_tts().speak(text)


def is_tts_available() -> bool:
    return _TTS


# ── STT ───────────────────────────────────────────────────────────────────────

class SpeechListener:
    def __init__(self, energy_threshold: int = 400):
        if not _STT:
            raise RuntimeError("SpeechRecognition not installed.")
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold         = energy_threshold
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold          = 0.8
        self._mic = None

    def _get_mic(self):
        if self._mic is None:
            self._mic = sr.Microphone()
        return self._mic

    def listen_once(self, timeout: int = 8, phrase_limit: int = 20) -> str | None:
        try:
            with self._get_mic() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
            return self.recognizer.recognize_google(audio).strip()
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except sr.RequestError as e:
            print(f"[STT Error] {e}")
            return None
        except Exception as e:
            print(f"[STT Error] {e}")
            return None


_listener: SpeechListener | None = None


def get_listener() -> SpeechListener:
    global _listener
    if _listener is None:
        _listener = SpeechListener()
    return _listener


def listen() -> str | None:
    if not _STT:
        return None
    return get_listener().listen_once()


def is_stt_available() -> bool:
    return _STT