# ClassTrack 开发进度追踪

> 最后更新: 2026-08-20
> 版本: v2.0 → **前后端分离重构(FastAPI + Vue3 + Element-Plus)**

---

## 0. 2026-08-20 架构重构(重要)

原 Flask + 原生 JS(约 9000 行单文件)已整体重构为前后端分离架构,**API 契约 100% 兼容**(msg 文案、code=1 业务错误形态、`{student_id: {...}}` 响应结构均逐字保留),旧数据目录可直接复用(SQLite schema v2.2 不变)。

### 新架构

| 层 | 技术 | 位置 |
|----|------|------|
| 后端 | FastAPI 0.115 + uvicorn + 同步 sqlite3(线程池) | `backend/app/`(routers/services/activation 分包) |
| 前端 | Vue 3.5 + TS(strict) + Vite + Element-Plus + Pinia + Vue Router(hash) + ECharts 6 | `frontend/src/` |
| 生产部署 | FastAPI 托管 `frontend/dist`(SPA catch-all),PyInstaller 打包进 exe | `ClassTrack.spec` / `launcher.py` |
| 开发调试 | `python backend/run.py --http --no-browser`(默认端口 5088);`cd frontend && npm run dev`(代理 /api → 127.0.0.1:8000) | — |

### 前端结构(15 文件)

- 基础层:`api/http.ts`(axios 拦截器兼容 `{code:1,msg}` 与 `{detail}`)、`api/index.ts`、`stores/app.ts`(班级/显示模式/导出日期)、`stores/activation.ts`、`composables/dialogs.ts`、`utils/grade.ts`、`utils/textImport.ts`、`components/HomeworkTypesDialog.vue`、`components/ReminderDialog.vue`
- 视图:`MainLayout.vue`(7 tab v-show 常驻)、`ActivationPage.vue`(#/activate)、`tabs/{Grouping,Homework,Exams,Export,Analytics,Settings,AIChat}Tab.vue`、`MobileScannerPage.vue`(#/mobile)、`PrintReportPage.vue`(#/print)

### 与旧版的关键行为对齐点

- 手机扫码页仅上报 `/api/mobile/scan/batch`(不校验学号、不带等级),桌面作业视图轮询 `/api/mobile/scans` 后按当前作业种类与等级确认入库
- 电脑扫码:批量模式入待确认列表;单点模式 prompt 等级(仅 A/B/C/X)后 `scan/single` 即时落库
- 激活页:`verify` 传 `{file_content}`、`fingerprint_export` 字段、成功绿光退场
- 显示模式 localStorage 契约:`classtrack_zone_display`('auto')/ `classtrack_privacy`('1'=code)
- 打包:`build.bat` 先 `npm run build` 再 PyInstaller;发布 zip 只含 exe + 说明书,**绝不打包 data 目录与 activation/private_key.pem**

### 遗留事项

- [ ] 旧版文件(main.py / main_nolock.py / app_paths.py / templates/ / static/)已 git 提交,是否物理删除待确认(新架构不再引用)
- [ ] `ClassTrack_nolock.spec` / `launcher_nolock.py` 输出 ClassTrack-Free(多开版)
- [ ] PyInstaller 打包链路未实测(需在装有 Node 的环境跑 build.bat 验证)

---

## 1. 已完成功能

### 核心功能
- [x] 多班级管理（创建、切换、删除）
- [x] 学生导入（Excel + 纯文字，支持学号识别）
- [x] 学生管理（增删改、批量操作、拖拽分组）
- [x] 分组管理（灵活分组、锁定、拖拽、颜色主题）
- [x] 作业登记（A/B/C/L/X 五级、批量登记、日期导航）
- [x] 作业种类管理（自定义种类、多作业并行）
- [x] 报表导出（单学生台账、全班汇总 Excel）
- [x] 数据概览（统计卡片、饼图、柱状图、折线图、环比趋势）
- [x] 小组排行榜（A率排序、提交率、平均分）
- [x] 学生预警与进步追踪
- [x] 催交作业通知（复制名单、打印、导出）
- [x] 扫码登记（电脑摄像头 + 手机联动）
- [x] 二维码生成与打印（服务端 Python 生成，离线可用）
- [x] HTTPS 支持（自签 CA 证书，手机扫码可用）
- [x] 激活校验（离线硬件指纹验证，RSA-2048 + 机器绑定）
- [x] 隐私保护（姓名/学号分区显示模式）

### AI 助手模块 (v2.0)
- [x] **AI 设置页面** — DeepSeek/OpenAI/通义千问/自定义
- [x] **AI 连接测试** / **AI 配置持久化**
- [x] **AI 智能对话** — 关键词意图识别 + LLM 数据驱动问答
- [x] **ECharts 可视化** — 柱状图/折线图/饼图 + 点击追问
- [x] **AI 评语生成** / **智能预警横幅** / **AI 智能分组**(蛇形算法,预览+应用)
- [x] **快捷提问** — 6 个常用问题

---

## 2. 进行中功能

- [ ] ECharts 深色主题适配（当前仅适配浅色）
- [ ] AI 对话历史持久化（跨会话保存）

---

## 3. 待办功能

- [ ] 单学生趋势图（AI对话中查询具体学生的历史趋势）
- [ ] AI 自动生成周报/月报
- [ ] 更多的图表交互（如拖拽排序分组）
- [ ] 多轮对话上下文记忆（当前每次提问独立）
- [ ] 移动端 AI 助手适配
- [ ] 离线 AI 支持（集成 Ollama 等本地模型）
- [ ] 作业批改建议（AI 根据学生历史给出作业难度建议）

---

## 4. 技术债务 / 已知问题

| 问题 | 严重程度 | 备注 |
|------|----------|------|
| API Key Base64 编码非真加密 | 低 | 本地单机使用，风险可控 |
| LLM 调用无重试机制 | 低 | 网络不稳定时可能一次失败 |
| AI 对话无历史持久化 | 中 | 刷新页面后对话丢失 |
| 前端构建产物无 hash 也无强制缓存策略 | 低 | FastAPI 静态托管,每次打包全量覆盖 |
| 老设备浏览器兼容 | 低 | Vue3 需 ES2015+,与旧版 vanilla JS 相比下限提高 |

---

## 5. 关键决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-08-20 | 后端路由按模块拆包(routers/) | 9000 行单文件不可维护,分包后每模块 <400 行 |
| 2026-08-20 | 同步 sqlite3 + `def` 路由线程池 | 数据仅本地单机使用,无需 async 驱动;`check_same_thread=False` |
| 2026-08-20 | 前端各 tab 用 v-show 常驻 + Pinia 统一状态 | 保持旧版"切 tab 不丢状态"体验 |
| 2026-08-20 | hash 模式路由 | exe 打包后无独立 Web 服务器,SPA catch-all 用 hash 最稳 |
| 2026-08-20 | 手机扫码回归旧数据流(mobile_scans 表 + 桌面确认) | 直接落库会丢作业种类上下文,旧版两步流程是正确设计 |
| 2026-08-20 | vue-tsc strict + noUnusedLocals | 5 个并行 agent 协作下,编译期捕获契约漂移 |
| 2026-08-04 | 选择 ECharts 5 作为 AI 可视化图表库 | 项目需求指定 |
| 2026-08-04 | 蛇形（Zigzag）分配算法实现智能分组 | 简单直观,均衡性好 |
| 2026-08-04 | 智能分组「预览」+「应用」两步 | 避免误操作覆盖现有分组 |
| 2026-08-04 | **图表引擎重构：服务端自动构建 ECharts option** | LLM 只指定图表类型,后端从数据库构建配置,保证图表完整可用 |

---

## 6. 下次启动任务点

1. **优先级最高**: 验证 PyInstaller 打包(build.bat)与 nolock 版,确认 exe 内 frontend/dist 路径生效
2. **联调收尾**: 浏览器实测激活页 → 主界面全 tab(尤其 AI 对话流、扫码摄像头、打印页)
3. **清理确认**: 与作者确认后物理删除旧版 main.py / templates/ / static/ 等
4. **功能增强**: AI 对话历史持久化
5. **体验优化**: 对话导出功能

---

## 7. 文件结构变更 (2026-08-20 重构)

```
新增:
├── backend/                     # FastAPI 后端(73 路由)
│   ├── run.py                   # 开发入口(--http 纯HTTP)
│   ├── requirements.txt
│   └── app/{main,config,database,deps,utils}.py
│       ├── routers/{auth,classes,students,groups,homework,homework_types,
│       │            exam_scores,analytics,scan,stats,print,import_export,
│       │            mobile,activation,config,ai,report}.py
│       ├── services/{tls_service,ai_service,report_service}.py
│       └── activation/{crypto,hardware_id,key_pair,license_manager}.py
├── frontend/                    # Vue3 + TS 前端(见上节结构)
├── launcher.py / launcher_nolock.py
├── ClassTrack.spec / ClassTrack_nolock.spec
└── 启动ClassTrack.bat            # 自动装依赖 + 构建前端 + 启动

保留:activation/(商家密钥,不分发) / data/(本地数据,不打包) / build.bat(重写)
```

---

## 8. API 路由清单

- 后端共 73 个路由,与旧版 Flask 契约一致(详见 `backend/app/routers/`)
- 业务错误双形态:HTTP 400 + `{code:1,msg}`;或 HTTP 200 + `code:1`(前端拦截器均兼容)
- 激活守卫:未激活时 /api/* 返回 403 `{code:403,msg:"软件未激活，请先完成激活登录"}`,白名单与旧版一致
