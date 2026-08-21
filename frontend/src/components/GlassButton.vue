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
    :text-color="textColor"
    :background-color="bgColor"
    @click="handleClick"
    :class="['glass-button-wrapper', `glass-button-type-${type}`, { 'glass-button-loading': loading }, $attrs.class]"
    :style="$attrs.style"
  >
    <span v-if="loading" class="glass-button-spinner"></span>
    <span class="glass-button-content">
      <slot></slot>
    </span>
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

// 根据按钮类型设置文字颜色（确保可读性）
const textColor = computed(() => {
  switch (props.type) {
    case 'primary':
    case 'success':
    case 'danger':
    case 'warning':
      return '#ffffff'
    case 'default':
    case 'info':
    case 'text':
    default:
      return '#1d1d1f'
  }
})

// 根据按钮类型设置背景颜色（半透明，确保玻璃效果）
const bgColor = computed(() => {
  switch (props.type) {
    case 'primary':
      return 'rgba(106, 162, 196, 0.6)'
    case 'success':
      return 'rgba(111, 174, 131, 0.6)'
    case 'danger':
      return 'rgba(216, 137, 168, 0.6)'
    case 'warning':
      return 'rgba(224, 180, 92, 0.6)'
    case 'info':
      return 'rgba(159, 140, 201, 0.6)'
    case 'default':
    case 'text':
    default:
      return 'rgba(255, 255, 255, 0.5)'
  }
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
  box-sizing: border-box;
}

.glass-button-wrapper :deep(button) {
  font-family: inherit !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  box-sizing: border-box !important;
}

/* 确保 slot 内容的文字颜色正确 */
.glass-button-content {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.glass-button-type-default .glass-button-content,
.glass-button-type-info .glass-button-content,
.glass-button-type-text .glass-button-content {
  color: #1d1d1f !important;
}

.glass-button-type-primary .glass-button-content,
.glass-button-type-success .glass-button-content,
.glass-button-type-danger .glass-button-content,
.glass-button-type-warning .glass-button-content {
  color: #ffffff !important;
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
