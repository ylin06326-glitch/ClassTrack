<template>
  <div class="homework-tab">
    <!-- ============ 作业控制卡 ============ -->
    <div class="ct-card hw-control-card">
      <div class="hw-control-row">
        <div class="date-picker-area">
          <span class="control-label">📅 登记日期：</span>
          <button class="date-nav-btn" title="前一天" @click="changeDate(-1)">◀</button>
          <el-date-picker
            v-model="hwDate"
            type="date"
            value-format="YYYY-MM-DD"
            :editable="false"
            placeholder="选择日期"
            class="date-input"
          />
          <button class="date-nav-btn" title="后一天" @click="changeDate(1)">▶</button>
          <button class="btn-today" @click="setToday">📌 今天</button>
          <span class="control-label label-gap">📋 作业种类：</span>
          <el-select v-model="store.currentHomeworkTypeId" class="type-select">
            <el-option v-for="t in store.homeworkTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <button class="btn-manage" title="管理作业种类" @click="typesDialogVisible = true">⚙️</button>
        </div>
        <div class="batch-area">
          <span class="batch-label">批量：</span>
          <button
            v-for="gv in GRADE_OPTIONS"
            :key="gv"
            class="grade-batch-btn"
            :class="`grade-${gv.toLowerCase()}`"
            @click="batchSetGrade(gv)"
          >全部 {{ gradeDisplayLabel(gv) }}</button>
        </div>
        <button class="btn-reminder" @click="reminderVisible = true">🔔 催交通知</button>
      </div>
    </div>

    <!-- ============ 登记方式子Tab ============ -->
    <div class="hw-subtab-nav">
      <button
        class="hw-subtab-btn"
        :class="{ active: activeSubtab === 'manual' }"
        @click="activeSubtab = 'manual'"
      >✏️ 手动登记</button>
      <button
        class="hw-subtab-btn"
        :class="{ active: activeSubtab === 'pcscan' }"
        @click="activeSubtab = 'pcscan'"
      >📷 电脑扫码</button>
      <button
        class="hw-subtab-btn"
        :class="{ active: activeSubtab === 'mobile' }"
        @click="activeSubtab = 'mobile'"
      >📱 手机扫码</button>
    </div>

    <!-- ============ 手动登记面板 ============ -->
    <div v-show="activeSubtab === 'manual'">
      <div v-if="store.students.length === 0" class="ct-card empty-state">
        <span class="empty-icon">📝</span>
        <p>请先在「班级分组」中导入学生并完成分组</p>
      </div>
      <div v-else class="hw-sections">
        <div v-for="sec in sections" :key="sec.key" class="ct-card hw-group-column">
          <div
            class="hw-group-header"
            :style="{ borderLeftColor: sec.color }"
            title="点击查看已交/未交名单"
            @click="showSectionDetail(sec)"
          >
            <span class="group-name-dot" :style="{ background: sec.color }"></span>
            <span class="hw-group-name">{{ sec.title }}</span>
            <span class="hw-group-count">已交 {{ submittedCount(sec.students) }}/{{ sec.students.length }}</span>
          </div>
          <div class="hw-group-students">
            <div
              v-for="s in sec.students"
              :key="s.id"
              class="hw-student-row"
              :class="{ 'privacy-row': isPrivacyRow(gradeOf(s.id)) }"
            >
              <span class="hw-avatar">{{ animalAvatar(s.name) }}</span>
              <span class="hw-student-name">
                <span v-if="showCodePrefix(gradeOf(s.id)) && s.student_code" class="student-code-label">{{ s.student_code }}</span>{{ displayNameOf(s, gradeOf(s.id)) }}
              </span>
              <GradeSegmented
                :model-value="gradeOf(s.id)"
                compact
                @update:model-value="(g: string) => setGrade(s, g as Grade)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 电脑扫码面板 ============ -->
    <div v-show="activeSubtab === 'pcscan'" class="ct-card scan-panel">
      <div class="panel-header">
        <span class="panel-icon">📷</span>
        <h3>电脑摄像头扫码</h3>
      </div>
      <div class="scan-mode-row">
        <span class="control-label">模式：</span>
        <button
          class="scan-type-btn"
          :class="{ active: pcScanMode === 'batch' }"
          @click="pcScanMode = 'batch'"
        >📦 批量分堆</button>
        <button
          class="scan-type-btn"
          :class="{ active: pcScanMode === 'single' }"
          @click="pcScanMode = 'single'"
        >👤 单点选择</button>
        <span class="control-label label-gap">📋 种类：</span>
        <el-select v-model="store.currentHomeworkTypeId" class="type-select">
          <el-option v-for="t in store.homeworkTypes" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <button class="btn-manage" title="管理作业种类" @click="typesDialogVisible = true">⚙️</button>
      </div>
      <div v-if="pcScanMode === 'batch'" class="grade-buttons-row">
        <span class="control-label">档位：</span>
        <button
          v-for="gv in GRADE_OPTIONS"
          :key="gv"
          class="grade-preset-btn"
          :class="[`grade-${gv.toLowerCase()}`, { active: pcScanGrade === gv }]"
          @click="pcScanGrade = gv"
        >{{ PC_GRADE_LABELS[gv] }}</button>
      </div>
      <div class="camera-box">
        <div id="pc-scan-region" class="pc-scan-region">
          <div v-if="!scannerRunning" class="camera-placeholder">📷 点击「开始扫描」开启摄像头</div>
        </div>
        <div v-if="scannerRunning" class="camera-guide"></div>
      </div>
      <div class="scan-actions">
        <button v-if="!scannerRunning" class="btn-start" @click="startPcScan">▶ 开始扫描</button>
        <button v-else class="btn-stop" @click="stopPcScan">⏹ 停止</button>
      </div>
    </div>

    <!-- ============ 手机扫码面板 ============ -->
    <div v-show="activeSubtab === 'mobile'" class="ct-card scan-panel">
      <div class="panel-header">
        <span class="panel-icon">📱</span>
        <h3>手机联动扫码</h3>
      </div>
      <div class="mobile-steps">
        <div class="mobile-step"><span class="step-num">1</span> 手机与电脑连接同一 WiFi</div>
        <div class="mobile-step"><span class="step-num">2</span> 点击下方按钮生成连接二维码</div>
        <div class="mobile-step"><span class="step-num">3</span> 手机微信/浏览器扫码即可接入</div>
      </div>
      <div class="mobile-pair-row">
        <button class="btn-pair" @click="generatePairQr">📱 生成连接二维码</button>
        <span class="mobile-status">{{ mobileStatus }}</span>
        <span class="mobile-url">{{ pairUrl }}</span>
      </div>
      <div v-if="pairQrDataUrl" class="pair-qr-box">
        <img :src="pairQrDataUrl" width="150" height="150" alt="配对二维码" />
      </div>
      <div class="mobile-grade-row">
        <span class="batch-label">批量档位：</span>
        <button
          v-for="gv in GRADE_OPTIONS"
          :key="gv"
          class="grade-preset-btn"
          :class="[`grade-${gv.toLowerCase()}`, { active: mobileScanGrade === gv }]"
          @click="mobileScanGrade = gv"
        >{{ gradeDisplayLabel(gv) }}</button>
      </div>
      <div class="mobile-actions">
        <button class="btn-refresh" @click="refreshMobile">🔄 刷新扫码记录</button>
        <button class="btn-clear" @click="clearMobile">🗑 清空</button>
        <span v-if="mobileScanCount > 0" class="mobile-scan-count">本次: {{ mobileScanCount }} 条</span>
      </div>
    </div>

    <!-- ============ 待确认列表(扫码/手机共用) ============ -->
    <div class="ct-card pending-card">
      <div class="panel-header">
        <span class="panel-icon">📋</span>
        <h3>待确认列表</h3>
        <span class="pending-count">{{ pendingScans.length }}条</span>
      </div>
      <div class="pending-list">
        <div v-if="pendingScans.length === 0" class="pending-empty">扫码后学生将显示在这里</div>
        <div
          v-for="(p, i) in pendingScans"
          :key="`${p.student_code}-${i}`"
          class="pending-item"
          :class="{ external: p.external }"
        >
          <span class="pi-code">{{ p.student_code }}</span>
          <span class="pi-name" :class="{ privacy: store.displayMode === 'code' }">{{ pendingDisplayName(p) }}</span>
          <span v-if="p.external" class="pi-external">⚠ 非本班</span>
          <span class="grade-badge" :class="`grade-${(p.grade || 'x').toLowerCase()}`">{{ gradeDisplayLabel(p.grade) }}</span>
          <button class="pi-del" title="移除" @click="pendingScans.splice(i, 1)">✕</button>
        </div>
      </div>
      <div class="pending-actions">
        <button class="btn-confirm" @click="confirmScans">✅ 确认保存</button>
        <button class="btn-clear" @click="pendingScans = []">🗑 清空列表</button>
        <span class="pending-hint">提示：保存后自动刷新台账和图表</span>
      </div>
    </div>

    <!-- ============ 全局弹窗组件 ============ -->
    <HomeworkTypesDialog v-model="typesDialogVisible" />
    <ReminderDialog v-model="reminderVisible" :date="hwDate" :type-id="store.currentHomeworkTypeId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Html5Qrcode } from 'html5-qrcode'
import QRCode from 'qrcode'
import { useAppStore } from '@/stores/app'
import { useDialogs, type DetailItem } from '@/composables/dialogs'
import {
  loadHomework, saveHomework, batchHomework, findStudentByCode, scanBatch, scanSingle,
  mobilePair, mobileScans, mobileClear,
  type Student,
} from '@/api'
import {
  VALID_GRADES, gradeDisplayLabel, gradeLabel, isSubmitted, animalAvatar, type Grade,
} from '@/utils/grade'
import HomeworkTypesDialog from '@/components/HomeworkTypesDialog.vue'
import GradeSegmented from '@/components/GradeSegmented.vue'
import ReminderDialog from '@/components/ReminderDialog.vue'

const store = useAppStore()
const dialogs = useDialogs()

// ============ 类型 ============
interface HomeworkRecord {
  id: number
  student_id: number
  student_name: string
  date: string
  grade: string
  group_id: number
  group_name: string
  group_color: string
}
interface PendingScan {
  student_code: string
  student_name: string
  grade: string
  student_id: number | null
  external: boolean
}
interface ScanStudent {
  id: number
  name: string
  student_code?: string
  group_id?: number
  group_name?: string
  group_color?: string
}
interface MobileScanItem {
  id: number
  student_code: string
  scanned_at: string
  student_name: string
  student_id: number | null
  found: boolean
}
interface MobileScansResponse {
  code: number
  msg?: string
  data: MobileScanItem[]
  since: string
  total: number
}
interface HwDetailItem extends DetailItem {
  grade?: string
  gradeLabel?: string
  sid?: number
}
interface StudentSection {
  key: string
  title: string
  color: string
  students: Student[]
}

// ============ 作业控制 ============
const GRADE_OPTIONS: Grade[] = [...VALID_GRADES]

const PC_GRADE_LABELS: Record<Grade, string> = {
  A: '🟢 A 优秀',
  B: '🔵 B 中等',
  C: '🟡 C 待改进',
  L: '🌿 请假',
  X: '🩷 未交',
}
const activeSubtab = ref<'manual' | 'pcscan' | 'mobile'>('manual')
const hwDate = ref(dayjs().format('YYYY-MM-DD'))
const typesDialogVisible = ref(false)
const reminderVisible = ref(false)

/** 当前日期+班级+种类的作业记录(student_id 字符串键 → 记录,与旧版缓存契约一致) */
const homework = ref<Record<string, HomeworkRecord>>({})

async function loadHomeworkForDate(): Promise<void> {
  try {
    const res = await loadHomework(hwDate.value, store.currentClassId, store.currentHomeworkTypeId)
    if (res.code === 0) homework.value = res.data || {}
  } catch { /* 拦截器已提示 */ }
}

function changeDate(delta: number): void {
  if (!hwDate.value) {
    hwDate.value = dayjs().format('YYYY-MM-DD')
    return
  }
  hwDate.value = dayjs(hwDate.value).add(delta, 'day').format('YYYY-MM-DD')
}

function setToday(): void {
  hwDate.value = dayjs().format('YYYY-MM-DD')
}

// ---- 批量设置(全部 A/B/C/请假/未交) ----
async function batchSetGrade(grade: Grade): Promise<void> {
  if (!hwDate.value) return
  const ok = await dialogs.confirm(
    `确定将 ${hwDate.value} 所有学生作业等级批量设为「${gradeDisplayLabel(grade)}」吗？`,
  )
  if (!ok) return
  try {
    const res = await batchHomework({
      date: hwDate.value, grade,
      class_id: store.currentClassId, homework_type_id: store.currentHomeworkTypeId,
    })
    if (res.code === 0) {
      ElMessage.success(res.msg || '批量设置成功')
      await Promise.all([loadHomeworkForDate(), store.loadStatsData()])
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 手动登记 ============
/** 按分组归类的学生(含未分组池),与旧版 State.students 按 group_id 过滤一致 */
const groupedStudents = computed<Map<number, Student[]>>(() => {
  const map = new Map<number, Student[]>()
  for (const s of store.students) {
    if (!s.group_id) continue
    const list = map.get(s.group_id)
    if (list) list.push(s)
    else map.set(s.group_id, [s])
  }
  for (const list of map.values()) list.sort((a, b) => a.sort_order - b.sort_order)
  return map
})
const poolStudents = computed<Student[]>(() => {
  const ids = new Set(store.unassigned.map((u) => u.id))
  return store.students.filter((s) => ids.has(s.id))
})
const sections = computed<StudentSection[]>(() => {
  const secs: StudentSection[] = store.groups.map((g) => ({
    key: `g${g.id}`,
    title: g.name,
    color: g.color,
    students: groupedStudents.value.get(g.id) || [],
  }))
  if (poolStudents.value.length > 0) {
    secs.push({ key: 'pool', title: '未分组', color: '#9aa8b5', students: poolStudents.value })
  }
  return secs
})

function gradeOf(sid: number): string {
  return homework.value[String(sid)]?.grade ?? 'X'
}

function submittedCount(students: Student[]): number {
  return students.filter((s) => isSubmitted(gradeOf(s.id))).length
}

/** 分区显示模式下的分区(旧版 getDisplayZone):已完成显名/未完成显学号 */
function displayZoneOf(grade: string): 'completed' | 'incomplete' | null {
  if (store.displayMode !== 'auto') return null
  if (grade === 'X') return 'incomplete'
  if (isSubmitted(grade)) return 'completed'
  return null
}

/** 学生姓名显示(旧版 formatStudentDisplay 等价) */
function displayNameOf(s: Student, grade: string): string {
  const zone = displayZoneOf(grade)
  if (zone === 'incomplete') return s.student_code || s.name
  if (zone === 'completed') return s.name
  if (store.displayMode === 'code') return s.student_code || '???'
  return s.name
}

/** 学号前缀小标签(旧版 formatStudentCodeHtml 等价) */
function showCodePrefix(grade: string): boolean {
  return displayZoneOf(grade) !== 'incomplete' && store.displayMode !== 'code'
}

/** 隐私模式行样式(等宽字体) */
function isPrivacyRow(grade: string): boolean {
  return displayZoneOf(grade) === 'incomplete' || store.displayMode === 'code'
}

// ---- 点击等级按钮:即时更新 + 后台保存,失败回滚(旧版 v1.2 交互) ----
const pendingGrades = new Map<string, string>()

async function setGrade(s: Student, grade: Grade): Promise<void> {
  const sid = s.id
  if (gradeOf(sid) === grade) return
  const key = `${sid}-${hwDate.value}`
  if (pendingGrades.get(key) === grade) return
  pendingGrades.set(key, grade)

  const prev = homework.value[String(sid)]
  homework.value[String(sid)] = {
    id: prev?.id ?? 0,
    student_id: sid,
    student_name: s.name,
    date: hwDate.value,
    grade,
    group_id: prev?.group_id ?? s.group_id,
    group_name: prev?.group_name ?? s.group_name,
    group_color: prev?.group_color ?? s.group_color,
  }
  try {
    const res = await saveHomework({
      student_id: sid, date: hwDate.value, grade,
      class_id: store.currentClassId, homework_type_id: store.currentHomeworkTypeId,
    })
    if (res.code !== 0) {
      ElMessage.error('保存失败: ' + (res.msg || ''))
      rollbackGrade(sid, prev)
      await loadHomeworkForDate()
    }
  } catch {
    // HTTP 错误由拦截器统一 toast,这里回滚并重载
    rollbackGrade(sid, prev)
    await loadHomeworkForDate()
  } finally {
    pendingGrades.delete(key)
    scheduleStatsRefresh()
  }
}

function rollbackGrade(sid: number, prev: HomeworkRecord | undefined): void {
  if (prev) homework.value[String(sid)] = prev
  else delete homework.value[String(sid)]
}

let statsTimer: number | undefined
/** 防抖刷新统计(旧版 debouncedLoadStats,800ms) */
function scheduleStatsRefresh(): void {
  window.clearTimeout(statsTimer)
  statsTimer = window.setTimeout(() => {
    store.loadStatsData().catch(() => { /* 拦截器已提示 */ })
  }, 800)
}

// ---- 组头点击:已交/未交名单 ----
function detailLabelOf(s: Student, grade: string): { label: string; sub: string } {
  const submitted = isSubmitted(grade)
  if (store.displayMode === 'code') return { label: s.student_code || s.name, sub: '' }
  if (store.displayMode === 'auto') {
    return submitted
      ? { label: s.name, sub: s.student_code }
      : { label: s.student_code || s.name, sub: '' }
  }
  return { label: s.name, sub: s.student_code }
}

function showSectionDetail(sec: StudentSection): void {
  const submitted: HwDetailItem[] = []
  const missing: HwDetailItem[] = []
  for (const s of sec.students) {
    const grade = gradeOf(s.id)
    const { label, sub } = detailLabelOf(s, grade)
    const item: HwDetailItem = { label, sub, grade, gradeLabel: gradeLabel(grade), sid: s.id }
    if (isSubmitted(grade)) submitted.push(item)
    else missing.push(item)
  }
  dialogs.showDetail(
    `📌 ${sec.title}`,
    `已交：${submitted.length} 人 · 未交：${missing.length} 人`,
    [...submitted, ...missing],
  )
}

// ============ 待确认列表(电脑扫码/手机扫码共用) ============
const pendingScans = ref<PendingScan[]>([])

function addPending(code: string, name: string, grade: string, studentId: number | null, external: boolean): void {
  pendingScans.value = pendingScans.value.filter((p) => p.student_code !== code)
  pendingScans.value.push({ student_code: code, student_name: name, grade, student_id: studentId, external })
}

function pendingDisplayName(p: PendingScan): string {
  return store.displayMode === 'code' ? p.student_code : p.student_name
}

async function confirmScans(): Promise<void> {
  if (pendingScans.value.length === 0) {
    ElMessage.error('没有待保存的记录')
    return
  }
  const valid = pendingScans.value.filter((p) => !p.external && p.student_id != null)
  if (valid.length === 0) {
    ElMessage.error('没有有效记录可保存')
    return
  }
  try {
    const res = await scanBatch({
      date: hwDate.value,
      records: valid.map((p) => ({ student_code: p.student_code, grade: p.grade })),
      class_id: store.currentClassId,
      homework_type_id: store.currentHomeworkTypeId,
    })
    if (res.code === 0) {
      if (res.msg) ElMessage.success(res.msg)
      pendingScans.value = []
      await Promise.all([loadHomeworkForDate(), store.loadStatsData()])
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 电脑扫码(html5-qrcode,后置摄像头) ============
const pcScanMode = ref<'batch' | 'single'>('batch')
const pcScanGrade = ref<Grade>('A')
const scannerRunning = ref(false)
let html5Qr: Html5Qrcode | null = null
const DEDUP_MS = 3000
const seenCodes: Record<string, number> = {}

async function startPcScan(): Promise<void> {
  if (html5Qr) return
  try {
    html5Qr = new Html5Qrcode('pc-scan-region')
    await html5Qr.start(
      { facingMode: 'environment' },
      { fps: 30, qrbox: { width: 250, height: 250 }, aspectRatio: 1 },
      (text) => { void onPcCodeDetected(text) },
      () => { /* 单帧未识别到二维码,忽略 */ },
    )
    scannerRunning.value = true
    ElMessage.info('PC 扫码已启动（软件识别）')
  } catch (err) {
    if (html5Qr) {
      html5Qr.stop().catch(() => { /* ignore */ })
      html5Qr = null
    }
    ElMessage.error('摄像头启动失败: ' + (err instanceof Error ? err.message : String(err)))
  }
}

async function stopPcScan(): Promise<void> {
  if (!html5Qr || !scannerRunning.value) return
  try {
    await html5Qr.stop()
  } catch { /* ignore */ }
  html5Qr.clear()
  html5Qr = null
  scannerRunning.value = false
  ElMessage.info('扫码已停止')
}

/** 扫码回调:去重(3 秒窗口)→ 验证学号 → 批量入待确认 / 单点弹窗选等级 */
async function onPcCodeDetected(text: string): Promise<void> {
  if (!scannerRunning.value) return
  const code = (text || '').trim()
  if (!code) return
  const now = Date.now()
  if (seenCodes[code] && now - seenCodes[code] < DEDUP_MS) return
  seenCodes[code] = now
  const expire = now - DEDUP_MS * 2
  for (const k of Object.keys(seenCodes)) {
    if (seenCodes[k] < expire) delete seenCodes[k]
  }
  await handlePcCode(code)
}

function plainDisplayName(name: string, code: string): string {
  return store.displayMode === 'code' ? code || '???' : name
}

async function handlePcCode(code: string): Promise<void> {
  try {
    const res = await findStudentByCode(code, store.currentClassId)
    if (res.code === 0 && res.data) {
      const s = res.data as ScanStudent
      const displayName = plainDisplayName(s.name, s.student_code || '')
      if (pcScanMode.value === 'single') {
        await promptSingleGrade(s, displayName, code)
      } else {
        addPending(code, displayName, pcScanGrade.value, s.id, false)
        ElMessage.info(`${displayName} → ${gradeDisplayLabel(pcScanGrade.value)}`)
      }
    } else {
      ElMessage.error(`未找到学号 ${code}，可能非本班学生`)
    }
  } catch {
    ElMessage.error('识别失败')
  }
}

/** 单点模式:弹窗输入等级后即时登记(旧版 prompt 文案与流程逐字保留,仅 A/B/C/X) */
async function promptSingleGrade(s: ScanStudent, displayName: string, code: string): Promise<void> {
  const suffix = store.displayMode !== 'code' && s.student_code ? ` (${s.student_code})` : ''
  try {
    const { value } = await ElMessageBox.prompt(
      `学生：${displayName}${suffix}\n请输入等级 (A/B/C/X)：`,
      '单点扫码登记',
      {
        inputValue: 'A',
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        inputPattern: /^[ABCX]$/i,
        inputErrorMessage: '请输入 A/B/C/X',
      },
    )
    const chosen = value.trim().toUpperCase()
    if (!/^[ABCX]$/.test(chosen)) return
    const res = await scanSingle({
      student_code: code,
      grade: chosen,
      date: hwDate.value,
      class_id: store.currentClassId,
      homework_type_id: store.currentHomeworkTypeId,
    })
    if (res.code === 0) {
      ElMessage.success(`${displayName} → ${chosen}`)
      await Promise.all([loadHomeworkForDate(), store.loadStatsData()])
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 用户取消 */ }
}

// ============ 手机扫码联动 ============
const mobileScanGrade = ref<Grade>('A')
const mobileStatus = ref('🔴 未连接')
const pairUrl = ref('')
const pairQrDataUrl = ref('')
const mobileScanCount = ref(0)
let mobilePollTimer: number | undefined

/** since 游标:初始为当前时间,不加载历史数据(旧版逻辑照搬) */
function nowScanTs(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19)
}
const mobileLastScanTs = ref(nowScanTs())

async function generatePairQr(): Promise<void> {
  try {
    const res = await mobilePair()
    if (res.code === 0 && res.data) {
      pairUrl.value = res.data.url
      mobileStatus.value = '🟢 等待手机连接...'
      pairQrDataUrl.value = await QRCode.toDataURL(res.data.url, { width: 160, margin: 1 })
      ElMessage.success('配对二维码已生成，手机扫码即可接入')
      startMobilePolling()
    }
  } catch { /* 拦截器已提示 */ }
}

function startMobilePolling(): void {
  if (mobilePollTimer) return
  mobileStatus.value = '🟢 监听中...'
  mobilePollTimer = window.setInterval(() => { void pollMobileScans() }, 500)
}

function stopMobilePolling(): void {
  if (mobilePollTimer) {
    window.clearInterval(mobilePollTimer)
    mobilePollTimer = undefined
  }
}

async function pollMobileScans(): Promise<void> {
  try {
    const res = (await mobileScans(mobileLastScanTs.value, store.currentClassId)) as MobileScansResponse
    if (res.code === 0 && res.data && res.data.length > 0) {
      mobileLastScanTs.value = res.since
      mobileStatus.value = `🟢 已连接 · ${res.data.length} 条新记录`
      mobileScanCount.value = res.data.length
      for (const s of res.data) {
        addPending(s.student_code, s.student_name, mobileScanGrade.value, s.student_id, !s.found)
      }
    }
  } catch { /* 轮询失败忽略 */ }
}

async function refreshMobile(): Promise<void> {
  mobileLastScanTs.value = nowScanTs()
  await pollMobileScans()
}

async function clearMobile(): Promise<void> {
  try {
    const res = await mobileClear()
    if (res.code === 0) {
      mobileLastScanTs.value = nowScanTs()
      ElMessage.info('已清空手机扫码记录')
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 生命周期 ============
watch(
  [hwDate, () => store.currentClassId, () => store.currentHomeworkTypeId],
  () => { void loadHomeworkForDate() },
)

onMounted(() => {
  void loadHomeworkForDate()
})

onBeforeUnmount(() => {
  stopMobilePolling()
  if (html5Qr) {
    html5Qr.stop().catch(() => { /* ignore */ })
    html5Qr.clear()
    html5Qr = null
  }
  scannerRunning.value = false
  window.clearTimeout(statsTimer)
})
</script>

<style scoped>
.homework-tab { display: flex; flex-direction: column; gap: 14px; }

/* ---- 作业控制卡 ---- */
.hw-control-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.date-picker-area { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.control-label { font-size: 14px; color: #5a6775; white-space: nowrap; }
.label-gap { margin-left: 12px; }
.date-nav-btn {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 8px; width: 30px; height: 30px; cursor: pointer;
  color: #5a6775; font-size: 12px; line-height: 1;
}
.date-nav-btn:hover { background: #f0f6fa; }
.date-input { width: 140px; }
.btn-today {
  border: 1px solid rgba(107, 163, 199, 0.4); background: #f0f6fa;
  color: #4a7a99; border-radius: 8px; padding: 6px 10px;
  cursor: pointer; font-size: 13px; font-family: inherit;
}
.btn-today:hover { background: #e0edf4; }
.type-select { width: 120px; }
.btn-manage {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 8px; width: 30px; height: 30px; cursor: pointer; font-size: 13px;
}
.btn-manage:hover { background: #f0f6fa; }
.batch-area { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.batch-label { font-size: 14px; color: #5a6775; }
.grade-batch-btn {
  border: 1px solid transparent; border-radius: 12px;
  padding: 5px 12px; cursor: pointer; font-size: 13px; font-weight: 600;
  font-family: inherit; transition: transform 0.15s ease;
}
.grade-batch-btn:hover { transform: scale(1.05); }
.grade-batch-btn.grade-a { background: var(--grade-a-bg); color: var(--grade-a-color); }
.grade-batch-btn.grade-b { background: var(--grade-b-bg); color: var(--grade-b-color); }
.grade-batch-btn.grade-c { background: var(--grade-c-bg); color: var(--grade-c-color); }
.grade-batch-btn.grade-l { background: var(--grade-l-bg); color: var(--grade-l-color); }
.grade-batch-btn.grade-x { background: var(--grade-x-bg); color: var(--grade-x-color); }
.btn-reminder {
  border: none; border-radius: 10px; padding: 8px 14px; cursor: pointer;
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6); color: #fff;
  font-size: 14px; font-weight: 600; font-family: inherit;
  box-shadow: 0 3px 10px rgba(107, 163, 199, 0.35);
}
.btn-reminder:hover { filter: brightness(1.05); }

/* ---- 登记方式子Tab ---- */
.hw-subtab-nav { display: flex; gap: 6px; }
.hw-subtab-btn {
  border: none; background: transparent; cursor: pointer;
  padding: 8px 16px; border-radius: 10px;
  font-size: 14px; color: #5a6775; font-family: inherit;
  transition: all 0.18s;
}
.hw-subtab-btn:hover { background: rgba(107, 163, 199, 0.12); }
.hw-subtab-btn.active {
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6);
  color: #fff; font-weight: 600;
  box-shadow: 0 3px 10px rgba(107, 163, 199, 0.35);
}

/* ---- 手动登记 ---- */
.empty-state { text-align: center; padding: 40px 16px; color: #8a97a8; }
.empty-icon { font-size: 40px; display: block; margin-bottom: 8px; }
.hw-sections {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-start;
}
.hw-group-column {
  flex: 1 1 500px;
  min-width: 480px;
  max-width: 620px;
}
.hw-group-column { padding: 0 16px 14px; overflow: visible; }
.hw-group-header {
  display: flex; align-items: center; gap: 8px;
  border-left: 4px solid transparent;
  padding: 10px 10px 10px 12px; margin: 0 -16px 8px;
  background: rgba(245, 248, 250, 0.8);
  cursor: pointer; user-select: none;
}
.hw-group-header:hover { background: rgba(235, 243, 248, 0.9); }
.group-name-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.hw-group-name { font-size: 15px; font-weight: 700; color: #3a4a5a; }
.hw-group-count { margin-left: auto; font-size: 12px; color: #8a97a8; }
.hw-group-students { display: flex; flex-direction: column; gap: 6px; }
.hw-student-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; border-radius: 10px;
  background: rgba(246, 248, 250, 0.7);
  flex-wrap: nowrap;
  overflow: visible;
  /* 确保等级滑块有足够空间 */
}
.hw-student-row .grade-segmented {
  flex-shrink: 0;
  flex-grow: 0;
  min-width: 310px;
  width: 310px;
  max-width: 310px;
}
.hw-avatar { font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; }
.hw-student-name { font-size: 13px; color: #3a4a5a; flex: 0 1 auto; max-width: 70px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.student-code-label { font-family: 'SF Mono', Consolas, monospace; color: #8a97a8; font-size: 12px; margin-right: 4px; }
.hw-student-row.privacy-row .hw-student-name { font-family: 'SF Mono', Consolas, monospace; letter-spacing: 1px; }
.grade-quick-select { display: flex; gap: 6px; }
.grade-qbtn {
  border: 1px solid rgba(150, 160, 175, 0.25); background: #fff;
  border-radius: 12px; min-width: 40px; height: 26px;
  cursor: pointer; font-size: 12px; font-weight: 600; font-family: inherit;
  transition: all 0.15s ease;
}
.grade-qbtn:hover { transform: scale(1.06); }
.grade-qbtn.grade-a { color: var(--grade-a-color); }
.grade-qbtn.grade-b { color: var(--grade-b-color); }
.grade-qbtn.grade-c { color: var(--grade-c-color); }
.grade-qbtn.grade-l { color: var(--grade-l-color); }
.grade-qbtn.grade-x { color: var(--grade-x-color); }
.grade-qbtn.active { border-color: transparent; color: #fff; box-shadow: 0 2px 6px rgba(90, 110, 140, 0.25); }
.grade-qbtn.grade-a.active { background: #6fae83; }
.grade-qbtn.grade-b.active { background: #6aa2c4; }
.grade-qbtn.grade-c.active { background: #e0b45c; color: #5b4c0d; }
.grade-qbtn.grade-l.active { background: #9f8cc9; }
.grade-qbtn.grade-x.active { background: #d889a8; }

/* ---- 扫码面板(电脑/手机共用结构) ---- */
.scan-panel { display: flex; flex-direction: column; gap: 12px; }
.panel-header { display: flex; align-items: center; gap: 8px; }
.panel-header h3 { margin: 0; font-size: 16px; color: #3a4a5a; }
.panel-icon { font-size: 18px; }
.scan-mode-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.scan-type-btn {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 10px; padding: 6px 14px; cursor: pointer;
  font-size: 14px; color: #5a6775; font-family: inherit; transition: all 0.18s;
}
.scan-type-btn:hover { background: #f0f6fa; }
.scan-type-btn.active {
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6);
  color: #fff; font-weight: 600; border-color: transparent;
  box-shadow: 0 3px 10px rgba(107, 163, 199, 0.35);
}
.grade-buttons-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.grade-preset-btn {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 12px; padding: 6px 14px; cursor: pointer;
  font-size: 13px; font-weight: 600; font-family: inherit; transition: all 0.15s ease;
}
.grade-preset-btn.grade-a { color: var(--grade-a-color); }
.grade-preset-btn.grade-b { color: var(--grade-b-color); }
.grade-preset-btn.grade-c { color: var(--grade-c-color); }
.grade-preset-btn.grade-l { color: var(--grade-l-color); }
.grade-preset-btn.grade-x { color: var(--grade-x-color); }
.grade-preset-btn:hover { transform: scale(1.05); }
.grade-preset-btn.active { border-color: transparent; color: #fff; box-shadow: 0 2px 8px rgba(90, 110, 140, 0.28); }
.grade-preset-btn.grade-a.active { background: #6fae83; }
.grade-preset-btn.grade-b.active { background: #6aa2c4; }
.grade-preset-btn.grade-c.active { background: #e0b45c; color: #5b4c0d; }
.grade-preset-btn.grade-l.active { background: #9f8cc9; }
.grade-preset-btn.grade-x.active { background: #d889a8; }

/* ---- 摄像头取景框 ---- */
.camera-box { position: relative; width: 100%; max-width: 520px; }
.pc-scan-region {
  position: relative; width: 100%; min-height: 280px;
  border-radius: 12px; overflow: hidden;
  background: #20262e; border: 1px solid rgba(150, 160, 175, 0.25);
}
.pc-scan-region :deep(video) { width: 100%; display: block; }
.camera-placeholder {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #8a97a8; font-size: 14px;
}
.camera-guide {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 250px; height: 250px; pointer-events: none;
  border-radius: 16px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.28);
}
.camera-guide::before, .camera-guide::after {
  content: ''; position: absolute; width: 32px; height: 32px;
  border: 3px solid rgba(107, 163, 199, 0.95);
}
.camera-guide::before { top: -3px; left: -3px; border-right: none; border-bottom: none; border-radius: 10px 0 0 0; }
.camera-guide::after { bottom: -3px; right: -3px; border-left: none; border-top: none; border-radius: 0 0 10px 0; }
.scan-actions { display: flex; gap: 10px; }
.btn-start, .btn-stop {
  border: none; border-radius: 10px; padding: 8px 18px; cursor: pointer;
  font-size: 14px; font-weight: 600; font-family: inherit;
}
.btn-start {
  background: linear-gradient(135deg, #6fae83, #8cc39e); color: #fff;
  box-shadow: 0 3px 10px rgba(111, 174, 131, 0.35);
}
.btn-stop { background: rgba(138, 74, 90, 0.85); color: #fff; }

/* ---- 手机联动 ---- */
.mobile-steps { display: flex; flex-direction: column; gap: 6px; }
.mobile-step { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #5a6775; }
.step-num {
  width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6); color: #fff;
  font-size: 12px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
}
.mobile-pair-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.btn-pair {
  border: none; border-radius: 10px; padding: 8px 18px; cursor: pointer;
  background: linear-gradient(135deg, #6fae83, #8cc39e); color: #fff;
  font-size: 14px; font-weight: 600; font-family: inherit;
  box-shadow: 0 3px 10px rgba(111, 174, 131, 0.35);
}
.mobile-status { font-size: 13px; color: #5a6775; font-weight: 600; }
.mobile-url { font-size: 12px; color: #8a97a8; word-break: break-all; }
.pair-qr-box { margin-top: 4px; }
.pair-qr-box img { display: block; border-radius: 12px; border: 1px solid rgba(150, 160, 175, 0.25); }
.mobile-grade-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mobile-actions { display: flex; align-items: center; gap: 8px; }
.btn-refresh, .btn-clear {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 8px; padding: 6px 12px; cursor: pointer;
  font-size: 13px; color: #5a6775; font-family: inherit;
}
.btn-refresh:hover { background: #f0f6fa; }
.btn-clear:hover { background: #fdf0f3; color: #8a4a5a; }
.mobile-scan-count { font-size: 12px; color: #8a97a8; }

/* ---- 待确认列表 ---- */
.pending-card { display: flex; flex-direction: column; gap: 8px; }
.pending-count {
  margin-left: auto; background: #e3ebf2; color: #55636f;
  padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 600;
}
.pending-list { display: flex; flex-direction: column; gap: 6px; min-height: 48px; }
.pending-empty { text-align: center; color: #8a97a8; padding: 20px; font-size: 13px; }
.pending-item {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 12px; border-radius: 10px; background: #f6f8fa; font-size: 13px;
}
.pending-item.external { background: #fdf6f0; }
.pi-code { font-family: 'SF Mono', Consolas, monospace; color: #55636f; font-size: 12px; }
.pi-name { color: #3a4a5a; }
.pi-name.privacy { font-family: 'SF Mono', Consolas, monospace; letter-spacing: 1px; }
.pi-external { color: #b0566a; font-size: 12px; }
.pending-item .grade-badge { margin-left: auto; }
.pi-del {
  border: none; background: transparent; cursor: pointer;
  color: #b0566a; font-size: 13px; padding: 2px 6px; border-radius: 6px;
}
.pi-del:hover { background: rgba(176, 86, 106, 0.12); }
.pending-actions { display: flex; align-items: center; gap: 8px; }
.btn-confirm {
  border: none; border-radius: 10px; padding: 8px 16px; cursor: pointer;
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6); color: #fff;
  font-size: 14px; font-weight: 600; font-family: inherit;
  box-shadow: 0 3px 10px rgba(107, 163, 199, 0.35);
}
.pending-hint { margin-left: auto; font-size: 12px; color: #8a97a8; }
</style>
