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
  /* 强制覆盖库的 CSS 变量，适配浅色背景 */
  --lg-nav-text: #3c4655 !important;
  --lg-nav-active: #1d1d1f !important;
  --lg-nav-text-hover: #2c3440 !important;
}

.grade-segmented--compact {
  transform: scale(1.0);
  transform-origin: left center;
}

/* 覆盖液态玻璃导航栏的默认样式，适配浅色背景 */
.grade-segmented :deep(.lg-bottom-nav) {
  position: relative !important;
  bottom: auto !important;
  left: auto !important;
  right: auto !important;
  width: 100% !important;
  min-width: 260px !important;
  background: rgba(0, 0, 0, 0.03) !important;
  backdrop-filter: none !important;
  border: 1px solid rgba(0, 0, 0, 0.06) !important;
  border-radius: 14px !important;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04) !important;
  padding: 5px !important;
}

/* 强制覆盖文字颜色 - 用多层选择器提高优先级 */
.grade-segmented :deep(.lg-bottom-nav .lg-nav-item),
.grade-segmented :deep(.lg-nav-item),
.grade-segmented :deep(.lg-nav-item span),
.grade-segmented :deep(.lg-nav-item .lg-nav-label) {
  color: #3c4655 !important;
  opacity: 1 !important;
  font-size: 17px !important;
  font-weight: 600 !important;
  padding: 8px 12px !important;
}

.grade-segmented :deep(.lg-nav-item.active),
.grade-segmented :deep(.lg-nav-item.active span),
.grade-segmented :deep(.lg-nav-item.active .lg-nav-label) {
  color: #1d1d1f !important;
  font-weight: 800 !important;
  opacity: 1 !important;
  font-size: 17px !important;
}

.grade-segmented :deep(.lg-nav-item:hover),
.grade-segmented :deep(.lg-nav-item:hover span) {
  color: #2c3440 !important;
}

/* 确保滑块颜色根据等级明显变化 */
.grade-segmented :deep(.lg-nav-thumb),
.grade-segmented :deep(.lg-bottom-nav-thumb),
.grade-segmented :deep(.lg-thumb) {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
</style>
