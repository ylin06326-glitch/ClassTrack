<template>
  <div class="grade-segmented" :class="{ 'grade-segmented--compact': compact }">
    <LiquidGlassBottomNavBar
      :model-value="modelValue"
      :items="gradeItems"
      :size="'medium'"
      :active-color="activeColor"
      :label-inactive-opacity="1"
      :label-active-scale="1.05"
      :hover-light="true"
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
  /* 强制覆盖库的 CSS 变量，适配浅色背景 */
  --lg-nav-text: #1d1d1f !important;
  --lg-nav-active: #000000 !important;
  --lg-nav-text-hover: #2c3440 !important;
  color: #1d1d1f !important;
}

.grade-segmented--compact {
  transform: none !important;
  transform-origin: left center;
}

/* 覆盖液态玻璃导航栏的默认样式，适配浅色背景 */
.grade-segmented :deep(*) {
  color: #1d1d1f !important;
}

/* 强制所有文字为深色，确保可读性 */
.grade-segmented :deep(span),
.grade-segmented :deep(div),
.grade-segmented :deep(p),
.grade-segmented :deep(label),
.grade-segmented :deep(a) {
  color: #1d1d1f !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

/* 确保滑块颜色根据等级明显变化 */
.grade-segmented :deep(.lg-nav-thumb),
.grade-segmented :deep(.lg-bottom-nav-thumb),
.grade-segmented :deep(.lg-thumb) {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
</style>
