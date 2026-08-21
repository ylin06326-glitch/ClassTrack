<template>
  <div class="ai-chat-container">
    <!-- ========== 左侧对话流 ========== -->
    <div class="ai-chat-left">
      <div class="ai-chat-messages" ref="messagesEl">
        <template v-for="m in messages" :key="m.id">
          <div v-if="m.role === 'user'" class="ai-msg ai-msg-user" v-html="m.html"></div>
          <template v-else>
            <div class="ai-msg ai-msg-ai" v-html="m.html"></div>
            <div v-if="m.followUps.length" class="ai-follow-ups">
              <span class="follow-label">💬 你可能还想问：</span>
              <GlassButton                 v-for="(f, i) in m.followUps"
                :key="i"
                class="ai-quick-btn follow-chip"
                @click="onFollowUp(f.text)"
              >{{ (f.icon || '') + ' ' + f.text }}</GlassButton>
            </div>
          </template>
        </template>
        <div v-if="waiting" class="ai-msg-loading"><span></span><span></span><span></span></div>
      </div>

      <div class="ai-quick-questions">
        <span v-if="suggestionsLoading" class="suggestions-loading">⏳ 加载建议中...</span>
        <template v-else>
          <GlassButton             v-for="(s, i) in suggestions"
            :key="i"
            class="ai-quick-btn"
            @click="onQuickAsk(s.text)"
          >{{ (s.icon || '') + ' ' + (s.label || s.text) }}</GlassButton>
        </template>
      </div>

      <!-- 考试数据上下文指示条 -->
      <div v-if="examBarData" class="ai-exam-bar">
        <span class="ai-exam-icon">📋</span>
        <span class="ai-exam-info">{{ examBarText }}</span>
        <GlassButton class="exam-btn exam-btn-outline" @click="onClearExam">✕ 清除</GlassButton>
        <GlassButton class="exam-btn exam-btn-export" @click="showExamApplyModal">✅ 登记成绩</GlassButton>
      </div>

      <div class="ai-chat-input-area">
        <label
          class="btn-upload-exam"
          :title="uploading ? '上传中...' : '上传考试 Excel'"
          :style="uploading ? 'opacity:0.5' : ''"
          @click="onPickExam"
        >
          <span>📎</span>
        </label>
        <input type="file" ref="examFileInput" accept=".xls,.xlsx" hidden @change="onExamFileChange" />
        <select v-model="hwTypeModel" class="ai-hw-select">
          <option :value="0">全部种类</option>
          <option v-for="t in store.homeworkTypes" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <input
          ref="inputEl"
          v-model="inputText"
          class="ai-chat-text"
          type="text"
          placeholder="输入你的问题，也可以先 📎 上传考试 Excel"
          autocomplete="off"
          :disabled="sending"
          @keydown.enter.exact.prevent="onSend"
        />
        <GlassButton class="ai-send-btn" :disabled="sending" @click="onSend">发送 ✈</GlassButton>
      </div>
    </div>

    <!-- ========== 右侧图表画布 ========== -->
    <div class="ai-chat-right">
      <div class="ai-chart-header">{{ chartHeader }}</div>
      <div class="ai-chart-body">
        <iframe
          v-show="vizVisible"
          ref="vizFrameEl"
          class="ai-viz-frame"
          title="可视化面板"
          :src="blobUrl"
          @load="onVizFrameLoad"
        ></iframe>
        <div v-show="echartsVisible" ref="chartDomEl" class="ai-echarts-dom"></div>
        <div v-show="placeholderVisible" class="ai-chart-placeholder">
          <span class="placeholder-icon">📊</span>
          <p>在这里查看可视化结果</p>
          <p class="placeholder-sub">AI 会根据你的问题自动生成可视化面板</p>
        </div>
        <div v-if="exportData" class="ai-export-bar">
          <GlassButton class="exp-btn" :disabled="exporting === 'word'" @click="onExportExcel">
            {{ exporting === 'excel' ? '⏳ 生成中...' : '📥 导出Excel' }}
          </GlassButton>
          <GlassButton class="exp-btn" :disabled="exporting === 'excel'" @click="onExportWord">
            {{ exporting === 'word' ? '⏳ 生成中...' : '📄 导出Word' }}
          </GlassButton>
        </div>
      </div>
    </div>

    <!-- ========== 考试数据预览弹窗 ========== -->
    <GlassDialog v-model="examPreviewVisible" title="📋 考试数据预览" width="720px" append-to-body>
      <div v-if="previewData" class="preview-content" v-html="previewHtml"></div>
      <template #footer>
        <GlassButton type="primary" @click="onExamApplyNow">✅ 登记成绩到系统</GlassButton>
        <span class="preview-tip">💡 登记后可在 AI 对话中提问分析</span>
      </template>
    </GlassDialog>

    <!-- ========== 登记考试成绩弹窗 ========== -->
    <GlassDialog v-model="examApplyVisible" title="✅ 登记考试成绩" width="480px" append-to-body>
      <p class="apply-desc">系统将根据学号或姓名自动匹配学生，将考试等第登记到作业记录中。</p>
      <div class="apply-row">
        <label>登记日期</label>
        <input v-model="applyDate" type="date" class="apply-input" />
      </div>
      <div class="apply-row">
        <label>目标班级</label>
        <select v-model="applyClassName" class="apply-select">
          <option value="">全部班级</option>
          <option v-for="(c, i) in applyClasses" :key="i" :value="c.class_name">{{ c.class_name }} ({{ c.student_count }}人)</option>
        </select>
      </div>
      <div class="apply-row">
        <label>作业种类</label>
        <select v-model="applyHwTypeId" class="apply-select">
          <option v-for="t in applyHwTypes" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
      </div>
      <template #footer>
        <div class="apply-footer">
          <GlassButton type="primary" :disabled="applying" @click="onExamApplyConfirm">
            {{ applying ? '⏳ 登记中...' : '✅ 确认登记' }}
          </GlassButton>
          <span class="apply-status" v-html="applyStatusHtml"></span>
        </div>
      </template>
    </GlassDialog>
  </div>
</template>

<script setup lang="ts">
/**
 * AI 助手 Tab：聊天流 + 可视化 iframe + 考试数据上传/登记 + 导出
 * 行为契约与旧版 static/js/ai.js setupAIChatTab 全部流程一致，msg 文案逐字保留
 */
import GlassDialog from '@/components/GlassDialog.vue'
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'
import { useAppStore } from '@/stores/app'
import http from '@/api/http'
import {
  loadAIConfig, aiChat, aiImportExam, aiExamData, aiExamDataClear, aiImportExamApply,
  loadAISuggestions, loadHomeworkTypes, type HomeworkType,
} from '@/api'

// 供 iframe 内 LLM 生成的脚本访问（与旧版 parent.echarts 注入机制一致）
;(window as unknown as Record<string, unknown>).echarts = echarts

const store = useAppStore()

// ============ 类型 ============
interface Suggestion { text: string; icon?: string; label?: string }
interface ChatMsg { id: number; role: 'user' | 'ai'; html: string; followUps: Suggestion[] }
interface ChartSpec { type?: 'pie' | 'bar' | 'line' | string; title?: string; option?: Record<string, any> }
interface AIChatData {
  reply: string
  chart: ChartSpec | null
  viz_html: string | null
  follow_ups: Suggestion[]
  export_data: Record<string, any> | null
}
interface ExamStudent {
  name: string
  code?: string
  score?: number | null
  score_display?: string
  grade?: string
}
interface ExamClassInfo {
  class_name: string
  student_count: number
  avg_score: number | string
  max_score: number | string
  min_score: number | string
  stats?: Record<string, number>
  students: ExamStudent[]
}
interface ExamResult {
  total_students: number
  classes: ExamClassInfo[]
  detected_columns?: string[]
}
interface ExamCache { source_file: string; data: ExamResult; imported_at: string }

// ============ 聊天状态 ============
const WELCOME_HTML =
  '<p>👋 你好！我是 ClassTrack AI 助手。<br>我可以帮你分析班级作业数据、生成图表、识别趋势。<br>试试下面的快捷提问，或直接输入你的问题吧！</p>'
const WELCOME_SWITCH_HTML =
  '<p>👋 你好！我是 ClassTrack AI 助手。<br>已切换到新班级。我可以帮你分析班级作业数据、生成图表、识别趋势。<br>试试下面的快捷提问，或直接输入你的问题吧！</p>'

let msgId = 0
const messages = ref<ChatMsg[]>([])
const waiting = ref(false)
const sending = ref(false)
const inputText = ref('')
const inputEl = ref<HTMLInputElement>()
const messagesEl = ref<HTMLDivElement>()

// 快捷提问
const DEFAULT_SUGGESTIONS: Suggestion[] = [
  { text: '今天哪个组表现最好？', icon: '🏆', label: '今日最佳小组' },
  { text: '最近一周的提交率趋势如何？', icon: '📈', label: '提交率趋势' },
  { text: '今天的作业等级分布是怎样的？', icon: '🍩', label: '等级分布' },
]
const suggestions = ref<Suggestion[]>([...DEFAULT_SUGGESTIONS])
const suggestionsLoading = ref(false)

// ============ 可视化状态 ============
const vizVisible = ref(false)
const echartsVisible = ref(false)
const placeholderVisible = ref(true)
const chartHeader = ref('📊 数据可视化')
const blobUrl = ref('')
const vizFrameEl = ref<HTMLIFrameElement>()
const chartDomEl = ref<HTMLDivElement>()
let currentChart: echarts.ECharts | null = null

// ============ 导出状态 ============
const lastExportData = ref<Record<string, any> | null>(null)
const lastReply = ref('')
const lastVizHtml = ref<string | null>(null)
const exportData = ref<Record<string, any> | null>(null)
const exporting = ref<'excel' | 'word' | ''>('')

// ============ 考试数据状态 ============
const examBarData = ref<ExamResult | null>(null)
const uploading = ref(false)
const examFileInput = ref<HTMLInputElement>()
const examPreviewVisible = ref(false)
const previewData = ref<ExamResult | null>(null)
const examApplyVisible = ref(false)
const applyDate = ref('')
const applyClassName = ref('')
const applyHwTypeId = ref<number>(0)
const applyClasses = ref<ExamClassInfo[]>([])
const applyHwTypes = ref<HomeworkType[]>([])
const applying = ref(false)
const applyStatusHtml = ref('')

const examBarText = computed(() => {
  const d = examBarData.value
  if (!d) return ''
  const classNames = d.classes.map((c) => c.class_name).join(', ')
  return `📋 ${d.total_students}人 · ${classNames}`
})

/** 作业种类选择器：镜像 store.currentHomeworkTypeId（与旧版 State 联动一致） */
const hwTypeModel = computed<number>({
  get: () => (store.homeworkTypes.some((t) => t.id === store.currentHomeworkTypeId) ? store.currentHomeworkTypeId : 0),
  set: (v: number) => { store.currentHomeworkTypeId = v },
})

// ============ 工具函数 ============
function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 与旧版 addChatMessage 完全一致的 Markdown-lite 转换 */
function markdownToHtml(text: string): string {
  const html = escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
  return `<p>${html}</p>`
}

function addChatMessage(role: 'user' | 'ai', text: string): void {
  messages.value.push({ id: ++msgId, role, html: markdownToHtml(text), followUps: [] })
  scrollToBottom()
}

function scrollToBottom(): void {
  nextTick(() => {
    const el = messagesEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

/** 追问建议挂在最后一条 AI 消息上（旧版：移除旧追问再追加到末尾） */
function attachFollowUps(followUps: Suggestion[]): void {
  for (const m of messages.value) m.followUps = []
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'ai') last.followUps = followUps
  scrollToBottom()
}

// ============ 发送消息 ============
async function sendMessage(question: string): Promise<void> {
  if (!question || sending.value) return
  inputText.value = ''
  sending.value = true
  addChatMessage('user', question)
  waiting.value = true

  const cid = store.currentClassId
  const hwTypeId = store.currentHomeworkTypeId || 0

  try {
    const res = (await aiChat(question, cid, hwTypeId)) as { code: number; msg?: string; data: AIChatData | null }
    waiting.value = false

    if (res.code === 0 && res.data) {
      // 兼容旧格式：reply 中可能仍带 ---VIZ--- 分隔（后端已拆分，此处兜底处理，逻辑逐字保留）
      let reply = res.data.reply || ''
      let vizHtml = res.data.viz_html || null
      const vizSplit = reply.split(/\n?---VIZ---\n?/)
      if (vizSplit.length === 2) {
        reply = vizSplit[0].trim()
        const vizRaw = vizSplit[1].trim()
        const htmlMatch = vizRaw.match(/```html?\s*\n(.*?)\n```/s)
        if (htmlMatch) {
          vizHtml = htmlMatch[1].trim()
        } else if (vizRaw[0] === '<') {
          vizHtml = vizRaw
        }
      }

      addChatMessage('ai', reply)

      // 保存 export_data 供导出使用
      lastExportData.value = res.data.export_data || null
      lastReply.value = reply
      lastVizHtml.value = vizHtml

      // 优先使用 LLM 生成的 HTML 可视化面板
      if (vizHtml) {
        renderVizHTML(vizHtml)
      } else if (res.data.chart) {
        renderECharts(res.data.chart)
      }

      // 显示追问建议
      if (res.data.follow_ups && res.data.follow_ups.length > 0) {
        attachFollowUps(res.data.follow_ups)
      }

      // 显示导出按钮
      exportData.value = lastExportData.value
    } else {
      if (res.data && res.data.reply) {
        addChatMessage('ai', res.data.reply)
      } else {
        addChatMessage('ai', `❌ ${res.msg ?? ''}\n\n> 💡 提示：请先在「⚙️ 设置」中配置 AI 服务。`)
      }
    }
  } catch {
    waiting.value = false
    addChatMessage('ai', '❌ 网络请求失败，请检查网络连接。')
  }

  sending.value = false
  nextTick(() => inputEl.value?.focus())

  // 每次对话后刷新建议
  loadSuggestions()
}

function onSend(): void {
  sendMessage(inputText.value.trim())
}

function onQuickAsk(text: string): void {
  sendMessage(text)
}

function onFollowUp(text: string): void {
  sendMessage(text)
}

// ============ 提问建议 ============
async function loadSuggestions(): Promise<void> {
  const cid = store.currentClassId
  const hwTypeId = store.currentHomeworkTypeId || 0
  suggestionsLoading.value = true
  try {
    const res = (await loadAISuggestions(cid, hwTypeId)) as { code: number; data: { suggestions: Suggestion[] } | null }
    if (res.code === 0 && res.data?.suggestions) {
      suggestions.value = res.data.suggestions
    } else {
      suggestions.value = [...DEFAULT_SUGGESTIONS]
    }
  } catch {
    // 加载失败，保留默认按钮
    suggestions.value = [...DEFAULT_SUGGESTIONS]
  }
  suggestionsLoading.value = false
}

// ============ HTML 可视化面板渲染（iframe 沙箱，与旧版 renderVizHTML 一致） ============
function disposeChart(): void {
  if (currentChart) {
    try { currentChart.dispose() } catch { /* ignore */ }
    currentChart = null
  }
}

function revokeBlob(): void {
  if (blobUrl.value) {
    try { URL.revokeObjectURL(blobUrl.value) } catch { /* ignore */ }
    blobUrl.value = ''
  }
}

function renderVizHTML(vizHtml: string): void {
  const frame = vizFrameEl.value
  if (!frame) return

  // 销毁旧的 ECharts 实例
  disposeChart()
  echartsVisible.value = false

  // 构建完整的 HTML 文档（CSP 阻止外部 CDN 脚本；echarts 由 parent 注入）
  const fullDoc = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #f8f6f5; color: #4a4543; padding: 16px; overflow-y: auto; }
body::-webkit-scrollbar { width: 4px; }
body::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { background: #7EB5D6; color: #fff; padding: 8px 10px; text-align: left; font-weight: 600; }
td { padding: 7px 10px; border-bottom: 1px solid #eee; }
tr:hover td { background: #f0f7fb; }
</style>
</head>
<body>
<script>
window._ctErrors = [];
window.addEventListener("error", function(e) {
  window._ctErrors.push((e.message||"") + " @ " + (e.filename||"inline") + ":" + (e.lineno||""));
  if (parent && parent.console) parent.console.error("[AI-Viz]", e.message);
});
try {
  if (parent && parent.echarts) window.echarts = parent.echarts;
} catch(_) {}
document.addEventListener("DOMContentLoaded", function() {
  if (typeof echarts !== "undefined") {
    window.dispatchEvent(new Event("echartsReady"));
  }
});
if (typeof echarts === "undefined") {
  var __t = 0, __fired = false;
  var __id = setInterval(function() {
    if (typeof echarts !== "undefined" && !__fired) {
      __fired = true; clearInterval(__id);
      window.dispatchEvent(new Event("echartsReady"));
      window.dispatchEvent(new Event("load"));
      if (typeof window.onload === "function") try { window.onload(); } catch(_) {}
    }
    if (++__t > 120) { clearInterval(__id); console.warn("ECharts unavailable"); }
  }, 50);
}
<\/script>
<div id="viz-root">
${vizHtml}
</div>
</body>
</html>`

  // 使用 Blob URL 加载，确保 echarts 注入时机正确；先移除旧 URL
  revokeBlob()
  const blob = new Blob([fullDoc], { type: 'text/html' })
  blobUrl.value = URL.createObjectURL(blob)

  // 显示 iframe，隐藏占位符
  vizVisible.value = true
  placeholderVisible.value = false

  // 更新标题
  chartHeader.value = '📊 数据可视化'
}

/** iframe 加载完成后注入 echarts 作为兜底，并延迟清理 Blob URL */
function onVizFrameLoad(): void {
  const frame = vizFrameEl.value
  if (frame && frame.contentWindow) {
    try {
      ;(frame.contentWindow as unknown as Record<string, unknown>).echarts = echarts
    } catch { /* ignore */ }
  }
  const url = blobUrl.value
  if (url) {
    setTimeout(() => {
      if (blobUrl.value === url) {
        try { URL.revokeObjectURL(url) } catch { /* ignore */ }
        blobUrl.value = ''
      }
    }, 1000)
  }
}

// ============ ECharts 渲染（兜底方案：当 LLM 未生成 HTML 时使用） ============
function buildDefaultChartOption(spec: ChartSpec): Record<string, any> {
  // 本地兜底：当服务端返回的 option 为空时使用
  const macaronColors = ['#7EB5D6', '#E8A0BF', '#A8D5BA', '#F4C97E', '#C4B5D6', '#F0B8A0', '#8EC8C0', '#D4A8C8']
  const type = spec.type || 'bar'
  const title = spec.title || ''
  return {
    title: { text: title, left: 'center', top: 10, textStyle: { fontSize: 15, fontWeight: 'bold', color: '#5D5A5A' } },
    tooltip: { trigger: type === 'pie' ? 'item' : 'axis' },
    color: macaronColors,
    grid: type !== 'pie' ? { left: '3%', right: '5%', bottom: '8%', top: '15%', containLabel: true } : undefined,
    animation: true,
    animationDuration: 800,
  }
}

function onChartResize(): void {
  try { currentChart?.resize() } catch { /* ignore */ }
}

function renderECharts(spec: ChartSpec): void {
  // 隐藏 iframe，使用直接 ECharts 渲染
  vizVisible.value = false
  placeholderVisible.value = false

  // 更新图表标题
  if (spec.title) {
    chartHeader.value = `📊 ${spec.title}`
  }

  disposeChart()
  echartsVisible.value = true

  nextTick(() => {
    const dom = chartDomEl.value
    if (!dom || !echartsVisible.value) return
    try {
      const chart = echarts.init(dom)
      currentChart = chart
      const option = spec.option || buildDefaultChartOption(spec)
      if (!option.tooltip) {
        option.tooltip = { trigger: spec.type === 'pie' ? 'item' : 'axis' }
      }
      chart.setOption(option, true)

      chart.off('click')
      chart.on('click', (params: any) => {
        let question = ''
        const chartType = spec.type || 'bar'
        if (chartType === 'pie') {
          question = `哪些学生的等级是${params.name}？`
        } else if (chartType === 'bar') {
          question = params.name ? `查看${params.name}的详细情况` : ''
        } else if (chartType === 'line' && params.name) {
          question = `${params.name}那天各组的作业情况是怎样的？`
        }
        if (question) {
          inputText.value = question
          sendMessage(question)
        }
      })

      window.addEventListener('resize', onChartResize)
    } catch (e) {
      console.error('ECharts render failed:', (e as Error).message)
    }
  })
}

// ============ 导出按钮 ============
async function onExportExcel(): Promise<void> {
  if (!lastExportData.value || exporting.value) return
  exporting.value = 'excel'
  try {
    const resp = await http.post(
      '/ai/export/excel',
      { export_data: lastExportData.value, title: 'AI分析报告' },
      { responseType: 'blob' },
    )
    const blob = resp.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'AI分析报告.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('✅ Excel 已下载')
  } catch {
    ElMessage.error('❌ 导出失败')
  }
  exporting.value = ''
}

async function onExportWord(): Promise<void> {
  if (!lastExportData.value || exporting.value) return
  exporting.value = 'word'
  try {
    const resp = await http.post(
      '/ai/export/word',
      {
        export_data: lastExportData.value,
        reply: lastReply.value || '',
        viz_html: lastVizHtml.value || '',
      },
      { responseType: 'blob' },
    )
    const blob = resp.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'AI分析报告.doc'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('✅ Word 已下载')
  } catch {
    ElMessage.error('❌ 导出失败')
  }
  exporting.value = ''
}

// ============ 考试 Excel 上传与处理 ============
function onPickExam(): void {
  examFileInput.value?.click()
}

async function onExamFileChange(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploading.value = true
  try {
    const res = (await aiImportExam(file, store.currentClassId)) as { code: number; msg?: string; data: ExamResult | null }
    if (res.code === 0 && res.data) {
      ElMessage.success(`✅ ${res.msg}`)
      showExamPreview(res.data)
      examBarData.value = res.data
    } else {
      ElMessage.error(`❌ ${res.msg}`)
    }
  } catch (err) {
    // HTTP 错误(400)拦截器已 toast 后端 msg，此处仅处理纯网络错误
    if (!axios.isAxiosError(err) || !err.response) {
      ElMessage.error('❌ 上传失败，请检查网络')
    }
  }
  uploading.value = false
  input.value = ''
}

/** 页面加载时检查是否有缓存数据 */
async function checkExistingExamData(): Promise<void> {
  try {
    const res = (await aiExamData(store.currentClassId)) as { code: number; data: ExamCache | null }
    if (res.code === 0 && res.data?.data) {
      examBarData.value = res.data.data
    }
  } catch { /* ignore */ }
}

/** 清除考试数据 */
async function onClearExam(): Promise<void> {
  try { await aiExamDataClear(store.currentClassId) } catch { /* ignore */ }
  examBarData.value = null
  ElMessage.success('🗑 考试数据已清除')
}

// ---- 考试数据预览 ----
const previewHtml = computed(() => buildPreviewHtml(previewData.value))

function showExamPreview(examData: ExamResult): void {
  previewData.value = examData
  examPreviewVisible.value = true
}

function buildPreviewHtml(examData: ExamResult | null): string {
  if (!examData) return ''
  let html =
    '<div style="margin-bottom:8px;color:#999595;font-size:.82rem">已识别 <strong>' + examData.total_students +
    '</strong> 名学生，<strong>' + examData.classes.length +
    '</strong> 个班级/组别 · 识别列: ' + (examData.detected_columns || []).join(', ') + '</div>'

  for (const cls of examData.classes) {
    const st = cls.stats || {}
    html +=
      '<div class="exam-preview-class">' +
      '<div class="exam-preview-class-header">' +
      '<span>📊</span> ' + escapeHtml(cls.class_name) +
      '<span style="font-weight:400;font-size:.78rem;margin-left:auto">' + cls.student_count +
      '人 · 均分 ' + cls.avg_score + ' · 最高 ' + cls.max_score + ' · 最低 ' + cls.min_score + '</span>' +
      '</div>' +
      '<div class="exam-preview-class-body">' +
      '<div class="exam-preview-stats">' +
      '<span>⭐ A(≥90): ' + (st.A || 0) + '人</span>' +
      '<span>🔵 B(≥75): ' + (st.B || 0) + '人</span>' +
      '<span>🟡 C(≥60): ' + (st.C || 0) + '人</span>' +
      '<span>🔴 未达标: ' + (st.X || 0) + '人</span>' +
      '</div>' +
      '<table style="width:100%;font-size:.78rem;border-collapse:collapse">' +
      '<tr style="border-bottom:1px solid #eee"><th style="text-align:left;padding:4px">姓名</th><th>学号</th><th>分数</th><th>等第</th></tr>'

    const students = cls.students || []
    const showCount = Math.min(students.length, 15)
    for (let j = 0; j < showCount; j++) {
      const s = students[j]
      const gColor =
        s.grade === 'A' ? '#7EB5D6' : s.grade === 'B' ? '#A8D5BA' : s.grade === 'C' ? '#F4C97E' : s.grade === 'L' ? '#C5B3E6' : '#E8A0BF'
      const gLabel = s.grade === 'X' ? '未交' : s.grade === 'L' ? '请假' : s.grade
      html +=
        '<tr><td style="padding:3px 4px">' + escapeHtml(s.name) + '</td>' +
        '<td style="color:#999595">' + escapeHtml(s.code || '-') + '</td>' +
        '<td>' + (s.score_display || '-') + '</td>' +
        '<td><span style="background:' + gColor + ';color:#fff;padding:1px 6px;border-radius:8px;font-size:.7rem;font-weight:600">' + gLabel + '</span></td></tr>'
    }
    if (students.length > showCount) {
      html +=
        '<tr><td colspan="4" style="text-align:center;color:#BFBBBB;padding:4px">... 还有 ' +
        (students.length - showCount) + ' 名学生</td></tr>'
    }
    html += '</table></div></div>'
  }
  return html
}

// ---- 登记成绩弹窗 ----
function showExamApplyModal(): void {
  // 填充日期
  const today = new Date().toISOString().split('T')[0]
  applyDate.value = today

  // 填充班级选项（仅首次）
  if (applyClasses.value.length === 0) {
    aiExamData(store.currentClassId)
      .then((res: { code: number; data: ExamCache | null }) => {
        if (res.code === 0 && res.data?.data) {
          applyClasses.value = res.data.data.classes || []
        }
      })
      .catch(() => { /* ignore */ })
  }

  // 填充作业种类（仅首次）
  if (applyHwTypes.value.length === 0) {
    loadHomeworkTypes()
      .then((res: { code: number; data: HomeworkType[] }) => {
        if (res.code === 0) {
          applyHwTypes.value = res.data || []
        }
      })
      .catch(() => { /* ignore */ })
  }

  applyStatusHtml.value = ''
  examApplyVisible.value = true
}

function onExamApplyNow(): void {
  examPreviewVisible.value = false
  showExamApplyModal()
}

async function onExamApplyConfirm(): Promise<void> {
  applying.value = true
  applyStatusHtml.value = ''
  try {
    const res = await aiImportExamApply({
      date: applyDate.value,
      class_name: applyClassName.value,
      class_id: store.currentClassId,
      homework_type_id: Number(applyHwTypeId.value) || 0,
    })
    if (res.code === 0) {
      applyStatusHtml.value = `<span style="color:#2d8a56">✅ ${res.msg}</span>`
      ElMessage.success(`✅ ${res.msg}`)
      setTimeout(() => { examApplyVisible.value = false }, 1500)
    } else {
      applyStatusHtml.value = `<span style="color:#c0392b">❌ ${res.msg}</span>`
    }
  } catch (err) {
    if (axios.isAxiosError(err) && err.response) {
      const msg = (err.response.data as { msg?: string } | undefined)?.msg
      if (msg) {
        applyStatusHtml.value = `<span style="color:#c0392b">❌ ${msg}</span>`
      } else {
        applyStatusHtml.value = '<span style="color:#c0392b">❌ 请求失败</span>'
      }
    } else {
      applyStatusHtml.value = '<span style="color:#c0392b">❌ 请求失败</span>'
    }
  }
  applying.value = false
}

// ============ 班级切换时重置 AI 上下文（与旧版 resetAIContext 一致） ============
function resetAIContext(): void {
  // 清空聊天记录
  messages.value = [{ id: ++msgId, role: 'ai', html: WELCOME_SWITCH_HTML, followUps: [] }]

  // 清除图表
  vizVisible.value = false
  revokeBlob()
  disposeChart()
  placeholderVisible.value = true
  echartsVisible.value = false

  // 清除导出数据
  lastExportData.value = null
  lastReply.value = ''
  lastVizHtml.value = null
  exportData.value = null

  // 重新加载提问建议
  loadSuggestions()
}

watch(() => store.currentClassId, () => { resetAIContext() })
watch(() => store.currentHomeworkTypeId, () => { loadSuggestions() })

// ============ 生命周期 ============
onMounted(() => {
  messages.value = [{ id: ++msgId, role: 'ai', html: WELCOME_HTML, followUps: [] }]
  initAIConfigCheck()
  checkExistingExamData()
  loadSuggestions()
})

/** 检查 AI 是否已配置，未配置显示引导文案 */
async function initAIConfigCheck(): Promise<void> {
  try {
    const res = (await loadAIConfig()) as { code: number; data: { has_key: boolean } | null }
    if (res.code === 0 && res.data && !res.data.has_key) {
      addChatMessage('ai', '💡 提示：请先在「⚙️ 设置」中配置 AI 服务。')
    }
  } catch { /* ignore */ }
}

onBeforeUnmount(() => {
  disposeChart()
  revokeBlob()
  window.removeEventListener('resize', onChartResize)
})
</script>

<style scoped>
.ai-chat-container {
  --blue: #7eb5d6;
  --text: #5d5a5a;
  --text-light: #999595;
  --text-lighter: #bfbbbb;
  --radius: 20px;
  --radius-sm: 14px;
  --transition-fast: 0.1s cubic-bezier(0.25, 0.1, 0.25, 1);
  display: flex;
  gap: 16px;
  height: calc(100vh - 200px);
  min-height: 500px;
}
.ai-chat-left {
  flex: 1;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(10px) saturate(1.3);
  -webkit-backdrop-filter: blur(10px) saturate(1.3);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--radius);
  overflow: hidden;
}
.ai-chat-right {
  flex: 1;
  min-width: 300px;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(10px) saturate(1.3);
  -webkit-backdrop-filter: blur(10px) saturate(1.3);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ai-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ai-chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid rgba(200, 190, 185, 0.12);
  display: flex;
  gap: 8px;
  align-items: center;
  background: rgba(255, 255, 255, 0.3);
}
.ai-chat-text {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 20px;
  font-size: 0.88rem;
  font-family: inherit;
  color: var(--text);
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  outline: none;
  transition: border-color var(--transition-fast);
}
.ai-chat-text:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(126, 181, 214, 0.12);
}
.ai-send-btn {
  padding: 10px 18px;
  border: none;
  border-radius: 20px;
  background: var(--blue);
  color: #fff;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: transform var(--transition-fast), opacity var(--transition-fast);
  white-space: nowrap;
}
.ai-send-btn:hover {
  background: #6ba5c4;
  transform: translateY(-1px);
}
.ai-send-btn:active {
  transform: scale(0.97);
}
.ai-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
.ai-hw-select {
  max-width: 130px;
  padding: 6px 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 16px;
  font-size: 0.78rem;
  font-family: inherit;
  color: var(--text);
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  outline: none;
  cursor: pointer;
}

/* 聊天气泡 */
.ai-msg {
  max-width: 90%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 0.85rem;
  line-height: 1.55;
  animation: aiMsgIn 0.3s ease-out;
}
@keyframes aiMsgIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.ai-msg-user {
  align-self: flex-end;
  background: var(--blue);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.ai-msg-ai {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.75);
  color: var(--text);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.ai-msg-ai :deep(p) { margin: 0 0 6px 0; }
.ai-msg-ai :deep(p:last-child) { margin-bottom: 0; }
.ai-msg-ai :deep(strong) { color: var(--text); }
.ai-msg-ai :deep(em) { color: var(--text-light); }
.ai-msg-loading {
  align-self: flex-start;
  display: flex;
  gap: 4px;
  padding: 12px 16px;
}
.ai-msg-loading span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-lighter);
  animation: aiDot 1.4s ease-in-out infinite;
}
.ai-msg-loading span:nth-child(2) { animation-delay: 0.2s; }
.ai-msg-loading span:nth-child(3) { animation-delay: 0.4s; }
@keyframes aiDot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 快捷提问按钮 */
.ai-quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 16px;
  border-top: 1px solid rgba(200, 190, 185, 0.08);
}
.suggestions-loading {
  color: var(--text-lighter);
  font-size: 0.78rem;
}
.ai-quick-btn {
  padding: 5px 12px;
  border: 1px solid rgba(126, 181, 214, 0.3);
  border-radius: 14px;
  background: rgba(126, 181, 214, 0.08);
  color: var(--blue);
  font-size: 0.78rem;
  cursor: pointer;
  font-family: inherit;
  transition: transform var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
  white-space: nowrap;
}
.ai-quick-btn:hover {
  background: rgba(126, 181, 214, 0.18);
  border-color: var(--blue);
}

/* 追问区 */
.ai-follow-ups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 16px 10px 16px;
  align-self: flex-start;
  max-width: 90%;
  animation: aiMsgIn 0.35s ease-out;
}
.follow-label {
  font-size: 0.75rem;
  color: var(--text-lighter);
  width: 100%;
  margin-bottom: 2px;
}
.follow-chip {
  font-size: 0.78rem;
  padding: 5px 10px;
  border-radius: 12px;
  cursor: pointer;
}

/* 考试上传条 */
.ai-exam-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(168, 213, 186, 0.15);
  border-bottom: 1px solid rgba(168, 213, 186, 0.25);
  font-size: 0.78rem;
  color: var(--text);
}
.ai-exam-icon { font-size: 1rem; }
.ai-exam-info { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.exam-btn {
  font-size: 0.7rem;
  padding: 2px 8px;
  margin-left: auto;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: inherit;
}
.exam-btn-outline {
  background: transparent;
  border: 2px solid rgba(0, 0, 0, 0.06);
  color: var(--text-light);
}
.exam-btn-outline:hover { border-color: var(--blue); color: var(--blue); }
.exam-btn-export {
  margin-left: 0;
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.6), rgba(142, 200, 224, 0.65));
  color: white;
  border: none;
  box-shadow: 0 2px 12px rgba(126, 181, 214, 0.22);
}
.exam-btn-export:hover { transform: translateY(-1px); }
.btn-upload-exam {
  width: 34px;
  height: 34px;
  border: 1px dashed rgba(126, 181, 214, 0.4);
  border-radius: 50%;
  background: rgba(126, 181, 214, 0.06);
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
  flex-shrink: 0;
}
.btn-upload-exam:hover {
  background: rgba(126, 181, 214, 0.15);
  border-color: var(--blue);
  transform: scale(1.05);
}

/* 图表区域 */
.ai-chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(200, 190, 185, 0.12);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
}
.ai-chart-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
.ai-viz-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #f8f6f5;
  display: block;
}
.ai-echarts-dom {
  width: 100%;
  height: 100%;
}
.ai-chart-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-lighter);
  font-size: 0.9rem;
  gap: 8px;
}
.ai-chart-placeholder .placeholder-icon {
  font-size: 3rem;
  opacity: 0.5;
}
.ai-chart-placeholder p { margin: 0; }
.placeholder-sub {
  font-size: 0.75rem;
  color: var(--text-lighter);
}

/* 导出按钮条 */
.ai-export-bar {
  display: flex;
  gap: 6px;
  padding: 8px 12px;
  justify-content: flex-end;
  border-top: 1px solid rgba(200, 190, 185, 0.12);
  background: rgba(255, 255, 255, 0.3);
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 10;
  animation: aiMsgIn 0.3s ease-out;
}
.exp-btn {
  font-size: 0.75rem;
  padding: 4px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.6), rgba(142, 200, 224, 0.65));
  color: white;
  cursor: pointer;
  font-family: inherit;
  box-shadow: 0 2px 12px rgba(126, 181, 214, 0.22);
}
.exp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 考试预览 */
.preview-content :deep(.exam-preview-class) {
  margin-bottom: 12px;
  border: 1px solid rgba(200, 190, 185, 0.15);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.preview-content :deep(.exam-preview-class-header) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(126, 181, 214, 0.08);
  font-weight: 600;
  font-size: 0.88rem;
}
.preview-content :deep(.exam-preview-class-body) {
  padding: 8px 14px;
  max-height: 240px;
  overflow-y: auto;
}
.preview-content :deep(.exam-preview-stats) {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 6px 0;
  font-size: 0.78rem;
  color: var(--text-light);
}
.preview-tip {
  font-size: 0.78rem;
  color: var(--text-light);
  margin-left: auto;
  display: flex;
  align-items: center;
}

/* 登记成绩弹窗 */
.apply-desc {
  font-size: 0.85rem;
  color: var(--text-light);
  margin: 0 0 12px;
}
.apply-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.apply-row label {
  flex: 0 0 100px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-light);
  text-align: right;
  white-space: nowrap;
}
.apply-input,
.apply-select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-family: inherit;
  color: var(--text);
  background: rgba(255, 255, 255, 0.7);
  outline: none;
}
.apply-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}
.apply-status {
  font-size: 0.78rem;
  color: var(--text-light);
  margin-left: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .ai-chat-container {
    flex-direction: column;
    height: auto;
  }
  .ai-chat-left,
  .ai-chat-right {
    min-width: auto;
    min-height: 300px;
  }
}
</style>
