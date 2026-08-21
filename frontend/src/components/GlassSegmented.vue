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

const glassStore = useGlassStore()

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
  activeColor: '#6ba3c7',
  compact: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const currentColor = computed(() => {
  const item = props.items.find(i => i.id === props.modelValue)
  return item?.color || props.activeColor
})

function onChange(value: string) {
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
</style>
