<template>
  <LiquidGlassButton
    :label="label || ''"
    :size="lgSize"
    :variant="lgVariant"
    :disabled="disabled"
    :width="width"
    :refraction-level="0.9"
    :blur="24"
    :specular-opacity="0.8"
    :specular-saturation="2.0"
    :bezel-width="3"
    :glass-thickness="4"
    :hover-light="true"
    @click="handleClick"
    class="glass-button-wrapper"
    :class="{ 'glass-button-loading': loading }"
  >
    <span v-if="loading" class="glass-button-spinner"></span>
    <slot></slot>
  </LiquidGlassButton>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassButton } from '@sapryniukt/vue-liquid-glass'

interface Props {
  label?: string
  type?: 'primary' | 'default' | 'success' | 'warning' | 'danger' | 'info' | 'text'
  size?: 'large' | 'default' | 'small'
  disabled?: boolean
  loading?: boolean
  width?: number
  icon?: string
  plain?: boolean
  round?: boolean
  circle?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  type: 'default',
  size: 'default',
  disabled: false,
  loading: false,
  plain: false,
  round: false,
  circle: false,
})

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

const lgSize = computed(() => {
  switch (props.size) {
    case 'large': return 'large'
    case 'small': return 'xSmall'
    default: return 'medium'
  }
})

const lgVariant = computed(() => {
  if (props.type === 'primary' || props.type === 'success') return 'primary'
  return 'default'
})

function handleClick(event: MouseEvent) {
  if (!props.disabled && !props.loading) {
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
  position: relative;
}

.glass-button-wrapper :deep(button) {
  font-family: inherit !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
}

.glass-button-loading {
  pointer-events: none;
  opacity: 0.7;
}

.glass-button-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: glass-spin 0.8s linear infinite;
  margin-right: 8px;
}

@keyframes glass-spin {
  to { transform: rotate(360deg); }
}
</style>
