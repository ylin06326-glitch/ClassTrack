<template>
  <div class="activation-overlay">
    <div class="activation-card" :class="{ 'card-exit': exiting }">
      <div class="logo-area">
        <span class="logo">🎒</span>
        <h1>ClassTrack YRL</h1>
        <p class="subtitle">班级作业分组管理系统</p>
      </div>

      <div class="status-area" :class="statusClass">{{ statusText }}</div>

      <!-- 步骤① 复制机器指纹 -->
      <div class="step-block">
        <div class="step-title">① 复制机器指纹,发送给商家</div>
        <div class="machine-code">{{ machineCode || '正在采集…' }}</div>
        <GlassButton type="primary" :loading="copying" @click="copyFingerprint">
          {{ copied ? '指纹已复制,请发送给商家 ✓' : '复制机器指纹' }}
        </GlassButton>
      </div>

      <!-- 步骤② 粘贴密钥验证 -->
      <div class="step-block">
        <div class="step-title">② 粘贴商家提供的激活密钥</div>
        <el-input
          v-model="keyText"
          type="textarea"
          :rows="3"
          placeholder="请粘贴激活密钥…"
          :disabled="verifying || activated"
          @keydown.ctrl.enter.prevent="verify"
        />
        <div class="btn-row">
          <GlassButton type="success" :loading="verifying" @click="verify">
            {{ verifying ? '⏳ 正在校验激活密钥...' : '✅ 验证激活' }}
          </GlassButton>
        </div>
        <div class="alt-import">
          <span class="file-label" :class="{ 'drag-over': dragOver }"
                @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false"
                @drop.prevent="onDropFile">
            📂 或选择激活文件导入
          </span>
          <input type="file" accept=".dat,.txt,.key" hidden @change="onPickFile" />
        </div>
      </div>

      <div class="footer-tip">未激活前,软件全部功能禁用</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useActivationStore } from '@/stores/activation'

const router = useRouter()
const store = useActivationStore()

const machineCode = ref('')
const fingerprint = ref('')
const keyText = ref('')
const verifying = ref(false)
const copying = ref(false)
const copied = ref(false)
const activated = ref(false)
const exiting = ref(false)
const statusText = ref('🔒 请粘贴商家提供的激活密钥')
const statusClass = ref('')
const dragOver = ref(false)

onMounted(async () => {
  await store.checkStatus()
  if (store.activated) {
    enterApp()
    return
  }
  try {
    const res = await store.getFingerprint()
    machineCode.value = res.machine_code
    fingerprint.value = res.fingerprint
  } catch {
    machineCode.value = '(采集失败,请重启程序重试)'
  }
})

async function copyFingerprint() {
  if (!fingerprint.value) {
    ElMessage.error('机器指纹尚未就绪')
    return
  }
  copying.value = true
  try {
    await navigator.clipboard.writeText(fingerprint.value)
  } catch {
    // 复制失败降级:选中文本
    const ta = document.createElement('textarea')
    ta.value = fingerprint.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  copying.value = false
  copied.value = true
  setTimeout(() => (copied.value = false), 2500)
}

async function verify() {
  const content = keyText.value.trim().replace(/^["']|["']$/g, '')
  if (!content) {
    ElMessage.warning('请先粘贴激活密钥')
    return
  }
  verifying.value = true
  statusText.value = '⏳ 正在校验激活密钥...'
  statusClass.value = ''
  try {
    const res = await store.verifyKey(content)
    if (res.success) {
      activated.value = true
      statusText.value = '✅ 激活成功!正在进入系统...'
      statusClass.value = 'success'
      setTimeout(enterApp, 800)
    } else {
      statusText.value = `❌ ${res.message}`
      statusClass.value = 'error'
    }
  } catch {
    statusText.value = '❌ 校验失败,请重试'
    statusClass.value = 'error'
  } finally {
    verifying.value = false
  }
}

function enterApp() {
  exiting.value = true
  // 绿光退场动画后跳转主界面(0.65s 兜底)
  setTimeout(() => router.replace('/'), 650)
}

function onPickFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) readFile(file)
  ;(e.target as HTMLInputElement).value = ''
}

function onDropFile(e: DragEvent) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) readFile(file)
}

function readFile(file: File) {
  const reader = new FileReader()
  reader.onload = async () => {
    keyText.value = String(reader.result ?? '')
    await verify()
  }
  reader.readAsText(file)
}
</script>

<style scoped>
.activation-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef5fa 0%, #fdf6f0 50%, #f2f0fb 100%);
  animation: fadeIn 0.45s ease;
}
.activation-card {
  width: 480px;
  padding: 32px 36px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(16px);
  box-shadow: 0 12px 40px rgba(90, 110, 140, 0.18);
  animation: cardIn 0.55s cubic-bezier(0.22, 0.98, 0.36, 1);
}
.card-exit {
  animation: cardOut 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
@keyframes fadeIn {
  from { opacity: 0; }
}
@keyframes cardIn {
  from { opacity: 0; transform: translateY(28px) scale(0.94); }
}
@keyframes cardOut {
  to { opacity: 0; transform: translateY(-40px) scale(0.95); }
}
.logo-area { text-align: center; margin-bottom: 20px; }
.logo { font-size: 52px; }
.logo-area h1 { margin: 8px 0 4px; color: #3a4a5a; }
.subtitle { color: #8a97a8; margin: 0; font-size: 14px; }
.status-area {
  text-align: center;
  padding: 10px;
  border-radius: 12px;
  background: #f0f4f8;
  color: #55636f;
  margin-bottom: 18px;
  font-size: 14px;
}
.status-area.success { background: #e8f7ee; color: #2d6a3f; }
.status-area.error { background: #fdeef2; color: #8a4a5a; }
.step-block { margin-bottom: 18px; }
.step-title { font-weight: 600; color: #3a4a5a; margin-bottom: 8px; font-size: 14px; }
.machine-code {
  font-family: 'Consolas', monospace;
  letter-spacing: 1px;
  background: #f6f8fa;
  border: 1px dashed #c8d4de;
  border-radius: 10px;
  padding: 10px;
  text-align: center;
  margin-bottom: 10px;
  font-size: 15px;
  user-select: all;
}
.btn-row { margin-top: 10px; text-align: center; }
.alt-import {
  margin-top: 12px;
  text-align: center;
}
.file-label {
  display: inline-block;
  padding: 8px 16px;
  border: 1px dashed #a8c4d8;
  border-radius: 10px;
  color: #55829f;
  cursor: pointer;
  font-size: 13px;
}
.file-label:hover, .file-label.drag-over {
  background: #eef6fb;
  border-color: #6ba3c7;
  box-shadow: 0 0 0 3px rgba(107, 163, 199, 0.2);
}
.footer-tip { text-align: center; color: #a8b2bd; font-size: 12px; margin-top: 4px; }
</style>
