<!--
  GroupingTab.vue — 班级分组 Tab(旧版 app.js 分组视图 + ai.js 预警横幅/智能分组弹窗)
  API 契约与旧版 100% 一致,msg 文案逐字保留。
-->
<template>
  <div class="grouping-tab">
    <!-- ========== AI 预警横幅 ========== -->
    <div
      v-for="(a, i) in alerts"
      :key="i"
      class="alert-banner"
      :class="a.level === 'danger' ? 'alert-banner-danger' : 'alert-banner-warning'"
    >
      <div class="alert-banner-item" @click="onAlertClick(a)">
        <span class="alert-icon">{{ a.level === 'danger' ? '🔴' : '🟠' }}</span>
        <div class="alert-content">
          <div class="alert-title">{{ a.title }}</div>
          <div class="alert-detail">{{ a.detail }}</div>
        </div>
        <span class="alert-action">点击查看详情 →</span>
      </div>
    </div>

    <!-- ========== 导入学生名单 ========== -->
    <div class="ct-card import-card">
      <div class="card-header">
        <span class="card-icon">📥</span>
        <h3>导入学生名单</h3>
        <div class="import-mode-switch">
          <button
            class="import-mode-btn"
            :class="{ active: importMode === 'excel' }"
            @click="importMode = 'excel'"
          >📂 Excel导入</button>
          <button
            class="import-mode-btn"
            :class="{ active: importMode === 'text' }"
            @click="importMode = 'text'"
          >📝 文字导入</button>
        </div>
      </div>
      <div class="card-body">
        <!-- Excel 导入模式 -->
        <div v-if="importMode === 'excel'" class="import-panel">
          <div
            class="upload-drop"
            :class="{ over: uploadDragging }"
            @click="pickFile"
            @dragover.prevent="uploadDragging = true"
            @dragleave="onUploadDragLeave"
            @drop.prevent="onUploadDrop"
          >
            <span class="btn-upload">
              <span class="btn-icon">📂</span>
              <span>选择 Excel 文件</span>
            </span>
            <span class="import-hint">支持 .xls / .xlsx 格式，或拖拽文件到此处</span>
          </div>
          <input ref="fileInputRef" type="file" accept=".xls,.xlsx" hidden @change="onFileChange">
        </div>
        <!-- 文字导入模式 -->
        <div v-else class="import-panel text-panel">
          <textarea
            v-model="textImportText"
            class="import-textarea"
            rows="4"
            placeholder="输入学生姓名，用换行、逗号、顿号或空格分隔&#10;例如：张三,李四,王五&#10;或每行一个姓名"
          ></textarea>
          <div class="import-text-actions">
            <span v-if="!textImportText" class="import-text-count">已识别 0 个姓名</span>
            <span v-else class="import-text-count" v-html="parsedPreviewHtml"></span>
            <button class="btn btn-sm btn-export" @click="onConfirmTextImport">✓ 确认导入</button>
          </div>
        </div>
        <span class="import-status" :class="importStatusColor">{{ importStatus }}</span>
      </div>
    </div>

    <!-- ========== 分组控制栏 ========== -->
    <div class="ct-card control-card">
      <div class="control-body">
        <div class="control-left">
          <label class="control-label">分组数量：</label>
          <div class="group-count-picker">
            <button
              v-for="n in [5, 6, 8]"
              :key="n"
              class="count-btn"
              :class="{ active: store.selectedCount === n }"
              :disabled="store.isLocked"
              @click="store.selectedCount = n"
            >{{ n }}组</button>
            <input
              v-model="customCount"
              class="count-input"
              type="number"
              min="2"
              max="20"
              placeholder="自定义"
              :disabled="store.isLocked"
              @keydown.enter="onApplyCount"
            >
            <button class="count-btn count-btn-apply" :disabled="store.isLocked" @click="onApplyCount">✓ 应用</button>
          </div>
        </div>
        <div class="control-center">
          <span v-if="selectedCount > 0" class="selection-info">
            已选 <strong>{{ selectedCount }}</strong> 人
            <button class="btn btn-sm btn-outline" @click="deselectAll">取消全选</button>
          </span>
        </div>
        <div class="control-right">
          <button class="btn btn-outline" :disabled="store.isLocked" @click="onResetGroups">🔄 重新分组</button>
          <button class="btn btn-export" @click="onExportGroups">📥 导出分组名单</button>
          <button v-if="!store.isLocked" class="btn btn-primary btn-lock" @click="onLockGroups">🔒 确定锁定</button>
          <button v-else class="btn btn-outline btn-lock" @click="onUnlockGroups">🔓 解锁分组</button>
          <button class="btn btn-export" title="AI智能均衡分组" :disabled="store.isLocked" @click="smartVisible = true">🧠 AI智能分组</button>
        </div>
      </div>
      <div class="lock-status">
        <span class="lock-dot" :class="{ locked: store.isLocked }"></span>
        <span>{{ lockStatusText }}</span>
      </div>
    </div>

    <!-- ========== 全选工具栏 ========== -->
    <div v-if="selectedCount > 0" class="select-toolbar">
      <button class="btn btn-sm btn-outline" @click="selectAll">☑ 全选所有</button>
      <button class="btn btn-sm btn-outline" @click="deselectAll">☐ 取消全选</button>
      <button class="btn btn-sm btn-danger" @click="onDeleteSelected">🗑 删除选中</button>
    </div>

    <!-- ========== 分组展示区 ========== -->
    <div v-if="store.groups.length === 0" class="empty-state">
      <span class="empty-icon">👥</span>
      <p>尚未设置分组</p>
    </div>
    <div v-else class="groups-container">
      <div
        v-for="g in sortedGroups"
        :key="g.id"
        class="group-column"
        :class="{ 'drag-over': dragOverCol === g.id }"
        :data-group-id="g.id"
        @dragover.prevent="dragOverCol = g.id"
        @dragleave="onColDragLeave"
        @drop.prevent="onColumnDrop(g)"
      >
        <div class="group-column-header">
          <span class="group-name">
            <span class="group-name-dot" :style="{ background: g.color }"></span>{{ g.name }}
          </span>
          <span class="group-student-count">{{ getGroupStudents(g.id).length }}人</span>
        </div>
        <div class="group-students">
          <div v-if="getGroupStudents(g.id).length === 0" class="group-empty-hint">拖拽学生到此处 👆</div>
          <div
            v-for="s in getGroupStudents(g.id)"
            :key="s.id"
            class="student-card"
            :class="cardClasses(s)"
            :draggable="!store.isLocked"
            :data-student-id="s.id"
            @click="onCardClick(s, $event)"
            @dragstart="onDragStart(s, $event)"
            @dragend="onDragEnd"
            @dragover.prevent.stop="onCardDragOver(s)"
            @dragleave="onCardDragLeave"
            @drop.stop.prevent="onCardDrop(s)"
            @animationend="onCardAnimationEnd($event, s.id)"
          >
            <div class="student-avatar" :style="{ background: cardColor(s) }">{{ animalAvatar(s.name) }}</div>
            <span v-if="!showCodes && s.student_code" class="student-code">{{ s.student_code }}</span>
            <span class="student-name" :class="{ 'privacy-mode': showCodes }">{{ displayName(s) }}</span>
            <button class="btn-delete-student" title="删除学生" @click.stop="onDeleteStudent(s)">✕</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 未分组学生名单池 ========== -->
    <div class="ct-card unassigned-card">
      <div class="unassigned-header">
        <span class="card-icon">📋</span>
        <h3>未分组学生名单池</h3>
        <span class="pool-count">{{ unassignedStudents.length }}人</span>
        <button class="btn btn-sm btn-danger" title="一键清除未分组学生" @click="onClearPool">🗑 清空名单池</button>
      </div>
      <div
        class="unassigned-pool"
        :class="{ 'drag-over': dragOverPool }"
        @dragover.prevent="dragOverPool = true"
        @dragleave="onPoolDragLeave"
        @drop.prevent="onPoolDrop"
      >
        <div v-if="unassignedStudents.length === 0" class="pool-placeholder">
          <template v-if="store.students.length === 0">
            <span class="placeholder-icon">📭</span>
            <p>暂无学生，请先导入名单<br>或将学生拖回此处取消分组</p>
          </template>
          <template v-else>
            <span class="placeholder-icon">🎉</span>
            <p>所有学生已分组完毕！</p>
          </template>
        </div>
        <div
          v-for="s in unassignedStudents"
          :key="s.id"
          class="student-card"
          :class="cardClasses(s)"
          :draggable="!store.isLocked"
          :data-student-id="s.id"
          @click="onCardClick(s, $event)"
          @dragstart="onDragStart(s, $event)"
          @dragend="onDragEnd"
          @dragover.prevent.stop="onCardDragOver(s)"
          @dragleave="onCardDragLeave"
          @drop.stop.prevent="onCardDrop(s)"
          @animationend="onCardAnimationEnd($event, s.id)"
        >
          <div class="student-avatar" :style="{ background: cardColor(s) }">{{ animalAvatar(s.name) }}</div>
          <span v-if="!showCodes && s.student_code" class="student-code">{{ s.student_code }}</span>
          <span class="student-name" :class="{ 'privacy-mode': showCodes }">{{ displayName(s) }}</span>
          <button class="btn-delete-student" title="删除学生" @click.stop="onDeleteStudent(s)">✕</button>
        </div>
      </div>
    </div>

    <!-- ========== AI 智能分组弹窗 ========== -->
    <GlassDialog v-model="smartVisible" title="🧠 AI 智能分组" width="640px" append-to-body>
      <div class="smart-controls">
        <span class="control-label">分组数量：</span>
        <el-input-number v-model="smartGroupCount" :min="2" :max="20" size="small" style="width: 110px" />
        <GlassButton type="primary" plain :loading="smartLoading" @click="onSmartPreview">
          {{ smartLoading ? '⏳ 计算中...' : '🔍 预览分组' }}
        </GlassButton>
      </div>
      <div class="smart-preview">
        <div v-if="!smartResult" class="smart-placeholder">
          <span class="placeholder-icon">🧠</span>
          <p>点击「预览分组」查看 AI 均衡分组结果</p>
          <p class="smart-sub">基于近30天作业等级自动均衡</p>
        </div>
        <template v-if="smartResult">
          <div v-for="g in smartResult.groups" :key="g.sort_order" class="smart-group-item">
            <span class="smart-group-color" :style="{ background: g.color }"></span>
            <span class="smart-group-name">{{ g.name }}</span>
            <span class="smart-group-info">{{ g.student_count }}人 · 均分 {{ g.avg_score }}</span>
            <span class="smart-group-students">{{ g.students.map((s) => s.name).join('、') }}</span>
          </div>
        </template>
      </div>
      <div v-if="smartResult" class="smart-actions">
        <GlassButton type="primary" :loading="smartApplying" @click="onSmartApply">
          {{ smartApplying ? '⏳ 应用中...' : '✅ 应用分组' }}
        </GlassButton>
        <GlassButton @click="smartVisible = false">取消</GlassButton>
        <span class="smart-balance">⚖️ 均衡度: {{ smartResult.balance_score }}（越小越均衡）</span>
      </div>
    </GlassDialog>
  </div>
</template>

<script setup lang="ts">
import GlassDialog from '@/components/GlassDialog.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import {
  importExcel, importText, initGroups, saveGroups, lockGroups, unlockGroups, resetGroups,
  moveStudent, batchMoveStudents, batchDeleteStudents, clearUnassigned, deleteStudent,
  loadAIAlerts, aiSmartGroups, aiSmartGroupsApply, downloadUrl,
  type Student, type GroupInfo,
} from '@/api'
import { animalAvatar } from '@/utils/grade'
import { parseTextNames, type ParsedRecord } from '@/utils/textImport'
import { useDialogs } from '@/composables/dialogs'

// ============ 类型(后端返回结构,契约与旧版一致) ============
interface AlertStudent {
  student_id: number
  student_name: string
  group_name: string
  consecutive_days: number
}
interface AlertItem {
  level: 'danger' | 'warning'
  title: string
  detail: string
  type: string
  students?: AlertStudent[]
  data?: Record<string, number>
}
interface SmartStudent { id: number; name: string; avg_score: number }
interface SmartGroup {
  name: string
  color: string
  sort_order: number
  student_count: number
  avg_score: number
  students: SmartStudent[]
}
interface SmartGroupResult {
  group_count: number
  balance_score: number
  groups: SmartGroup[]
  student_count: number
}

const store = useAppStore()
const dialogs = useDialogs()

// ============ AI 预警横幅 ============
const alerts = ref<AlertItem[]>([])
let alertTimer: number | undefined

async function loadAlerts(): Promise<void> {
  try {
    const res = await loadAIAlerts(store.currentClassId)
    if (res.code === 0) {
      const data = res.data as { has_alerts: boolean; alerts: AlertItem[] } | undefined
      alerts.value = data?.has_alerts ? data.alerts : []
    } else {
      alerts.value = []
    }
  } catch { /* 预警加载失败不影响主流程 */ }
}

function onAlertClick(alert: AlertItem): void {
  if (alert.type === 'consecutive_missing' && alert.students && alert.students.length > 0) {
    dialogs.showDetail(
      '⚠️ 连续未交学生名单',
      `<span style="color:#c0392b;font-weight:600">共 ${alert.students.length} 名学生连续3天以上未交作业</span>`,
      alert.students.map((s) => ({
        label: s.student_name,
        sub: `${s.group_name} · 连续 ${s.consecutive_days} 天未交`,
      })),
    )
  } else if (alert.type === 'a_rate_drop') {
    ElMessage.info(`📉 A率下降详情：${alert.detail}`)
  }
}

// ============ 导入 ============
const importMode = ref<'excel' | 'text'>('excel')
const importStatus = ref('')
const importStatusColor = ref<'ok' | 'err' | 'info'>('info')
const textImportText = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadDragging = ref(false)

const parsedRecords = computed<ParsedRecord[]>(() => parseTextNames(textImportText.value))

/** 实时识别计数(与旧版一致:前10条展开预览) */
const parsedPreviewHtml = computed<string>(() => {
  const parsed = parsedRecords.value
  if (parsed.length === 0) return '已识别 0 条'
  const withCodes = parsed.filter((p) => p.code).length
  const previewItems = parsed.slice(0, 10).map((p) =>
    p.code
      ? `<span class="parsed-item">${escapeHtml(p.code)} ${escapeHtml(p.name)}</span>`
      : `<span class="parsed-item">${escapeHtml(p.name)}</span>`,
  )
  const more = parsed.length > 10 ? ` 等${parsed.length}条` : ''
  return `已识别 <strong>${parsed.length}</strong> 条${withCodes > 0 ? `（含学号 ${withCodes} 条）` : ''}：${previewItems.join('、')}${more}`
})

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

function pickFile(): void {
  fileInputRef.value?.click()
}

function onFileChange(e: Event): void {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void handleFileImport(file)
}

function onUploadDragLeave(e: DragEvent): void {
  const zone = e.currentTarget as HTMLElement
  if (!zone.contains(e.relatedTarget as Node | null)) uploadDragging.value = false
}

function onUploadDrop(e: DragEvent): void {
  uploadDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) void handleFileImport(file)
}

async function handleFileImport(file: File): Promise<void> {
  importStatus.value = '⏳ 正在导入...'
  importStatusColor.value = 'info'
  try {
    const res = await importExcel(file, store.currentClassId)
    if (res.code === 0) {
      importStatus.value = `✅ ${res.msg}`
      importStatusColor.value = 'ok'
      ElMessage.success(res.msg)
      await afterImportReload()
    } else {
      importStatus.value = `❌ ${res.msg}`
      importStatusColor.value = 'err'
      if (res.msg) ElMessage.error(res.msg)
    }
  } catch {
    importStatus.value = '❌ 导入失败'
    importStatusColor.value = 'err'
  }
  if (fileInputRef.value) fileInputRef.value.value = ''
  setTimeout(() => {
    if (importStatus.value.startsWith('✅')) importStatus.value = ''
  }, 5000)
}

/** 导入成功后的刷新:首次导入学生时自动初始化分组(与旧版一致) */
async function afterImportReload(): Promise<void> {
  if (store.groups.length === 0) {
    try { await initGroups(store.currentClassId, store.selectedCount) } catch { /* 拦截器已提示 */ }
  }
  await Promise.all([store.loadStudentsData(), store.loadGroupsData(), store.loadStatsData()])
}

/** 轻量刷新:仅重载学生+分组(拖拽移动后用) */
async function reloadStudentsAndGroups(): Promise<void> {
  localReorder.value = {}
  await Promise.all([store.loadStudentsData(), store.loadGroupsData()])
}

async function onConfirmTextImport(): Promise<void> {
  const text = textImportText.value
  if (!text.trim()) { ElMessage.error('请输入学生姓名'); return }
  const parsed = parseTextNames(text)
  if (parsed.length === 0) { ElMessage.error('未能解析出有效记录'); return }
  try {
    const res = await importText(text, parsed, store.currentClassId)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      textImportText.value = ''
      await afterImportReload()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 分组控制 ============
const customCount = ref('')

async function applyGroupCount(): Promise<void> {
  try {
    const res = await initGroups(store.currentClassId, store.selectedCount)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

async function onApplyCount(): Promise<void> {
  const v = parseInt(customCount.value, 10)
  if (v >= 2 && v <= 20) {
    store.selectedCount = v
    await applyGroupCount()
    customCount.value = ''
  } else if (customCount.value.trim()) {
    ElMessage.error('请输入2-20之间的数字')
  }
}

/**
 * 保存整张分组表(与旧版 saveCurrentGrouping 一致,单事务)
 * 返回是否保存成功;锁定前调用,失败则不锁定。
 */
async function saveCurrentGrouping(): Promise<boolean> {
  const groups: { group_id: number; student_ids: number[] }[] = []
  for (const g of sortedGroups.value) {
    groups.push({ group_id: g.id, student_ids: getGroupStudents(g.id).map((s) => s.id) })
  }
  const poolIds = unassignedStudents.value.map((s) => s.id)
  if (poolIds.length > 0) groups.push({ group_id: 0, student_ids: poolIds })
  if (groups.length === 0) return true
  try {
    const res = await saveGroups(store.currentClassId, groups)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      return true
    }
    ElMessage.error(res.msg || '分组保存失败，请重试')
    return false
  } catch {
    return false // 网络错误由拦截器提示
  }
}

async function onLockGroups(): Promise<void> {
  const saved = await saveCurrentGrouping()
  if (!saved) { ElMessage.error('分组保存失败，未锁定'); return }
  try {
    const res = await lockGroups(store.currentClassId)
    if (res.code === 0) {
      ElMessage.success('分组已锁定！✅')
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

async function onUnlockGroups(): Promise<void> {
  try {
    const res = await unlockGroups(store.currentClassId)
    if (res.code === 0) {
      ElMessage.success('分组已解锁 ✅')
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

async function onResetGroups(): Promise<void> {
  const ok = await dialogs.confirm('确定重新分组？所有学生将回到未分组状态。')
  if (!ok) return
  try {
    const res = await resetGroups(store.currentClassId)
    if (res.code === 0) {
      ElMessage.info('已重置')
      await applyGroupCount()
      selectedIds.value = []
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

function onExportGroups(): void {
  window.open(downloadUrl('/export/groups', { class_id: store.currentClassId }), '_blank')
}

// ============ 多选(与旧版 toggleSelect 交互一致) ============
const selectedIds = ref<number[]>([])
const selectedCount = computed(() => selectedIds.value.length)

function selectAll(): void {
  selectedIds.value = store.students.map((s) => s.id)
}

function deselectAll(): void {
  selectedIds.value = []
}

function toggleSelect(sid: number, e: MouseEvent): void {
  if (e.ctrlKey || e.metaKey) {
    const i = selectedIds.value.indexOf(sid)
    if (i >= 0) selectedIds.value.splice(i, 1)
    else selectedIds.value.push(sid)
  } else if (e.shiftKey && selectedIds.value.length > 0) {
    const target = e.target as HTMLElement
    const container = target.closest('.group-students') ?? target.closest('.unassigned-pool')
    if (container) {
      const ids = Array.from(container.querySelectorAll<HTMLElement>('.student-card'))
        .map((c) => parseInt(c.dataset.studentId ?? '', 10))
      const clickedIdx = ids.indexOf(sid)
      const lastSelected = selectedIds.value[selectedIds.value.length - 1]
      const lastIdx = ids.indexOf(lastSelected)
      if (clickedIdx >= 0 && lastIdx >= 0) {
        const from = Math.min(clickedIdx, lastIdx)
        const to = Math.max(clickedIdx, lastIdx)
        for (let i = from; i <= to; i++) {
          if (!selectedIds.value.includes(ids[i])) selectedIds.value.push(ids[i])
        }
      }
    }
  } else {
    const i = selectedIds.value.indexOf(sid)
    if (i >= 0) selectedIds.value.splice(i, 1)
    else selectedIds.value.push(sid)
  }
}

function onCardClick(s: Student, e: MouseEvent): void {
  toggleSelect(s.id, e)
}

async function onDeleteSelected(): Promise<void> {
  const ids = [...selectedIds.value]
  if (ids.length === 0) { ElMessage.error('没有选中的学生'); return }
  const ok = await dialogs.confirm(`确定要删除选中的 ${ids.length} 名学生吗？\n该操作不可恢复，相关作业记录也将一并删除。`)
  if (!ok) return
  try {
    const res = await batchDeleteStudents(ids)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      selectedIds.value = []
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

async function onClearPool(): Promise<void> {
  const unassigned = unassignedStudents.value
  if (unassigned.length === 0) { ElMessage.error('没有未分组的学生'); return }
  const ok = await dialogs.confirm(`确定要清空名单池吗？\n将删除全部 ${unassigned.length} 名未分组学生及其作业记录，此操作不可恢复。`)
  if (!ok) return
  try {
    const res = await clearUnassigned(store.currentClassId)
    if (res.code === 0) {
      ElMessage.success(res.msg || '已清除')
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

async function onDeleteStudent(s: Student): Promise<void> {
  const name = displayName(s)
  const ok = await dialogs.confirm(`确定要删除学生「${name}」吗？\n该操作不可恢复，相关作业记录也将一并删除。`)
  if (!ok) return
  try {
    const res = await deleteStudent(s.id)
    if (res.code === 0) {
      ElMessage.success(`已删除「${name}」`)
      selectedIds.value = selectedIds.value.filter((id) => id !== s.id)
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 展示 ============
/** 分组 Tab 无分区概念:'auto' 模式等同显示姓名,仅 'code' 模式显示学号(旧版 formatStudentDisplay) */
const showCodes = computed(() => store.displayMode === 'code')

const sortedGroups = computed<GroupInfo[]>(() => [...store.groups].sort((a, b) => a.sort_order - b.sort_order))
const unassignedStudents = computed<Student[]>(() => store.students.filter((s) => !s.group_id))

/** 组内排序的本地覆盖(组内拖拽排序用,保存/重载后清空) */
const localReorder = ref<Record<number, number[]>>({})
const bouncedIds = ref<number[]>([])

const studentsByGroup = computed<Record<number, Student[]>>(() => {
  const map: Record<number, Student[]> = {}
  for (const g of store.groups) map[g.id] = []
  for (const s of store.students) {
    if (s.group_id && map[s.group_id]) map[s.group_id].push(s)
  }
  for (const key of Object.keys(map)) {
    const gid = Number(key)
    const order = localReorder.value[gid]
    if (order && order.length > 0) {
      map[gid].sort((a, b) => {
        const ia = order.indexOf(a.id)
        const ib = order.indexOf(b.id)
        if (ia === -1) return 1
        if (ib === -1) return -1
        return ia - ib
      })
    } else {
      map[gid].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
    }
  }
  return map
})

function getGroupStudents(gid: number): Student[] {
  return studentsByGroup.value[gid] ?? []
}

function displayName(s: Student): string {
  return store.displayMode === 'code' ? (s.student_code || '???') : s.name
}

function cardColor(s: Student): string {
  return s.group_color || 'rgba(174,207,226,0.55)'
}

function cardClasses(s: Student): Record<string, boolean> {
  return {
    selected: selectedIds.value.includes(s.id),
    'drop-bounce': bouncedIds.value.includes(s.id),
    'drag-over-card': dragOverCardId.value === s.id,
    dragging: draggingId.value === s.id,
  }
}

function onCardAnimationEnd(e: Event, sid: number): void {
  if (e.target !== e.currentTarget) return
  bouncedIds.value = bouncedIds.value.filter((id) => id !== sid)
}

const lockStatusText = computed(() =>
  store.isLocked
    ? `分组状态：已锁定${store.lastLockTime ? ` (${store.lastLockTime})` : ''}`
    : '分组状态：未锁定',
)

// ============ 拖拽(原生 HTML5,与旧版一致) ============
let dragStudentId: number | null = null
let dragSourceGroupId = 0
let isBatchDrag = false
const dragOverCol = ref<number | null>(null)
const dragOverPool = ref(false)
const dragOverCardId = ref<number | null>(null)
const draggingId = ref<number | null>(null)

function onDragStart(s: Student, e: DragEvent): void {
  dragStudentId = s.id
  dragSourceGroupId = s.group_id || 0
  draggingId.value = s.id
  const dt = e.dataTransfer
  if (!dt) return
  if (selectedIds.value.includes(s.id) && selectedIds.value.length > 1) {
    isBatchDrag = true
    dt.setData('text/plain', JSON.stringify([...selectedIds.value]))
    dt.effectAllowed = 'move'
    const count = selectedIds.value.length
    const ghost = document.createElement('div')
    ghost.style.cssText = 'position:absolute;top:-1000px;background:#7EB5D6;color:white;padding:6px 14px;border-radius:20px;font-size:14px;font-weight:700;white-space:nowrap;'
    ghost.textContent = `📦 移动 ${count} 名学生`
    document.body.appendChild(ghost)
    dt.setDragImage(ghost, 50, 20)
    setTimeout(() => ghost.remove(), 0)
  } else {
    isBatchDrag = false
    dt.setData('text/plain', String(s.id))
    dt.effectAllowed = 'move'
  }
}

function onDragEnd(): void {
  draggingId.value = null
  dragStudentId = null
  dragSourceGroupId = 0
  isBatchDrag = false
  dragOverCol.value = null
  dragOverPool.value = false
  dragOverCardId.value = null
}

function onCardDragOver(s: Student): void {
  if (s.id !== dragStudentId) dragOverCardId.value = s.id
}

function onCardDragLeave(): void {
  dragOverCardId.value = null
}

function onColDragLeave(e: DragEvent): void {
  const col = e.currentTarget as HTMLElement
  if (!col.contains(e.relatedTarget as Node | null)) dragOverCol.value = null
}

function onPoolDragLeave(e: DragEvent): void {
  const pool = e.currentTarget as HTMLElement
  if (!pool.contains(e.relatedTarget as Node | null)) dragOverPool.value = false
}

async function onColumnDrop(g: GroupInfo): Promise<void> {
  dragOverCol.value = null
  if (store.isLocked) { ElMessage.error('分组已锁定，请先点击「解锁分组」'); return }
  if (isBatchDrag) {
    if (selectedIds.value.length > 0) await batchMoveSelected(g.id)
    return
  }
  if (!dragStudentId || g.id === dragSourceGroupId) return
  await moveStudentToGroup(dragStudentId, g.id)
}

async function onPoolDrop(): Promise<void> {
  dragOverPool.value = false
  if (store.isLocked) { ElMessage.error('分组已锁定，请先点击「解锁分组」'); return }
  if (isBatchDrag) {
    if (selectedIds.value.length > 0) await batchMoveSelected(0)
    return
  }
  if (!dragStudentId || dragSourceGroupId === 0) return
  await moveStudentToGroup(dragStudentId, 0)
}

async function onCardDrop(target: Student): Promise<void> {
  dragOverCardId.value = null
  if (store.isLocked) { ElMessage.error('分组已锁定，请先点击「解锁分组」'); return }
  const targetGid = target.group_id || 0
  if (isBatchDrag) {
    if (selectedIds.value.length > 0) await batchMoveSelected(targetGid)
    return
  }
  if (!dragStudentId || dragStudentId === target.id) return
  if (targetGid === dragSourceGroupId) {
    if (targetGid === 0) return // 名单池内无排序概念
    await reorderInGroup(dragStudentId, target.id, targetGid)
    return
  }
  await moveStudentToGroup(dragStudentId, targetGid)
}

/** 组内排序:本地重排后经 saveGroups 持久化(旧版 saveCurrentGrouping 单事务整表保存) */
async function reorderInGroup(sid: number, targetId: number, gid: number): Promise<void> {
  const list = getGroupStudents(gid).map((s) => s.id)
  if (!list.includes(sid) || !list.includes(targetId)) return
  const remaining = list.filter((id) => id !== sid)
  const to = remaining.indexOf(targetId)
  const newOrder = [...remaining.slice(0, to), sid, ...remaining.slice(to)]
  localReorder.value = { ...localReorder.value, [gid]: newOrder }
  await saveCurrentGrouping()
  await reloadStudentsAndGroups() // 无论成败都重新拉取,重置本地排序
}

async function moveStudentToGroup(sid: number, gid: number): Promise<void> {
  try {
    const res = await moveStudent(sid, gid)
    if (res.code === 0) {
      bouncedIds.value = [sid]
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
  await reloadStudentsAndGroups()
}

async function batchMoveSelected(gid: number): Promise<void> {
  const ids = [...selectedIds.value]
  try {
    const res = await batchMoveStudents(store.currentClassId, ids, gid)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      bouncedIds.value = [...ids]
      selectedIds.value = []
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
  await reloadStudentsAndGroups()
}

// ============ AI 智能分组 ============
const smartVisible = ref(false)
const smartGroupCount = ref(6)
const smartLoading = ref(false)
const smartApplying = ref(false)
const smartResult = ref<SmartGroupResult | null>(null)

function onSmartPreview(): void {
  const count = parseInt(String(smartGroupCount.value), 10) || 6
  void previewSmartGroups(count)
}

async function previewSmartGroups(count: number): Promise<void> {
  smartLoading.value = true
  try {
    const res = await aiSmartGroups(store.currentClassId, count)
    if (res.code === 0) {
      smartResult.value = res.data as SmartGroupResult
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
  smartLoading.value = false
}

async function onSmartApply(): Promise<void> {
  if (!smartResult.value) return
  const ok = await dialogs.confirm('确定应用 AI 智能分组吗？当前分组将被 AI 分组结果覆盖。')
  if (!ok) return
  smartApplying.value = true
  try {
    const res = await aiSmartGroupsApply(store.currentClassId, smartResult.value.groups)
    if (res.code === 0) {
      ElMessage.success('✅ AI 智能分组已应用')
      smartVisible.value = false
      await store.loadAllData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 拦截器已提示 */ }
  smartApplying.value = false
}

// ============ 生命周期 ============
onMounted(() => {
  void loadAlerts()
  alertTimer = window.setInterval(() => { void loadAlerts() }, 5 * 60 * 1000)
})

onBeforeUnmount(() => {
  if (alertTimer !== undefined) window.clearInterval(alertTimer)
})

// 切换班级:重载学生+分组
watch(
  () => store.currentClassId,
  async () => {
    selectedIds.value = []
    await Promise.all([store.loadStudentsData(), store.loadGroupsData(), store.loadStatsData()])
    void loadAlerts()
  },
)

// 与旧版 loadGroups 一致:分组数变化时同步选中数量
watch(
  () => store.groups.length,
  (n) => { store.selectedCount = n || 6 },
)
</script>

<style scoped>
/* ---- AI 预警横幅 ---- */
.alert-banner {
  margin: 0 0 12px;
  border-radius: 16px;
  overflow: hidden;
  animation: alertSlideIn 0.4s ease-out;
}
@keyframes alertSlideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
.alert-banner-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; cursor: pointer;
  transition: filter 0.18s ease;
}
.alert-banner-item:hover { filter: brightness(0.96); }
.alert-banner-danger {
  background: linear-gradient(135deg, rgba(231,76,60,0.12), rgba(232,160,191,0.18));
  border: 1px solid rgba(231,76,60,0.2);
}
.alert-banner-warning {
  background: linear-gradient(135deg, rgba(243,156,18,0.1), rgba(244,201,126,0.15));
  border: 1px solid rgba(243,156,18,0.2);
}
.alert-icon { font-size: 1.4rem; flex-shrink: 0; }
.alert-content { flex: 1; min-width: 0; }
.alert-title { font-size: 0.85rem; font-weight: 700; color: #3a4a5a; }
.alert-detail {
  font-size: 0.78rem; color: #8a97a8; margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.alert-action { flex-shrink: 0; font-size: 0.75rem; color: #6ba3c7; font-weight: 600; }

/* ---- 卡片头部 ---- */
.card-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.card-header h3 { font-size: 0.98rem; font-weight: 600; color: #3a4a5a; margin: 0; }
.card-icon { font-size: 1.2rem; }
.import-card, .control-card, .unassigned-card { margin-bottom: 14px; }

/* ---- 导入区 ---- */
.import-mode-switch {
  display: flex; gap: 4px; margin-left: auto;
  background: rgba(255,255,255,0.35);
  backdrop-filter: blur(6px); border-radius: 10px; padding: 3px;
}
.import-mode-btn {
  padding: 5px 12px; border: none; background: transparent;
  border-radius: 8px; cursor: pointer; font-size: 0.8rem;
  color: #8a97a8; font-family: inherit; transition: all 0.18s ease;
}
.import-mode-btn:hover { color: #3a4a5a; }
.import-mode-btn.active {
  background: rgba(255,255,255,0.8); color: #6ba3c7;
  font-weight: 600; box-shadow: 0 2px 8px rgba(90,110,140,0.12);
}
.import-mode-btn:active { transform: scale(0.97); }
.import-panel { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.text-panel { flex-direction: column; align-items: stretch; }
.import-status { display: block; margin-top: 10px; font-size: 0.82rem; font-weight: 600; color: #8a97a8; }
.import-status.ok { color: #2d6a3f; }
.import-status.err { color: #8a4a5a; }
.import-hint { font-size: 0.78rem; color: #8a97a8; }
.upload-drop {
  display: inline-flex; align-items: center; gap: 14px; flex-wrap: wrap;
  border: 2px dashed transparent; border-radius: 12px; padding: 6px;
  transition: border-color 0.18s ease, background 0.18s ease;
}
.upload-drop.over { border-color: #6ba3c7; background: rgba(126,181,214,0.12); }
.btn-upload {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; color: white; border-radius: 10px; cursor: pointer;
  font-size: 0.9rem; font-weight: 600; font-family: inherit;
  background: linear-gradient(135deg, rgba(126,181,214,0.65), rgba(142,200,224,0.7));
  box-shadow: 0 2px 12px rgba(126,181,214,0.25);
  border: 1px solid rgba(255,255,255,0.25);
  backdrop-filter: blur(6px);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.btn-upload:hover { transform: translateY(-1px); box-shadow: 0 4px 18px rgba(126,181,214,0.35); }
.btn-upload:active { transform: translateY(0) scale(0.97); }
.import-textarea {
  width: 100%; padding: 12px 14px;
  border: 1px solid rgba(255,255,255,0.25); border-radius: 10px;
  font-size: 0.88rem; font-family: inherit; color: #3a4a5a;
  resize: vertical; min-height: 80px; line-height: 1.7;
  background: rgba(255,255,255,0.55); backdrop-filter: blur(8px);
  transition: border-color 0.18s ease;
}
.import-textarea:focus { outline: none; border-color: #6ba3c7; }
.import-textarea::placeholder { color: #8a97a8; }
.import-text-actions { display: flex; align-items: center; justify-content: space-between; width: 100%; margin-top: 4px; }
.import-text-count { font-size: 0.82rem; color: #5a6775; }
.import-text-count strong { color: #3a4a5a; }
.parsed-item {
  display: inline-block; background: rgba(174,207,226,0.35); color: #2d5a7a;
  padding: 1px 8px; border-radius: 5px; font-size: 0.78rem; margin: 2px; font-weight: 600;
}

/* ---- 控制栏 ---- */
.control-body { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.control-left, .control-center, .control-right { display: flex; align-items: center; gap: 8px; }
.control-label { font-size: 0.85rem; font-weight: 600; color: #3a4a5a; white-space: nowrap; }
.group-count-picker {
  display: flex; align-items: center; gap: 4px;
  background: rgba(255,255,255,0.35); backdrop-filter: blur(6px);
  border-radius: 10px; padding: 3px;
}
.count-btn {
  padding: 6px 13px; border: none; background: transparent;
  border-radius: 8px; cursor: pointer; font-size: 0.84rem;
  color: #8a97a8; font-family: inherit; transition: all 0.18s ease;
}
.count-btn:hover:not(:disabled) { color: #3a4a5a; background: rgba(255,255,255,0.6); }
.count-btn.active {
  background: rgba(255,255,255,0.8); color: #6ba3c7;
  box-shadow: 0 2px 8px rgba(90,110,140,0.12); font-weight: 600;
}
.count-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.count-btn:active:not(:disabled) { transform: scale(0.97); }
.count-input {
  width: 68px; padding: 6px 8px; border: 2px dashed rgba(0,0,0,0.1);
  border-radius: 8px; text-align: center; font-size: 0.82rem;
  background: rgba(255,255,255,0.4); color: #3a4a5a; font-family: inherit;
  transition: border-color 0.18s ease;
}
.count-input:focus { outline: none; border-color: #6ba3c7; border-style: solid; }
.count-btn-apply { background: #7cb583; color: white; font-weight: 600; }
.count-btn-apply:hover:not(:disabled) { background: #66a06d; color: white; }
.count-btn-apply:active:not(:disabled) { transform: scale(0.97); }
.selection-info {
  font-size: 0.82rem; color: #6ba3c7; background: rgba(174,207,226,0.35);
  padding: 3px 10px; border-radius: 8px; font-weight: 600;
  display: inline-flex; align-items: center; gap: 6px;
}
.selection-info strong { font-weight: 700; }

/* ---- 玻璃按钮系统(与旧版一致) ---- */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 22px; border: 1px solid rgba(255,255,255,0.25);
  border-radius: 10px; cursor: pointer; font-size: 0.92rem; font-weight: 600;
  font-family: inherit; white-space: nowrap; background: transparent; color: #5a6775;
  backdrop-filter: blur(8px);
  transition: transform 0.22s cubic-bezier(0.34,1.3,0.64,1), box-shadow 0.22s ease,
    opacity 0.22s ease, border-color 0.22s ease, background 0.22s ease, color 0.22s ease;
}
.btn:active:not(:disabled) { transform: scale(0.97); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
  background: linear-gradient(135deg, #e8a0bf, #f0a8c0); color: white;
  box-shadow: 0 2px 14px rgba(232,160,191,0.4); font-weight: 700;
}
.btn-primary:hover:not(:disabled) {
  transform: scale(1.05); background: linear-gradient(135deg, #d4789a, #e890b0);
  box-shadow: 0 6px 28px rgba(210,120,150,0.55); color: #fff;
}
.btn-outline {
  background: transparent; border: 2px solid rgba(0,0,0,0.06);
  color: #5a6775; backdrop-filter: none;
}
.btn-outline:hover:not(:disabled) { border-color: #6ba3c7; color: #6ba3c7; background: rgba(174,207,226,0.25); }
.btn-export {
  background: linear-gradient(135deg, rgba(126,181,214,0.7), rgba(142,200,224,0.75));
  color: white; box-shadow: 0 2px 12px rgba(126,181,214,0.22);
}
.btn-export:hover:not(:disabled) {
  transform: scale(1.05); background: linear-gradient(135deg, #5ba0c0, #7eb5d6);
  box-shadow: 0 6px 28px rgba(100,160,200,0.5); color: #fff;
}
.btn-danger {
  background: linear-gradient(135deg, rgba(224,112,128,0.55), rgba(212,136,159,0.6));
  color: white; box-shadow: 0 2px 12px rgba(224,112,128,0.22);
}
.btn-danger:hover:not(:disabled) {
  transform: translateY(-1px); box-shadow: 0 4px 18px rgba(224,112,128,0.32);
  background: linear-gradient(135deg, rgba(208,96,112,0.65), rgba(196,120,143,0.7));
}
.btn-lock { font-size: 1rem; padding: 10px 26px; }
.btn-sm { padding: 6px 14px; font-size: 0.82rem; border-radius: 8px; }
.btn-icon { font-size: 1rem; }

/* ---- 锁定状态 ---- */
.lock-status {
  display: flex; align-items: center; gap: 8px;
  margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(0,0,0,0.06);
  font-size: 0.8rem; color: #8a97a8;
}
.lock-dot { width: 10px; height: 10px; border-radius: 50%; background: #a8b2bd; transition: background 0.18s ease; }
.lock-dot.locked { background: #a8d5ba; box-shadow: 0 0 8px rgba(168,213,186,0.5); }

/* ---- 全选工具栏 ---- */
.select-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }

/* ---- 分组容器 ---- */
.groups-container {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px; margin-bottom: 14px;
}
.group-column {
  background: rgba(255,255,255,0.48);
  backdrop-filter: blur(8px) saturate(1.2);
  border: 2px dashed rgba(200,190,185,0.18);
  border-radius: 16px; min-height: 130px;
  display: flex; flex-direction: column; position: relative; overflow: hidden;
  transition: transform 0.18s ease, background 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  animation: staggerIn 0.35s ease-out both;
}
.group-column::after {
  content: ""; position: absolute; top: 0; left: 5%; right: 5%; height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 30%, rgba(255,255,255,0.3) 70%, transparent 100%);
  pointer-events: none;
}
.group-column.drag-over {
  border-color: #6ba3c7; background: rgba(126,181,214,0.12);
  box-shadow: 0 0 0 3px rgba(107,163,199,0.35); transform: scale(1.015);
}
.group-column-header {
  padding: 10px 12px 6px; border-bottom: 1px solid rgba(0,0,0,0.04);
  display: flex; align-items: center; justify-content: space-between;
}
.group-name { font-size: 0.85rem; font-weight: 700; color: #3a4a5a; display: flex; align-items: center; gap: 6px; }
.group-name-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.group-student-count {
  font-size: 0.72rem; color: #8a97a8; background: rgba(0,0,0,0.03);
  padding: 2px 8px; border-radius: 6px;
}
.group-students { flex: 1; padding: 6px; display: flex; flex-direction: column; gap: 7px; min-height: 50px; }
.group-empty-hint { text-align: center; color: #8a97a8; font-size: 0.75rem; padding: 16px 6px; }

/* ---- 学生卡片 ---- */
.student-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: rgba(255,255,255,0.7); backdrop-filter: blur(6px);
  border: 1px solid rgba(255,255,255,0.3); border-radius: 8px;
  box-shadow: 0 2px 8px rgba(90,110,140,0.08);
  cursor: pointer; user-select: none; position: relative;
  transition: transform 0.22s cubic-bezier(0.34,1.3,0.64,1), box-shadow 0.22s ease,
    opacity 0.22s ease, border-color 0.22s ease;
}
.student-card::before {
  content: ""; position: absolute; top: 0; left: 10%; right: 10%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
  pointer-events: none;
}
.student-card:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(90,110,140,0.14); }
.student-card.dragging { opacity: 0.5; transform: scale(0.95); transition: none !important; }
.student-card.drag-over-card { border-color: #6ba3c7; transform: scale(1.03); }
.student-card.selected { border: 2px solid #6ba3c7; background: rgba(174,207,226,0.25); }
.student-card.selected::after {
  content: "✓"; position: absolute; top: -6px; right: -6px;
  width: 20px; height: 20px; border-radius: 50%;
  background: #6ba3c7; color: white; font-size: 11px;
  display: flex; align-items: center; justify-content: center; font-weight: 700;
}
.student-card.drop-bounce { animation: dropBounce 0.3s cubic-bezier(0.34,1.3,0.64,1); }
@keyframes dropBounce {
  0% { transform: scale(0.6); opacity: 0.4; }
  60% { transform: scale(1.06); }
  100% { transform: scale(1); }
}
.student-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; flex-shrink: 0;
}
.student-code {
  font-size: 0.75rem; color: #8a97a8; font-family: "SF Mono", "Consolas", monospace;
  flex-shrink: 0; background: rgba(0,0,0,0.04); padding: 2px 7px;
  border-radius: 5px; min-width: 32px; text-align: center; font-weight: 600;
}
.student-name {
  font-size: 0.92rem; font-weight: 600; color: #3a4a5a;
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.privacy-mode { font-family: "SF Mono", "Consolas", "Courier New", monospace !important; letter-spacing: 1px; }
.btn-delete-student {
  width: 22px; height: 22px; border: none; border-radius: 50%;
  background: rgba(0,0,0,0.06); color: #8a97a8; cursor: pointer; font-size: 0.7rem;
  display: none; align-items: center; justify-content: center; flex-shrink: 0;
  transition: transform 0.18s ease, background 0.18s ease, color 0.18s ease;
}
.student-card:hover .btn-delete-student { display: flex; }
.btn-delete-student:hover { background: #e8a0bf; color: white; transform: scale(1.05); }
.btn-delete-student:active { transform: scale(0.97); }

/* ---- 未分组池 ---- */
.unassigned-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.unassigned-header h3 { font-size: 0.98rem; font-weight: 600; color: #3a4a5a; margin: 0; }
.pool-count {
  font-size: 0.78rem; color: #8a97a8; background: rgba(255,255,255,0.4);
  padding: 2px 8px; border-radius: 6px; margin-left: auto;
}
.unassigned-pool {
  display: flex; flex-wrap: wrap; gap: 7px; min-height: 70px;
  align-items: flex-start; align-content: flex-start;
  transition: background 0.18s ease; border-radius: 10px; padding: 4px;
}
.unassigned-pool.drag-over { background: rgba(244,201,126,0.25); }
.pool-placeholder { width: 100%; text-align: center; padding: 25px; color: #8a97a8; }
.placeholder-icon { font-size: 2.2rem; display: block; margin-bottom: 6px; }
.empty-state {
  text-align: center; padding: 40px 20px; color: #8a97a8;
  background: rgba(255,255,255,0.48); border-radius: 16px; margin-bottom: 14px;
}
.empty-state p { margin: 8px 0 0; }
.empty-icon { font-size: 2.4rem; }

/* ---- AI 智能分组弹窗 ---- */
.smart-controls { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.smart-preview { max-height: 340px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.smart-placeholder { text-align: center; color: #8a97a8; padding: 30px; }
.smart-placeholder p { margin: 4px 0; }
.smart-sub { font-size: 0.78rem; }
.smart-group-item {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 12px; border-radius: 8px; background: #f6f8fa;
}
.smart-group-color { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.smart-group-name { font-weight: 700; font-size: 0.85rem; color: #3a4a5a; }
.smart-group-info { font-size: 0.78rem; color: #8a97a8; }
.smart-group-students { flex-basis: 100%; font-size: 0.78rem; color: #5a6775; line-height: 1.6; }
.smart-actions { margin-top: 16px; display: flex; align-items: center; gap: 8px; }
.smart-balance { font-size: 0.78rem; color: #8a97a8; margin-left: auto; }

@keyframes staggerIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
