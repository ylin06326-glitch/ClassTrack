<template>
  <GlassDialog
    :model-value="modelValue"
    title="⚙️ 管理作业种类"
    width="420px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="types-list">
      <div v-for="t in store.homeworkTypes" :key="t.id" class="type-row">
        <span class="type-name">
          {{ t.name }}
          <el-tag v-if="t.id === store.currentHomeworkTypeId" size="small" type="success">当前</el-tag>
        </span>
        <span class="type-actions">
          <el-button size="small" @click="onRename(t)">重命名</el-button>
          <el-button size="small" type="danger" plain @click="onDelete(t)">删除</el-button>
        </span>
      </div>
    </div>
    <div class="type-add-row">
      <el-input v-model="newTypeName" placeholder="输入新作业种类名称" maxlength="20" @keyup.enter="onAdd" />
      <el-button type="success" @click="onAdd">+ 新增</el-button>
    </div>
  </GlassDialog>
</template>

<script setup lang="ts">
import GlassDialog from '@/components/GlassDialog.vue'
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import {
  createHomeworkType, renameHomeworkType, deleteHomeworkType,
  type HomeworkType,
} from '@/api'
import { useDialogs } from '@/composables/dialogs'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const store = useAppStore()
const dialogs = useDialogs()
const newTypeName = ref('')

async function onAdd(): Promise<void> {
  const name = newTypeName.value.trim()
  if (!name) return
  const res = await createHomeworkType(name)
  if (res.code === 0) {
    ElMessage.success(res.msg || '已创建')
    newTypeName.value = ''
    await store.loadTypesData()
  } else if (res.msg) {
    ElMessage.error(res.msg)
  }
}

async function onRename(t: HomeworkType): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt('输入新的种类名称', `重命名「${t.name}」`, {
      inputValue: t.name,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    const res = await renameHomeworkType(t.id, value.trim())
    if (res.code === 0) {
      ElMessage.success(res.msg || '已重命名')
      await store.loadTypesData()
    } else if (res.msg) {
      ElMessage.error(res.msg)
    }
  } catch { /* 用户取消 */ }
}

async function onDelete(t: HomeworkType): Promise<void> {
  const ok = await dialogs.confirm(`确定删除作业种类「${t.name}」？`, '⚠️ 确认操作')
  if (!ok) return
  const res = await deleteHomeworkType(t.id)
  if (res.code === 0) {
    ElMessage.success(res.msg || '已删除')
    await store.loadTypesData()
  } else if (res.msg) {
    ElMessage.error(res.msg)
  }
}
</script>

<style scoped>
.types-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.type-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-radius: 10px; background: #f6f8fa;
}
.type-name { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #3a4a5a; }
.type-add-row { display: flex; gap: 8px; }
</style>
