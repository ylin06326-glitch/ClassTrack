<template>
  <div class="mobile-page">
    <div class="header">
      <h1>📱 ClassTrack 手机扫码</h1>
      <p>连续扫描学生二维码 · 数据实时同步电脑</p>
    </div>

    <!-- 证书信任指南 -->
    <div v-if="certVisible" class="cert-hint">
      <div class="cert-hint-title">🔐 信任证书指南</div>
      <div v-if="!certDone" class="cert-hint-steps">
        <p class="cert-intro">首次使用需安装 CA 证书以消除"不安全"警告：</p>
        <div class="cert-step"><span class="cert-step-num">1</span> 点击下方按钮下载证书</div>
        <div class="cert-step"><span class="cert-step-num">2</span> 打开下载的 <b>ClassTrack_CA_Certificate.crt</b></div>
        <div class="cert-step"><span class="cert-step-num">3</span> 按系统提示安装并<b>信任</b>此证书</div>
      </div>
      <div v-else class="cert-hint-done">✅ 证书已信任，无需重复操作</div>
      <div class="cert-hint-actions">
        <a class="cert-download-btn" href="/api/cert/download">📥 下载证书</a>
        <GlassButton @click="onCertDismiss">我知道了，先试用</GlassButton>
      </div>
      <details class="cert-details">
        <summary>📱 各平台详细步骤</summary>
        <div class="cert-details-body">
          <b>iOS：</b>设置 → 通用 → VPN与设备管理 → 安装描述文件 → 设置 → 通用 → 关于本机 → 证书信任设置 → 开启 ClassTrack<br>
          <b>Android：</b>设置 → 安全 → 加密与凭据 → 从存储设备安装 → 选择 .crt 文件 → 确定<br>
          <b>Windows：</b>电脑端已自动信任，无需操作
        </div>
      </details>
    </div>

    <!-- 扫码框 -->
    <div class="scan-box">
      <div id="reader"></div>
    </div>

    <!-- 控制按钮 -->
    <div class="controls">
      <GlassButton :disabled="starting" @click="startScan">
        {{ starting ? '⏳ 启动中...' : '▶ 开始扫描' }}
      </GlassButton>
      <GlassButton v-show="scanning" @click="stopScan">⏹ 停止扫描</GlassButton>
    </div>

    <!-- 日志区 -->
    <div class="log-area">
      <div class="log-title">📋 扫码记录 <span class="log-count">({{ scanCount }})</span></div>
      <div class="log-list">
        <div v-if="logs.length === 0" class="log-placeholder">等待扫描...</div>
        <div
          v-for="(l, i) in logs"
          :key="i"
          class="log-item"
          :class="l.type"
        ><span class="log-code">{{ l.code }}</span><span class="log-time">{{ l.time }}</span></div>
      </div>
    </div>

    <div class="status" :class="{ connected: statusConnected }">{{ statusText }}</div>
  </div>
</template>

<script setup lang="ts">
/**
 * 手机扫码独立页(/#/mobile)：无 MainLayout、无 useDialogs。
 * 行为契约与旧版 templates/mobile.html 内联 JS 全部流程一致，状态文案逐字保留：
 * 扫到的学号不做校验、不带等级，仅批量上报 /mobile/scan/batch，
 * 由电脑端作业视图轮询 /mobile/scans 后按当前作业种类与等级确认入库。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'
import { mobilePair, mobileScanBatch } from '@/api'

interface BufferItem { code: string; time: string }
interface LogItem { code: string; time: string; type: 'success' | 'error' }

const BATCH_INTERVAL = 300
const BATCH_MAX = 20
const CERT_DISMISS_KEY = 'classtrack_cert_dismissed'

const scanning = ref(false)
const starting = ref(false)
const scanBuffer = ref<BufferItem[]>([])
const scanCount = ref(0)
const logs = ref<LogItem[]>([])
const statusText = ref('🟡 准备就绪')
const statusConnected = ref(false)
const certVisible = ref(true)
const certDone = ref(false)

let scanner: Html5Qrcode | null = null
let batchTimer: number | null = null
let certTimer: number | null = null
let prevTitle = ''

function updateStatus(msg: string, connected: boolean): void {
  statusText.value = msg
  statusConnected.value = connected
}

function addLogItem(code: string, time: string, type: 'success' | 'error'): void {
  logs.value.unshift({ code, time, type })
  if (logs.value.length > 100) logs.value.pop()
}

// ---- 页面加载时验证与电脑的连通性(旧版 checkConnection 逐字) ----
async function checkConnection(): Promise<void> {
  try {
    const res = await mobilePair()
    if (res.code === 0) {
      updateStatus('🟢 已连接到电脑 · 准备就绪', true)
    }
  } catch {
    updateStatus('⚠️ 无法连接到电脑，请检查 WiFi', false)
  }
}

// ---- 摄像头扫描 ----
async function startScan(): Promise<void> {
  starting.value = true
  try {
    scanner = new Html5Qrcode('reader')
    updateStatus('🟢 扫描中...', true)

    await scanner.start(
      { facingMode: 'environment' },
      { fps: 20, qrbox: { width: 280, height: 280 }, aspectRatio: 1, disableFlip: true },
      onScanSuccess,
      onScanError,
    )
    scanning.value = true
  } catch (err) {
    const e = err as { message?: string }
    updateStatus('❌ 摄像头启动失败：' + (e?.message ?? ''), false)
    scanner = null
  }
  starting.value = false
}

async function stopScan(): Promise<void> {
  if (scanner && scanning.value) {
    await scanner.stop()
    scanning.value = false
    scanner = null
  }
  // 提交缓冲区剩余
  if (scanBuffer.value.length > 0) await flushBuffer()
  updateStatus('🟡 已停止 · 共扫 ' + scanCount.value + ' 条', false)
}

function onScanSuccess(decodedText: string): void {
  if (!scanning.value) return
  const code = (decodedText || '').trim()
  if (!code) return

  const now = new Date().toLocaleTimeString()

  // 加入批量缓冲区(不做学号校验,未知学号由电脑端确认时提示)
  scanBuffer.value.push({ code, time: now })
  scanCount.value += 1
  addLogItem(code, now, 'success')

  // 震动反馈
  if (navigator.vibrate) navigator.vibrate([30, 50, 30])

  // 批量发送:满 20 条立即发,否则定时发
  if (scanBuffer.value.length >= BATCH_MAX) {
    void flushBuffer()
  } else if (!batchTimer) {
    batchTimer = window.setTimeout(() => void flushBuffer(), BATCH_INTERVAL)
  }

  updateStatus('🟢 已扫 ' + scanCount.value + ' 条 · 继续扫描中...', true)
}

function onScanError(): void {
  // 正常扫描尝试中的虚警，忽略
}

/** 批量提交到后端(旧版逐字:POST /mobile/scan/batch,只报学号列表) */
async function flushBuffer(): Promise<void> {
  if (batchTimer) {
    clearTimeout(batchTimer)
    batchTimer = null
  }
  if (scanBuffer.value.length === 0) return

  const batch = scanBuffer.value.splice(0)
  const codes = batch.map((b) => b.code)
  try {
    const res = await mobileScanBatch(codes)
    if (res.code === 0) {
      console.log('批量提交成功:', res.data?.count ?? codes.length, '条')
    } else {
      console.warn('批量提交异常:', res.msg)
    }
  } catch {
    console.warn('批量提交网络错误')
    // 失败时重新入队(防止无限堆积)
    if (scanBuffer.value.length < BATCH_MAX * 2) {
      for (const item of batch) {
        scanBuffer.value.unshift(item)
      }
    }
  }
}

// ---- 证书信任提示(旧版 initCertHint 逐字) ----
function onCertDismiss(): void {
  certVisible.value = false
  localStorage.setItem(CERT_DISMISS_KEY, '1')
}

function initCertHint(): void {
  if (localStorage.getItem(CERT_DISMISS_KEY) === '1') {
    certVisible.value = false
    return
  }
  certTimer = window.setTimeout(() => {
    certDone.value = true
  }, 2000)
}

// ---- 页面关闭时停止扫描 ----
function onBeforeUnload(): void {
  if (scanner && scanning.value) {
    void scanner.stop()
  }
  if (scanBuffer.value.length > 0) {
    void flushBuffer()
  }
}

onMounted(() => {
  prevTitle = document.title
  document.title = 'ClassTrack 手机扫码'
  // 全局 style.css 为桌面布局设置了 min-width:1024px,移动端页面覆盖之
  document.body.style.minWidth = '0'
  initCertHint()
  void checkConnection()
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (batchTimer) {
    clearTimeout(batchTimer)
    batchTimer = null
  }
  if (certTimer) {
    clearTimeout(certTimer)
    certTimer = null
  }
  if (scanner && scanning.value) {
    void scanner.stop()
  }
  scanner = null
  document.body.style.minWidth = ''
  if (prevTitle) document.title = prevTitle
})
</script>

<style scoped>
/* ============================================================
   ClassTrack Mobile — 液态玻璃视觉(样式逐字复刻旧 mobile.html)
   ============================================================ */
.mobile-page {
  --glass-blur: 16px;
  --glass-saturate: 1.3;
  --blue: #7eb5d6;
  --blue-light: #b8d8e8;
  --pink: #e8a0bf;
  --green: #a8d5ba;
  --text: #5d5a5a;
  --text-light: #999595;
  --radius: 18px;
  --radius-sm: 14px;

  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background: #f5f1ed;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  position: relative;
}
/* 纯色背景装饰 */
.mobile-page::before {
  content: "";
  position: fixed;
  top: -150px;
  right: -100px;
  width: 350px;
  height: 350px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(126, 181, 214, 0.08) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}
.mobile-page::after {
  content: "";
  position: fixed;
  bottom: -120px;
  left: -80px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(232, 160, 191, 0.08) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.header { text-align: center; margin-bottom: 16px; position: relative; z-index: 1; }
.header h1 { font-size: 1.2rem; color: var(--blue); margin-bottom: 4px; }
.header p { font-size: 0.75rem; color: var(--text-light); }

/* 扫码框 — 玻璃卡片 */
.scan-box {
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--radius);
  padding: 12px;
  box-shadow: 0 4px 20px rgba(80, 60, 50, 0.08);
  margin-bottom: 14px;
  position: relative;
  z-index: 1;
  overflow: hidden;
}
.scan-box::after {
  content: "";
  position: absolute;
  top: 0;
  left: 5%;
  right: 5%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
  pointer-events: none;
}
#reader { width: 100%; border-radius: 14px; overflow: hidden; }
#reader :deep(video) { border-radius: 14px; width: 100%; }

/* 控制按钮 */
.controls {
  display: flex;
  gap: 10px;
  width: 100%;
  max-width: 400px;
  margin-bottom: 14px;
  position: relative;
  z-index: 1;
}
.btn {
  flex: 1;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 16px;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-start {
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.6), rgba(142, 200, 224, 0.65));
  color: white;
  box-shadow: 0 2px 12px rgba(126, 181, 214, 0.25);
}
.btn-stop {
  background: linear-gradient(135deg, rgba(232, 160, 191, 0.55), rgba(240, 168, 192, 0.6));
  color: white;
}
.btn:active { transform: scale(0.97); }

/* 日志区 — 玻璃面板 */
.log-area {
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 2px 12px rgba(80, 60, 50, 0.05);
  position: relative;
  z-index: 1;
  overflow: hidden;
}
.log-area::after {
  content: "";
  position: absolute;
  top: 0;
  left: 5%;
  right: 5%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  pointer-events: none;
}
.log-title { font-size: 0.8rem; font-weight: 700; color: var(--text); margin-bottom: 8px; }
.log-count { color: #999; }
.log-list { max-height: 200px; overflow-y: auto; }
.log-placeholder {
  color: #999;
  font-size: 0.75rem;
  text-align: center;
  padding: 12px;
}
.log-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 4px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border-radius: 10px;
  font-size: 0.8rem;
  animation: slideIn 0.3s ease-out;
}
.log-item.success { background: rgba(168, 213, 186, 0.3); }
.log-item.error { background: rgba(232, 160, 191, 0.25); }
.log-code { font-weight: 700; font-family: monospace; }
.log-time { font-size: 0.7rem; color: var(--text-light); }
@keyframes slideIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
.status {
  text-align: center;
  font-size: 0.75rem;
  color: var(--text-light);
  margin-top: 16px;
  position: relative;
  z-index: 1;
}
.status.connected { color: var(--green); font-weight: 600; }

/* 证书信任指南 */
.cert-hint {
  width: 100%;
  max-width: 400px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 12px;
  position: relative;
  z-index: 1;
}
.cert-hint-title { font-size: 0.85rem; font-weight: 700; color: #f57f17; margin-bottom: 8px; }
.cert-hint-steps { font-size: 0.73rem; color: #856404; line-height: 1.7; }
.cert-intro { margin: 0 0 8px; }
.cert-step { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.cert-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f57f17;
  color: white;
  font-size: 0.68rem;
  font-weight: 700;
  flex-shrink: 0;
}
.cert-hint-done {
  font-size: 0.8rem;
  color: #2d6a3f;
  font-weight: 600;
  text-align: center;
  padding: 6px;
}
.cert-hint-actions { display: flex; gap: 8px; margin-top: 10px; }
.cert-download-btn {
  flex: 1;
  display: block;
  text-align: center;
  padding: 10px;
  background: linear-gradient(135deg, #f57f17, #ffa000);
  color: white;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.2s;
}
.cert-download-btn:active { transform: scale(0.96); }
.cert-dismiss-btn {
  padding: 10px 14px;
  border: 1px solid #ffe082;
  border-radius: 12px;
  background: white;
  color: #856404;
  font-size: 0.78rem;
  cursor: pointer;
  font-family: inherit;
}
.cert-details {
  margin-top: 8px;
  font-size: 0.7rem;
  color: #856404;
  cursor: pointer;
}
.cert-details summary { font-weight: 600; }
.cert-details-body {
  margin-top: 6px;
  line-height: 1.8;
  text-align: left;
}
</style>
