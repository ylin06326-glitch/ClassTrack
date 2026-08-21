<template>
  <div class="grade-segmented" :class="{ 'grade-segmented--compact': compact }" :style="thumbStyle">
    <LiquidGlassBottomNavBar
      :model-value="modelValue"
      :items="gradeItems"
      :size="'medium'"
      :active-color="activeColor"
      :label-inactive-opacity="1"
      :label-active-scale="1.05"
      :hover-light="true"
      :press-lerp="0.5"
      :release-delay-ms="60"
      :drag-overflow-damping="1.5"
      :morph-lerp="0.6"
      :morph-max-stretch="20"
      :morph-skew-factor="0.4"
      :morph-max-skew-deg="6"
      :track-filter-blur="glassStore.effectiveBlur"
      :track-filter-refractive-index="glassStore.effectiveRefractiveIndex"
      :track-filter-specular-opacity="glassStore.effectiveSpecularOpacity"
      :thumb-filter-blur="Math.max(0.1, glassStore.effectiveBlur * 0.1)"
      :thumb-filter-refractive-index="glassStore.effectiveRefractiveIndex"
      :thumb-filter-specular-opacity="glassStore.effectiveSpecularOpacity"
      @update:model-value="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGlassStore } from '../stores/glass'
import { LiquidGlassBottomNavBar } from '@sapryniukt/vue-liquid-glass'
import { playSound } from '../composables/useSound'

interface Props {
  modelValue: string
  compact?: boolean
}

const glassStore = useGlassStore()

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

// 等级颜色配置
const GRADE_COLORS = {
  A: { hex: '#6fae83', rgb: '111,174,131' },  // 绿色
  B: { hex: '#6aa2c4', rgb: '106,162,196' },  // 蓝色
  C: { hex: '#e0b45c', rgb: '224,180,92' },   // 黄色
  L: { hex: '#9f8cc9', rgb: '159,140,201' },  // 紫色
  X: { hex: '#d889a8', rgb: '216,137,168' },  // 粉色
}

// 根据选中的等级动态改变滑块颜色（通过 CSS 变量）
const currentGradeColor = computed(() => {
  return GRADE_COLORS[props.modelValue as keyof typeof GRADE_COLORS] || GRADE_COLORS.A
})

// 滑块样式：设置 CSS 变量让滑块变成对应等级的颜色
const thumbStyle = computed(() => {
  const color = currentGradeColor.value
  return {
    '--lg-nav-thumb-rgb': color.rgb,
    '--lg-nav-thumb-bg': `rgba(${color.rgb}, 0.85)`,
    '--lg-nav-active': color.hex,
  }
})

// 选中文字颜色（保持深色，确保可读性）
const activeColor = computed(() => '#1d1d1f')

function onChange(value: string) {
  if (value !== props.modelValue) {
    playSound('slider')
  }
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

/* 滑块颜色通过 CSS 变量动态控制，添加平滑过渡 */
.grade-segmented :deep(.lg-nav-thumb),
.grade-segmented :deep(.lg-bottom-nav-thumb),
.grade-segmented :deep(.lg-thumb) {
  transition: background-color 0.18s cubic-bezier(0.25, 0.46, 0.45, 0.94),
              transform 0.18s cubic-bezier(0.25, 0.46, 0.45, 0.94) !important;
}

/* 减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  .grade-segmented :deep(*) {
    transition: none !important;
    animation: none !important;
  }
}
</style>
