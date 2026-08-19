# ClassTrack YRL — 商家激活工具（手机版）

移动版 PWA（Progressive Web App），替代原 PC 版的 `merchant_tool.py`（Tkinter GUI）。

## 功能

- 📥 接收用户机器指纹（Base64）
- 🔐 使用 RSA 私钥签名生成激活密钥
- 📋 一键复制 / 📤 分享发送给用户
- 📱 支持安装到手机主屏幕，像原生 App 一样使用
- 🌓 自动适配深色/浅色模式

## 与 PC 版的对应关系

| PC 版 (Python) | 手机版 (JavaScript) |
|---|---|
| `cryptography` 库 RSA 签名 | Web Crypto API (`crypto.subtle.sign`) |
| `base64.urlsafe_b64encode` | `base64UrlEncode()` |
| `base64.urlsafe_b64decode` | `base64UrlDecode()` |
| `hashlib.sha256` | `crypto.subtle.digest("SHA-256")` |
| Tkinter GUI | HTML5 + CSS3 响应式 |
| 文件保存 `.dat` | 剪贴板 + 系统分享 |

**生成的激活密钥格式完全兼容**，可以互相通用。

## 部署方式

### 方式 A：本地打开（最简单）
直接将 `index.html` 用浏览器打开即可使用。

> ⚠️ 部分浏览器在 `file://` 协议下会禁用 Web Crypto API。
> 推荐使用方式 B 或 C。

### 方式 B：本地 HTTP 服务器
```bash
cd mobile/
python -m http.server 8080
```
然后用手机浏览器访问 `http://<电脑IP>:8080`

### 方式 C：部署到服务器
将整个 `mobile/` 目录上传到任意静态文件服务器（Nginx、GitHub Pages、Vercel 等）。

### 安装到手机主屏幕（PWA）
1. 用手机浏览器打开页面
2. Chrome: 菜单 → "添加到主屏幕"
3. Safari: 分享按钮 → "添加到主屏幕"
4. 之后可以像原生 App 一样离线使用

## 文件结构

```
mobile/
├── index.html       # 主应用（单文件，离线可用）
├── manifest.json    # PWA 配置
├── sw.js            # Service Worker（离线缓存）
├── favicon.ico      # 浏览器图标
├── icon-192.png     # PWA 图标 (192×192)
├── icon-512.png     # PWA 图标 (512×512)
└── README.md
```

## 安全说明

⚠️ **私钥安全**：
- 私钥存储在浏览器的 `localStorage` 中
- 不会上传到任何服务器
- 清除浏览器数据会同时清除私钥
- 建议仅在受信任的私人设备上使用
- 原 PC 版的安全警告同样适用于此移动版

## 技术栈

- 纯 HTML/CSS/JavaScript，无框架依赖
- Web Crypto API (RSASSA-PKCS1-v1_5 + SHA-256)
- PWA (Service Worker + Web App Manifest)
- 响应式设计，适配 320px–480px 手机屏幕
