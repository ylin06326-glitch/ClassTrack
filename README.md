# ClassTrack - 班级作业分组管理系统

> [English](./README.en.md) | 中文

> 一款面向中小学教师的轻量级班级管理工具，支持学生导入、拖拽分组、作业等级登记、报表导出，以及 AI 智能助手。

---

## 🎬 演示视频

| 平台 | 链接 |
|------|------|
| 🇨🇳 **B站 (bilibili)** | [ClassTrack中小学老师登记作业神器](https://www.bilibili.com/video/BV1Hqgv6cExM) |
| 🌍 **YouTube** | 即将上线 |

> 视频涵盖：学生导入 → 拖拽分组 → 作业登记 → 报表导出 → AI 智能助手全流程演示

---

## 🖼️ 软件截图

### 核心功能

| 班级分组 | 作业登记 |
|---------|---------|
| ![班级分组](docs/images/01-grouping.png) | ![作业登记](docs/images/02-assignment.png) |

| AI 智能助手 | 手机扫码登记 |
|------------|-------------|
| ![AI助手](docs/images/05-ai-assistant.png) | ![手机扫码](docs/images/04-mobile-qr.png) |

### 更多功能

| 电脑扫码 | 催交通知 | AI 评语生成 |
|---------|---------|------------|
| ![电脑扫码](docs/images/03-qr-scanner.png) | ![催交通知](docs/images/06-reminder.png) | ![AI评语](docs/images/07-ai-comment.png) |

---

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [许可协议](#许可协议)
- [联系方式](#联系方式)

---

## 功能特性

### 核心功能

| 模块 | 说明 |
|------|------|
| 👥 **多班级管理** | 创建、切换、删除班级，独立数据隔离 |
| 📥 **学生导入** | 支持 Excel (.xls/.xlsx) 和纯文字导入，自动识别学号 |
| 🖱️ **拖拽分组** | 灵活分组、锁定、拖拽调整、颜色主题 |
| 📝 **作业登记** | A/B/C/请假/未交 五级评定，批量登记，日期导航 |
| 📊 **报表导出** | 单学生台账、全班汇总 Excel 导出 |
| 📈 **数据概览** | 统计卡片、饼图、柱状图、折线图、环比趋势 |
| 🏆 **小组排行榜** | A率排序、提交率、平均分 |
| ⚠️ **学生预警** | 连续未交、A率骤降智能预警 |
| 📱 **扫码登记** | 电脑摄像头 + 手机联动，二维码生成与打印 |
| 🔒 **隐私保护** | 姓名/学号分区显示模式 |

### AI 智能助手 (v2.0)

- 🤖 **AI 对话**：关键词意图识别 + LLM 数据驱动问答，支持 ECharts 可视化
- 📝 **AI 评语生成**：基于近30天数据生成个性化学生评语
- 🧠 **AI 智能分组**：蛇形均衡分配算法，基于作业表现自动分组
- 🔔 **智能预警横幅**：首页实时展示连续未交 / A率下降预警
- ⚙️ **多服务商支持**：DeepSeek / OpenAI / 通义千问 / 自定义

### v2.1 新特性

- 🍎 **Apple Design 界面**：流体交互动画（滑块可拖动 + 动量预测 + 橡皮筋边界）、半透明材质层级、顶部亮边、系统字体排版
- 👋 **新手引导**：首次使用自动弹出 8 步引导，覆盖全部核心功能
- 🖨️ **二维码打印**：批量打印学生二维码，支持 A4 排版
- 📱 **手机扫码端**：独立 /mobile 页面，手机浏览器直接扫码登记作业
- ❤️ **打赏支持**：导航栏打赏按钮，微信收款码弹窗
- ⚡ **性能优化**：同步路由替代异步阻塞，解决卡顿问题
- ♿ **无障碍支持**：Reduced Motion / Reduced Transparency / 高对比度

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 前端 | Vue 3 + TypeScript / HTML5 / CSS3 / JavaScript / ECharts |
| 数据 | SQLite (本地文件数据库) |
| 打包 | PyInstaller (Windows 单文件 exe) |
| AI | OpenAI 兼容 API (DeepSeek / OpenAI / 通义千问) |
| 其他 | qrcode / pandas / openpyxl / html5-qrcode |

---

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.8 或以上
- Chrome / Edge / Firefox 浏览器

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/ylin06326-glitch/ClassTrack.git
cd ClassTrack

# 2. 安装依赖
pip install -r backend/requirements.txt

# 3. 启动（默认 HTTPS 5088）
python backend/run.py

# 或 HTTP 调试模式
python backend/run.py --http --port 5099
```

启动后浏览器将自动打开 `https://localhost:5088`。

> **手机扫码登记**：确保手机和电脑在同一局域网，访问 `https://<电脑IP>:5088/mobile`

### 打包为 exe

```bash
pyinstaller ClassTrack.spec
```

打包产物在 `dist/` 目录下。

---

## 项目结构

```
ClassTrack/
├── backend/                  # FastAPI 后端
│   ├── run.py               # 开发启动入口
│   ├── requirements.txt     # Python 依赖
│   └── app/
│       ├── main.py          # FastAPI 应用 + 路由注册
│       ├── config.py        # 配置与路径管理
│       ├── database.py      # SQLite 数据库
│       ├── deps.py          # 依赖注入
│       ├── routers/         # API 路由 (11个模块)
│       ├── services/        # 业务服务 (AI/报表/TLS)
│       └── activation/      # 激活与授权
├── frontend/                 # Vue 3 + TypeScript 前端
│   ├── src/                 # 源代码
│   └── dist/                # 构建产物 (后端托管)
├── launcher.py               # 打包版启动入口
├── launcher_nolock.py        # 无锁版启动入口
├── ClassTrack.spec           # PyInstaller 打包配置
├── ClassTrack_nolock.spec    # 无锁版打包配置
├── build.bat                 # 打包脚本
├── 启动ClassTrack.bat         # Windows 快捷启动
├── static/                   # 老版静态资源 (CSS/JS/图片)
├── templates/                # 老版 HTML 模板
├── docs/images/              # 软件截图
├── data/                     # 数据库文件 (运行时生成)
├── LICENSE                   # 许可协议
├── README.md                 # 中文说明
└── README.en.md              # 英文说明
```

---

## 许可协议

本项目采用 **源码可用许可证（Source-Available License）**：

| 用途 | 是否允许 |
|------|----------|
| ✅ 个人学习、研究 | 免费 |
| ✅ 教育机构非盈利使用 | 免费 |
| ✅ 开源社区贡献与测试 | 免费 |
| ❌ 任何商业用途 | **必须事先联系作者获得授权** |

> 商业用途包括但不限于：将本软件集成到商业产品、用于商业服务、作为内部商业工具、销售副本或衍生作品等。

详见 [LICENSE](./LICENSE) 文件。

---

---

## 支持作者 💖

如果 ClassTrack 对你有帮助，欢迎请作者喝杯咖啡！你的支持是我持续更新的动力。

| 微信支付 |
|:---:|
| ![微信支付](./docs/images/wechat-donate.png) |

> 💡 想留下名字？欢迎在 [GitHub Issues](https://github.com/ylin06326-glitch/ClassTrack/issues) 留言，或通过邮箱告诉我！

---

## 联系方式

- **作者**：杨润林 (YRL)
- 📧 **邮箱**：[ylin06326@gmail.com](mailto:ylin06326@gmail.com) / [yrl666hello@qq.com](mailto:yrl666hello@qq.com)
- **商业授权 / 合作**：欢迎邮件联系或 GitHub Issues
- **问题反馈**：欢迎提交 Issue

---

*ClassTrack - 让作业管理变得简单可爱 🎒*
