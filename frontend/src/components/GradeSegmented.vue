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
  { id: 'L', label: '璇峰亣' },
  { id: 'X', label: '鏈氦' },
]

// 绛夌骇棰滆壊閰嶇疆
const GRADE_COLORS = {
  A: { hex: '#6fae83', rgb: '111,174,131' },  // 缁胯壊
  B: { hex: '#6aa2c4', rgb: '106,162,196' },  // 钃濊壊
  C: { hex: '#e0b45c', rgb: '224,180,92' },   // 榛勮壊
  L: { hex: '#9f8cc9', rgb: '159,140,201' },  // 绱壊
  X: { hex: '#d889a8', rgb: '216,137,168' },  // 绮夎壊
}

// 鏍规嵁閫変腑鐨勭瓑绾у姩鎬佹敼鍙樻粦鍧楅鑹诧紙閫氳繃 CSS 鍙橀噺锛?
const currentGradeColor = computed(() => {
  return GRADE_COLORS[props.modelValue as keyof typeof GRADE_COLORS] || GRADE_COLORS.A
})

// 婊戝潡鏍峰紡锛氳缃?CSS 鍙橀噺璁╂粦鍧楀彉鎴愬搴旂瓑绾х殑棰滆壊
const thumbStyle = computed(() => {
  const color = currentGradeColor.value
  return {
    '--lg-nav-thumb-rgb': color.rgb,
    '--lg-nav-thumb-bg': `rgba(${color.rgb}, 0.85)`,
    '--lg-nav-active': color.hex,
  }
})

// 閫変腑鏂囧瓧棰滆壊锛堜繚鎸佹繁鑹诧紝纭繚鍙鎬э級
const activeColor = computed(() => '#1d1d1f')

function onChange(value: string) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.grade-segmented {
  display: inline-flex;
  align-items: center;
  /* 寮哄埗瑕嗙洊搴撶殑 CSS 鍙橀噺锛岄€傞厤娴呰壊鑳屾櫙 */
  --lg-nav-text: #1d1d1f !important;
  --lg-nav-active: #000000 !important;
  --lg-nav-text-hover: #2c3440 !important;
  color: #1d1d1f !important;
}

.grade-segmented--compact {
  transform: none !important;
  transform-origin: left center;
}

/* 瑕嗙洊娑叉€佺幓鐠冨鑸爮鐨勯粯璁ゆ牱寮忥紝閫傞厤娴呰壊鑳屾櫙 */
.grade-segmented :deep(*) {
  color: #1d1d1f !important;
}

/* 寮哄埗鎵€鏈夋枃瀛椾负娣辫壊锛岀‘淇濆彲璇绘€?*/
.grade-segmented :deep(span),
.grade-segmented :deep(div),
.grade-segmented :deep(p),
.grade-segmented :deep(label),
.grade-segmented :deep(a) {
  color: #1d1d1f !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

/* 婊戝潡棰滆壊閫氳繃 CSS 鍙橀噺鍔ㄦ€佹帶鍒讹紝娣诲姞骞虫粦杩囨浮 */
.grade-segmented :deep(.lg-nav-thumb),
.grade-segmented :deep(.lg-bottom-nav-thumb),
.grade-segmented :deep(.lg-thumb) {
  transition: background-color 0.4s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
</style>

