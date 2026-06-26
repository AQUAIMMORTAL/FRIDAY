"""
live_agent.py — FRIDAY Live Agent using Gemini Native Audio (Live API)
Uses Gemini's built-in Aoede voice — natural, human-quality voice.
"""
import asyncio
import base64
import mimetypes
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path

import sounddevice as sd
from google import genai
from google.genai import types

from config import get_api_key
from memory import load_memory, update_memory, format_memory_for_prompt
from actions.screen_processor  import screen_processor
from actions.computer_control  import computer_control
from actions.web_search        import web_search, fetch_url
from actions.file_handler      import file_handler
from actions.open_app          import open_app
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.weather_report    import weather_action
from actions.computer_settings import computer_settings
from actions.youtube_video     import youtube_video
from actions.browser_control   import browser_control
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.flight_finder     import flight_finder
from actions.game_updater      import game_updater
from actions.file_processor    import file_processor
# FIX: import desktop_control at top level (was missing, caused NameError in tool router)
from actions.desktop           import desktop_control as _desktop_control
from actions.file_controller   import file_controller as _file_controller

# ── Audio constants ───────────────────────────────────────────────────────────
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core" / "prompt.txt"
_CTRL_RE     = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# Allowed shell commands (whitelist for run_command safety)
_ALLOWED_COMMANDS = re.compile(
    r"^\s*(dir|ls|pwd|echo|type|cat|ipconfig|ifconfig|hostname|whoami|date|time|"
    r"ping\s|tracert\s|nslookup\s|curl\s|wget\s|python\s|pip\s|node\s|npm\s|"
    r"git\s|code\s|notepad|calc|mspaint|explorer)\b",
    re.IGNORECASE,
)


def _clean_transcript(text: str) -> str:
    return _CTRL_RE.sub("", text).strip()


def _load_system_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "You are FRIDAY, a casual and friendly personal AI assistant."


# ── Tool declarations ─────────────────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Opens any application on the computer. Use whenever the user asks to open, launch, or start any app, website, or program. Always call this tool — never just say you opened it.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a message to a contact via WhatsApp, Telegram, Instagram, Discord, Signal, or Messenger.",
        "parameters": {
            "type": "object",
            "properties": {
                "platform":     {"type": "string", "description": "e.g. whatsapp, telegram, instagram, discord"},
                "receiver":     {"type": "string", "description": "Contact name or username"},
                "message_text": {"type": "string", "description": "The message to send"},
            },
            "required": ["platform", "receiver", "message_text"],
        },
    },
    {
        "name": "reminder",
        "description": "Set a reminder for a specific date and time.",
        "parameters": {
            "type": "object",
            "properties": {
                "date":    {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "string", "description": "Time in HH:MM (24h) format"},
                "message": {"type": "string", "description": "Reminder message"},
            },
            "required": ["date", "time", "message"],
        },
    },
    {
        "name": "weather",
        "description": "Show weather for a city by opening Google weather search.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "time": {"type": "string", "description": "today, tomorrow, this week etc."},
            },
            "required": ["city"],
        },
    },
    {
        "name": "computer_settings",
        "description": "Control system settings: volume (set/mute/unmute), brightness, WiFi, Bluetooth, dark/light mode, sleep.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "e.g. set_volume, mute, unmute, set_brightness, wifi_on, wifi_off, bluetooth_on, dark_mode, light_mode, sleep"},
                "value":  {"type": "number", "description": "0-100 for volume or brightness"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "youtube",
        "description": "Search and play a YouTube video in the browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or video title"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "screen_processor",
        "description": "Capture the user's screen or webcam and analyze the image.",
        "parameters": {
            "type": "object",
            "properties": {
                "source":   {"type": "string", "enum": ["screen", "webcam"]},
                "question": {"type": "string"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "computer_control",
        "description": (
            "Control the computer: mouse, keyboard, clipboard. "
            "For run_command, only safe read-only commands are allowed "
            "(ls, dir, ipconfig, ping, etc). Never use for destructive shell commands."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action":  {"type": "string"},
                "x":       {"type": "integer"},
                "y":       {"type": "integer"},
                "button":  {"type": "string"},
                "clicks":  {"type": "integer"},
                "text":    {"type": "string"},
                "keys":    {"type": "string"},
                "key":     {"type": "string"},
                "app":     {"type": "string"},
                "command": {"type": "string"},
                "path":    {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query":       {"type": "string"},
                "max_results": {"type": "integer"},
                "deep":        {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch and read content from a specific URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url":       {"type": "string"},
                "max_chars": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "file_handler",
        "description": "Read, write, list, copy, move, delete, or search files and folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "action":    {"type": "string", "enum": ["read","write","list","delete","copy","move","search","info"]},
                "path":      {"type": "string"},
                "content":   {"type": "string"},
                "src":       {"type": "string"},
                "dst":       {"type": "string"},
                "directory": {"type": "string"},
                "pattern":   {"type": "string"},
                "append":    {"type": "boolean"},
                "recursive": {"type": "boolean"},
                "confirmed": {"type": "boolean"},
                "depth":     {"type": "integer"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "shutdown_friday",
        "description": "Shut down and close FRIDAY completely. Use when the user says goodbye, close yourself, shut down, exit, or similar.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "browser_control",
        "description": "Control a web browser: open URLs, search, click, type, scroll, get page text, take screenshots. Use for any web browsing task.",
        "parameters": {
            "type": "object",
            "properties": {
                "action":      {"type": "string", "description": "go_to, search, click, type, scroll, get_text, get_url, press, new_tab, close_tab, back, forward, reload, close, smart_click, smart_type, screenshot"},
                "url":         {"type": "string"},
                "query":       {"type": "string"},
                "engine":      {"type": "string", "description": "google, bing, duckduckgo"},
                "selector":    {"type": "string"},
                "text":        {"type": "string"},
                "description": {"type": "string"},
                "direction":   {"type": "string", "enum": ["up", "down"]},
                "amount":      {"type": "integer"},
                "key":         {"type": "string"},
                "browser":     {"type": "string", "description": "chrome, edge, firefox, brave"},
                "path":        {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "code_helper",
        "description": "Write, edit, run, analyze, or optimize code files. Can build and fix Python projects.",
        "parameters": {
            "type": "object",
            "properties": {
                "action":   {"type": "string", "description": "write, edit, run, analyze, optimize, build"},
                "path":     {"type": "string", "description": "File path"},
                "content":  {"type": "string", "description": "Code content"},
                "language": {"type": "string"},
                "task":     {"type": "string", "description": "Description of what to do"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "dev_agent",
        "description": "Build complete software projects from a description. Creates files, installs dependencies, and runs the project.",
        "parameters": {
            "type": "object",
            "properties": {
                "task":     {"type": "string", "description": "What to build"},
                "language": {"type": "string", "description": "Python, JavaScript, etc."},
                "path":     {"type": "string", "description": "Where to create the project"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "flight_finder",
        "description": "Search for flights between two cities on a given date using Google Flights.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin":       {"type": "string", "description": "Departure city or airport code"},
                "destination":  {"type": "string", "description": "Arrival city or airport code"},
                "date":         {"type": "string", "description": "Departure date e.g. tomorrow, 2025-06-15"},
                "return_date":  {"type": "string", "description": "Return date for round trips"},
                "passengers":   {"type": "integer", "description": "Number of passengers"},
                "cabin":        {"type": "string",  "enum": ["economy","premium","business","first"]},
                "save":         {"type": "boolean", "description": "Save results to Desktop"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    {
        "name": "game_updater",
        "description": "Update, verify, or check a Steam game. Can also open Steam library.",
        "parameters": {
            "type": "object",
            "properties": {
                "action":   {"type": "string", "enum": ["update","verify","open_library","check_update"], "description": "What to do"},
                "game":     {"type": "string", "description": "Game name e.g. CS2, GTA V, Dota 2"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "file_processor",
        "description": "Process any file — summarize PDFs, analyze CSVs, describe images, transcribe audio, review code, extract text from documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path":     {"type": "string", "description": "Full path to the file"},
                "action":   {"type": "string", "description": "summarize, analyze, extract_text, describe, transcribe, review, fix, word_count, stats, convert"},
                "output":   {"type": "string", "description": "Optional output file path"},
                "language": {"type": "string", "description": "For code review/fix: programming language"},
            },
            "required": ["path", "action"],
        },
    },
    {
        "name": "file_controller",
        "description": "Advanced file management: write, create, read, list, delete, move, copy, find files or check disk usage.",
        "parameters": {
            "type": "object",
            "properties": {
                "action":  {"type": "string", "description": "write | create_file | read | list | delete | move | copy | find | disk_usage"},
                "path":    {"type": "string", "description": "Folder path. Use 'desktop' for Desktop."},
                "name":    {"type": "string", "description": "Filename"},
                "content": {"type": "string", "description": "File content (for write/create_file)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "desktop_control",
        "description": "Control the desktop: set wallpaper, organize/clean desktop files, list desktop items, or run a desktop task.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "wallpaper | organize | clean | list | task"},
                "path":   {"type": "string", "description": "Path (e.g. wallpaper image path)"},
                "task":   {"type": "string", "description": "Natural language task description"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "agentic_task",
        "description": "Use for complex multi-step goals that require planning: research + save, install software, multi-app workflows, etc. The planner/executor backend handles this automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The full goal in natural language"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "save_memory",
        "description": "Save or update information about the user for future sessions.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["identity","preferences","projects","relationships","wishes","notes"]},
                "key":      {"type": "string"},
                "value":    {"type": "string"},
            },
            "required": ["category", "key", "value"],
        },
    },
]


# ── Tool router ───────────────────────────────────────────────────────────────
_shutdown_event = threading.Event()
_live_ui_ref    = None  # set by start_live_agent


def _call_tool(name: str, args: dict) -> str:
    try:
        if name == "open_app":
            return open_app(args)
        elif name == "send_message":
            return send_message(args)
        elif name == "reminder":
            return reminder(args)
        elif name == "weather":
            return weather_action(args)
        elif name == "computer_settings":
            return computer_settings(args)
        elif name == "youtube":
            return youtube_video(args)
        elif name == "screen_processor":
            return screen_processor(args)
        elif name == "computer_control":
            if args.get("action", "").lower() == "run_command":
                cmd = args.get("command", "")
                if not _ALLOWED_COMMANDS.match(cmd):
                    return f"Blocked: '{cmd}' is not in the allowed command list for safety."
            return computer_control(args)
        elif name == "web_search":
            return web_search(args)
        elif name == "fetch_url":
            return fetch_url(args)
        elif name == "file_handler":
            return file_handler(args)
        elif name == "file_controller":
            # FIX: use top-level import instead of inline import
            return _file_controller(parameters=args, player=None)
        elif name == "desktop_control":
            # FIX: use top-level import instead of inline import
            return _desktop_control(parameters=args, player=None)
        elif name == "browser_control":
            return browser_control(parameters=args, player=_live_ui_ref)
        elif name == "code_helper":
            return code_helper(parameters=args, player=_live_ui_ref, speak=None)
        elif name == "dev_agent":
            return dev_agent(parameters=args, player=_live_ui_ref, speak=None)
        elif name == "flight_finder":
            return flight_finder(parameters=args, speak=None)
        elif name == "game_updater":
            return game_updater(parameters=args)
        elif name == "file_processor":
            return file_processor(parameters=args)
        elif name == "agentic_task":
            from agent.task_queue import get_queue, TaskPriority
            goal = args.get("goal", "")
            if not goal:
                return "No goal provided for agentic_task."
            queue = get_queue()
            task_id = queue.submit(goal=goal, priority=TaskPriority.NORMAL)
            return f"Task queued: {task_id}"
        elif name == "save_memory":
            cat   = args.get("category", "notes")
            key   = args.get("key", "")
            value = args.get("value", "")
            if key and value:
                update_memory({cat: {key: {"value": value}}})
            return "ok"
        elif name == "shutdown_friday":
            import time as _t, os as _os
            def _do_exit():
                _t.sleep(1.2)
                _os._exit(0)
            threading.Thread(target=_do_exit, daemon=True).start()
            return "shutting_down"
    except Exception as e:
        return f"Tool error: {e}"
    return f"Unknown tool: {name}"


# ── Live Agent ────────────────────────────────────────────────────────────────
class FridayLive:

    def __init__(self, ui):
        self.ui                = ui
        self.session           = None
        self.audio_in_queue    = None
        self.out_queue         = None
        self._loop             = None
        self._is_speaking      = False
        self._is_executing     = False
        self._speaking_lock    = threading.Lock()
        self._turn_done_event  = None
        self._pending_files    = []  # list[str] set by UI file drop/browse

    def send_text(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True,
            ),
            self._loop,
        )

    def send_file(self, path: str):
        """Queue a file to be sent with the next user turn."""
        if path not in self._pending_files:
            self._pending_files.append(path)

    # Gemini Live API only accepts these inline_data MIME categories.
    # Anything else causes the server to close the connection (code 1007).
    _SUPPORTED_MIME_PREFIXES = ("image/", "audio/", "video/", "text/")
    _SUPPORTED_MIME_EXACT = {"application/pdf"}

    # Extensions that are plain text but mimetypes may not recognise
    # (or that map to application/octet-stream / unknown).
    _TEXT_EXTENSIONS = {
        ".txt", ".md", ".markdown", ".log", ".csv", ".tsv", ".json", ".xml",
        ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml", ".env",
        ".gitconfig", ".gitignore", ".gitattributes", ".editorconfig",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
        ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
        ".php", ".swift", ".kt", ".sh", ".bash", ".sql", ".lua", ".r",
    }

    def _resolve_mime(self, path: Path) -> str | None:
        """Return a Live-API-safe MIME type for this file, or None if
        the file type can't be sent as inline data."""
        mime = mimetypes.guess_type(str(path))[0]

        if mime and (mime.startswith(self._SUPPORTED_MIME_PREFIXES)
                      or mime in self._SUPPORTED_MIME_EXACT):
            return mime

        # No/unsupported MIME guess — treat known text-like extensions
        # (including dotfiles like .gitconfig) as text/plain.
        ext = path.suffix.lower()
        name = path.name.lower()
        if ext in self._TEXT_EXTENSIONS or name in self._TEXT_EXTENSIONS or not ext:
            return "text/plain"

        return None

    def _build_file_part(self, path: str) -> dict | None:
        """Read file, base64-encode, return inline data part for Gemini.
        Returns None if the file type isn't supported by the Live API."""
        try:
            p = Path(path)
            if not p.exists() or not p.is_file():
                return None
            mime = self._resolve_mime(p)
            if mime is None:
                print(f"[FRIDAY] ⚠️ Skipping unsupported file type: {p.name}")
                return None
            data = base64.b64encode(p.read_bytes()).decode()
            return {"inline_data": {"mime_type": mime, "data": data}}
        except Exception as e:
            print(f"[FRIDAY] ⚠️ File read failed: {e}")
            return None

    def send_text_with_file(self, text: str, file_path: str):
        """Send text + a single file's contents to the session."""
        self.send_text_with_files(text, [file_path])

    def send_text_with_files(self, text: str, file_paths: list[str]):
        """Send text + one or more files' contents to the session.
        Files with unsupported MIME types are skipped (noted in the text)
        rather than sent, since they would close the Live API connection."""
        if not self._loop or not self.session:
            return
        skipped = []
        parts = []
        for file_path in file_paths:
            file_part = self._build_file_part(file_path)
            if file_part:
                parts.append(file_part)
            else:
                skipped.append(Path(file_path).name)

        full_text = text
        if skipped:
            names = ", ".join(f"'{n}'" for n in skipped)
            full_text += f"\n[Note: could not attach {names} — unsupported file type for direct upload.]"

        parts.insert(0, {"text": full_text})
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": parts},
                turn_complete=True,
            ),
            self._loop,
        )

    def _ui_safe(self, fn, *args):
        """Call a UI method only if the Qt object is still alive."""
        try:
            fn(*args)
        except RuntimeError:
            pass  # Qt C++ object already deleted

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        self._ui_safe(self.ui.set_state, "SPEAKING" if value else "LISTENING")

    # FIX: speak() was re-routing to session.send_client_content which caused
    # audio echo when used for narrating tool results mid-conversation.
    # Kept as a no-op stub for that purpose. The startup greeting uses
    # send_text() directly (see run()), which is safe because it happens
    # once, before any user audio is flowing.
    def speak(self, text: str):
        """No-op stub — Live API speaks via audio pipeline automatically."""
        pass

    def _mic_blocked(self) -> bool:
        """True when mic input should be suppressed."""
        with self._speaking_lock:
            return self._is_speaking or self._is_executing

    def _build_config(self) -> types.LiveConnectConfig:
        memory  = load_memory()
        mem_str = format_memory_for_prompt(memory)
        prompt  = _load_system_prompt()
        now     = datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = f"[CURRENT DATE & TIME]\nRight now it is: {now}\n\n"

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[FRIDAY] 🔧 {name} {args}")
        self._ui_safe(self.ui.set_state, "THINKING")
        self._is_executing = True
        try:
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: _call_tool(name, args))
        finally:
            self._is_executing = False
        self._ui_safe(self.ui.set_state, "LISTENING")
        print(f"[FRIDAY] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result},
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[FRIDAY] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if not self._mic_blocked() and not getattr(self.ui, "muted", False):
                try:
                    loop.call_soon_threadsafe(
                        self.out_queue.put_nowait,
                        {"data": indata.tobytes(), "mime_type": "audio/pcm"},
                    )
                except asyncio.QueueFull:
                    pass

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[FRIDAY] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[FRIDAY] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[FRIDAY] 👂 Recv started")
        in_buf, out_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self._ui_safe(self.ui.append_log, "YOU", full_in)
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self._ui_safe(self.ui.append_log, "FRIDAY", full_out)
                            out_buf = []

                    if response.tool_call:
                        responses = []
                        for fc in response.tool_call.function_calls:
                            fr = await self._execute_tool(fc)
                            responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=responses
                        )

        except Exception as e:
            print(f"[FRIDAY] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[FRIDAY] 🔊 Play started")
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                try:
                    await asyncio.to_thread(stream.write, chunk)
                except RuntimeError:
                    # Executor shutting down — exit play loop quietly
                    break
        except Exception as e:
            print(f"[FRIDAY] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def _watch_shutdown(self):
        """Polls the shutdown event and exits cleanly."""
        while True:
            await asyncio.sleep(0.5)
            if _shutdown_event.is_set():
                import os as _os
                _os._exit(0)
                return

    async def run(self):
        key = get_api_key()
        if not key:
            self._ui_safe(self.ui.append_log, "FRIDAY", "No API key set. Open Settings and add your Gemini key.")
            return

        client = genai.Client(
            api_key=key,
            http_options={"api_version": "v1beta"},
        )

        while not _shutdown_event.is_set():
            try:
                print("[FRIDAY] 🔌 Connecting to Live API...")
                self._ui_safe(self.ui.set_state, "THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self._loop            = asyncio.get_event_loop()
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=100)
                    self._turn_done_event = asyncio.Event()

                    print("[FRIDAY] ✅ Connected.")
                    self._ui_safe(self.ui.set_state, "LISTENING")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._watch_shutdown())

                    # Greet the user out loud on connect/reconnect. Sent as a
                    # client turn so Gemini generates audio for it; the
                    # instruction itself isn't shown in the log (only the
                    # spoken reply, captured via output_audio_transcription).
                    await session.send_client_content(
                        turns={"parts": [{"text":
                            "[SYSTEM] You just came online. Greet the user "
                            "briefly and naturally, in character — keep it short."
                        }]},
                        turn_complete=True,
                    )

            except SystemExit:
                print("[FRIDAY] 👋 Graceful shutdown.")
                import os; os._exit(0)
            except Exception as e:
                if _shutdown_event.is_set():
                    import os; os._exit(0)
                print(f"[FRIDAY] ❌ Session error: {e}")
                traceback.print_exc()
                self._ui_safe(self.ui.set_state, "THINKING")
                await asyncio.sleep(3)
                print("[FRIDAY] 🔄 Reconnecting...")


def start_live_agent(ui):
    global _live_ui_ref
    _live_ui_ref = ui

    from agent.task_queue import get_queue
    get_queue()  # initialises and starts the daemon worker

    agent = FridayLive(ui)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(agent.run())

    t = threading.Thread(target=_run, daemon=True, name="FRIDAY-Live")
    t.start()
    return agent