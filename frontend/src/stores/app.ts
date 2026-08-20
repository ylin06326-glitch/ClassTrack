/**
 * 全局应用状态:班级/学生/分组/作业种类/统计。
 * 对应旧版 app.js 的命令式 State 对象,改用 Pinia 响应式管理。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  loadClasses, activateClass, loadStudents, loadGroups, loadStats, loadHomeworkTypes,
  type ClassInfo, type Student, type GroupInfo, type HomeworkType, type Stats,
} from '@/api'

export const useAppStore = defineStore('app', () => {
  // ---- 班级 ----
  const classes = ref<ClassInfo[]>([])
  const currentClassId = ref(1)
  const currentClassName = computed(
    () => classes.value.find((c) => c.id === currentClassId.value)?.name ?? '我的班级',
  )

  // ---- 学生/分组 ----
  const students = ref<Student[]>([])
  const groups = ref<GroupInfo[]>([])
  const unassigned = ref<{ id: number; name: string }[]>([])
  const isLocked = ref(false)
  const lastLockTime = ref('')

  // ---- 作业种类 ----
  const homeworkTypes = ref<HomeworkType[]>([])
  const currentHomeworkTypeId = ref(1)

  // ---- 统计 ----
  const stats = ref<Stats | null>(null)

  // ---- 报表导出的日期区间(报表导出 Tab 与学生个人报表弹窗共享) ----
  const exportStartDate = ref('')
  const exportEndDate = ref('')

  // ---- 分组 UI 状态 ----
  const selectedCount = ref(6)

  // ---- 姓名显示模式: 'name' | 'code' | 'auto'(auto=已完成显名/未完成显学号) ----
  // 与旧版 localStorage 契约保持一致: classtrack_zone_display=auto / classtrack_privacy=1
  const displayMode = ref<'name' | 'code' | 'auto'>('name')
  function initDisplayMode(): void {
    try {
      if (localStorage.getItem('classtrack_zone_display') === 'auto') displayMode.value = 'auto'
      else if (localStorage.getItem('classtrack_privacy') === '1') displayMode.value = 'code'
    } catch { /* localStorage 不可用时保持默认 */ }
  }
  function setDisplayMode(mode: 'name' | 'code' | 'auto'): void {
    displayMode.value = mode
    try {
      localStorage.setItem('classtrack_zone_display', mode === 'auto' ? 'auto' : '')
      localStorage.setItem('classtrack_privacy', mode === 'code' ? '1' : '0')
    } catch { /* ignore */ }
  }
  /** 是否以学号展示(隐私模式:仅显示学号,或分区模式下的未完成分区) */
  const showsCodes = computed(() => displayMode.value !== 'name')

  /** 切换班级:调 activate API 后全量刷新 */
  async function switchClass(classId: number): Promise<void> {
    if (classId === currentClassId.value) return
    await activateClass(classId)
    currentClassId.value = classId
    await loadAllData()
  }

  /** 全量加载:班级 → 学生/分组/统计/作业种类(与旧版 loadAllData 对应) */
  async function loadAllData(): Promise<void> {
    const res = await loadClasses()
    classes.value = res.data
    if (!classes.value.some((c) => c.id === currentClassId.value)) {
      currentClassId.value = res.active_id
    }
    await Promise.all([loadStudentsData(), loadGroupsData(), loadStatsData(), loadTypesData()])
  }

  async function loadStudentsData(): Promise<void> {
    const res = await loadStudents(currentClassId.value)
    students.value = res.data
  }

  async function loadGroupsData(): Promise<void> {
    const res = await loadGroups(currentClassId.value)
    groups.value = res.data.groups
    unassigned.value = res.data.unassigned
    isLocked.value = res.data.groups.some((g) => g.is_locked)
  }

  async function loadStatsData(): Promise<void> {
    const res = await loadStats(currentClassId.value, currentHomeworkTypeId.value)
    stats.value = res.data
    isLocked.value = res.data.is_locked
    lastLockTime.value = res.data.last_lock_time
  }

  async function loadTypesData(): Promise<void> {
    const res = await loadHomeworkTypes()
    homeworkTypes.value = res.data
    if (!homeworkTypes.value.some((t) => t.id === currentHomeworkTypeId.value)) {
      currentHomeworkTypeId.value = homeworkTypes.value[0]?.id ?? 1
    }
  }

  return {
    classes, currentClassId, currentClassName,
    students, groups, unassigned, isLocked, lastLockTime,
    homeworkTypes, currentHomeworkTypeId,
    stats, selectedCount, exportStartDate, exportEndDate,
    displayMode, initDisplayMode, setDisplayMode, showsCodes,
    switchClass, loadAllData, loadStudentsData, loadGroupsData, loadStatsData, loadTypesData,
  }
})
