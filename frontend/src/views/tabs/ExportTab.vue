<template>
  <div class="export-tab">
    <!-- ========== 1. 筛选条件 ========== -->
    <div class="ct-card export-filter-card">
      <div class="card-header"><span class="card-icon">🔍</span><h3>筛选条件</h3></div>
      <div class="export-filter-body">
        <div class="filter-row">
          <label class="filter-label">📅 起始：</label>
          <input v-model="startDate" type="date" class="date-input">
          <label class="filter-label">结束：</label>
          <input v-model="endDate" type="date" class="date-input">
          <GlassButton @click="queryRecords">🔍 查询</GlassButton>
        </div>
        <div class="filter-result">
          <span class="result-text">共 <strong>{{ resultTotal }}</strong> 条</span>
        </div>
      </div>
    </div>

    <!-- ========== 2. 导出报表 ========== -->
    <div class="ct-card export-action-card">
      <div class="card-header"><span class="card-icon">📤</span><h3>导出报表</h3></div>
      <div class="export-action-body">
        <div class="export-option">
          <div class="export-option-info">
            <h4>📄 单学生台账</h4>
            <p>导出指定学生在日期区间内的所有记录</p>
          </div>
          <div class="export-option-action">
            <el-select
              v-model="selectedStudentId"
              class="student-select"
              placeholder="-- 请选择学生 --"
            >
              <el-option
                v-for="o in studentOptions"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
            <GlassButton @click="exportStudent"><span>📥</span> 导出</GlassButton>
            <GlassButton :disabled="aiLoading" @click="onGenerateComment">
              <span>{{ aiLoading ? '⏳ 生成中...' : '🤖 AI 生成评语' }}</span>
            </GlassButton>
          </div>
        </div>
        <div class="export-divider"></div>
        <div class="export-option">
          <div class="export-option-info">
            <h4>📊 全班汇总</h4>
            <p>导出全班学生在日期区间内的所有记录及统计</p>
          </div>
          <div class="export-option-action">
            <GlassButton @click="exportClass"><span>📥</span> 导出全班汇总</GlassButton>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 3. 数据预览 ========== -->
    <div v-if="previewRecords.length > 0" class="ct-card preview-card">
      <div class="card-header">
        <span class="card-icon">📋</span><h3>数据预览</h3>
        <span class="preview-count">共 {{ previewRecords.length }} 条</span>
      </div>
      <div class="table-wrapper">
        <table class="preview-table">
          <thead>
            <tr><th>学生姓名</th><th>所属分组</th><th>登记日期</th><th>作业评级</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in previewRows" :key="r.id">
              <td :class="{ 'privacy-mode': store.displayMode === 'code' }">{{ rowDisplayName(r) }}</td>
              <td>{{ r.group_name }}</td>
              <td>{{ r.date }}</td>
              <td>
                <span class="grade-badge" :class="`grade-${(r.grade || 'x').toLowerCase()}`">{{ r.grade_label }}</span>
              </td>
            </tr>
            <tr v-if="hasMore">
              <td colspan="4" class="preview-more">仅显示前200条，完整数据请导出Excel</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ========== AI 评语弹窗(照旧 ai.js showCommentModal) ========== -->
    <GlassDialog v-model="commentVisible" title="🤖 AI 评语" width="520px" append-to-body>
      <div v-if="commentData" class="comment-body">
        <div class="comment-stats">
          <div class="comment-stat"><strong>{{ commentData.student_name }}</strong></div>
          <div class="comment-stat">📝 共 {{ commentData.stats.total }} 次</div>
          <div class="comment-stat">⭐ A率 {{ commentData.stats.a_rate }}%</div>
          <div class="comment-stat">✅ 提交率 {{ commentData.stats.submit_rate }}%</div>
          <div v-if="commentData.stats.consecutive_x >= 2" class="comment-stat comment-warn">
            ⚠️ 连续{{ commentData.stats.consecutive_x }}天未交
          </div>
        </div>
        <div class="comment-content">{{ commentData.comment }}</div>
        <div class="comment-actions">
          <GlassButton type="primary" plain @click="onCopyComment">📋 复制评语</GlassButton>
        </div>
      </div>
    </GlassDialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 报表导出 Tab — 日期区间查询 / 单学生台账 / 全班汇总 / AI 评语 / 数据预览。
 * 对应旧版 app.js prepareExportTab~exportClass(1764-1817)与 templates/index.html tabExport(567-614)。
 */
import GlassDialog from '@/components/GlassDialog.vue'
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { loadHomeworkRange, aiComment, downloadUrl, type ApiResponse } from '@/api'

const store = useAppStore()

// ---- 类型 ----
interface RangeRecord {
  id: number
  student_id: number
  student_name: string
  date: string
  grade: string
  grade_label: string
  group_name: string
}

interface CommentStats {
  total: number
  A: number
  B: number
  C: number
  X: number
  a_rate: number
  submit_rate: number
  consecutive_x: number
}

interface CommentData {
  student_name: string
  comment: string
  stats: CommentStats
}

// ---- 日期区间(与学生个人报表弹窗共享,读写 store.exportStartDate/exportEndDate) ----
const startDate = computed({
  get: () => store.exportStartDate,
  set: (v: string) => { store.exportStartDate = v },
})
const endDate = computed({
  get: () => store.exportEndDate,
  set: (v: string) => { store.exportEndDate = v },
})

const resultTotal = ref(0)
const previewRecords = ref<RangeRecord[]>([])
const selectedStudentId = ref<number | null>(null)
const aiLoading = ref(false)
const commentVisible = ref(false)
const commentData = ref<CommentData | null>(null)

const previewRows = computed(() => previewRecords.value.slice(0, 200))
const hasMore = computed(() => previewRecords.value.length > 200)

const studentCodeMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {}
  for (const s of store.students) map[s.id] = s.student_code || ''
  return map
})

// ---- 显示模式感知的学生选项:姓名 + [学号] + [组名](照旧 1764-1775) ----
const studentOptions = computed<{ value: number; label: string }[]>(() =>
  store.students.map((s) => {
    const displayName = store.displayMode === 'code' ? (s.student_code || '???') : s.name
    const codeLabel = store.displayMode !== 'code' && s.student_code ? `[${s.student_code}] ` : ''
    const groupLabel = s.group_name ? ` [${s.group_name}]` : ''
    return { value: s.id, label: `${codeLabel}${displayName}${groupLabel}` }
  }),
)

// ---- 日期工具 ----
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

onMounted(() => {
  // 默认区间:今天往前 30 天(照旧 1764-1767)
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  store.exportStartDate = toDateStr(start)
  store.exportEndDate = toDateStr(end)
})

// ---- 查询(照旧 1777-1785) ----
async function queryRecords(): Promise<void> {
  const start = startDate.value
  const end = endDate.value
  if (!start || !end) { ElMessage.error('请选择日期范围'); return }
  if (start > end) { ElMessage.error('起始日期不能晚于结束日期'); return }
  try {
    const res = await loadHomeworkRange(start, end, store.currentClassId)
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    resultTotal.value = res.total || 0
    previewRecords.value = (res.data || []) as RangeRecord[]
  } catch { /* 拦截器已提示 */ }
}

function rowDisplayName(r: RangeRecord): string {
  const code = studentCodeMap.value[r.student_id] || ''
  return store.displayMode === 'code' ? (code || '???') : r.student_name
}

// ---- 导出(照旧 1804-1816) ----
function exportStudent(): void {
  const sid = selectedStudentId.value
  if (!sid) { ElMessage.error('请选择学生'); return }
  window.open(
    downloadUrl(`/export/student/${sid}`, {
      class_id: store.currentClassId,
      start: startDate.value,
      end: endDate.value,
    }),
    '_blank',
  )
}

function exportClass(): void {
  window.open(
    downloadUrl('/export/class', {
      class_id: store.currentClassId,
      start: startDate.value,
      end: endDate.value,
    }),
    '_blank',
  )
}

// ---- AI 生成评语(照旧 ai.js 1131-1214) ----
async function onGenerateComment(): Promise<void> {
  const sid = selectedStudentId.value
  if (!sid) { ElMessage.error('⚠️ 请先选择一名学生'); return }
  aiLoading.value = true
  try {
    const res: ApiResponse<CommentData> = await aiComment(sid, store.currentClassId)
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    commentData.value = res.data ?? null
    commentVisible.value = true
  } catch { /* 拦截器已提示 */ } finally {
    aiLoading.value = false
  }
}

async function onCopyComment(): Promise<void> {
  if (!commentData.value) return
  try {
    await navigator.clipboard.writeText(commentData.value.comment)
    ElMessage.success('📋 评语已复制到剪贴板')
  } catch {
    ElMessage.error('⚠️ 复制失败，请手动复制')
  }
}

watch(
  () => store.currentClassId,
  () => {
    selectedStudentId.value = null
    if (startDate.value && endDate.value) void queryRecords()
  },
)
</script>

<style scoped>
.export-filter-card { margin-bottom: 12px; }
.export-action-card { margin-bottom: 12px; }
.preview-card { margin-bottom: 12px; }
.card-header { display: flex; align-items: center; gap: 8px; padding-bottom: 10px; }
.card-header h3 { font-size: .95rem; font-weight: 600; color: #3a4a5a; margin: 0; }
.card-icon { font-size: 1.1rem; }
.export-filter-body { display: flex; flex-direction: column; gap: 10px; }
.filter-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-label { font-size: .84rem; color: #3a4a5a; font-weight: 600; }
.filter-result { padding: 2px 0; }
.result-text { font-size: .84rem; color: #5a6775; }
.result-text strong { color: var(--el-color-primary); font-size: 1.05rem; }

.date-input {
  padding: 6px 10px; border: 1px solid rgba(150, 160, 175, 0.3);
  border-radius: 8px; font-size: .85rem; background: rgba(255, 255, 255, 0.7);
  color: #3a4a5a; outline: none; font-family: inherit;
}
.date-input:focus { border-color: var(--el-color-primary); }

/* 通用玻璃按钮(液态玻璃风格) */
.btn {
  border: none; cursor: pointer; font-family: inherit;
  border-radius: 8px; color: #fff;
  transition: transform .2s ease, box-shadow .2s ease, background .2s ease, border-color .2s ease;
}
.btn:active { transform: scale(.97); }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.btn-sm { padding: 6px 14px; font-size: .82rem; border-radius: 8px; }
.btn-query {
  background: linear-gradient(135deg, rgba(196, 181, 214, 0.65), rgba(220, 208, 232, 0.7));
  color: #fff;
}
.btn-query:hover { background: linear-gradient(135deg, rgba(196, 181, 214, 0.8), rgba(220, 208, 232, 0.85)); }
.btn-export {
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.75), rgba(142, 200, 224, 0.8));
  box-shadow: 0 2px 12px rgba(126, 181, 214, 0.25);
}
.btn-export:hover {
  transform: scale(1.05);
  background: linear-gradient(135deg, #5BA0C0, #7EB5D6);
  box-shadow: 0 6px 28px rgba(100, 160, 200, 0.5);
}
.btn-export-all {
  background: linear-gradient(135deg, rgba(142, 200, 192, 0.65), rgba(160, 216, 208, 0.7));
  font-size: .92rem; padding: 9px 22px;
}
.btn-export-all:hover {
  transform: scale(1.05);
  background: linear-gradient(135deg, #6BB8AE, #8EC8C0);
  box-shadow: 0 6px 28px rgba(110, 190, 180, 0.45);
}
.btn-primary {
  background: linear-gradient(135deg, #E8A0BF, #D4789A);
  color: #fff; box-shadow: 0 2px 12px rgba(210, 120, 150, 0.3);
}
.btn-primary:hover {
  transform: scale(1.05);
  background: linear-gradient(135deg, #D4789A, #E890B0);
  box-shadow: 0 6px 28px rgba(210, 120, 150, 0.55);
}
.btn-ai { margin-left: 4px; }

/* 导出选项 */
.export-action-body { display: flex; flex-direction: column; }
.export-option {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 10px 0; flex-wrap: wrap;
}
.export-option-info h4 { font-size: .9rem; margin: 0 0 3px; color: #3a4a5a; }
.export-option-info p { font-size: .76rem; color: #5a6775; margin: 0; }
.export-option-action { display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; }
.student-select { min-width: 170px; }
.export-divider {
  height: 1px; border: none;
  background: linear-gradient(90deg, transparent, rgba(0, 0, 0, 0.06), transparent);
  margin: 2px 0;
}

/* 预览表格 */
.preview-count { font-size: .75rem; color: #9aa8b5; margin-left: auto; }
.table-wrapper { overflow: auto; max-height: 350px; -webkit-overflow-scrolling: touch; }
.preview-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.preview-table thead { position: sticky; top: 0; z-index: 1; }
.preview-table th {
  background: rgba(255, 255, 255, 0.7); padding: 9px 14px;
  text-align: left; font-weight: 700; font-size: .78rem;
  color: #5a6775; border-bottom: 2px solid rgba(0, 0, 0, 0.05);
}
.preview-table td { padding: 8px 14px; border-bottom: 1px solid rgba(0, 0, 0, 0.03); color: #3a4a5a; }
.preview-table tbody tr:hover { background: rgba(174, 207, 226, 0.25); }
.privacy-mode { font-family: monospace; letter-spacing: 1px; }
.preview-more { text-align: center; color: #9aa8b5; }

/* AI 评语弹窗 */
.comment-body { display: flex; flex-direction: column; gap: 12px; }
.comment-stats { display: flex; gap: 8px; flex-wrap: wrap; }
.comment-stat {
  display: flex; align-items: center; gap: 4px;
  font-size: .8rem; color: #5a6775;
  background: rgba(255, 255, 255, 0.5); border: 1px solid rgba(150, 160, 175, 0.2);
  padding: 4px 10px; border-radius: 10px;
}
.comment-warn { color: #c0392b; }
.comment-content {
  padding: 14px 16px; font-size: .9rem; line-height: 1.8; color: #3a4a5a;
  background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(150, 160, 175, 0.2);
  border-radius: 10px; min-height: 80px; max-height: 260px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-word;
}
.comment-actions { display: flex; gap: 8px; }
</style>
