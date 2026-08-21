<template>
  <div class="grade-segmented" :class="{ 'grade-segmented--compact': compact }">
    <LiquidGlassBottomNavBar
      :model-value="modelValue"
      :items="gradeItems"
      :size="compact ? 'small' : 'medium'"
      :active-color="activeColor"
      @update:model-value="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassBottomNavBar } from '@sapryniukt/vue-liquid-glass'

interface Props {
  modelValue: string
  compact?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const gradeItems = [
  { id: 'A', label: 'A' },
  { id: 'B', label: 'B' },
  { id: 'C', label: 'C' },
  { id: 'L', label: '请假' },
  { id: 'X', label: '未交' },
]

// 根据选中的等级动态改变滑块颜色
const activeColor = computed(() => {
  switch (props.modelValue) {
    case 'A': return '#6fae83'  // 绿色
    case 'B': return '#6aa2c4'  // 蓝色
    case 'C': return '#e0b45c'  // 黄色
    case 'L': return '#9f8cc9'  // 紫色
    case 'X': return '#d889a8'  // 粉色
    default: return '#6ba3c7'
  }
})

function onChange(value: string) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.grade-segmented {
  display: inline-flex;
  align-items: center;
}

.grade-segmented--compact {
  transform: scale(0.85);
  transform-origin: left center;
}

/* 覆盖液态玻璃导航栏的默认样式，适配浅色背景 */
.grade-segmented :deep(.lg-bottom-nav) {
  position: relative !important;
  bottom: auto !important;
  left: auto !important;
  right: auto !important;
  width: auto !important;
  background: rgba(0, 0, 0, 0.03) !important;
  backdrop-filter: none !important;
  border: 1px solid rgba(0, 0, 0, 0.06) !important;
  border-radius: 12px !important;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04) !important;
  padding: 3px !important;
}

/* 文字颜色适配浅色背景 */
.grade-segmented :deep(.lg-nav-item) {
  color: rgba(60, 70, 85, 0.65) !important;
}

.grade-segmented :deep(.lg-nav-item.active) {
  color: #1d1d1f !important;
  font-weight: 600 !important;
}
</style>
