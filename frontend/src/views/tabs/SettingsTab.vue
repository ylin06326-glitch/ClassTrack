<template>
  <div class="settings-container">
    <!-- ========== AI 服务配置 ========== -->
    <div class="settings-card">
      <h3>🤖 AI 服务配置</h3>
      <div class="settings-row">
        <label>AI 服务商</label>
        <el-select v-model="form.provider" class="settings-select" @change="onProviderChange">
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="OpenAI" value="openai" />
          <el-option label="通义千问" value="qwen" />
          <el-option label="自定义" value="custom" />
        </el-select>
      </div>
      <div class="settings-row">
        <label>API Key</label>
        <el-input
          v-model="form.apiKey"
          type="password"
          show-password
          autocomplete="off"
          :placeholder="apiKeyPlaceholder"
        />
      </div>
      <div class="settings-row">
        <label>Base URL</label>
        <el-input v-model="form.baseUrl" placeholder="https://api.deepseek.com/v1" />
      </div>
      <div class="settings-row">
        <label>模型名称</label>
        <el-input v-model="form.model" placeholder="deepseek-chat" />
      </div>
      <div class="settings-actions">
        <el-button class="btn-test" :loading="testing" :disabled="testing" @click="onTest">
          {{ testing ? '⏳ 测试中...' : '🔌 测试连接' }}
        </el-button>
        <el-button type="primary" :loading="saving" :disabled="saving" @click="onSave">
          {{ saving ? '⏳ 保存中...' : '💾 保存配置' }}
        </el-button>
      </div>
      <div v-if="statusText" class="settings-status" :class="statusClass">{{ statusText }}</div>
    </div>

    <!-- ========== 使用说明 ========== -->
    <div class="settings-card">
      <h3>📋 使用说明</h3>
      <div class="usage-guide">
        <p><strong>DeepSeek</strong>：注册 <a href="https://platform.deepseek.com" target="_blank">platform.deepseek.com</a> 获取 API Key，推荐使用 <code>deepseek-chat</code> 模型。</p>
        <p><strong>OpenAI</strong>：需自备 API Key，推荐 <code>gpt-3.5-turbo</code> 或 <code>gpt-4o-mini</code>。</p>
        <p><strong>通义千问</strong>：注册阿里云百炼平台获取 Key，推荐 <code>qwen-plus</code>。</p>
        <p><strong>自定义</strong>：兼容 OpenAI 格式的任何 API（如 Ollama、vLLM 等）。</p>
        <p class="usage-note">💡 API Key 使用 Base64 编码存储，仅保存在您的本地电脑。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 设置 Tab：AI 服务配置 + 使用说明
 * 行为契约与旧版 static/js/ai.js setupSettingsTab/loadAIConfig 一致
 */
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { loadAIConfig, saveAIConfig, testAIConfig } from '@/api'

/** 各服务商默认 Base URL 与模型（与旧版 ai.js defaults 一致） */
const PROVIDER_DEFAULTS: Record<string, { url: string; model: string }> = {
  deepseek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  openai: { url: 'https://api.openai.com/v1', model: 'gpt-3.5-turbo' },
  qwen: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  custom: { url: '', model: '' },
}

interface AIConfigData {
  provider: string
  api_key_masked: string
  has_key: boolean
  base_url: string
  model: string
}

const form = reactive({
  provider: 'deepseek',
  apiKey: '',
  baseUrl: '',
  model: '',
})

const apiKeyPlaceholder = ref('请输入 API Key')
const testing = ref(false)
const saving = ref(false)
const statusText = ref('')
const statusClass = ref<'success' | 'error' | ''>('')

/** 切换服务商时自动填充默认 Base URL / 模型（自定义不填） */
function onProviderChange(provider: string): void {
  const d = PROVIDER_DEFAULTS[provider] || { url: '', model: '' }
  if (provider !== 'custom') {
    form.baseUrl = d.url
    form.model = d.model
  }
}

/** 加载已保存配置（与旧版 loadAIConfig 逻辑一致） */
async function initConfig(): Promise<void> {
  try {
    const res = (await loadAIConfig()) as { code: number; data: AIConfigData | null }
    if (res.code === 0 && res.data) {
      form.provider = res.data.provider || 'deepseek'
      if (res.data.has_key) {
        apiKeyPlaceholder.value = `已保存 (${res.data.api_key_masked})`
      }
      if (!res.data.base_url) {
        // 未保存过 Base URL 时按服务商填充默认值
        onProviderChange(form.provider)
      } else {
        form.baseUrl = res.data.base_url || ''
      }
      form.model = res.data.model || ''
    }
  } catch (e) {
    console.log('AI config load failed:', (e as Error).message)
  }
}

/** 提取 HTTP 错误中的后端 msg（400 拦截器已 toast，状态区同步展示） */
function errMsg(e: unknown): string | undefined {
  if (axios.isAxiosError(e)) {
    const data = e.response?.data as { msg?: string } | undefined
    if (data?.msg) return data.msg
  }
  return undefined
}

/** 🔌 测试连接：状态区显示后端 msg（如「连接成功 🟢」） */
async function onTest(): Promise<void> {
  testing.value = true
  statusText.value = ''
  statusClass.value = ''
  try {
    const res = await testAIConfig({
      provider: form.provider,
      api_key: form.apiKey,
      base_url: form.baseUrl,
      model: form.model,
    })
    if (res.code === 0) {
      statusClass.value = 'success'
      statusText.value = res.msg || '连接成功 🟢'
    } else {
      statusClass.value = 'error'
      statusText.value = `🔴 ${res.msg}`
    }
  } catch (e) {
    statusClass.value = 'error'
    const msg = errMsg(e)
    statusText.value = msg ? `🔴 ${msg}` : '🔴 网络请求失败，请检查网络连接'
  }
  testing.value = false
}

/** 💾 保存配置 */
async function onSave(): Promise<void> {
  const apiKey = form.apiKey.trim()
  if (!apiKey) {
    statusClass.value = 'error'
    statusText.value = '🔴 请输入 API Key'
    return
  }
  saving.value = true
  try {
    const res = await saveAIConfig({
      provider: form.provider,
      api_key: apiKey,
      base_url: form.baseUrl.trim(),
      model: form.model.trim(),
    })
    if (res.code === 0) {
      statusClass.value = 'success'
      statusText.value = '✅ 配置已保存'
      if (res.msg) ElMessage.success(`✅ ${res.msg}`)
    } else {
      statusClass.value = 'error'
      statusText.value = `🔴 ${res.msg}`
    }
  } catch (e) {
    statusClass.value = 'error'
    const msg = errMsg(e)
    statusText.value = msg ? `🔴 ${msg}` : '🔴 保存失败，请重试'
  }
  saving.value = false
}

onMounted(initConfig)

</script>

<style scoped>
.settings-container {
  --blue: #7eb5d6;
  --text: #5d5a5a;
  --text-light: #999595;
  --text-lighter: #bfbbbb;
  --radius: 20px;
  --radius-sm: 14px;
  max-width: 640px;
  margin: 0 auto;
  padding: 8px 0;
}
.settings-card {
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(12px) saturate(1.4);
  -webkit-backdrop-filter: blur(12px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 16px;
  box-shadow: 0 4px 20px rgba(80, 60, 50, 0.04);
}
.settings-card h3 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 18px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.settings-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.settings-row label {
  flex: 0 0 100px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-light);
  text-align: right;
  white-space: nowrap;
}
.settings-select {
  flex: 1;
}
.settings-row :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.25) inset;
}
.settings-row :deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.25) inset;
}
.settings-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(200, 190, 185, 0.12);
}
.settings-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  font-weight: 600;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
}
.settings-status.success {
  color: #2d8a56;
  background: rgba(168, 213, 186, 0.2);
}
.settings-status.error {
  color: #c0392b;
  background: rgba(232, 160, 191, 0.2);
}

/* 使用说明 */
.usage-guide {
  font-size: 0.85rem;
  color: var(--text-light);
  line-height: 1.7;
}
.usage-guide p {
  margin: 0 0 6px;
}
.usage-guide code {
  background: rgba(126, 181, 214, 0.12);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 0.8rem;
}
.usage-guide a {
  color: var(--blue);
}
.usage-note {
  margin-top: 8px;
  color: var(--text-lighter);
  font-size: 0.78rem;
}

@media (max-width: 768px) {
  .settings-row {
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
  }
  .settings-row label {
    text-align: left;
    flex: none;
  }
}
</style>
