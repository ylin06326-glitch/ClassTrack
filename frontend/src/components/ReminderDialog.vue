<template>
  <GlassDialog
    :model-value="modelValue"
    title="🔔 催交通知"
    width="600px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <div class="reminder-date">📅 日期：<strong>{{ date }}</strong> &nbsp;|&nbsp; 未交人数：<strong>{{ total }}</strong></div>
    <div class="reminder-summary">⚠️ 截至 {{ date }}，以下 {{ total }} 名学生未交作业，请及时提醒：</div>
    <div class="reminder-list" :class="{ privacy }">
      <div v-for="(names, gname) in grouped" :key="gname" class="reminder-group">
        <strong>📌 {{ gname }}：</strong>{{ names.join('、') }}
      </div>
      <div v-if="total === 0" style="color: #2d6a3f; font-weight: 600">🎉 太棒了！所有学生都已交作业！</div>
    </div>
    <div class="reminder-actions">
      <label class="privacy-toggle-label">
        <el-switch v-model="privacy" size="small" @change="onPrivacyChange" />
        <span class="privacy-toggle-text">🔒 仅显示学号（隐私保护）</span>
      </label>
    </div>
    <template #footer>
      <el-button type="success" @click="copyReminder">📋 复制名单</el-button>
      <el-button type="primary" @click="printReminder">🖨️ 打印通知单</el-button>
      <el-button @click="exportReminder">📥 导出催交名单</el-button>
    </template>
  </GlassDialog>
</template>

<script setup lang="ts">
import GlassDialog from '@/components/GlassDialog.vue'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { loadMissing, downloadUrl } from '@/api'

const props = defineProps<{ modelValue: boolean; date: string; typeId: number }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const store = useAppStore()

interface MissingStudent {
  student_id: number
  student_name: string
  student_code?: string
  group_name?: string
}

const data = ref<MissingStudent[]>([])
const total = ref(0)
const privacy = ref(false)

/** 按分组聚合;隐私模式(仅显示学号)时用学号替代姓名 */
const grouped = computed<Record<string, string[]>>(() => {
  const byGroup: Record<string, string[]> = {}
  for (const s of data.value) {
    const gname = s.group_name || '未分组'
    if (!byGroup[gname]) byGroup[gname] = []
    const showCodes = privacy.value
    byGroup[gname].push(showCodes ? (s.student_code || s.student_name) : s.student_name)
  }
  return byGroup
})

async function onOpen(): Promise<void> {
  privacy.value = store.showsCodes
  const res = await loadMissing(props.date, store.currentClassId, props.typeId)
  if (res.code === 0) {
    total.value = res.total
    // 补充学号信息(与旧版一致)
    data.value = res.data.map((s: MissingStudent) => {
      const student = store.students.find((st) => st.id === s.student_id)
      return { ...s, student_code: student?.student_code || '' }
    })
  }
}

function onPrivacyChange(checked: boolean): void {
  // 与旧版一致:勾选=仅显示学号,取消=显示姓名(会覆盖分区显示模式)
  store.setDisplayMode(checked ? 'code' : 'name')
}

function getReminderText(): string {
  let text = `【催交通知】${props.date}\n`
  for (const [gname, entries] of Object.entries(grouped.value)) {
    text += `📌 ${gname}：${entries.join('、')}\n`
  }
  text += `\n请以上同学尽快补交作业！`
  return text
}

async function copyReminder(): Promise<void> {
  try {
    await navigator.clipboard.writeText(getReminderText())
    ElMessage.success('已复制到剪贴板，可直接粘贴到家长群')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

function printReminder(): void {
  const w = window.open('', '_blank', 'width=650,height=500')
  if (!w) return
  const isPrivacy = privacy.value
  const privacyTitle = isPrivacy ? '（仅显示学号）' : ''
  let listHtml = ''
  for (const [gname, entries] of Object.entries(grouped.value)) {
    listHtml += `<div class="group"><strong>📌 ${gname}：</strong>${entries.join('、')}</div>`
  }
  w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>催交通知单</title>
    <style>body{font-family:"Microsoft YaHei",sans-serif;padding:30px;line-height:2.2;font-size:15px}
    h2{color:#E8A0BF} .date{color:#999} .group{margin:8px 0}
    .privacy{font-family:"SF Mono",Consolas,monospace;letter-spacing:1px}
    @media print{body{padding:20px}}</style></head>
    <body><h2>🔔 催交通知单${privacyTitle}</h2><p class="date">日期：${props.date}</p>
    ${listHtml}
    <p style="margin-top:20px;color:#999">—— ClassTrack 班级作业管理</p></body></html>`)
  w.document.close()
  setTimeout(() => w.print(), 500)
}

function exportReminder(): void {
  window.open(
    downloadUrl('/export/class', {
      class_id: store.currentClassId,
      start: props.date,
      end: props.date,
    }),
    '_blank',
  )
}
</script>

<style scoped>
.reminder-date { color: #5a6775; font-size: 14px; margin-bottom: 8px; }
.reminder-summary { color: #8a97a8; font-size: 13px; margin-bottom: 10px; }
.reminder-list {
  max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px;
  font-size: 13px; color: #3a4a5a; line-height: 1.7;
}
.reminder-group { background: #f6f8fa; border-radius: 8px; padding: 8px 12px; }
.reminder-list.privacy .reminder-group {
  font-family: 'SF Mono', Consolas, monospace; letter-spacing: 1px;
}
.reminder-actions { margin-top: 12px; }
.privacy-toggle-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.privacy-toggle-text { font-size: 13px; color: #5a6775; }
</style>
