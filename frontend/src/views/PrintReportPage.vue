<template>
  <div class="print-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <label>🏫 班级：</label>
      <select v-model="classId" @change="refreshGrid">
        <option v-if="classes.length === 0" value="">加载中...</option>
        <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <label>📐 列数：</label>
      <select v-model="cols" @change="refreshGrid">
        <option :value="4">4列</option>
        <option :value="3">3列</option>
        <option :value="5">5列</option>
      </select>
      <GlassButton @click="onPrint">🖨️ 打印</GlassButton>
      <GlassButton @click="refreshGrid">🔄 刷新</GlassButton>
      <span v-if="phase === 'done'" class="print-count">共 {{ students.length }} 名学生</span>
    </div>

    <!-- 二维码网格 -->
    <div class="grid-container" :style="{ gridTemplateColumns: 'repeat(' + cols + ', 1fr)' }">
      <template v-if="phase === 'done'">
        <div v-for="s in students" :key="s.id" class="qr-card">
          <div class="name">{{ s.name }}</div>
          <div class="code">学号: {{ studentCode(s) }}</div>
          <div v-if="s.group_name" class="group">📁 {{ s.group_name }}</div>
          <div class="qr-code">
            <img :src="qrMap[s.id]" width="100" height="100" :alt="'QR-' + studentCode(s)" style="display:block" />
          </div>
        </div>
        <div v-if="students.length === 0" class="empty-state">📭 该班级暂无学生，请先导入名单</div>
      </template>
      <div v-else class="empty-state">{{ phase === 'initial' ? '正在加载学生列表...' : '⏳ 加载中...' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 学生二维码打印独立页(/#/print)：无 MainLayout、无 useDialogs。
 * 行为契约与旧版 templates/print.html 内联 JS 全部流程一致，文案逐字保留。
 * 差异点(按任务要求)：二维码由前端 npm qrcode 包客户端生成
 * (QRCode.toDataURL，深色 #5D5A5A)，不再请求服务端 /api/qrcode。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import QRCode from 'qrcode'
import { loadClasses, loadStudents, type ClassInfo, type Student } from '@/api'

const classes = ref<ClassInfo[]>([])
const students = ref<Student[]>([])
const classId = ref(1)
const cols = ref(4)
const phase = ref<'initial' | 'loading' | 'done'>('initial')
const qrMap = ref<Record<number, string>>({})
let prevTitle = ''

function studentCode(s: Student): string {
  return s.student_code || 'S' + s.id
}

function onPrint(): void {
  window.print()
}

/** 加载班级列表(旧版 loadClasses 逐字) */
async function initClasses(): Promise<void> {
  try {
    const res = await loadClasses()
    if (res.code === 0 && res.data) {
      classes.value = res.data
      classId.value = res.active_id
      await refreshGrid()
    } else {
      phase.value = 'done'
    }
  } catch {
    phase.value = 'done'
  }
}

/** 刷新二维码网格(旧版 refreshGrid 流程逐字) */
async function refreshGrid(): Promise<void> {
  phase.value = 'loading'
  qrMap.value = {}
  try {
    const res = await loadStudents(classId.value)
    if (res.code !== 0 || !res.data || res.data.length === 0) {
      students.value = []
      phase.value = 'done'
      return
    }
    students.value = res.data
    // 客户端批量生成二维码
    const entries = await Promise.all(
      res.data.map(async (s) => {
        try {
          const url = await QRCode.toDataURL(studentCode(s), {
            width: 100,
            margin: 2,
            color: { dark: '#5D5A5A', light: '#ffffff' },
          })
          return [s.id, url] as [number, string]
        } catch {
          return [s.id, ''] as [number, string]
        }
      }),
    )
    qrMap.value = Object.fromEntries(entries)
    phase.value = 'done'
  } catch {
    students.value = []
    phase.value = 'done'
  }
}

onMounted(() => {
  prevTitle = document.title
  document.title = 'ClassTrack - 学生二维码打印'
  // 全局 style.css 为桌面布局设置了 min-width:1024px,打印页覆盖之(旧版无此限制)
  document.body.style.minWidth = '0'
  void initClasses()
})

onBeforeUnmount(() => {
  document.body.style.minWidth = ''
  if (prevTitle) document.title = prevTitle
})
</script>

<style scoped>
/* ============================================================
   ClassTrack Print — 液态玻璃视觉(样式逐字复刻旧 print.html)
   打印时自动去除玻璃效果
   ============================================================ */
.print-page {
  --glass-blur: 14px;
  --glass-saturate: 1.3;
  --blue: #7eb5d6;
  --text: #5d5a5a;
  --text-light: #999595;
  --radius: 18px;
  --radius-sm: 14px;
  --shadow-sm: 0 2px 10px rgba(80, 60, 50, 0.06);

  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background: #f5f1ed;
  min-height: 100vh;
  padding: 20px;
  position: relative;
}
/* 纯色背景装饰 */
.print-page::before {
  content: "";
  position: fixed;
  top: -150px;
  right: -100px;
  width: 350px;
  height: 350px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(126, 181, 214, 0.06) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* 工具栏 — 玻璃导航 */
.toolbar {
  max-width: 1200px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--radius);
  padding: 14px 20px;
  box-shadow: var(--shadow-sm);
  position: relative;
  z-index: 1;
  overflow: hidden;
}
.toolbar::after {
  content: "";
  position: absolute;
  top: 0;
  left: 5%;
  right: 5%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  pointer-events: none;
}
.toolbar select,
.toolbar input {
  padding: 7px 12px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 12px;
  font-size: 0.85rem;
  font-family: inherit;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  color: var(--text);
}
.toolbar label { font-size: 0.85rem; font-weight: 600; color: var(--text); }
.toolbar button {
  padding: 8px 18px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 14px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.btn-print {
  background: linear-gradient(135deg, rgba(126, 181, 214, 0.6), rgba(142, 200, 224, 0.65));
  color: white;
  box-shadow: 0 2px 10px rgba(126, 181, 214, 0.22);
}
.btn-print:hover { transform: translateY(-1px); }
.print-count { font-size: 0.8rem; color: #999; margin-left: auto; }

.grid-container {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  position: relative;
  z-index: 1;
}

/* 二维码卡片 — 玻璃卡片 */
.qr-card {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 16px;
  padding: 14px;
  text-align: center;
  box-shadow: var(--shadow-sm);
  page-break-inside: avoid;
  position: relative;
  overflow: hidden;
}
.qr-card::after {
  content: "";
  position: absolute;
  top: 0;
  left: 8%;
  right: 8%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  pointer-events: none;
}
.qr-card .name { font-size: 0.9rem; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.qr-card .code { font-size: 0.7rem; color: var(--text-light); margin-bottom: 8px; }
.qr-card .group { font-size: 0.7rem; color: var(--blue); margin-bottom: 6px; }
.qr-code { display: flex; justify-content: center; }
.empty-state { grid-column: 1/-1; text-align: center; padding: 60px; color: var(--text-light); }

/* 打印时去除玻璃效果 */
@media print {
  :global(body) { background: white; padding: 10px; }
  .print-page { background: white; padding: 10px; }
  .print-page::before { display: none; }
  .toolbar { display: none; }
  .grid-container { grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .qr-card {
    box-shadow: none;
    border: 1px dashed #ddd;
    padding: 10px;
    background: white !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
  }
  .qr-card::after { display: none; }
}
@media (max-width: 800px) {
  .grid-container { grid-template-columns: repeat(2, 1fr); }
}
</style>
