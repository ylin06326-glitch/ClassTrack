/**
 * 业务 API 封装:所有后端接口的类型定义与调用
 */
import http, { get, post, put, del } from './http'

// ============ 类型 ============
export interface ClassInfo {
  id: number
  name: string
  created_at: string
}

export interface Student {
  id: number
  name: string
  student_code: string
  group_id: number
  group_name: string
  group_color: string
  sort_order: number
  class_id: number
}

export interface GroupInfo {
  id: number
  name: string
  color: string
  sort_order: number
  is_locked: boolean
  students: { id: number; name: string; sort_order: number }[]
}

export interface HomeworkType {
  id: number
  name: string
  sort_order: number
}

export interface Stats {
  total_students: number
  total_groups: number
  grouped_students: number
  unassigned_students: number
  total_homework_records: number
  last_lock_time: string
  is_locked: boolean
  class_name: string
}

export interface ApiResponse<T = any> {
  code: number
  msg?: string
  data?: T
}

// ============ 班级 ============
export const loadClasses = () => get<{ code: number; data: ClassInfo[]; active_id: number }>('/classes')
export const createClass = (name: string) => post('/classes', { name })
export const renameClass = (id: number, name: string) => put(`/classes/${id}`, { name })
export const deleteClass = (id: number) => del(`/classes/${id}`)
export const activateClass = (id: number) => post(`/classes/${id}/activate`)

// ============ 学生 ============
export const loadStudents = (classId: number) => get<{ code: number; data: Student[] }>('/students', { class_id: classId })
export const deleteStudent = (id: number) => del(`/students/${id}`)
export const batchDeleteStudents = (student_ids: number[]) => post('/students/batch-delete', { student_ids })
export const clearUnassigned = (classId: number) => post('/students/clear-unassigned', { class_id: classId })
export const importExcel = (file: File, classId: number) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/import', fd, { params: { class_id: classId } }).then((r) => r.data)
}
export const importText = (text: string, parsed_records: { name: string; code: string }[], classId: number) =>
  post('/import/text', { text, class_id: classId, parsed_records })

// ============ 分组 ============
export const loadGroups = (classId: number) =>
  get<{ code: number; data: { groups: GroupInfo[]; unassigned: { id: number; name: string }[] } }>('/groups', { class_id: classId })
export const initGroups = (classId: number, count: number) => post('/groups/init', { class_id: classId, count })
export const saveGroups = (classId: number, groups: { group_id: number; student_ids: number[] }[]) =>
  post('/groups/save', { class_id: classId, groups })
export const lockGroups = (classId: number) => post('/groups/lock', { class_id: classId })
export const unlockGroups = (classId: number) => post('/groups/unlock', { class_id: classId })
export const resetGroups = (classId: number) => post('/groups/reset', { class_id: classId })
export const moveStudent = (sid: number, group_id: number) => put(`/students/${sid}/move`, { group_id })
export const batchMoveStudents = (classId: number, student_ids: number[], group_id: number) =>
  put('/students/batch-move', { class_id: classId, student_ids, group_id })

// ============ 作业 ============
export const loadHomework = (date: string, classId: number, homeworkTypeId: number) =>
  get<{ code: number; data: Record<string, any> }>('/homework', { date, class_id: classId, homework_type_id: homeworkTypeId })
export const saveHomework = (payload: { student_id: number; date: string; grade: string; class_id: number; homework_type_id: number }) =>
  post('/homework', payload)
export const batchHomework = (payload: { date: string; grade: string; class_id: number; homework_type_id: number; group_id?: number; student_ids?: number[] }) =>
  post('/homework/batch', payload)
export const loadHomeworkRange = (start: string, end: string, classId: number) =>
  get<{ code: number; msg?: string; data: any[]; total: number }>('/homework/range', { start, end, class_id: classId })
export const loadMissing = (date: string, classId: number, homeworkTypeId: number) =>
  get<{ code: number; data: any[]; total: number }>('/homework/missing', { date, class_id: classId, homework_type_id: homeworkTypeId })

export const loadHomeworkTypes = () => get<{ code: number; data: HomeworkType[] }>('/homework-types')
export const createHomeworkType = (name: string) => post('/homework-types', { name })
export const renameHomeworkType = (id: number, name: string) => put(`/homework-types/${id}`, { name })
export const deleteHomeworkType = (id: number) => del(`/homework-types/${id}`)

// ============ 成绩 ============
export const loadExams = (classId: number) => get<{ code: number; msg?: string; data: { exam_name: string; date: string; total_score: number }[] }>('/exam-scores/exams', { class_id: classId })
export const loadExamScores = (examName: string, date: string, classId: number) =>
  get<{ code: number; msg?: string; data: Record<string, any> }>('/exam-scores', { exam_name: examName, date, class_id: classId })
export const saveExamScore = (payload: { student_id: number; exam_name: string; date: string; score: number; total_score: number; class_id: number }) =>
  post('/exam-scores', payload)
export const batchExamScores = (payload: { exam_name: string; date: string; total_score: number; class_id: number; score: number; group_id?: number; student_ids?: number[] }) =>
  post('/exam-scores/batch', payload)
export const importExamScores = (file: File, date: string, classId: number) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/exam-scores/import', fd, { params: { date, class_id: classId } }).then((r) => r.data)
}

// ============ 统计 ============
export const loadStats = (classId: number, homeworkTypeId: number) =>
  get<{ code: number; data: Stats }>('/stats', { class_id: classId, homework_type_id: homeworkTypeId })
export const loadOverview = (date: string, classId: number, homeworkTypeId: number) =>
  get('/analytics/overview', { date, class_id: classId, homework_type_id: homeworkTypeId })
export const loadTrend = (days: number, classId: number, homeworkTypeId: number) =>
  get('/analytics/trend', { days, class_id: classId, homework_type_id: homeworkTypeId })
export const loadGroupRanking = (date: string, classId: number, homeworkTypeId: number) =>
  get('/analytics/group-ranking', { date, class_id: classId, homework_type_id: homeworkTypeId })
export const loadTrendCompare = (period: string, classId: number, homeworkTypeId: number) =>
  get('/analytics/trend-compare', { period, class_id: classId, homework_type_id: homeworkTypeId })
export const loadStudentAlerts = (days: number, classId: number, homeworkTypeId: number) =>
  get('/analytics/student-alerts', { days, class_id: classId, homework_type_id: homeworkTypeId })
export const loadSubmitted = (date: string, grade: string, classId: number, homeworkTypeId: number) =>
  get('/analytics/submitted', { date, grade, class_id: classId, homework_type_id: homeworkTypeId })
export const loadAnalyticsMissing = (date: string, classId: number, homeworkTypeId: number) =>
  get('/analytics/missing', { date, class_id: classId, homework_type_id: homeworkTypeId })
export const loadExamOverview = (examName: string, date: string, classId: number) =>
  get('/analytics/exam-overview', { exam_name: examName, date, class_id: classId })
export const loadStudentReport = (sid: number) => get(`/student/${sid}/report`)

// ============ 扫码 ============
export const findStudentByCode = (code: string, classId: number) => get(`/student/by-code/${encodeURIComponent(code)}`, { class_id: classId })
export const scanBatch = (payload: { date: string; records: { student_code: string; grade: string }[]; class_id: number; homework_type_id: number }) =>
  post('/scan/batch', payload)
export const scanSingle = (payload: { student_code: string; grade: string; date: string; class_id: number; homework_type_id: number }) =>
  post('/scan/single', payload)
export const mobilePair = () => get<{ code: number; data: { ip: string; port: number; url: string; ssl: boolean } }>('/mobile/pair')
export const mobileScanBatch = (codes: string[]) =>
  post<{ code: number; msg: string; data: { count: number } }>('/mobile/scan/batch', { codes })
export const mobileScans = (since: string, classId: number) =>
  http.get('/mobile/scans', { params: { since, class_id: classId }, headers: { 'Cache-Control': 'no-cache' } }).then((r) => r.data)
export const mobileClear = () => post('/mobile/clear')

// ============ 配置 ============
export const loadConfig = () => get('/config')
export const saveConfig = (kv: Record<string, any>) => post('/config', kv)

// ============ AI ============
export const loadAIConfig = () => get('/ai/config')
export const saveAIConfig = (payload: { provider: string; api_key: string; base_url: string; model: string }) => post('/ai/config', payload)
export const testAIConfig = (payload?: any) => post('/ai/test', payload || {})
export const loadAISuggestions = (classId: number, homeworkTypeId: number) =>
  get('/ai/suggestions', { class_id: classId, homework_type_id: homeworkTypeId })
export const aiChat = (question: string, classId: number, homeworkTypeId: number) =>
  post('/ai/chat', { question, class_id: classId, homework_type_id: homeworkTypeId })
export const loadAIAlerts = (classId: number) => get('/ai/alerts', { class_id: classId })
export const aiComment = (sid: number, classId: number) => get(`/ai/comment/${sid}`, { class_id: classId })
export const aiSmartGroups = (classId: number, group_count: number) => post('/ai/smart-groups', { class_id: classId, group_count })
export const aiSmartGroupsApply = (classId: number, groups: any[]) => post('/ai/smart-groups/apply', { class_id: classId, groups })
export const aiImportExam = (file: File, classId: number) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/ai/import-exam', fd, { params: { class_id: classId } }).then((r) => r.data)
}
export const aiExamData = (classId: number) => get('/ai/exam-data', { class_id: classId })
export const aiExamDataClear = (classId: number) => post('/ai/exam-data/clear', { class_id: classId })
export const aiImportExamApply = (payload: { class_name: string; date: string; class_id: number; homework_type_id: number }) =>
  post('/ai/import-exam/apply', payload)
export const aiExportExcel = (payload: { export_data: any; title: string }) => post('/ai/export/excel', payload)
export const aiExportWord = (payload: { export_data: any; reply: string; viz_html: string }) => post('/ai/export/word', payload)

// ============ 文件下载(直接打开,非 fetch) ============
export function downloadUrl(path: string, params: Record<string, any>): string {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
  return `/api${path}?${qs}`
}

// ============ 系统 ============
export const shutdown = () => post('/shutdown')
