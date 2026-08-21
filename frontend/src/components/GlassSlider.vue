<template>
  <LiquidGlassSlider
    :model-value="modelValue"
    :min="min"
    :max="max"
    :size="lgSize"
    :disabled="disabled"
    @update:model-value="(val: number) => emit('update:modelValue', val)"
    class="glass-slider-wrapper"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassSlider } from '@sapryniukt/vue-liquid-glass'

interface Props {
  modelValue?: number
  min?: number
  max?: number
  size?: 'large' | 'default' | 'small'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  min: 0,
  max: 100,
  size: 'default',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const lgSize = computed(() => {
  switch (props.size) {
    case 'large': return 'large'
    case 'small': return 'small'
    default: return 'medium'
  }
})
</script>

<style scoped>
.glass-slider-wrapper {
  width: 100%;
}
</style>
