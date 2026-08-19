# ClassTrack Hardened — 安全加固文档

## 一、原版逆向漏洞清单与修复

### 漏洞 1：明文数据库
| 项目 | 详情 |
|------|------|
| **原始状态** | SQLite 数据库 `data/classtrack.db` 明文存储于 exe 同级目录 |
| **风险** | 任意用户可用 DB Browser for SQLite 直接查看所有学生、分组、作业数据 |
| **修复** | 替换为 pysqlcipher3（SQLCipher），AES-256-CBC 加密，密钥分3段分散存储 |

### 漏洞 2：明文源码
| 项目 | 详情 |
|------|------|
| **原始状态** | Python 源码直接可见，包含完整业务逻辑、数据库路径、密钥、端口号 |
| **风险** | 反编译工具可直接提取所有源代码，修改后重新打包 |
| **修复** | PyArmor 字节码加密 + PyInstaller --key 加密 + XOR 字符串加密三层保护 |

### 漏洞 3：前端资源明文落盘
| 项目 | 详情 |
|------|------|
| **原始状态** | `templates/` 和 `static/` 文件夹包含完整 HTML/JS/CSS，明文暴露 |
| **风险** | JS 中 API 路由地址、业务逻辑完全可见；攻击者可分析接口调用链 |
| **修复** | Fernet 对称加密后嵌入 Python 代码为二进制 blob，仅运行时内存解密 |

### 漏洞 4：打印日志泄露
| 项目 | 详情 |
|------|------|
| **原始状态** | `print()` 输出数据库路径、端口号、IP 地址、激活状态 |
| **风险** | 控制台输出直接暴露内部路径结构 |
| **修复** | 删除所有 print 语句，异常堆栈统一返回 "Internal server error" |

### 漏洞 5：数据库路径可预测
| 项目 | 详情 |
|------|------|
| **原始状态** | `data/classtrack.db` — 路径固定、名称固定、扩展名固定 |
| **风险** | 任意知道路径的人可直接复制数据库文件，SQLCipher 可暴力破解 |
| **修复** | 路径迁移至 `%LOCALAPPDATA%\ClassTrack_v2\storage.dat`，隐藏目录 + 随机扩展名 |

### 漏洞 6：API 无鉴权
| 项目 | 详情 |
|------|------|
| **原始状态** | 所有 API 接口直接可访问，无任何 Token/Key 校验 |
| **风险** | 局域网内任意设备可直接调用 `/api/shutdown` 关闭服务、`/api/students/clear` 清空数据 |
| **修复** | 本地内置 Token 鉴权（SHA256 生成），高危接口（删除/清空/关闭）强制校验 |

### 漏洞 7：无反逆向保护
| 项目 | 详情 |
|------|------|
| **原始状态** | 无任何反调试、反虚拟机检测 |
| **风险** | x64dbg/IDA/OllyDbg 可直接附加调试，VMware 中可完整分析 |
| **修复** | 启动时检测调试器进程/VM 特征，检测到静默退出（仅运行一次） |

### 漏洞 8：无完整性校验
| 项目 | 详情 |
|------|------|
| **原始状态** | 数据库文件可被任意修改，程序无感知 |
| **风险** | 篡改数据库内容（修改成绩、删除记录）不会被发现 |
| **修复** | 启动时校验数据库文件 SHA256 哈希，不一致则拒绝运行 |

### 漏洞 9：字符串常量明文
| 项目 | 详情 |
|------|------|
| **原始状态** | 代码中所有字符串明文可读（表名、列名、中文提示、端口号、路径） |
| **风险** | strings 命令即可提取全部敏感信息 |
| **修复** | XOR 三密钥分段加密，运行时动态解密，strings 提取无效 |

### 漏洞 10：SSL 证书私钥明文
| 项目 | 详情 |
|------|------|
| **原始状态** | CA 私钥和服务器私钥以 PEM 文件明文存储 |
| **风险** | 私钥泄露可被用于中间人攻击 |
| **修复** | 证书和私钥存储于加密 AppData 目录，文件权限限制 |

---

## 二、加固版本防护层次总览

```
┌─────────────────────────────────────────────────────┐
│  用户运行 ClassTrack.exe                             │
├─────────────────────────────────────────────────────┤
│  Layer 1: 反逆向检测                                  │
│  ├── IsDebuggerPresent() 检测                        │
│  ├── CheckRemoteDebuggerPresent() 检测              │
│  ├── 进程黑名单扫描 (x64dbg/IDA/OllyDbg 等 50+)      │
│  ├── VM 硬件特征检测 (VMware/VirtualBox/QEMU 等)      │
│  └── 检测到 → 静默 _exit(0)，不弹窗不打印            │
├─────────────────────────────────────────────────────┤
│  Layer 2: PyInstaller --key 加密                      │
│  ├── 单文件 exe，字节码 AES-256 加密                   │
│  └── 无控制台窗口 (windowed mode)                    │
├─────────────────────────────────────────────────────┤
│  Layer 3: PyArmor 字节码混淆                          │
│  ├── 代码混淆 (obf-code=2)                           │
│  ├── 字符串混淆 (mix-str)                             │
│  ├── 模块保护 (obf-module=1)                         │
│  └── 反篡改检测                                       │
├─────────────────────────────────────────────────────┤
│  Layer 4: XOR 字符串加密 (3密钥分段)                    │
│  ├── 敏感字符串 (100+) 静态加密存储                     │
│  ├── 运行时 _sx() 解密 → 用完即焚                      │
│  └── 3个16字节密钥分散嵌入代码                          │
├─────────────────────────────────────────────────────┤
│  Layer 5: SQLCipher 加密数据库                         │
│  ├── AES-256-CBC, PBKDF2-HMAC-SHA512 (256k 迭代)     │
│  ├── 密钥分3段: 代码 + 用户路径 + 计算值               │
│  ├── 存储于 %LOCALAPPDATA%\ClassTrack_v2\storage.dat  │
│  └── 启动时 SHA256 完整性校验                          │
├─────────────────────────────────────────────────────┤
│  Layer 6: Fernet 加密前端资源                          │
│  ├── HTML/CSS/JS → Fernet AES-128-CBC → Base64 → 嵌入代码│
│  ├── 仅运行时内存解密，永不落盘                          │
│  ├── 解密后 LRU 缓存，避免重复解密                       │
│  └── render_template_string 内存渲染                   │
├─────────────────────────────────────────────────────┤
│  Layer 7: API Token 鉴权                              │
│  ├── SHA256(DBPath + PID + Secret) → 32-char Token    │
│  ├── 高危接口: @_ca 装饰器强制校验                      │
│  │   ├── DELETE /api/classes/<id>                     │
│  │   ├── DELETE /api/students/clear                   │
│  │   ├── POST  /api/groups/reset                      │
│  │   ├── POST  /api/shutdown                          │
│  │   └── DELETE /api/homework-types/<id>              │
│  └── Token 通过 Header X-CT-Auth 或 Query _token 传递│
├─────────────────────────────────────────────────────┤
│  Layer 8: 异常屏蔽                                     │
│  ├── @app.errorhandler(Exception) → 固定错误响应       │
│  └── 永不返回 Python traceback 到前端                  │
└─────────────────────────────────────────────────────┘
```

---

## 三、构建与打包流程

### 前置要求
- Windows 10/11 x64
- Python 3.10+ (with pip)
- Visual C++ Build Tools (for pysqlcipher3)
- OpenSSL (for SQLCipher)

### 步骤

```batch
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行构建脚本 (加密资源 + 生成加固核心)
python build.py

# 3. PyArmor 字节码加密 (可选但推荐)
pyarmor gen --platform windows.x86_64 --obf-code 2 --mix-str --private class_track_core.py
# 输出: dist/class_track_core.py

# 4. PyInstaller 打包
pyinstaller --clean --onefile --windowed ^
    --name="ClassTrack" ^
    --key="自定义加密密钥" ^
    --hidden-import=flask --hidden-import=cryptography ^
    --hidden-import=pandas --hidden-import=qrcode ^
    class_track_core.py

# 或直接运行一键构建脚本
build.bat
```

### 输出
- `dist/ClassTrack.exe` — 单文件可执行程序
- 用户运行后数据存储: `%LOCALAPPDATA%\ClassTrack_v2\`
  - `storage.dat` — 加密数据库
  - `storage.dat.hash` — 完整性校验文件
  - `cert.pem` / `key.pem` — HTTPS 证书
  - `ca-cert.pem` / `ca-key.pem` — CA 根证书

---

## 四、加固配置参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| SQLCipher KDF 迭代 | 256,000 | 防暴力破解, 越高越安全 (越高启动越慢) |
| SQLCipher 页大小 | 4096 | 数据库页大小 |
| Fernet 算法 | AES-128-CBC + HMAC-SHA256 | 资源加密 |
| XOR 密钥数 | 3 × 16 字节 | 字符串分段加密 |
| 反调试进程黑名单 | 50+ | 覆盖主流调试/逆向工具 |
| WAL 模式 | 开启 | 数据库并发性能 |
| 内存缓存 | LRU | 解密资源缓存 |

---

## 五、可选增强方案

### 5.1 硬件机器绑定授权
```
当前: 激活模块基于硬件指纹 (CPU + 磁盘序列号 → SHA256)
增强: 使用 TPM 芯片 + Secure Boot 状态 + 主板序列号多因素绑定
实现: Windows TPM API (NCrypt) → 私钥不可导出 → 硬件级反克隆
```

### 5.2 EXE 加壳
```
推荐工具:
- VMProtect (商业): 虚拟化关键函数、反调试、内存保护
- Themida (商业): 多层加密、代码变形、反篡改
- UPX (开源): 基础压缩 (已被多数杀软识别)

使用教程 (以 VMProtect 为例):
1. 打开 VMProtect, File → Open → 选择 ClassTrack.exe
2. 在 Functions 列表中选择核心函数 (数据库操作/加密解密)
3. 右键 → Add to Virtualization (虚拟化保护)
4. Options → Memory Protection → Enable
5. Project → Compile → 输出 protected 版本
```

### 5.3 C 扩展高性能加固
```python
# 将核心加密/解密逻辑编译为 C 扩展 (.pyd)
# setup.py
from Cython.Build import cythonize
from setuptools import setup, Extension

# 关键函数: verify_hash, decrypt_resource, check_token
ext = Extension(
    "ct_security",
    sources=["ct_security.pyx"],
    extra_compile_args=["/O2", "/GL"],  # 全优化
)
setup(ext_modules=cythonize(ext, language_level=3))

# 编译: python setup.py build_ext --inplace
# 输出: ct_security.cp310-win_amd64.pyd (难以反编译的原生代码)
```

---

## 六、安全检查清单

- [ ] `sys.dont_write_bytecode = True` — 禁用 pyc 缓存
- [ ] `IsDebuggerPresent()` + `CheckRemoteDebuggerPresent()` — 反调试
- [ ] 进程黑名单 50+ 项覆盖 — 反逆向工具
- [ ] VM 硬件特征检测 — 反虚拟机
- [ ] 所有 print 已删除 — 无信息泄露
- [ ] 所有注释/文档字符串已删除 — 无辅助信息
- [ ] 敏感字符串 XOR 加密 — 静态分析无效
- [ ] 数据库 SQLCipher AES-256 — 数据加密
- [ ] 数据库路径迁移至 AppData — 隐藏存储
- [ ] 数据库哈希校验 — 防篡改
- [ ] 前端资源 Fernet 加密嵌入 — 不落盘
- [ ] 前端资源内存缓存 — 性能优化
- [ ] API Token 鉴权 — 高危接口保护
- [ ] 异常堆栈屏蔽 — 无错误信息泄露
- [ ] 数据库密钥分3段 — 无全局明文密钥
- [ ] PyInstaller --key 加密 — 打包加密
- [ ] PyArmor 字节码混淆 — 代码保护
- [ ] WAL 模式 — 数据库性能

---

## 七、版本对比

| 特性 | 原版 v1.5 | 加固版 v2.0 |
|------|----------|------------|
| 数据库 | SQLite 明文 | SQLCipher AES-256 加密 |
| 存储位置 | exe 同级 data/ | %LOCALAPPDATA%\ClassTrack_v2\ |
| 文件扩展名 | .db | .dat (隐藏) |
| 数据库完整性 | 无 | SHA256 哈希校验 |
| 源码保护 | 无 | PyArmor + PyInstaller --key + XOR 字符串 |
| 前端资源 | 明文落盘 templates/static/ | Fernet 加密嵌入代码 |
| API 鉴权 | 无 | Token 鉴权 + 高危强校验 |
| 反调试 | 无 | 50+ 进程检测 + 远程调试检测 |
| 反虚拟机 | 无 | VMware/VirtualBox/QEMU 检测 |
| 字符串保护 | 全部明文 | XOR 三密钥分段加密 |
| 调试输出 | print() 路径/端口/密钥 | 全部删除 |
| 异常处理 | 完整 traceback | 统一 "Internal server error" |
| .pyc 缓存 | 默认生成 | sys.dont_write_bytecode = True |
| 业务功能 | 100% | 100% (完全兼容) |
