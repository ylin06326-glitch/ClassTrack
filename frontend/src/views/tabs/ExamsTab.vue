<template>
  <div class="exams-tab">
    <!-- ========== 1. 控制卡 ========== -->
    <div class="ct-card exam-control-card">
      <div class="exam-header-row">
        <span class="control-label">📋 考试名称：</span>
        <input
          v-model="examNameInput"
          type="text"
          class="exam-name-input"
          placeholder="如：第一单元测验"
          maxlength="30"
        >
        <span class="control-label">满分：</span>
        <input
          v-model="examTotalScoreInput"
          type="number"
          class="exam-total-input"
          min="1"
          max="999"
        >
        <GlassButton @click="onCreateOrSwitch">+ 新建/切换</GlassButton>
      </div>

      <div class="date-picker-area">
        <span class="control-label">📅 考试日期：</span>
        <GlassButton title="前一天" @click="navigateExamDate(-1)">◀</GlassButton>
        <input v-model="examDate" type="date" class="date-input" @change="onExamDateChange">
        <GlassButton title="后一天" @click="navigateExamDate(1)">▶</GlassButton>
        <GlassButton @click="onExamToday">📌 今天</GlassButton>
      </div>

      <div class="batch-area">
        <span class="batch-label">批量：</span>
        <GlassButton @click="onBatch(100)">满分</GlassButton>
        <GlassButton @click="onBatch(85)">85分</GlassButton>
        <GlassButton @click="onBatch(70)">70分</GlassButton>
        <GlassButton @click="onBatch(60)">60分</GlassButton>
        <GlassButton @click="onCustomBatch">自定义...</GlassButton>
      </div>

      <div class="exam-action-row">
        <GlassButton @click="onImportClick">📂 导入考试Excel</GlassButton>
        <GlassButton @click="onExportScores">📥 导出成绩</GlassButton>
        <span class="exam-count-info">{{ countInfo }}</span>
      </div>

      <!-- 隐藏的文件上传 input -->
      <input
        ref="examFileInputRef"
        type="file"
        accept=".xls,.xlsx"
        class="hidden-file-input"
        @change="onFileChange"
      >
    </div>

    <!-- ========== 2. 已有考试 ========== -->
    <div v-if="examList.length > 0" class="ct-card exam-list-card">
      <div class="card-header"><span class="card-icon">📋</span><h3>已有考试</h3></div>
      <div class="exam-list">
        <GlassButton v-for="e in examList"
 :key="`${e.exam_name}_${e.date}`"
 
 :class="{ active: isActiveExam(e) }"
 @click="onChipClick(e)"
>
          {{ e.exam_name }} <small>{{ e.date }}</small>
        </GlassButton>
      </div>
    </div>

    <!-- ========== 3. 成绩录入分组视图 ========== -->
    <div v-if="!contextName" class="empty-state">
      <span class="empty-icon">📊</span>
      <p>请输入考试名称和日期后开始录入成绩<br>或点击「导入考试Excel」批量导入</p>
    </div>
    <div v-else-if="store.students.length === 0 || store.groups.length === 0" class="empty-state">
      <span class="empty-icon">📊</span>
      <p>请先在「班级分组」中导入学生并完成分组</p>
    </div>
    <div v-else class="exam-groups">
      <div v-for="g in store.groups" :key="g.id" class="exam-group-column">
        <div class="hw-group-header" :style="{ borderLeft: `4px solid ${g.color}` }">
          <span class="group-name-dot" :style="{ background: g.color }"></span>
          <span>{{ g.name }}</span>
          <span class="group-count">{{ groupedStudents.get(g.id)?.length || 0 }}人</span>
        </div>
        <div class="exam-group-students">
          <div v-for="s in groupedStudents.get(g.id) || []" :key="s.id" class="exam-student-row">
            <span class="exam-student-name">
              <span v-if="store.displayMode !== 'code' && s.student_code" class="student-code-label">[{{ s.student_code }}]</span>
              <span :class="{ 'privacy-mode': store.displayMode === 'code' }">{{ studentDisplayName(s) }}</span>
            </span>
            <div class="score-input-area">
              <input
                type="number"
                class="exam-score-input"
                :value="scoreOf(s)"
                placeholder="分数"
                min="0"
                :max="currentTotalScore()"
                step="0.5"
                @change="onScoreChange(s, $event)"
              >
              <span class="exam-grade-badge" :class="gradeClassOf(s)">{{ gradeOf(s) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 4. 考试统计 ========== -->
    <div v-if="contextName && store.students.length > 0 && store.groups.length > 0" class="stats-cards">
      <div class="stat-card stat-card-total">
        <div class="stat-card-icon">👨‍🎓</div>
        <div class="stat-card-value">{{ examStats.total }}</div>
        <div class="stat-card-label">参考人数</div>
      </div>
      <div class="stat-card stat-card-submitted">
        <div class="stat-card-icon">📊</div>
        <div class="stat-card-value">{{ examStats.avg }}</div>
        <div class="stat-card-label">平均分</div>
      </div>
      <div class="stat-card stat-card-arate">
        <div class="stat-card-icon">🏆</div>
        <div class="stat-card-value">{{ examStats.max }}</div>
        <div class="stat-card-label">最高分</div>
      </div>
      <div class="stat-card">
        <div class="stat-card-icon">📉</div>
        <div class="stat-card-value">{{ examStats.min }}</div>
        <div class="stat-card-label">最低分</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 成绩管理 Tab — 考试上下文切换 / 分组成绩录入 / 批量 / 导入导出 / 统计。
 * 对应旧版 app.js setupExamManagement(2772-3066)与 templates/index.html tabExams(505-564)。
 */
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useDialogs } from '@/composables/dialogs'
import {
  loadExams, loadExamScores, saveExamScore, batchExamScores, importExamScores,
  downloadUrl, type ApiResponse, type Student,
} from '@/api'

const store = useAppStore()
const { confirm } = useDialogs()

// ---- 类型 ----
interface ExamInfo {
  exam_name: string
  date: string
  total_score: number
}

interface ExamRecord {
  id?: number
  student_id: number
  student_name?: string
  student_code?: string
  date?: string
  exam_name?: string
  score: number
  total_score?: number
  grade?: string
  group_id?: number
  group_name?: string
  group_color?: string
}

// ---- 考试上下文(经「新建/切换」或已有考试 chip 确认后生效) ----
const examNameInput = ref('')
const examDate = ref(todayStr())
const examTotalScoreInput = ref('100')
const contextName = ref('')
const examList = ref<ExamInfo[]>([])
const examRecords = ref<Record<string, ExamRecord>>({})
const examFileInputRef = ref<HTMLInputElement | null>(null)

// ---- 日期工具 ----
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}
function todayStr(): string {
  return toDateStr(new Date())
}
function parseDate(s: string): Date | null {
  const [y, m, d] = s.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

/** 等第计算(与后端一致):>=90 A / >=75 B / >=60 C / 其余 D */
function calcExamGrade(score: number, total: number): string {
  const pct = total > 0 ? (score / total) * 100 : 0
  if (pct >= 90) return 'A'
  if (pct >= 75) return 'B'
  if (pct >= 60) return 'C'
  return 'D'
}

function currentTotalScore(): number {
  const v = parseFloat(examTotalScoreInput.value)
  return isNaN(v) ? 100 : v
}

// ---- 分组学生视图 ----
const groupedStudents = computed<Map<number, Student[]>>(() => {
  const map = new Map<number, Student[]>()
  for (const g of store.groups) map.set(g.id, [])
  for (const s of store.students) {
    if (s.group_id && map.has(s.group_id)) map.get(s.group_id)!.push(s)
  }
  return map
})

function studentDisplayName(s: Student): string {
  return store.displayMode === 'code' ? (s.student_code || '???') : s.name
}
function scoreOf(s: Student): number | string {
  const r = examRecords.value[String(s.id)]
  return r ? r.score : ''
}
function gradeOf(s: Student): string {
  return examRecords.value[String(s.id)]?.grade || ''
}
function gradeClassOf(s: Student): string {
  const g = gradeOf(s)
  return g ? `grade-${g.toLowerCase()}` : ''
}

// ---- 统计(数据从当前录入缓存计算,照旧 2995-3006) ----
const examStats = computed(() => {
  const records = Object.values(examRecords.value)
  const scores = records.map((r) => r.score).filter((s) => s > 0)
  const entered = records.length
  return {
    total: entered || store.students.length,
    avg: scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : '0',
    max: scores.length > 0 ? Math.max(...scores) : 0,
    min: scores.length > 0 ? Math.min(...scores) : 0,
    entered,
  }
})

const countInfo = computed(() => (contextName.value ? `已录入 ${examStats.value.entered} 人` : ''))

function isActiveExam(e: ExamInfo): boolean {
  return e.exam_name === contextName.value && e.date === examDate.value
}

// ---- 数据加载 ----
async function loadExamList(): Promise<void> {
  try {
    const res = await loadExams(store.currentClassId)
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    examList.value = res.data || []
  } catch { /* 拦截器已提示 */ }
}

async function loadScores(): Promise<void> {
  if (!contextName.value) { examRecords.value = {}; return }
  try {
    const res = await loadExamScores(contextName.value, examDate.value, store.currentClassId)
    if (res.code !== 0) {
      if (res.msg) ElMessage.error(res.msg)
      examRecords.value = {}
      return
    }
    examRecords.value = (res.data || {}) as Record<string, ExamRecord>
  } catch { examRecords.value = {} }
}

// ---- 新建/切换考试(状态机照旧 2798-2805) ----
async function onCreateOrSwitch(): Promise<void> {
  const name = examNameInput.value.trim()
  if (!name) { ElMessage.error('请输入考试名称'); return }
  contextName.value = name
  await loadExamList()
  await loadScores()
}

function onChipClick(e: ExamInfo): void {
  contextName.value = e.exam_name
  examNameInput.value = e.exam_name
  examDate.value = e.date
  examTotalScoreInput.value = String(e.total_score || 100)
  void loadScores()
}

// ---- 日期导航 ----
function navigateExamDate(delta: number): void {
  const d = parseDate(examDate.value) ?? new Date()
  d.setDate(d.getDate() + delta)
  examDate.value = toDateStr(d)
  void loadScores()
}
function onExamToday(): void {
  examDate.value = todayStr()
  void loadScores()
}
function onExamDateChange(): void {
  void loadScores()
}

// ---- 单条成绩保存(输入即保存,照旧 2964-2993) ----
async function onScoreChange(s: Student, e: Event): Promise<void> {
  const val = (e.target as HTMLInputElement).value
  const score = parseFloat(val) || 0
  const total = currentTotalScore()
  try {
    const res: ApiResponse = await saveExamScore({
      student_id: s.id,
      exam_name: contextName.value,
      date: examDate.value,
      score,
      total_score: total,
      class_id: store.currentClassId,
    })
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    // 旧版逐格保存静默成功,不弹提示
    examRecords.value[String(s.id)] = { student_id: s.id, score, grade: calcExamGrade(score, total) }
  } catch { /* 拦截器已提示 */ }
}

// ---- 批量成绩(照旧 3007-3026) ----
async function onBatch(score: number): Promise<void> {
  if (!contextName.value) { ElMessage.error('请先输入考试名称'); return }
  const ok = await confirm(`确定将所有学生成绩设置为 ${score} 分吗？`)
  if (!ok) return
  try {
    const res: ApiResponse = await batchExamScores({
      exam_name: contextName.value,
      date: examDate.value,
      total_score: currentTotalScore(),
      class_id: store.currentClassId,
      score,
    })
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    if (res.msg) ElMessage.success(res.msg)
    await loadScores()
  } catch { /* 拦截器已提示 */ }
}

async function onCustomBatch(): Promise<void> {
  if (!contextName.value) { ElMessage.error('请先输入考试名称'); return }
  try {
    const { value } = await ElMessageBox.prompt('请输入要批量设置的分数：', '批量设置分数', {
      inputValue: '80',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const score = parseFloat(value)
    if (!isNaN(score)) await onBatch(score)
  } catch { /* 用户取消 */ }
}

// ---- 导入考试 Excel(照旧 3028-3058) ----
function onImportClick(): void {
  examFileInputRef.value?.click()
}

async function onFileChange(): Promise<void> {
  const input = examFileInputRef.value
  const file = input?.files?.[0]
  if (!input || !file) return
  try {
    const res: ApiResponse<{ imported: number; skipped: number }> = await importExamScores(
      file, examDate.value, store.currentClassId,
    )
    if (res.code !== 0) { if (res.msg) ElMessage.error(res.msg); return }
    if (res.msg) ElMessage.success(res.msg)
    await loadExamList()
    // 自动填入最近一次导入的考试(列表按日期倒序,取第一项)
    if (examList.value.length > 0) {
      const last = examList.value[0]
      contextName.value = last.exam_name
      examNameInput.value = last.exam_name
      examDate.value = last.date
      examTotalScoreInput.value = String(last.total_score || 100)
      await loadScores()
    }
  } catch { /* 拦截器已提示 */ } finally {
    input.value = ''
  }
}

// ---- 导出成绩(照旧 3060-3065) ----
function onExportScores(): void {
  if (!contextName.value) { ElMessage.error('请先选择考试'); return }
  window.open(
    downloadUrl('/export/exam-scores', {
      class_id: store.currentClassId,
      exam_name: contextName.value,
      date: examDate.value,
    }),
    '_blank',
  )
}

onMounted(() => {
  void loadExamList()
})

watch(
  () => store.currentClassId,
  () => {
    void loadExamList()
    void loadScores()
  },
)
</script>

<style scoped>
.exam-control-card { margin-bottom: 12px; }
.exam-header-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; flex-wrap: wrap;
}
.control-label { font-size: .85rem; font-weight: 600; color: #3a4a5a; white-space: nowrap; }
.exam-name-input {
  min-width: 180px; padding: 6px 10px;
  border: 1px solid rgba(150, 160, 175, 0.3); border-radius: 8px;
  font-size: .85rem; background: rgba(255, 255, 255, 0.7);
  outline: none; font-family: inherit; color: #3a4a5a;
}
.exam-name-input:focus { border-color: var(--el-color-primary); }
.exam-total-input {
  width: 70px; padding: 6px 8px;
  border: 1px solid rgba(150, 160, 175, 0.3); border-radius: 8px;
  font-size: .85rem; text-align: center; background: rgba(255, 255, 255, 0.7);
  outline: none; font-family: inherit; color: #3a4a5a;
}
.exam-total-input:focus { border-color: var(--el-color-primary); }

/* 通用玻璃按钮(液态玻璃风格) */
.btn {
  border: none; cursor: pointer; font-family: inherit;
  border-radius: 8px; color: #fff;
  transition: transform .2s ease, box-shadow .2s ease, background .2s ease, border-color .2s ease;
}
.btn:active { transform: scale(.97); }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.btn-sm { padding: 6px 14px; font-size: .82rem; border-radius: 8px; }
.btn-export {
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.75), rgba(142, 200, 224, 0.8));
  box-shadow: 0 2px 12px rgba(126, 181, 214, 0.25);
}
.btn-export:hover {
  transform: scale(1.05);
  background: linear-gradient(135deg, #5BA0C0, #7EB5D6);
  box-shadow: 0 6px 28px rgba(100, 160, 200, 0.5);
}
.btn-outline {
  background: rgba(255, 255, 255, 0.55); border: 1px solid rgba(150, 160, 175, 0.35);
  color: #5a6775;
}
.btn-outline:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); background: rgba(174, 207, 226, 0.25); }
.btn-today { background: rgba(244, 201, 126, 0.6); color: #7A6510; font-weight: 600; }
.btn-today:hover { background: rgba(244, 201, 126, 0.8); }

/* 日期选择区 */
.date-picker-area { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.date-input {
  padding: 6px 10px; border: 1px solid rgba(150, 160, 175, 0.3);
  border-radius: 8px; font-size: .85rem; background: rgba(255, 255, 255, 0.7);
  color: #3a4a5a; outline: none; font-family: inherit;
}
.date-input:focus { border-color: var(--el-color-primary); }
.date-nav-btn {
  width: 30px; height: 30px; border: 1px solid rgba(150, 160, 175, 0.25);
  background: rgba(255, 255, 255, 0.6); border-radius: 50%;
  cursor: pointer; font-size: .75rem; color: #3a4a5a;
  display: flex; align-items: center; justify-content: center;
  transition: transform .15s, background .15s, color .15s;
}
.date-nav-btn:hover { background: var(--el-color-primary); color: #fff; }
.date-nav-btn:active { transform: scale(.97); }

/* 批量分数按钮 */
.batch-area { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.batch-label { font-size: .78rem; color: #5a6775; font-weight: 600; }
.grade-batch-btn {
  padding: 5px 13px; border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 8px; cursor: pointer; font-size: .78rem; font-weight: 600;
  font-family: inherit; color: #fff;
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  transition: transform .15s ease, box-shadow .15s ease;
}
.grade-batch-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(90, 110, 140, 0.2); }
.grade-batch-btn:active { transform: scale(.97); }
.grade-batch-btn.grade-a { background: rgba(168, 213, 186, 0.65); }
.grade-batch-btn.grade-b { background: rgba(126, 181, 214, 0.6); }
.grade-batch-btn.grade-c { background: rgba(244, 201, 126, 0.6); color: #7A6510; }
.grade-batch-btn.grade-x { background: rgba(232, 160, 191, 0.6); }

.exam-action-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.exam-count-info { font-size: .78rem; color: #5a6775; margin-left: auto; }
.hidden-file-input { display: none; }

/* 已有考试 chips */
.exam-list-card { margin-bottom: 12px; }
.card-header { display: flex; align-items: center; gap: 8px; padding-bottom: 8px; }
.card-header h3 { font-size: .95rem; font-weight: 600; color: #3a4a5a; margin: 0; }
.card-icon { font-size: 1.1rem; }
.exam-list { display: flex; flex-wrap: wrap; gap: 6px; }
.exam-list-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 12px; border: 1px solid rgba(150, 160, 175, 0.3);
  border-radius: 8px; background: rgba(255, 255, 255, 0.6);
  cursor: pointer; font-size: .82rem; font-family: inherit; color: #3a4a5a;
  transition: transform .15s, border-color .15s, background .15s;
}
.exam-list-btn:hover { border-color: var(--el-color-primary); background: rgba(126, 181, 214, 0.1); }
.exam-list-btn.active { border-color: var(--el-color-primary); background: rgba(126, 181, 214, 0.18); font-weight: 600; }
.exam-list-btn small { font-size: .7rem; color: #9aa8b5; font-weight: 400; }

/* 空状态 */
.empty-state {
  text-align: center; padding: 40px 20px;
  color: #9aa8b5; background: rgba(255, 255, 255, 0.5);
  border-radius: 14px; line-height: 1.8;
}
.empty-state p { margin: 0; }
.empty-icon { font-size: 3rem; display: block; margin-bottom: 10px; }

/* 成绩录入分组视图 */
.exam-groups {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px; margin-bottom: 14px;
}
.exam-group-column {
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  border-radius: 12px; box-shadow: var(--card-shadow); overflow: hidden;
}
.hw-group-header {
  padding: 10px 14px; font-weight: 700; font-size: .85rem;
  display: flex; align-items: center; gap: 7px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04); color: #3a4a5a;
}
.group-name-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.group-count { margin-left: auto; font-size: .72rem; color: #9aa8b5; font-weight: 400; }
.exam-student-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: background .15s;
}
.exam-student-row:hover { background: rgba(126, 181, 214, 0.06); }
.exam-student-row:last-child { border-bottom: none; }
.exam-student-name { font-size: .85rem; color: #3a4a5a; display: flex; gap: 4px; align-items: center; }
.student-code-label { font-family: monospace; color: #9aa8b5; font-size: .75rem; }
.privacy-mode { font-family: monospace; letter-spacing: 1px; }
.score-input-area { display: flex; align-items: center; gap: 6px; }
.exam-score-input {
  width: 72px; padding: 5px 8px; border: 1px solid rgba(150, 160, 175, 0.35);
  border-radius: 8px; text-align: center; font-size: .85rem;
  background: rgba(255, 255, 255, 0.8); font-family: inherit; color: #3a4a5a;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
.exam-score-input:focus {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(126, 181, 214, 0.15);
}
.exam-score-input:hover { border-color: var(--el-color-primary); }
.exam-grade-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; border-radius: 6px;
  font-size: .72rem; font-weight: 600; background: #f0f0f0; color: #999;
}
.exam-grade-badge.grade-a { background: #D4EDDA; color: #155724; }
.exam-grade-badge.grade-b { background: #D6EAF8; color: #0C5460; }
.exam-grade-badge.grade-c { background: #FFF3CD; color: #856404; }
.exam-grade-badge.grade-d { background: #F8D7DA; color: #721C24; }

/* 考试统计卡片 */
.stats-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 14px; }
.stat-card {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  border-radius: 14px; padding: 14px 16px; box-shadow: var(--card-shadow);
  text-align: center;
}
.stat-card-icon { font-size: 1.3rem; margin-bottom: 4px; }
.stat-card-value { font-size: 1.5rem; font-weight: 700; color: #3a4a5a; }
.stat-card-label { font-size: .75rem; color: #5a6775; margin-top: 2px; }
.stat-card-total .stat-card-value { color: #2D5A7A; }
.stat-card-submitted .stat-card-value { color: #2D6A3F; }
.stat-card-arate .stat-card-value { color: #B8860B; }
</style>
