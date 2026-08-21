<template>
  <LiquidGlassSwitch
    :model-value="modelValue"
    :size="lgSize"
    :disabled="disabled"
    @update:model-value="(val: boolean) => emit('update:modelValue', val)"
    class="glass-switch-wrapper"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassSwitch } from '@sapryniukt/vue-liquid-glass'

interface Props {
  modelValue?: boolean
  size?: 'large' | 'default' | 'small'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  size: 'default',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
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
.glass-switch-wrapper {
  display: inline-flex;
  align-items: center;
}
</style>
