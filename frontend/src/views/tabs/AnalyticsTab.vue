<!--
  数据总览 Tab(旧版 Tab 4)
  ============================================================
  对应旧版 static/js/app.js:
    - loadAnalytics(1854-2006):日期控制 + 7 张统计卡片 + 饼图/柱状/趋势线
    - renderTrendCompare / renderGroupRanking / renderStudentAlerts(2012-2170)
    - openDetailModal(2435-2545):统计卡片点击详情弹窗
  API 契约与旧版 100% 一致,msg 文案逐字保留。
  图表由旧版 Chart.js 迁移为 ECharts,配色/标签/动画沿用旧版。
-->
<template>
  <div class="analytics-tab">
    <!-- ========== 控制卡:统计日期 + 作业种类 ========== -->
    <div class="ct-card analytics-control-card">
      <span class="control-label">📅 统计日期：</span>
      <button class="date-nav-btn" @click="shiftDate(-1)">◀</button>
      <input v-model="date" type="date" class="date-input" />
      <button class="date-nav-btn" @click="shiftDate(1)">▶</button>
      <button class="btn-today" @click="setToday">📌 今天</button>
      <span class="control-label type-label">📋 作业种类：</span>
      <el-select v-model="store.currentHomeworkTypeId" class="type-select" size="small">
        <el-option v-for="t in store.homeworkTypes" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <button class="btn-manage-types" title="管理作业种类" @click="typesDialogVisible = true">⚙️</button>
      <span class="class-info">{{ analyticsClassInfo }}</span>
    </div>

    <!-- ========== 7 张统计卡片 ========== -->
    <div class="stats-cards">
      <div class="stat-card stat-card-total" @click="openDetailModal('all')">
        <div class="stat-card-icon">👨‍🎓</div>
        <div class="stat-card-value">{{ cardValues.total }}</div>
        <div class="stat-card-label">班级总人数</div>
      </div>
      <div class="stat-card stat-card-submitted" @click="openDetailModal('submitted')">
        <div class="stat-card-icon">✅</div>
        <div class="stat-card-value">{{ cardValues.submitted }}</div>
        <div class="stat-card-label">已交率</div>
      </div>
      <div class="stat-card stat-card-arate" @click="openDetailModal('arate')">
        <div class="stat-card-icon">⭐</div>
        <div class="stat-card-value">{{ cardValues.aRate }}</div>
        <div class="stat-card-label">A率</div>
      </div>
      <div class="stat-card" @click="openDetailModal('brate')">
        <div class="stat-card-icon">🔵</div>
        <div class="stat-card-value">{{ cardValues.bRate }}</div>
        <div class="stat-card-label">B率</div>
      </div>
      <div class="stat-card" @click="openDetailModal('crate')">
        <div class="stat-card-icon">🟡</div>
        <div class="stat-card-value">{{ cardValues.cRate }}</div>
        <div class="stat-card-label">C率</div>
      </div>
      <div class="stat-card stat-card-missing" @click="openDetailModal('missing')">
        <div class="stat-card-icon">⚠️</div>
        <div class="stat-card-value">{{ cardValues.missing }}</div>
        <div class="stat-card-label">未交人数</div>
      </div>
      <div class="stat-card no-click">
        <div class="stat-card-icon">📊</div>
        <div class="stat-card-value">{{ cardValues.avgScore }}</div>
        <div class="stat-card-label">全班平均分</div>
      </div>
    </div>

    <!-- ========== 图表区 ========== -->
    <div class="charts-grid">
      <div class="ct-card chart-card">
        <div class="card-header"><span class="card-icon">🍩</span><h3>今日作业分布</h3></div>
        <div ref="pieRef" class="chart-body"></div>
      </div>
      <div class="ct-card chart-card">
        <div class="card-header"><span class="card-icon">📊</span><h3>分组对比</h3></div>
        <div ref="barRef" class="chart-body"></div>
      </div>
    </div>
    <div class="ct-card chart-card">
      <div class="card-header"><span class="card-icon">📈</span><h3>近14天提交率趋势</h3></div>
      <div ref="lineRef" class="chart-body"></div>
    </div>

    <!-- 环比趋势对比 -->
    <div class="ct-card chart-card">
      <div class="card-header">
        <span class="card-icon">📉</span><h3>环比趋势对比</h3>
        <div class="compare-btns">
          <button
            class="compare-period-btn"
            :class="{ active: comparePeriod === 'week' }"
            @click="onComparePeriod('week')"
          >本周vs上周</button>
          <button
            class="compare-period-btn"
            :class="{ active: comparePeriod === 'month' }"
            @click="onComparePeriod('month')"
          >本月vs上月</button>
        </div>
      </div>
      <div ref="compareRef" class="chart-body"></div>
      <div class="compare-summary" v-html="compareSummaryHtml"></div>
    </div>

    <!-- 小组排行榜 -->
    <div class="ct-card chart-card">
      <div class="card-header">
        <span class="card-icon">🏆</span><h3>小组排行榜</h3>
        <span class="ranking-date">{{ rankingDate }}</span>
      </div>
      <div v-if="!rankingLoaded" class="ranking-empty">加载中...</div>
      <div v-else-if="ranking.length === 0" class="ranking-empty">暂无分组数据</div>
      <div v-else>
        <div v-for="(g, i) in ranking" :key="g.group_id" class="ranking-item">
          <span class="ranking-medal">{{ i < 3 ? medals[i] : i + 1 }}</span>
          <span class="ranking-name">{{ g.group_name }}</span>
          <div class="ranking-bar-wrap">
            <div
              class="ranking-bar-fill"
              :style="{
                background: g.color || groupColor(i),
                transform: `scaleX(${rankingAnimated ? g.a_rate / 100 : 0})`,
              }"
            >
              <span class="ranking-bar-label">{{ g.a_rate }}%</span>
            </div>
          </div>
          <span class="ranking-stats">提交率 {{ g.submit_rate }}% · {{ g.total }}人</span>
        </div>
      </div>
    </div>

    <!-- 学生预警与进步追踪 -->
    <div class="ct-card chart-card">
      <div class="card-header"><span class="card-icon">🔔</span><h3>学生预警与进步追踪</h3></div>
      <div v-if="!alertsLoaded" class="alerts-empty">加载中...</div>
      <div
        v-else-if="!alertsData || (alertsData.at_risk.length === 0 && alertsData.improving.length === 0)"
        class="alerts-empty"
      >🎉 目前没有需要特别关注的学生</div>
      <template v-else>
        <div class="alerts-tabs">
          <button
            class="alerts-tab-btn tab-risk"
            :class="{ active: alertsTab === 'risk' }"
            @click="alertsTab = 'risk'"
          >⚠️ 需关注 ({{ alertsData.at_risk.length }})</button>
          <button
            class="alerts-tab-btn tab-improve"
            :class="{ active: alertsTab === 'improve' }"
            @click="alertsTab = 'improve'"
          >🌟 进步中 ({{ alertsData.improving.length }})</button>
        </div>
        <div v-show="alertsTab === 'risk'">
          <div v-if="alertsData.at_risk.length === 0" class="alerts-empty">✅ 暂无连续未交的学生</div>
          <div
            v-for="s in alertsData.at_risk"
            :key="s.student_id"
            class="alert-student-item risk"
            @click="dialogs.showStudentReport(s.student_id, alertDisplayName(s.student_name, s.student_id, 'incomplete'))"
          >
            <span class="alert-student-name">{{ alertDisplayName(s.student_name, s.student_id, 'incomplete') }}</span>
            <span class="alert-student-group">{{ s.group_name }}</span>
            <span class="alert-student-tag risk">连续{{ s.consecutive_x }}次未交</span>
            <span class="alert-student-grades">
              <span v-for="(g, gi) in s.last_grades" :key="gi" :class="`g-${g}`">{{ gradeDisplayLabel(g) }}</span>
            </span>
          </div>
        </div>
        <div v-show="alertsTab === 'improve'">
          <div v-if="alertsData.improving.length === 0" class="alerts-empty">💪 暂未检测到明显进步趋势</div>
          <div
            v-for="s in alertsData.improving"
            :key="s.student_id"
            class="alert-student-item improve"
            @click="dialogs.showStudentReport(s.student_id, alertDisplayName(s.student_name, s.student_id, 'completed'))"
          >
            <span class="alert-student-name">{{ alertDisplayName(s.student_name, s.student_id, 'completed') }}</span>
            <span class="alert-student-group">{{ s.group_name }}</span>
            <span class="alert-student-tag improve">{{ s.from_grade }}→{{ s.to_grade }} 进步</span>
            <span class="alert-student-grades">
              <span v-for="(g, gi) in s.recent_grades" :key="gi" :class="`g-${g}`">{{ gradeDisplayLabel(g) }}</span>
            </span>
          </div>
        </div>
      </template>
    </div>

    <HomeworkTypesDialog v-model="typesDialogVisible" />
  </div>
</template>

<script setup lang="ts">
/**
 * 数据总览:7 张统计卡片 + 5 类图表 + 排行榜 + 学生预警。
 * 接口契约与旧版 app.js 完全一致(backend/app/routers/analytics.py)。
 */
import { computed, reactive, ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { useAppStore } from '@/stores/app'
import { useDialogs, type DetailItem } from '@/composables/dialogs'
import {
  loadOverview, loadTrend, loadGroupRanking, loadTrendCompare,
  loadStudentAlerts, loadSubmitted, loadAnalyticsMissing,
  type ApiResponse,
} from '@/api'
import { GRADE_META, groupColor, gradeDisplayLabel } from '@/utils/grade'
import HomeworkTypesDialog from '@/components/HomeworkTypesDialog.vue'

// ============ 接口类型(补充自 backend/app/routers/analytics.py) ============
interface GradeCounts { A: number; B: number; C: number; L: number; X: number }
interface GroupComparison {
  group_id: number; group_name: string; color: string
  total: number; a_count: number; missing: number; a_rate: number
}
interface OverviewData {
  date: string; total_students: number
  grade_counts: GradeCounts; unrecorded: number
  group_comparison: GroupComparison[]
}
interface TrendPoint { date: string; submitted: number; total: number; rate: number }
interface RankingItem {
  group_id: number; group_name: string; color: string; total: number
  a_count: number; b_count: number; c_count: number; x_count: number; submit_count: number
  a_rate: number; submit_rate: number; avg_score: number
}
interface GroupRankingResponse extends ApiResponse<RankingItem[]> { date?: string }
interface ComparePoint { date: string; rate: number }
interface TrendCompareData {
  current: ComparePoint[]; previous: ComparePoint[]
  current_avg: number; previous_avg: number; change: number
  period: string; total_students: number
}
interface RiskStudent {
  student_id: number; student_name: string; group_name: string
  consecutive_x: number; last_grades: string[]
}
interface ImprovingStudent {
  student_id: number; student_name: string; group_name: string
  from_grade: string; to_grade: string; recent_grades: string[]
}
interface StudentAlertsData { at_risk: RiskStudent[]; improving: ImprovingStudent[] }
interface SubmittedStudent {
  student_id: number; student_name: string; student_code: string
  grade: string; grade_label: string; group_name: string; group_color: string
}
interface SubmittedResponse extends ApiResponse<SubmittedStudent[]> { total?: number }
interface MissingStudent {
  student_id: number; student_name: string; student_code: string
  group_name: string; group_color: string
}
interface MissingResponse extends ApiResponse<MissingStudent[]> { total?: number }
/** 详情弹窗条目:在全局 DetailItem 上补充等级徽章与个人报表跳转字段(MainLayout 渲染) */
interface DetailItemExt extends DetailItem { grade?: string; gradeLabel?: string; sid?: number }

const store = useAppStore()
const dialogs = useDialogs()

// ============ 控制区 ============
const date = ref(todayStr())
const comparePeriod = ref<'week' | 'month'>('week')
const typesDialogVisible = ref(false)
const analyticsClassInfo = computed(() => `班级：${store.currentClassName}`)

function todayStr(): string {
  return new Date().toISOString().split('T')[0]
}
function setToday(): void {
  date.value = todayStr()
}
function shiftDate(delta: number): void {
  const d = new Date(date.value)
  d.setDate(d.getDate() + delta)
  date.value = d.toISOString().split('T')[0]
}

// ============ 7 张统计卡片(数值平滑动画,照旧 animateValue) ============
type CardKey = 'total' | 'submitted' | 'aRate' | 'bRate' | 'cRate' | 'missing' | 'avgScore'
const cardValues = reactive<Record<CardKey, string>>({
  total: '0',
  submitted: '0%',
  aRate: '0%',
  bRate: '0%',
  cRate: '0%',
  missing: '0',
  avgScore: '0.0',
})
const cardAnimFrames: Partial<Record<CardKey, number>> = {}

/** 数值平滑动画:从当前显示值 easeOutCubic 过渡到目标值(照旧 animateValue) */
function animateText(key: CardKey, target: number, opts: { suffix?: string; decimals?: number } = {}): void {
  const { suffix = '', decimals = 0 } = opts
  const current = parseFloat(cardValues[key].replace(/[^0-9.]/g, '')) || 0
  const duration = 350
  if (isNaN(current) || isNaN(target)) {
    cardValues[key] = `${target}${suffix}`
    return
  }
  if (current === target) {
    cardValues[key] = `${decimals > 0 ? target.toFixed(decimals) : target}${suffix}`
    return
  }
  const prev = cardAnimFrames[key]
  if (prev !== undefined) cancelAnimationFrame(prev)
  const start = performance.now()
  const step = (now: number): void => {
    const progress = Math.min((now - start) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // easeOutCubic
    const val = current + (target - current) * eased
    cardValues[key] = `${decimals > 0 ? val.toFixed(decimals) : Math.round(val)}${suffix}`
    if (progress < 1) cardAnimFrames[key] = requestAnimationFrame(step)
  }
  cardAnimFrames[key] = requestAnimationFrame(step)
}

// ============ 图表(ECharts 替代旧版 Chart.js,配色照旧) ============
type EChart = ReturnType<typeof echarts.init>
const pieRef = ref<HTMLDivElement | null>(null)
const barRef = ref<HTMLDivElement | null>(null)
const lineRef = ref<HTMLDivElement | null>(null)
const compareRef = ref<HTMLDivElement | null>(null)

let chartPie: EChart | null = null
let chartBar: EChart | null = null
let chartLine: EChart | null = null
let chartCompare: EChart | null = null
let chartsReady = false
let resizeObserver: ResizeObserver | null = null

const overviewData = ref<OverviewData | null>(null)
const trendData = ref<TrendPoint[]>([])
const compareData = ref<TrendCompareData | null>(null)
const compareSummaryHtml = ref('')

function percentValueFormatter(value: unknown): string {
  const v = Array.isArray(value) ? value[0] : value
  const n = typeof v === 'number' ? v : Number(v)
  return `${isNaN(n) ? 0 : n}%`
}

/** 🍩 今日作业分布(等级色照旧:#A8D5BA/#7EB5D6/#F4C97E/#C5B3E6/#E8A0BF) */
function buildPieOption(d: OverviewData): EChartsOption {
  const gc = d.grade_counts
  const missing = (gc.X || 0) + (d.unrecorded || 0)
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '45%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
        label: { show: false },
        data: [
          { name: 'A (优秀)', value: gc.A || 0, itemStyle: { color: GRADE_META.A.color } },
          { name: 'B (良好)', value: gc.B || 0, itemStyle: { color: GRADE_META.B.color } },
          { name: 'C (待提升)', value: gc.C || 0, itemStyle: { color: GRADE_META.C.color } },
          { name: '请假', value: gc.L || 0, itemStyle: { color: GRADE_META.L.color } },
          { name: '未交', value: missing, itemStyle: { color: GRADE_META.X.color } },
        ],
      },
    ],
  }
}

/** 📊 分组对比:A率 + 未交人数(照旧配色 #A8D5BA / #E8A0BF) */
function buildBarOption(gc: GroupComparison[]): EChartsOption {
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
    grid: { left: 44, right: 16, top: 28, bottom: 48 },
    xAxis: { type: 'category', data: gc.map((g) => g.group_name), axisLabel: { fontSize: 11 } },
    yAxis: {
      type: 'value', min: 0,
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: 'A率 (%)', type: 'bar', data: gc.map((g) => g.a_rate), barMaxWidth: 26,
        itemStyle: { color: GRADE_META.A.color, borderRadius: [8, 8, 0, 0] },
      },
      {
        name: '未交人数', type: 'bar', data: gc.map((g) => g.missing), barMaxWidth: 26,
        itemStyle: { color: GRADE_META.X.color, borderRadius: [8, 8, 0, 0] },
      },
    ],
  }
}

/** 📈 近14天提交率趋势 */
function buildTrendOption(td: TrendPoint[]): EChartsOption {
  return {
    tooltip: { trigger: 'axis', valueFormatter: percentValueFormatter },
    grid: { left: 44, right: 16, top: 28, bottom: 30 },
    xAxis: {
      type: 'category', boundaryGap: false,
      data: td.map((t) => t.date.slice(5)),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'value', min: 0, max: 100,
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
      axisLabel: { fontSize: 11, formatter: '{value}%' },
    },
    series: [
      {
        name: '提交率 (%)', type: 'line', data: td.map((t) => t.rate),
        smooth: 0.4, symbol: 'circle', symbolSize: 8,
        lineStyle: { width: 2, color: '#7EB5D6' },
        itemStyle: { color: '#7EB5D6' },
        areaStyle: { color: 'rgba(126,181,214,0.1)' },
      },
    ],
  }
}

/** 📉 环比趋势对比:本期实线 + 上期虚线(照旧 #7EB5D6 / #BFBBBB) */
function buildCompareOption(data: TrendCompareData): EChartsOption {
  return {
    tooltip: { trigger: 'axis', valueFormatter: percentValueFormatter },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11 } },
    grid: { left: 44, right: 16, top: 28, bottom: 48 },
    xAxis: {
      type: 'category', boundaryGap: false,
      data: data.current.map((d) => d.date),
      axisLabel: { fontSize: 9 },
    },
    yAxis: {
      type: 'value', min: 0, max: 100,
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
      axisLabel: { fontSize: 10, formatter: '{value}%' },
    },
    series: [
      {
        name: '本期', type: 'line', data: data.current.map((d) => d.rate),
        smooth: 0.4, symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#7EB5D6' },
        itemStyle: { color: '#7EB5D6' },
        areaStyle: { color: 'rgba(126,181,214,0.08)' },
      },
      {
        name: '上期', type: 'line', data: data.previous.map((d) => d.rate),
        smooth: 0.4, symbol: 'circle', symbolSize: 4,
        lineStyle: { width: 1.5, color: '#BFBBBB', type: [5, 3] },
        itemStyle: { color: '#BFBBBB' },
      },
    ],
  }
}

function renderPie(): void {
  if (chartPie && overviewData.value) chartPie.setOption(buildPieOption(overviewData.value))
}
function renderBar(): void {
  if (chartBar && overviewData.value) chartBar.setOption(buildBarOption(overviewData.value.group_comparison || []))
}
function renderTrend(): void {
  if (chartLine) chartLine.setOption(buildTrendOption(trendData.value))
}
function renderCompare(): void {
  if (chartCompare && compareData.value) chartCompare.setOption(buildCompareOption(compareData.value))
}
function renderAllCharts(): void {
  renderPie()
  renderBar()
  renderTrend()
  renderCompare()
}

function initCharts(): void {
  if (chartsReady) return
  if (!pieRef.value || !barRef.value || !lineRef.value || !compareRef.value) return
  // Tab 以 v-show 切换,隐藏时无尺寸;待可见(容器有宽度)后再初始化
  if (pieRef.value.offsetWidth === 0) return
  chartPie = echarts.init(pieRef.value)
  chartBar = echarts.init(barRef.value)
  chartLine = echarts.init(lineRef.value)
  chartCompare = echarts.init(compareRef.value)
  chartsReady = true
  renderAllCharts()
}

function onResize(): void {
  initCharts()
  chartPie?.resize()
  chartBar?.resize()
  chartLine?.resize()
  chartCompare?.resize()
}

// ============ 小组排行榜 / 学生预警 ============
const ranking = ref<RankingItem[]>([])
const rankingDate = ref('')
const rankingLoaded = ref(false)
const rankingAnimated = ref(false)
const medals = ['🥇', '🥈', '🥉']

const alertsData = ref<StudentAlertsData | null>(null)
const alertsLoaded = ref(false)
const alertsTab = ref<'risk' | 'improve'>('risk')

/** 排行榜条形入场动画(照旧:双 rAF 后 scaleX 过渡) */
function animateRanking(): void {
  rankingAnimated.value = false
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      rankingAnimated.value = true
    })
  })
}

/** 环比对比底部总结文案(照旧 compareSummary) */
function buildCompareSummary(data: TrendCompareData): string {
  const arrow = data.change >= 0 ? '↑' : '↓'
  const color = data.change >= 0 ? '#A8D5BA' : '#E8A0BF' // 旧版 var(--green)/var(--pink)
  return `本期平均 <strong>${data.current_avg}%</strong> | 上期 <strong>${data.previous_avg}%</strong> | 变化 <strong style="color:${color}">${arrow} ${Math.abs(data.change)}%</strong>`
}

// ============ 姓名显示(照旧 formatStudentDisplay / formatStudentCodeHtml) ============
/** 详情弹窗条目姓名:incomplete 显学号;completed 显姓名(非隐私模式带学号前缀);null 按显示模式 */
function detailDisplayName(name: string, code: string, zone: 'completed' | 'incomplete' | null): string {
  if (zone === 'incomplete') return code || name
  if (zone === 'completed') return store.displayMode === 'code' ? name : code ? `${code} ${name}` : name
  if (store.displayMode === 'code') return code || '???'
  return code ? `${code} ${name}` : name
}
/** 预警列表姓名(照旧:需关注显学号、进步中显姓名,无学号前缀) */
function alertDisplayName(name: string, sid: number, zone: 'completed' | 'incomplete'): string {
  const code = store.students.find((s) => s.id === sid)?.student_code || ''
  return zone === 'incomplete' ? code || name : name
}

// ============ 数据加载(照旧 loadAnalytics) ============
async function loadAnalytics(): Promise<void> {
  try {
    const [overview, trendRes, rankingRes, compareRes, alertsRes] = await Promise.all([
      loadOverview(date.value, store.currentClassId, store.currentHomeworkTypeId) as Promise<ApiResponse<OverviewData>>,
      loadTrend(14, store.currentClassId, store.currentHomeworkTypeId) as Promise<ApiResponse<TrendPoint[]>>,
      loadGroupRanking(date.value, store.currentClassId, store.currentHomeworkTypeId) as Promise<GroupRankingResponse>,
      loadTrendCompare(comparePeriod.value, store.currentClassId, store.currentHomeworkTypeId) as Promise<ApiResponse<TrendCompareData>>,
      loadStudentAlerts(14, store.currentClassId, store.currentHomeworkTypeId) as Promise<ApiResponse<StudentAlertsData>>,
    ])
    if (overview.code !== 0) {
      if (overview.msg) ElMessage.error(overview.msg)
      return
    }
    const d = overview.data
    if (!d) return
    overviewData.value = d

    // 7 张统计卡片
    const total = d.total_students
    const aCount = d.grade_counts.A || 0
    const bCount = d.grade_counts.B || 0
    const cCount = d.grade_counts.C || 0
    const submitted = aCount + bCount + cCount
    const missing = (d.grade_counts.X || 0) + (d.unrecorded || 0)
    const aRate = total > 0 ? Math.round((aCount / total) * 100) : 0
    const bRate = total > 0 ? Math.round((bCount / total) * 100) : 0
    const cRate = total > 0 ? Math.round((cCount / total) * 100) : 0
    const submitRate = total > 0 ? Math.round((submitted / total) * 100) : 0
    const avgScore = submitted > 0 ? ((aCount * 3 + bCount * 2 + cCount * 1) / submitted).toFixed(1) : '0.0'
    animateText('total', total)
    animateText('submitted', submitRate, { suffix: '%' })
    animateText('aRate', aRate, { suffix: '%' })
    animateText('bRate', bRate, { suffix: '%' })
    animateText('cRate', cRate, { suffix: '%' })
    animateText('missing', missing)
    cardValues.avgScore = avgScore // 平均分不参与动画(照旧)

    // 近14天趋势
    if (trendRes.code === 0) trendData.value = trendRes.data || []
    else if (trendRes.msg) ElMessage.error(trendRes.msg)

    // 小组排行榜
    if (rankingRes.code === 0) {
      ranking.value = rankingRes.data || []
      rankingDate.value = rankingRes.date || ''
      animateRanking()
    } else if (rankingRes.msg) ElMessage.error(rankingRes.msg)
    rankingLoaded.value = true

    // 环比趋势对比
    if (compareRes.code === 0) {
      compareData.value = compareRes.data ?? null
      compareSummaryHtml.value = compareRes.data ? buildCompareSummary(compareRes.data) : ''
    } else if (compareRes.msg) ElMessage.error(compareRes.msg)

    // 学生预警与进步追踪
    if (alertsRes.code === 0) alertsData.value = alertsRes.data || { at_risk: [], improving: [] }
    else if (alertsRes.msg) ElMessage.error(alertsRes.msg)
    alertsLoaded.value = true

    renderAllCharts()
  } catch {
    /* HTTP 400 已由拦截器 toast */
  }
}

// ============ 环比周期切换(照旧 compare-period-btn) ============
async function onComparePeriod(period: 'week' | 'month'): Promise<void> {
  comparePeriod.value = period
  try {
    const res: ApiResponse<TrendCompareData> = await loadTrendCompare(
      period, store.currentClassId, store.currentHomeworkTypeId,
    )
    if (res.code === 0) {
      compareData.value = res.data ?? null
      compareSummaryHtml.value = res.data ? buildCompareSummary(res.data) : ''
      renderCompare()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch {
    /* HTTP 400 已由拦截器 toast */
  }
}

// ============ 统计卡片详情弹窗(照旧 openDetailModal 2435-2545) ============
type DetailType = 'all' | 'submitted' | 'arate' | 'brate' | 'crate' | 'missing'

async function openDetailModal(type: DetailType): Promise<void> {
  try {
    if (type === 'all') {
      const items: DetailItemExt[] = store.students.map((s) => ({
        label: detailDisplayName(s.name, s.student_code, null),
        sub: s.group_name || '未分组',
        sid: s.id,
      }))
      dialogs.showDetail(
        '👨‍🎓 班级全部学生',
        `共 <strong>${store.students.length}</strong> 名学生`,
        items,
      )
      return
    }
    if (type === 'submitted' || type === 'arate' || type === 'brate' || type === 'crate') {
      const grade = type === 'submitted' ? '' : type.charAt(0).toUpperCase()
      const res: SubmittedResponse = await loadSubmitted(
        date.value, grade, store.currentClassId, store.currentHomeworkTypeId,
      )
      if (res.code !== 0) {
        if (res.msg) ElMessage.error(res.msg)
        return
      }
      const list = res.data || []
      const toItems = (): DetailItemExt[] => list.map((s) => ({
        label: detailDisplayName(s.student_name, s.student_code, 'completed'),
        sub: s.group_name,
        grade: s.grade,
        gradeLabel: s.grade_label,
        sid: s.student_id,
      }))
      if (type === 'submitted') {
        dialogs.showDetail(
          '✅ 今日已交学生',
          `日期：<strong>${date.value}</strong> &nbsp;|&nbsp; 已交：<strong>${res.total}</strong> 人`,
          toItems(),
        )
        return
      }
      // A/B/C 率详情:额外取 overview 计算比例(照旧)
      const gradeCount = res.total || 0
      const overview: ApiResponse<OverviewData> = await loadOverview(
        date.value, store.currentClassId, store.currentHomeworkTypeId,
      )
      const total = overview.code === 0 ? overview.data?.total_students ?? 0 : 0
      const rate = total > 0 ? Math.round((gradeCount / total) * 100) : 0
      const titles: Record<string, string> = { A: '⭐ A率详情', B: '🔵 B率详情', C: '🟡 C率详情' }
      dialogs.showDetail(
        titles[grade],
        `日期：<strong>${date.value}</strong> &nbsp;|&nbsp; ${grade}率：<strong>${rate}%</strong>（${gradeCount}/${total}）`,
        list.length === 0 ? [{ label: `暂无获得${grade}的学生` }] : toItems(),
      )
      return
    }
    // 未交名单
    const res: MissingResponse = await loadAnalyticsMissing(
      date.value, store.currentClassId, store.currentHomeworkTypeId,
    )
    if (res.code !== 0) {
      if (res.msg) ElMessage.error(res.msg)
      return
    }
    const list = res.data || []
    dialogs.showDetail(
      '⚠️ 今日未交学生',
      `日期：<strong>${date.value}</strong> &nbsp;|&nbsp; 未交：<strong>${res.total}</strong> 人`,
      list.length === 0
        ? [{ label: '🎉 太棒了！所有学生都已交作业！' }]
        : list.map((s) => ({
            label: detailDisplayName(s.student_name, s.student_code, 'incomplete'),
            sub: s.group_name,
            sid: s.student_id,
          })),
    )
  } catch {
    /* HTTP 400 已由拦截器 toast */
  }
}

// ============ 生命周期 ============
// 班级 / 作业种类 / 日期任一变化 → 全量重载(照旧 loadAnalytics)
watch(
  [() => store.currentClassId, () => store.currentHomeworkTypeId, () => date.value],
  () => { void loadAnalytics() },
)

onMounted(() => {
  initCharts()
  resizeObserver = new ResizeObserver(() => onResize())
  for (const el of [pieRef.value, barRef.value, lineRef.value, compareRef.value]) {
    if (el) resizeObserver.observe(el)
  }
  window.addEventListener('resize', onResize)
  void loadAnalytics()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  resizeObserver?.disconnect()
  resizeObserver = null
  chartPie?.dispose()
  chartBar?.dispose()
  chartLine?.dispose()
  chartCompare?.dispose()
  chartPie = null
  chartBar = null
  chartLine = null
  chartCompare = null
  chartsReady = false
})
</script>

<style scoped>
/* ============================================================
   玻璃风格(复刻旧版 style_v2.css 数据概览区块)
   ============================================================ */

/* ---- 控制卡 ---- */
.analytics-control-card {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 12px 16px; margin-bottom: 14px;
}
.control-label { font-size: 0.88rem; color: #5a6775; font-weight: 600; }
.type-label { margin-left: 8px; }
.date-nav-btn {
  width: 30px; height: 30px; border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  border-radius: 50%; cursor: pointer; font-size: 0.75rem; color: #5d5a5a;
  display: flex; align-items: center; justify-content: center;
  transition: transform 0.18s, background 0.18s, color 0.18s;
}
.date-nav-btn:hover { background: #7eb5d6; color: #fff; }
.date-nav-btn:active { transform: scale(0.97); }
.date-input {
  padding: 6px 10px; border: 1px solid rgba(200, 190, 185, 0.3);
  border-radius: 10px; font-size: 0.85rem; color: #5d5a5a;
  background: rgba(255, 255, 255, 0.75); font-family: inherit;
  transition: border-color 0.18s;
}
.date-input:focus { outline: none; border-color: #7eb5d6; }
.btn-today {
  padding: 5px 12px; border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 10px; background: rgba(255, 255, 255, 0.55); cursor: pointer;
  font-size: 0.8rem; font-weight: 600; color: #5a6775; font-family: inherit;
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  transition: transform 0.18s, background 0.18s;
}
.btn-today:hover { background: #e4f0f6; }
.btn-today:active { transform: scale(0.97); }
.type-select { width: 130px; }
.btn-manage-types {
  width: 28px; height: 28px; border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%; background: rgba(255, 255, 255, 0.45); cursor: pointer;
  font-size: 0.8rem; color: #5a6775;
  transition: transform 0.18s, background 0.18s;
}
.btn-manage-types:hover { background: #e4f0f6; }
.btn-manage-types:active { transform: scale(0.97); }
.class-info { font-size: 0.78rem; color: #999595; margin-left: auto; }

/* ---- 7 张统计卡片(玻璃色块,复刻旧版 stat-card) ---- */
.stats-cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px; margin-bottom: 14px;
}
.stat-card {
  background: rgba(255, 255, 255, 0.48);
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 26px; padding: 22px;
  text-align: center; box-shadow: 0 2px 10px rgba(80, 60, 50, 0.06);
  transition: transform 0.28s cubic-bezier(0.34, 1.3, 0.64, 1), box-shadow 0.28s;
  position: relative; overflow: hidden; cursor: pointer;
}
.stat-card::after {
  content: ''; position: absolute; top: 0; left: 8%; right: 8%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  pointer-events: none;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(80, 60, 50, 0.08); }
.stat-card:active { transform: scale(0.97); }
.stat-card.no-click { cursor: default; }
.stat-card-icon { font-size: 2.2rem; margin-bottom: 6px; }
.stat-card-value { font-size: 2.3rem; font-weight: 800; color: #5d5a5a; }
.stat-card-label { font-size: 0.78rem; color: #999595; margin-top: 2px; }
.stat-card-total .stat-card-value { color: #7eb5d6; }
.stat-card-submitted .stat-card-value { color: #a8d5ba; }
.stat-card-missing .stat-card-value { color: #e8a0bf; }
.stat-card-arate .stat-card-value { color: #f4c97e; }

/* ---- 图表区 ---- */
.charts-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 14px; margin-bottom: 14px;
}
.chart-card { margin-bottom: 14px; }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.card-icon { font-size: 1.1rem; }
.card-header h3 { font-size: 1rem; margin: 0; color: #3a4a5a; }
.chart-body { position: relative; height: 280px; width: 100%; }

/* ---- 环比趋势按钮 ---- */
.compare-btns { margin-left: auto; display: flex; gap: 4px; }
.compare-period-btn {
  padding: 4px 12px; border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px; cursor: pointer; font-size: 0.75rem; font-family: inherit;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  color: #999595; transition: transform 0.18s, background 0.18s, border-color 0.18s;
}
.compare-period-btn.active { background: #7eb5d6; color: #fff; border-color: #7eb5d6; }
.compare-period-btn:active { transform: scale(0.97); }
.compare-summary {
  padding: 0 16px 12px; font-size: 0.82rem; color: #999595; text-align: center;
}

/* ---- 小组排行榜 ---- */
.ranking-date { font-size: 0.75rem; color: #999595; margin-left: auto; }
.ranking-empty { text-align: center; color: #bfbbbb; padding: 20px; }
.ranking-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; margin-bottom: 6px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  transition: transform 0.18s, background 0.18s;
}
.ranking-item:hover { background: rgba(255, 255, 255, 0.75); transform: translateX(3px); }
.ranking-medal { font-size: 1.3rem; width: 28px; text-align: center; flex-shrink: 0; }
.ranking-name { font-weight: 700; font-size: 0.88rem; min-width: 80px; }
.ranking-bar-wrap {
  flex: 1; height: 20px; background: rgba(0, 0, 0, 0.04);
  border-radius: 10px; overflow: hidden; position: relative;
}
.ranking-bar-fill {
  height: 100%; border-radius: 10px;
  transform: scaleX(0); transform-origin: left;
  transition: transform 0.35s cubic-bezier(0.22, 0.98, 0.36, 1);
  display: flex; align-items: center; padding-left: 8px;
}
.ranking-bar-label { font-size: 0.7rem; font-weight: 700; color: #fff; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }
.ranking-stats { font-size: 0.75rem; color: #999595; min-width: 110px; text-align: right; flex-shrink: 0; white-space: nowrap; }

/* ---- 学生预警 ---- */
.alerts-tabs { display: flex; gap: 4px; margin-bottom: 10px; }
.alerts-tab-btn {
  flex: 1; padding: 6px 12px; border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px; cursor: pointer; font-size: 0.82rem; font-weight: 600;
  font-family: inherit; background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  color: #999595; transition: transform 0.18s, background 0.18s;
}
.alerts-tab-btn.active { background: #fff; color: #5d5a5a; box-shadow: 0 2px 10px rgba(80, 60, 50, 0.06); }
.alerts-tab-btn.tab-risk.active { color: #8a4a5a; background: #faebf0; }
.alerts-tab-btn.tab-improve.active { color: #2d6a3f; background: #e8f4eb; }
.alerts-tab-btn:active { transform: scale(0.97); }

.alert-student-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 12px; margin-bottom: 4px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 14px; transition: transform 0.18s;
  font-size: 0.84rem; cursor: pointer;
}
.alert-student-item:hover { transform: translateX(3px); }
.alert-student-item.risk { border-left: 3px solid #e8a0bf; }
.alert-student-item.improve { border-left: 3px solid #a8d5ba; }
.alert-student-name { font-weight: 600; flex: 1; }
.alert-student-group { font-size: 0.73rem; color: #999595; background: rgba(0, 0, 0, 0.04); padding: 2px 8px; border-radius: 10px; }
.alert-student-tag { font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.alert-student-tag.risk { background: #faebf0; color: #8a4a5a; }
.alert-student-tag.improve { background: #e8f4eb; color: #2d6a3f; }
.alert-student-grades { font-size: 0.72rem; color: #999595; display: flex; gap: 2px; }
.alert-student-grades span { padding: 1px 4px; border-radius: 3px; }
.alert-student-grades .g-A { background: #e8f4eb; color: #2d6a3f; }
.alert-student-grades .g-B { background: #e4f0f6; color: #2d5a7a; }
.alert-student-grades .g-C { background: #fef6e5; color: #7a6510; }
.alert-student-grades .g-X { background: #faebf0; color: #8a4a5a; }
.alerts-empty { text-align: center; padding: 20px; color: #bfbbbb; }

@media (max-width: 1100px) {
  .charts-grid { grid-template-columns: 1fr; }
  .stats-cards { grid-template-columns: repeat(2, 1fr); }
}
</style>
