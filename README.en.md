# ClassTrack - Class Assignment & Group Management System

> English | [中文](./README.md)

> A lightweight classroom management tool for K-12 teachers, featuring student import, drag-and-drop grouping, assignment grading, report export, and an AI assistant.

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

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.8+ / Flask / Waitress |
| Frontend | HTML5 / CSS3 / JavaScript / ECharts / Chart.js |
| Database | SQLite (local file database) |
| Packaging | PyInstaller (Windows single-file exe) |
| AI | OpenAI-compatible API (DeepSeek / OpenAI / Tongyi Qianwen) |
| Others | qrcode / pandas / openpyxl / pywebview |

---

## Quick Start

### Requirements

- Windows 10/11
- Python 3.8 or above
- Chrome / Edge / Firefox browser

### Installation & Run

```bash
# 1. Clone the repository
git clone https://github.com/ylin06326-glitch/-AI-Class-Assignment-Group-Management-System-with-AI-Assistant-.git
cd ClassTrack

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch
python main.py
```

The browser will automatically open `https://localhost:5088`.

### Package as exe

```bash
pyinstaller ClassTrack.spec
```

The packaged output will be in the `dist/` directory.

---

## Project Structure

```
ClassTrack/
├── main.py                  # Main entry (Flask server + routes)
├── app_paths.py             # Path configuration
├── requirements.txt         # Python dependencies
├── ClassTrack.spec          # PyInstaller build config
├── build.bat                # Build script
├── 启动ClassTrack.bat        # Windows quick launcher
├── LICENSE                  # License agreement
├── README.md                # Chinese documentation
├── README.en.md             # English documentation
├── PROGRESS.md              # Development progress tracker
├── 使用说明书.md             # Detailed user manual
├── docs/images/             # Screenshots
├── backend_server/          # Backend service modules
├── static/                  # Static assets (CSS/JS/images)
├── templates/               # HTML templates
├── data/                    # Database files (generated at runtime)
├── docs/                    # Documentation
└── media/                   # Media resources
```

---

## License

This project is licensed under the **Source-Available License**:

| Use Case | Allowed |
|----------|---------|
| ✅ Personal learning and research | Free |
| ✅ Non-profit use by educational institutions | Free |
| ✅ Open-source community contribution and testing | Free |
| ❌ Any commercial use | **Must contact the author for authorization first** |

> Commercial use includes but is not limited to: integrating this software into commercial products, using it for commercial services, as an internal business tool, selling copies or derivative works, etc.

See the [LICENSE](./LICENSE) file for details.

---

## Contact

- **Author**: Yang Runlin (YRL)
- 📧 **Email**: [ylin06326@gmail.com](mailto:ylin06326@gmail.com) / [yrl666hello@qq.com](mailto:yrl666hello@qq.com)
- **Commercial licensing / collaboration**: Feel free to email or open a GitHub Issue
- **Bug reports / feedback**: Issues are welcome

---

*ClassTrack - Making assignment management simple and delightful 🎒*
