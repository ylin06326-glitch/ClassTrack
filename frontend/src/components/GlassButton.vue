<template>
  <LiquidGlassButton
    :label="label || ''"
    :size="lgSize"
    :variant="type === 'primary' ? 'primary' : 'default'"
    :disabled="disabled"
    :width="width"
    :refraction-level="0.8"
    :blur="20"
    @click="handleClick"
    class="glass-button-wrapper"
  >
    <slot></slot>
  </LiquidGlassButton>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassButton } from '@sapryniukt/vue-liquid-glass'

interface Props {
  label?: string
  type?: 'primary' | 'default' | 'success' | 'warning' | 'danger' | 'info'
  size?: 'large' | 'default' | 'small'
  disabled?: boolean
  width?: number
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  type: 'default',
  size: 'default',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

const lgSize = computed(() => {
  switch (props.size) {
    case 'large': return 'large'
    case 'small': return 'small'
    default: return 'medium'
  }
})

function handleClick(event: MouseEvent) {
  if (!props.disabled) {
    emit('click', event)
  }
}
</script>

<style scoped>
.glass-button-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.glass-button-wrapper :deep(button) {
  font-family: inherit !important;
}
</style>
