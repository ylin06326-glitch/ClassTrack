<template>
  <div class="main-layout">
    <!-- 壁纸层 -->
    <div class="wallpaper-layer" :class="wallpaperStore.currentCssClass" :style="customWallpaperStyle"></div>
    <!-- 视频壁纸 -->
    <video
      v-if="wallpaperStore.isVideoWallpaper && wallpaperStore.currentVideoUrl"
      class="video-wallpaper-element"
      :src="wallpaperStore.currentVideoUrl"
      :muted="wallpaperStore.videoMuted"
      :loop="wallpaperStore.videoLoop"
      autoplay
      playsinline
    ></video>
    <div v-if="wallpaperStore.isVideoWallpaper" class="video-wallpaper-overlay"></div>
    <!-- 莫兰迪壁纸的光晕层 -->
    <div v-if="wallpaperStore.currentWallpaperId === 'morandi-breathing'" class="wallpaper-glow-layer"></div>
    <div v-if="wallpaperStore.currentWallpaperId === 'morandi-breathing'" class="wallpaper-glow-3"></div>
    <!-- ========== 顶部导航栏 ========== -->
    <header class="app-header">
      <div class="header-inner">
        <div class="logo-area">
          <span class="logo-icon">🎒</span>
          <h1 class="app-title">ClassTrack</h1>
          <span class="brand-badge" title="关于" @click="aboutVisible = true">YRL</span>
        </div>

        <!-- 班级选择器 -->
        <div class="class-selector">
          <el-select
            :model-value="store.currentClassId"
            class="class-select"
            placeholder="我的班级"
            title="切换班级"
            @change="onSwitchClass"
          >
            <el-option v-for="c in store.classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
          <GlassButton title="管理班级" class="header-icon-btn" :width="40" @click="classVisible = true">⚙️</GlassButton>
        </div>

        <!-- Tab 导航（液态玻璃） -->
        <div class="tab-nav-wrapper">
          <LiquidGlassBottomNavBar
            :model-value="activeTab" @update:model-value="onTabChange"
            :items="tabItems"
            size="small"
            active-color="#6ba3c7"
          />
        </div>
        <GlassButton title="支持作者" class="header-icon-btn" :width="40" @click="donateVisible = true">❤️</GlassButton>

        <!-- 姓名显示模式 -->
        <el-dropdown trigger="click" @command="onDisplayMode">
          <GlassButton title="切换姓名显示模式" class="header-icon-btn" :width="40">
            {{ DM_CONFIG[store.displayMode].icon }}
          </GlassButton>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="(cfg, mode) in DM_CONFIG" :key="mode" :command="mode">
                <span>{{ cfg.icon }}</span> {{ cfg.label }}
                <span v-if="store.displayMode === mode" style="color:var(--el-color-primary)">✓</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <a class="btn-print-qr" href="#/print" target="_blank" title="打印学生二维码">🖨️</a>
        <GlassButton title="退出程序" class="header-icon-btn" :width="40" @click="onExit">⏻</GlassButton>
      </div>
    </header>

    <!-- ========== 主内容区(所有 Tab 常驻,v-show 切换保留状态) ========== -->
    <main class="app-main">
      <GroupingTab v-show="activeTab === 'grouping'" />
      <HomeworkTab v-show="activeTab === 'homework'" />
      <ExamsTab v-show="activeTab === 'exams'" />
      <AnalyticsTab v-show="activeTab === 'analytics'" />
      <ExportTab v-show="activeTab === 'export'" />
      <AIChatTab v-show="activeTab === 'aichat'" />
      <SettingsTab v-show="activeTab === 'settings'" />
    </main>

    <!-- ========== 班级管理 ========== -->
    <GlassDialog v-model="classVisible" title="🏫 班级管理" width="460px" append-to-body>
      <div class="class-list">
        <div v-for="c in store.classes" :key="c.id" class="class-row">
          <span class="class-name">
            {{ c.name }}
            <el-tag v-if="c.id === store.currentClassId" size="medium" type="success">当前</el-tag>
          </span>
          <span class="class-actions">
            <GlassButton v-if="c.id !== store.currentClassId" size="small" type="primary" plain :width="56" @click="onActivateClass(c.id)">切换</GlassButton>
            <GlassButton size="small" :width="56" @click="onRenameClass(c)">重命名</GlassButton>
            <GlassButton size="small" type="danger" plain :width="56" @click="onDeleteClass(c)">删除</GlassButton>
          </span>
        </div>
      </div>
      <div class="class-add-row">
        <GlassInput v-model="newClassName" placeholder="输入新班级名称" @keyup.enter="onAddClass" />
        <GlassButton type="primary" :width="100" @click="onAddClass">+ 新建班级</GlassButton>
      </div>
    </GlassDialog>

    <!-- ========== 关于 ========== -->
    <GlassDialog v-model="aboutVisible" title="🏷️ 关于 ClassTrack" width="380px" append-to-body>
      <div class="brand-info">
        <div class="brand-logo">🎒</div>
        <h2 class="brand-name">ClassTrack</h2>
        <p class="brand-sub">班级作业分组管理系统</p>
        <div class="brand-divider"></div>
        <p class="brand-dev">由 <strong>杨润林</strong> 开发</p>
        <p class="brand-code">代号 <strong>YRL</strong></p>
        <div class="brand-divider"></div>
        <p class="brand-legal">© 2024-2026 保留所有权利</p>
        <p class="brand-legal">禁止反编译、破解、逆向工程</p>
      </div>
    </GlassDialog>

    <!-- ========== 打赏 ========== -->
    <GlassDialog v-model="donateVisible" title="❤️ 支持作者" width="360px" append-to-body>
      <div class="donate-modal-body">
        <p class="donate-intro">如果 ClassTrack 对你有帮助，欢迎请作者喝杯咖啡！</p>
        <div class="donate-qr-wrapper">
          <img src="/wechat-donate.png" alt="微信支付" class="donate-qr-img">
        </div>
        <p class="donate-tip">📱 微信扫一扫，感谢你的支持！</p>
        <p class="donate-author">—— 杨润林 (YRL)</p>
        <div class="donate-divider"></div>
        <p class="donate-feedback-title">🐛 反馈 Bug / 建议</p>
        <p class="donate-email">
          📧 <a href="mailto:ylin06326@gmail.com" class="donate-email-link">ylin06326@gmail.com</a>
        </p>
        <p class="donate-email">
          📧 <a href="mailto:yrl666hello@qq.com" class="donate-email-link">yrl666hello@qq.com</a>
        </p>
      </div>
    </GlassDialog>

    <!-- ========== 详情列表(已交/未交/全班名单等) ========== -->
    <GlassDialog v-model="detailVisible" :title="detailTitle" width="560px" append-to-body>
      <div class="detail-summary" v-html="detailSummary"></div>
      <div class="detail-list">
        <div
          v-for="(item, i) in detailItems"
          :key="i"
          class="detail-item"
          :class="{ clickable: item.sid != null }"
          @click="item.sid != null && dialogs.showStudentReport(item.sid, item.label)"
        >
          <span class="detail-name">{{ item.label }}</span>
          <span v-if="item.sub" class="detail-group">{{ item.sub }}</span>
          <span
            v-if="item.grade"
            class="grade-badge"
            :class="`grade-${item.grade.toLowerCase()}`"
          >{{ item.gradeLabel || item.grade }}</span>
        </div>
      </div>
    </GlassDialog>

    <!-- ========== 学生个人作业报表 ========== -->
    <GlassDialog v-model="reportVisible" :title="reportTitle" width="560px" append-to-body>
      <div v-if="reportLoading" class="report-loading">⏳ 加载中...</div>
      <div v-else-if="reportError" class="report-loading" style="color:#8a4a5a">加载失败</div>
      <template v-else>
        <div class="report-stats">
          <span v-for="g in ['A', 'B', 'C', 'L', 'X']" :key="g" class="report-stat-item" :class="`grade-${g.toLowerCase()}-bg`">
            {{ STAT_ICONS[g] }} {{ STAT_LABELS[g] }} × {{ reportData?.stats?.[g] || 0 }}
          </span>
        </div>
        <div class="report-table-wrapper">
          <el-table :data="reportData?.records || []" size="medium" height="320">
            <el-table-column prop="date" label="日期" width="140" />
            <el-table-column label="等级" width="140">
              <template #default="{ row }">
                <span class="grade-badge" :class="`grade-${(row.grade || 'x').toLowerCase()}`">{{ row.grade_label }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="report-actions">
          <GlassButton type="primary" size="small" @click="exportStudentReport">📥 导出Excel</GlassButton>
          <span class="report-total">共 {{ reportData?.total || 0 }} 条记录</span>
        </div>
      </template>
    </GlassDialog>
  </div>
</template>

<script setup lang="ts">
import GlassDialog from '@/components/GlassDialog.vue'
import GlassButton from '@/components/GlassButton.vue'
import GlassInput from '@/components/GlassInput.vue'
import { ref, onMounted, provide, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { DIALOG_KEY, type DialogApi, type DetailItem } from '@/composables/dialogs'
import {
  loadStudentReport, createClass, renameClass, deleteClass, activateClass, shutdown,
  downloadUrl, type ClassInfo,
} from '@/api'
import GroupingTab from './tabs/GroupingTab.vue'
import HomeworkTab from './tabs/HomeworkTab.vue'
import ExamsTab from './tabs/ExamsTab.vue'
import AnalyticsTab from './tabs/AnalyticsTab.vue'
import ExportTab from './tabs/ExportTab.vue'
import AIChatTab from './tabs/AIChatTab.vue'
import SettingsTab from './tabs/SettingsTab.vue'
import { LiquidGlassBottomNavBar } from '@sapryniukt/vue-liquid-glass'
import { glassMessageBox } from '@/components/glassMessageBox'
import { useWallpaperStore } from '@/stores/wallpaper'
import { initSound, playSound } from '@/composables/useSound'

const store = useAppStore()
const wallpaperStore = useWallpaperStore()

// 自定义壁纸样式
const customWallpaperStyle = computed(() => {
  if (wallpaperStore.currentWallpaperId === 'custom' && wallpaperStore.customImage) {
    return { backgroundImage: `url(${wallpaperStore.customImage})` }
  }
  return {}
})

const TABS = [
  { id: 'grouping', icon: '👥', label: '班级分组' },
  { id: 'homework', icon: '📝', label: '作业登记' },
  { id: 'exams', icon: '📊', label: '成绩管理' },
  { id: 'analytics', icon: '📈', label: '数据总览' },
  { id: 'export', icon: '📋', label: '报表导出' },
  { id: 'aichat', icon: '🤖', label: 'AI助手' },
  { id: 'settings', icon: '⚙️', label: '设置' },
] as const

// 液态玻璃导航栏的 items（icon 用 emoji）
const tabItems = TABS.map(t => ({ id: t.id, label: t.label, icon: t.icon }))



const DM_CONFIG: Record<'name' | 'code' | 'auto', { icon: string; label: string }> = {
  name: { icon: '👤', label: '显示姓名' },
  code: { icon: '🔒', label: '仅显示学号' },
  auto: { icon: '🎯', label: '分区显示' },
}

const activeTab = ref('grouping')

// Tab 切换时播放音效
function onTabChange(tab: string) {
  if (tab !== activeTab.value) {
    playSound('tab')
  }
  activeTab.value = tab
}

// ---- 班级管理 ----
const classVisible = ref(false)
const aboutVisible = ref(false)
const donateVisible = ref(false)
const newClassName = ref('')

// ---- 详情列表弹窗 ----
const detailVisible = ref(false)
const detailTitle = ref('📋 详情')
const detailSummary = ref('')
const detailItems = ref<DetailItem[]>([])

// ---- 学生个人报表 ----
const reportVisible = ref(false)
const reportTitle = ref('📄 学生作业报表')
const reportLoading = ref(false)
const reportError = ref(false)
const reportData = ref<{ total: number; stats: Record<string, number>; records: { date: string; grade: string; grade_label: string }[] } | null>(null)
const _reportSid = ref(0)

const STAT_ICONS: Record<string, string> = { A: '⭐', B: '🔵', C: '🟡', L: '🌿', X: '⬜' }
const STAT_LABELS: Record<string, string> = { A: 'A', B: 'B', C: 'C', L: '请假', X: '未交' }

onMounted(() => {
  store.initDisplayMode()
  store.loadAllData().catch(() => { /* 拦截器已提示 */ })
  // 初始化音效系统（在用户首次交互后解锁 AudioContext）
  const unlockAudio = () => {
    initSound()
    window.removeEventListener('pointerdown', unlockAudio)
    window.removeEventListener('keydown', unlockAudio)
  }
  window.addEventListener('pointerdown', unlockAudio)
  window.addEventListener('keydown', unlockAudio)
})

// ========== 全局弹窗服务 ==========
const dialogs: DialogApi = {
  async confirm(msg: string, title?: string): Promise<boolean> {
    try {
      await glassMessageBox.confirm(msg, title || '⚠️ 确认操作', {
        confirmButtonText: '确认', cancelButtonText: '取消',
      })
      return true
    } catch {
      return false
    }
  },
  showDetail(title: string, summary: string, items: DetailItem[]): void {
    detailTitle.value = title
    detailSummary.value = summary
    detailItems.value = items
    detailVisible.value = true
  },
  showStudentReport(sid: number, name: string): void {
    _reportSid.value = sid
    reportTitle.value = `📄 ${name} - 作业报表`
    reportVisible.value = true
    reportLoading.value = true
    reportError.value = false
    reportData.value = null
    loadStudentReport(sid)
      .then((res) => {
        if (res.code === 0) {
          reportData.value = res.data
        } else {
          reportError.value = true
          if (res.msg) ElMessage.error(res.msg)
        }
      })
      .catch(() => { reportError.value = true })
      .finally(() => { reportLoading.value = false })
  },
}
provide(DIALOG_KEY, dialogs)

// ========== 班级操作 ==========
async function refreshClasses(): Promise<void> {
  await store.loadAllData()
}

async function onSwitchClass(id: number): Promise<void> {
  await store.switchClass(id)
}

async function onActivateClass(id: number): Promise<void> {
  const res = await activateClass(id)
  if (res.code === 0) {
    await refreshClasses()
  }
}

async function onAddClass(): Promise<void> {
  const name = newClassName.value.trim()
  if (!name) return
  const res = await createClass(name)
  if (res.code === 0) {
    ElMessage.success(res.msg)
    newClassName.value = ''
    await refreshClasses()
  } else if (res.msg) {
    ElMessage.error(res.msg)
  }
}

async function onRenameClass(c: ClassInfo): Promise<void> {
  try {
    const value = await glassMessageBox.prompt('输入新的班级名称', `重命名「${c.name}」`, {
      inputValue: c.name,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    const res = await renameClass(c.id, value.trim())
    if (res.code === 0) {
      ElMessage.success(res.msg)
      await refreshClasses()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 用户取消 */ }
}

async function onDeleteClass(c: ClassInfo): Promise<void> {
  const ok = await dialogs.confirm(
    `确定删除班级「${c.name}」？该班级的所有学生和记录将被删除`,
    '⚠️ 确认操作',
  )
  if (!ok) return
  const res = await deleteClass(c.id)
  if (res.code === 0) {
    ElMessage.success(res.msg)
    await refreshClasses()
  } else if (res.msg) {
    ElMessage.error(res.msg)
  }
}

// ========== 其他头部操作 ==========
function onDisplayMode(mode: 'name' | 'code' | 'auto'): void {
  store.setDisplayMode(mode)
}

async function onExit(): Promise<void> {
  try { await shutdown() } catch { /* 服务可能已停止 */ }
  window.close()
  // window.close 对非脚本打开的窗口无效,提示用户
  setTimeout(() => {
    ElMessage.info('程序已停止,请关闭此窗口')
  }, 300)
}

function exportStudentReport(): void {
  if (!_reportSid.value) return
  // 与旧版一致:仅当起止日期都已选择时才附带区间
  const params: Record<string, any> = { class_id: store.currentClassId }
  if (store.exportStartDate && store.exportEndDate) {
    params.start = store.exportStartDate
    params.end = store.exportEndDate
  }
  window.open(downloadUrl(`/export/student/${_reportSid.value}`, params), '_blank')
}
</script>

<style scoped>
.main-layout { min-height: 100vh; display: flex; flex-direction: column; }
.app-header {
  position: sticky; top: 0; z-index: 100;
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border-bottom: none !important;
  box-shadow: none !important;
  padding: 12px 20px;
}
.header-inner {
  display: flex; align-items: center; gap: 8px;
  max-width: 100%; margin: 0 auto; padding: 10px 18px;
  flex-wrap: nowrap;
  overflow-x: hidden;
  overflow-y: visible;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
.header-inner::-webkit-scrollbar { height: 4px; }
.header-inner::-webkit-scrollbar-thumb { background: rgba(150,160,175,0.3); border-radius: 2px; }

/* 顶部栏小药丸形图标按钮 */
.header-icon-btn {
  min-width: 40px !important;
  width: 40px !important;
  max-width: 40px !important;
  height: 40px !important;
  padding: 0 !important;
  font-size: 18px !important;
  flex-shrink: 0 !important;
  display: inline-flex !important;
}
.header-icon-btn :deep(*) {
  min-width: 40px !important;
  width: 40px !important;
  max-width: 40px !important;
  height: 40px !important;
  padding: 0 !important;
}
.header-icon-btn :deep(.lg-button) {
  min-width: 40px !important;
  width: 40px !important;
  max-width: 40px !important;
  height: 40px !important;
  padding: 0 !important;
}
.header-icon-btn :deep(.lg-button-content),
.header-icon-btn :deep(.glass-button-content) {
  min-width: 40px !important;
  width: 40px !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}
.logo-area {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 20px;
  padding: 6px 14px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.logo-icon { font-size: 26px; }
.app-title { font-size: 20px; margin: 0; color: #3a4a5a; }
.brand-badge {
  background: linear-gradient(135deg, #6ba3c7, #8fb8d6);
  color: #fff; font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 10px; cursor: pointer;
}
.class-selector {
  display: flex; align-items: center; gap: 4px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 20px;
  padding: 6px 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.class-select { width: 130px; }
.btn-class-manage {
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 8px; padding: 4px 8px; cursor: pointer; font-size: 13px;
}
.btn-class-manage:hover { background: #f0f6fa; }
.tab-nav-wrapper {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(28px) saturate(200%);
  -webkit-backdrop-filter: blur(28px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 28px;
  padding: 5px 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  /* 覆盖液态玻璃导航栏的默认白色文字，适配浅色背景 */
  --lg-nav-text: rgba(60, 70, 85, 0.7);
  --lg-nav-active: #1d1d1f;
  --lg-nav-track-bg: rgba(0, 0, 0, 0.03);
  --lg-nav-track-border: rgba(0, 0, 0, 0.06);
  --lg-nav-thumb-rgb: 255, 255, 255;
  --lg-nav-thumb-border: rgba(255, 255, 255, 0.7);
  --lg-nav-thumb-border-active: rgba(255, 255, 255, 0.55);
  --lg-nav-thumb-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), inset 0 1px 1px rgba(255, 255, 255, 0.85);
  --lg-nav-thumb-shadow-active: 0 6px 20px rgba(0, 0, 0, 0.15), inset 0 1px 1px rgba(255, 255, 255, 0.75);
  --lg-nav-track-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.04);
}
/* 确保未选中标签文字清晰 */
.tab-nav-wrapper :deep(.lg-nav-item) {
  color: var(--lg-nav-text) !important;
}
.tab-nav-wrapper :deep(.lg-nav-item.active) {
  color: var(--lg-nav-active) !important;
  font-weight: 600 !important;
}
.tab-nav-wrapper :deep(.lg-bottom-nav) {
  position: relative !important;
  bottom: auto !important;
  left: auto !important;
  right: auto !important;
  width: auto !important;
  background: transparent !important;
  backdrop-filter: none !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
.tab-btn-donate {
  display: flex; align-items: center; gap: 5px;
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 10px; padding: 6px 10px; cursor: pointer;
  font-size: 13px; color: #4a5a68; font-family: inherit;
}
.tab-btn-donate:hover { background: #fff5f5; }
.tab-btn {
  display: flex; align-items: center; gap: 5px;
  border: none; background: transparent; cursor: pointer;
  padding: 7px 12px; border-radius: 10px;
  font-size: 14px; color: #5a6775; font-family: inherit;
  transition: all 0.18s;
}
.tab-btn:hover { background: rgba(107, 163, 199, 0.12); }
.tab-btn.active {
  background: linear-gradient(135deg, #6ba3c7, #7fb5d6);
  color: #fff; font-weight: 600;
  box-shadow: 0 3px 10px rgba(107, 163, 199, 0.35);
}
.display-mode-btn {
  display: flex; align-items: center; gap: 5px;
  border: 1px solid rgba(150, 160, 175, 0.3); background: #fff;
  border-radius: 10px; padding: 6px 10px; cursor: pointer;
  font-size: 13px; color: #4a5a68; font-family: inherit; outline: none;
}
.display-mode-arrow { font-size: 10px; color: #9aa8b5; }
.btn-print-qr {
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  font-size: 18px;
  text-decoration: none;
  color: inherit;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.btn-print-qr:hover {
  background: rgba(255, 255, 255, 0.85);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.95);
}
.btn-print-qr:hover { background: #f0f6fa; }
.btn-exit {
  border: none; background: transparent; font-size: 17px;
  cursor: pointer; color: #b0566a; padding: 4px 8px;
}
.btn-exit:hover { color: #8a4a5a; }
.app-main { flex: 1; max-width: 1560px; width: 100%; margin: 0 auto; padding: 16px 18px 40px; }

/* 班级管理 */
.class-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.class-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-radius: 10px; background: #f6f8fa;
}
.class-name { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #3a4a5a; }
.class-add-row { display: flex; gap: 8px; }

/* 关于 */
.brand-info { text-align: center; }
.brand-logo { font-size: 44px; }
.brand-name { margin: 6px 0 2px; color: #3a4a5a; }
.brand-sub { color: #8a97a8; margin: 0 0 10px; }
.brand-divider { height: 1px; background: rgba(150, 160, 175, 0.2); margin: 10px 0; }
.brand-dev, .brand-code { color: #5a6775; font-size: 14px; margin: 2px 0; }
.brand-legal { color: #a8b2bd; font-size: 12px; margin: 1px 0; }

/* 打赏 */
.donate-modal-body { text-align: center; }
.donate-intro { font-size: 14px; color: #666; margin: 0 0 16px; line-height: 1.6; }
.donate-qr-wrapper {
  background: #fff; border-radius: 12px; padding: 14px;
  margin: 0 auto 14px; width: 220px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.donate-qr-img { width: 100%; height: auto; display: block; border-radius: 4px; }
.donate-tip { font-size: 13px; color: #888; margin: 0 0 8px; }
.donate-author { font-size: 12px; color: #aaa; margin: 0; font-style: italic; }
.donate-divider { height: 1px; background: rgba(150, 160, 175, 0.2); margin: 16px 0 12px; }
.donate-feedback-title { font-size: 13px; color: #666; margin: 0 0 8px; font-weight: 600; }
.donate-email { font-size: 12px; color: #888; margin: 4px 0; }
.donate-email-link { color: #6ba3c7; text-decoration: none; }
.donate-email-link:hover { text-decoration: underline; }

/* 详情列表 */
.detail-summary { color: #5a6775; font-size: 13px; margin-bottom: 10px; }
.detail-list { max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.detail-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.5); backdrop-filter: blur(8px); font-size: 13px;
}
.detail-item.clickable { cursor: pointer; }
.detail-item.clickable:hover { background: rgba(238, 246, 251, 0.7); }
.detail-name { color: #3a4a5a; }
.detail-group {
  background: rgba(227, 235, 242, 0.6); color: #55636f; padding: 1px 8px; border-radius: 10px; font-size: 11px;
}

/* 学生报表 */
.report-loading { text-align: center; padding: 30px; color: #8a97a8; }
.report-stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.report-stat-item {
  padding: 4px 10px; border-radius: 14px; font-size: 12px; font-weight: 600;
}
.report-table-wrapper { margin-bottom: 10px; }
.report-actions { display: flex; align-items: center; gap: 10px; }
.report-total { font-size: 12px; color: #8a97a8; margin-left: auto; }
</style>
