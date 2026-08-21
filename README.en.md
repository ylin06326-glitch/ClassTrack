# ClassTrack - Class Assignment & Group Management System

> English | [中文](./README.md)

> A lightweight classroom management tool for K-12 teachers, featuring student import, drag-and-drop grouping, assignment grading, report export, and an AI assistant. Built with Apple-style Liquid Glass design for a fluid, delightful experience.

---

## ✨ Latest Features v2.2

### 🍎 Apple-Style Liquid Glass UI
- Real liquid glass effects using the open-source `@sapryniukt/vue-liquid-glass` library
- Buttons, tab bars, and segmented controls all feature liquid glass material
- Light refraction, dispersion, specular highlights, and spring deformation
- Settings page allows free adjustment of glass intensity, blur, refractive index, and highlights

### 🎨 Dynamic Wallpaper System
- 7 preset wallpapers: Morandi Breathing, Apple Sunset, Apple Aurora, Apple Ocean, Apple Mountain, Pure Black
- 3 preset dynamic video wallpapers: Ocean, Sunset, Aurora
- Custom image wallpaper upload support
- Custom video wallpaper upload support
- Wallpaper settings auto-save and persist across sessions

### 🔊 Sound & Haptic Feedback
- 8 sound effects generated via Web Audio API (no audio files needed)
- Sounds for button clicks, tab switches, slider movement, and dialog open/close
- Mobile haptic vibration feedback
- Configurable sound toggle

### 🎯 Fluid Interaction Animations
- Based on Apple WWDC "Designing Fluid Interfaces" design principles
- Spring animation utilities (interruptible, velocity handoff, momentum projection)
- Optimized slider drag physics (deformation, stretch, rubber-band boundaries)
- Dialog animation lifecycle management

### ♿ Complete Accessibility Support
- `prefers-reduced-motion`: reduced motion preference
- `prefers-reduced-transparency`: reduced transparency preference
- `prefers-contrast`: high contrast preference
- Keyboard navigation focus visibility
- Screen reader friendly

---

## 🎬 Demo Video

| Platform | Link |
|----------|------|
| 🇨🇳 **Bilibili** | [ClassTrack - Assignment Tracking Tool for Teachers](https://www.bilibili.com/video/BV1Hqgv6cExM) |
| 🌍 **YouTube** | Coming Soon |

> Video covers the full workflow: Student Import → Drag-and-Drop Grouping → Assignment Grading → Report Export → AI Assistant

---

## 🖼️ Screenshots

### Core Features

| Grouping | Assignment Grading |
|----------|-------------------|
| ![Grouping](docs/images/01-grouping.png) | ![Assignment](docs/images/02-assignment.png) |

| AI Assistant | Mobile QR Check-in |
|-------------|-------------------|
| ![AI Assistant](docs/images/05-ai-assistant.png) | ![Mobile QR](docs/images/04-mobile-qr.png) |

### More Features

| Webcam QR Scanner | Reminder Notification | AI Comment Generation |
|-------------------|----------------------|----------------------|
| ![QR Scanner](docs/images/03-qr-scanner.png) | ![Reminder](docs/images/06-reminder.png) | ![AI Comment](docs/images/07-ai-comment.png) |

> 💡 Screenshots show the latest Liquid Glass UI. If you see the old version, please refresh your cache.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [License](#license)
- [Contact](#contact)

---

## Features

### Core Features

| Module | Description |
|--------|-------------|
| 👥 **Multi-class Management** | Create, switch, and delete classes with isolated data |
| 📥 **Student Import** | Excel (.xls/.xlsx) and plain text import with auto ID detection |
| 🖱️ **Drag-and-Drop Grouping** | Flexible grouping, locking, drag-to-rearrange, color themes |
| 📝 **Assignment Grading** | A/B/C/Leave/Missing five-level grading, batch operations, date navigation |
| 📊 **Report Export** | Individual student ledger and class summary Excel export |
| 📈 **Data Dashboard** | Stat cards, pie charts, bar charts, line charts, trend analysis |
| 🏆 **Group Leaderboard** | Ranked by A-rate, submission rate, and average score |
| ⚠️ **Student Alerts** | Smart alerts for consecutive missing assignments and A-rate drops |
| 📱 **QR Check-in** | Webcam + mobile phone integration, QR code generation and printing |
| 🔒 **Privacy Protection** | Partitioned display mode for names and student IDs |

### AI Assistant (v2.0)

- 🤖 **AI Chat**: Keyword intent recognition + LLM data-driven Q&A with ECharts visualization
- 📝 **AI Comment Generation**: Personalized student comments based on the last 30 days of data
- 🧠 **AI Smart Grouping**: Snake-shaped balanced allocation algorithm based on assignment performance
- 🔔 **Smart Alert Banner**: Real-time alerts for consecutive missing assignments / A-rate drops on the homepage
- ⚙️ **Multi-provider Support**: DeepSeek / OpenAI / Tongyi Qianwen / Custom

### v2.1 New Features

- 🍎 **Apple Design Interface**: Fluid interaction animations (draggable sliders + momentum prediction + rubber-band boundaries), translucent material hierarchy, top edge highlights, system font typography
- 👋 **Onboarding Guide**: 8-step guide auto-pops up on first use, covering all core features
- 🖨️ **QR Code Printing**: Batch print student QR codes with A4 layout support
- 📱 **Mobile QR Check-in**: Standalone /mobile page for mobile browser direct assignment check-in
- ❤️ **Donation Support**: Donation button in navigation bar with WeChat payment QR code dialog
- ⚡ **Performance Optimization**: Synchronous routing replaces async blocking, resolving lag issues
- ♿ **Accessibility Support**: Reduced Motion / Reduced Transparency / High Contrast

### v2.2 New Features

- 🔮 **Liquid Glass UI**: Site-wide buttons, tabs, and segmented controls feature liquid glass material with light refraction and dispersion
- 🎨 **Dynamic Wallpaper System**: 7 gradient wallpapers + 3 video wallpapers + custom image/video upload
- 🔊 **Sound Feedback System**: 8 Web Audio generated sound effects + mobile haptic feedback
- 🎯 **Spring Animation Utilities**: Interruptible spring physics, velocity handoff, momentum projection, rubber-band boundaries
- ♿ **Complete Accessibility**: Full support for reduced-motion / reduced-transparency / prefers-contrast
- ✍️ **Typography Optimization**: Apple-style font optical sizing (negative tracking for headings, relaxed line-height for body)
- ⚡ **GPU Performance Optimization**: Hardware-accelerated compositing for animated elements, reduced repaints

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / FastAPI / Uvicorn |
| Frontend | Vue 3.5 + TypeScript + Vite + Pinia + Element Plus |
| Liquid Glass | `@sapryniukt/vue-liquid-glass` (GPL-3.0) |
| Charts | ECharts 5 |
| Database | SQLite (local file database) |
| Packaging | PyInstaller (Windows single-file exe) |
| AI | OpenAI-compatible API (DeepSeek / OpenAI / Tongyi Qianwen) |
| Others | qrcode / pandas / openpyxl / html5-qrcode |

---

## Quick Start

### Requirements

- Windows 10/11
- Python 3.8 or above
- Chrome / Edge / Firefox browser (with backdrop-filter support)

### Installation & Run

```bash
# 1. Clone the repository
git clone https://github.com/ylin06326-glitch/ClassTrack.git
cd ClassTrack

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Install frontend dependencies (optional, for modifying frontend)
cd frontend
npm install
cd ..

# 4. Start (default HTTPS 5088)
python backend/run.py

# Or HTTP debug mode
python backend/run.py --http --port 5099
```

The browser will automatically open `https://localhost:5088` after startup.

> **Mobile QR Check-in**: Ensure your phone and computer are on the same LAN, then visit `https://<computer-ip>:5088/mobile`

### Frontend Development

```bash
cd frontend
npm run dev      # Development mode
npm run build    # Build production version to dist/
```

### Package as exe

```bash
pyinstaller ClassTrack.spec
```

The packaged executable will be in the `dist/` directory.

---

## Project Structure

```
ClassTrack/
├── backend/                  # FastAPI backend
│   ├── run.py               # Development entry point
│   ├── requirements.txt     # Python dependencies
│   └── app/
│       ├── main.py          # FastAPI app + route registration
│       ├── config.py        # Configuration and path management
│       ├── database.py      # SQLite database
│       ├── deps.py          # Dependency injection
│       ├── routers/         # API routes (11 modules)
│       ├── services/        # Business services (AI/reports/TLS)
│       └── activation/      # Activation and authorization
├── frontend/                 # Vue 3 + TypeScript frontend
│   ├── src/
│   │   ├── components/      # Components (GlassButton/GlassDialog/GlassSegmented etc.)
│   │   ├── composables/     # Composables (useSpringAnimation/useSound)
│   │   ├── stores/          # Pinia stores (app/glass/wallpaper)
│   │   ├── views/           # Views (MainLayout + 7 tabs)
│   │   ├── liquid-glass-core.css  # Liquid glass core styles
│   │   └── style.css        # Global styles
│   └── dist/                # Build output (served by backend)
├── launcher.py               # Packaged version entry point
├── launcher_nolock.py        # No-lock version entry point
├── ClassTrack.spec           # PyInstaller packaging config
├── ClassTrack_nolock.spec    # No-lock packaging config
├── build.bat                 # Packaging script
├── 启动ClassTrack.bat         # Windows quick launch
├── static/                   # Legacy static assets (CSS/JS/images)
├── templates/                # Legacy HTML templates
├── docs/images/              # Software screenshots
├── data/                     # Database files (generated at runtime)
├── LICENSE                   # License agreement
├── README.md                 # Chinese documentation
└── README.en.md              # English documentation
```

---

## License

This project uses a **Source-Available License**:

| Use Case | Allowed |
|----------|---------|
| ✅ Personal learning, research | Free |
| ✅ Non-profit use by educational institutions | Free |
| ✅ Open-source community contribution and testing | Free |
| ❌ Any commercial use | **Must contact author for authorization in advance** |

> Commercial use includes but is not limited to: integrating this software into commercial products, using it for commercial services, using it as an internal business tool, selling copies or derivative works, etc.

See the [LICENSE](./LICENSE) file for details.

> ⚠️ The liquid glass library `@sapryniukt/vue-liquid-glass` is licensed under GPL-3.0. Using this project requires compliance with its license terms.

---

## Support the Author 💖

If ClassTrack has helped you, feel free to buy the author a coffee! Your support is my motivation to keep updating.

| WeChat Pay |
|:---:|
| ![WeChat Pay](./docs/images/wechat-donate.png) |

> 💡 Want to leave your name? Feel free to leave a message in [GitHub Issues](https://github.com/ylin06326-glitch/ClassTrack/issues), or let me know via email!

---

## Contact

- **Author**: Yang Runlin (YRL)
- 📧 **Email**: [ylin06326@gmail.com](mailto:ylin06326@gmail.com) / [yrl666hello@qq.com](mailto:yrl666hello@qq.com)
- **Commercial Licensing / Collaboration**: Welcome to contact via email or GitHub Issues
- **Bug Reports**: Welcome to submit an Issue

---

*ClassTrack - Making assignment management simple and delightful 🎒*
