# FRIDAY

**F**riendly **R**apid **I**ntelligence **D**igital **A**utonomous **Y**ielder

A locally-run, voice-first AI assistant for Windows, built with **PyQt6** and **Google Gemini 2.5 Flash (Live API)**. FRIDAY speaks with a real, human-quality voice — not robotic TTS — and can see your screen, control your computer, browse the web, manage files, and autonomously plan and execute multi-step tasks.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)
![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash%20Live-orange)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## ✨ Features

| Category | Capability |
|---|---|
| 🧠 **AI Brain** | Google Gemini 2.5 Flash Native Audio via the Live API — real-time, full-duplex conversation |
| 🎤 **Voice I/O** | Continuous mic listening + natural Gemini-generated voice output (no Windows SAPI/TTS) |
| 🎨 **UI** | Custom dark, cyan-accented PyQt6 interface with an animated reactive orb, live system metrics, and a typewriter-style conversation log |
| 🤖 **Agentic Core** | A planner → executor → error-handler pipeline that breaks down complex goals into steps, runs them, and self-corrects on failure |
| 📋 **Task Queue** | Background task queue with pending/running/completed/failed/cancelled state tracking |
| 👁️ **Screen & Webcam Awareness** | Captures the screen or webcam and sends it to Gemini for visual analysis |
| 🖱️ **Computer Control** | Mouse, keyboard, clipboard, window/process management, and system settings control |
| 🌐 **Browser Control** | Automated browsing via Playwright |
| 🔍 **Web Search** | DuckDuckGo-based search with full page fetching |
| 📁 **File Management** | Read, write, copy, move, delete, search, and drag-and-drop file handling, plus a universal multi-format file processor |
| 🛠️ **Dev Agent** | Generates, runs, and iteratively debugs code projects (up to 5 self-fix attempts) in a sandboxed project folder |
| 🕹️ **Game Updater** | Looks up and launches Steam app updates for known games |
| ✈️ **Flight Finder / 🌦️ Weather / 📨 Messaging / ⏰ Reminders** | Assorted everyday-utility actions |
| 💾 **Persistent Memory** | Long-term local memory (`memory/long_term.json`) that persists context across sessions |
| 🔒 **Privacy-first** | All memory and config stay on your machine; only audio/text you send goes to Google's Gemini API |

---

## 🏗️ Architecture

```
                ┌────────────────────┐
                │       ui.py         │  PyQt6 glassmorphism UI
                │  (orb, log, stats)  │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │  agent/live_agent.py │  Gemini Live API session
                └──────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐ ┌────────────────┐ ┌──────────────────┐
│ agent/planner  │ │ agent/executor  │ │ agent/error_handler│
│  (breaks goal  │ │ (runs steps,    │ │ (diagnoses failures,│
│   into steps)  │ │  calls tools)   │ │  proposes/applies fixes)│
└───────────────┘ └────────┬───────┘ └──────────────────┘
                           │
                ┌──────────▼──────────┐
                │   agent/task_queue   │  background execution
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │      actions/*       │  20+ tool modules
                │ (screen, files, web, │
                │  desktop, code, etc.)│
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │  memory/memory_manager│  persistent long-term memory
                └─────────────────────┘
```

FRIDAY's personality and response style are defined in [`core/prompt.txt`](FRIDAY/core/prompt.txt) — including strict rules for how it opens replies depending on whether a task succeeded, failed, or was purely informational.

---

## 🚀 Getting Started

### 1. Prerequisites
- Windows 10/11
- [Python 3.11+](https://python.org)

### 2. Install & launch
```bash
python setup.py
```
This installs all dependencies from `requirements.txt`, installs the Playwright Chromium browser, and launches FRIDAY.

### 3. Get a free Gemini API key
Grab one from [Google AI Studio](https://aistudio.google.com/apikey), then enter it in FRIDAY's in-app Settings on first launch.

> ⚠️ **Security note:** `config/api_keys.json` stores your API key in plain text and is created automatically. **Add it to `.gitignore` before pushing this repo to GitHub** so you don't leak your key.

### 4. Run manually (after first-time setup)
```bash
python main.py
```

---

## 🎙️ How It Works

FRIDAY uses the **Gemini Live API** with `response_modalities=["AUDIO"]`, meaning Gemini itself generates the voice in real time — there's no separate TTS engine in the loop for normal conversation (a local `pyttsx3` engine exists as a fallback/utility voice path).

- **Speak** — FRIDAY listens continuously through your mic
- **Type** — use the input box and hit Send or Enter
- **Mute** — toggle the 🎤 button to pause voice input
- **Watch** — the animated orb reflects FRIDAY's state (idle / listening / thinking / speaking)

For multi-step requests ("research X and write me a report," "build and fix this script"), FRIDAY's agent layer plans the steps, executes them via the relevant `actions/` module, and automatically replans if a step fails.

---

## 📂 Project Structure

```
FRIDAY/
├── main.py                    # Entry point
├── setup.py                   # Dependency install + launch
├── ui.py                      # PyQt6 UI (orb, stats, log, settings, file drop)
├── orb.html                   # Web-rendered orb assets
├── requirements.txt
├── core/
│   └── prompt.txt              # FRIDAY's personality & response rules
├── agent/
│   ├── live_agent.py           # Gemini Live API session handling
│   ├── planner.py               # Goal → step plan generation
│   ├── executor.py              # Step execution & tool dispatch
│   ├── error_handler.py         # Failure diagnosis & fix generation
│   └── task_queue.py            # Background task state management
├── actions/                    # 20+ tool modules, e.g.:
│   ├── screen_processor.py      # Screen/webcam capture + analysis
│   ├── computer_control.py      # Mouse/keyboard/window/process control
│   ├── computer_settings.py     # System settings control
│   ├── desktop.py                # Desktop interaction
│   ├── browser_control.py       # Playwright-driven browsing
│   ├── web_search.py             # DuckDuckGo search
│   ├── file_handler.py / file_controller.py / file_processor.py
│   ├── code_helper.py / dev_agent.py   # Code generation & self-debugging
│   ├── open_app.py / send_message.py / reminder.py
│   ├── weather_report.py / flight_finder.py / youtube_video.py
│   ├── game_updater.py           # Steam game update lookups
│   └── voice_engine.py           # TTS/STT fallback (pyttsx3 / SpeechRecognition)
├── memory/
│   ├── memory_manager.py
│   └── long_term.json           # Auto-created persistent memory
└── config/
    ├── __init__.py
    └── api_keys.json            # Auto-created — DO NOT COMMIT
```

---

## 🔐 Privacy

- Memory and configuration are stored **locally only**.
- Audio and text are streamed to **Google's Gemini Live API** using your own API key.
- No telemetry beyond the Gemini API calls you initiate.

---

## 🙏 Acknowledgements

FRIDAY's architecture incorporates components and UI ideas ported from the Jarvis/Mark-XXXIX reference project.

---

## 📄 License

No license file is currently included — add one (MIT, Apache-2.0, etc.) before sharing or accepting contributions.
