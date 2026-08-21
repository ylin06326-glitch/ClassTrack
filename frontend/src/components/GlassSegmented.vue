<template>
  <div class="glass-segmented" :class="{ 'glass-segmented--compact': compact }">
    <LiquidGlassBottomNavBar
      :model-value="modelValue"
      :items="items"
      :size="size"
      :active-color="currentColor"
      :label-inactive-opacity="1"
      :label-active-scale="1.05"
      :hover-light="true"
      :press-lerp="0.2"
      :release-delay-ms="300"
      :drag-overflow-damping="2.5"
      :morph-lerp="0.3"
      :morph-max-stretch="28"
      :morph-skew-factor="0.6"
      :morph-max-skew-deg="10"
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
import { LiquidGlassBottomNavBar } from '@sapryniukt/vue-liquid-glass'
import { useGlassStore } from '../stores/glass'
import { playSound } from '../composables/useSound'

interface SegmentedItem {
  id: string
  label: string
  icon?: string
  color?: string
}

interface Props {
  modelValue: string
  items: SegmentedItem[]
  size?: 'small' | 'medium' | 'large'
  activeColor?: string
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
  activeColor: '#6ba3c7',
  compact: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const glassStore = useGlassStore()

const currentColor = computed(() => {
  const item = props.items.find(i => i.id === props.modelValue)
  return item?.color || props.activeColor
})

function onChange(value: string) {
  if (value !== props.modelValue) {
    playSound('tab')
  }
  emit('update:modelValue', value)
}
</script>

<style scoped>
.glass-segmented {
  display: inline-flex;
  align-items: center;
  --lg-nav-text: #1d1d1f !important;
  --lg-nav-active: #000000 !important;
  --lg-nav-text-hover: #2c3440 !important;
  color: #1d1d1f !important;
}

.glass-segmented--compact {
  transform: none !important;
  transform-origin: left center;
}

/* 强制所有文字为深色，确保可读性 */
.glass-segmented :deep(*) {
  color: #1d1d1f !important;
}

.glass-segmented :deep(span),
.glass-segmented :deep(div),
.glass-segmented :deep(p),
.glass-segmented :deep(label),
.glass-segmented :deep(a) {
  color: #1d1d1f !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

/* 减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  .glass-segmented :deep(*) {
    transition: none !important;
    animation: none !important;
  }
}
</style>
