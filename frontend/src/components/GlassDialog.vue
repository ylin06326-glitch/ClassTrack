<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    :width="width"
    :top="top"
    :modal="modal"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="closeOnPressEscape"
    :show-close="showClose"
    :center="center"
    :align-center="alignCenter"
    :destroy-on-close="destroyOnClose"
    @update:model-value="(val: boolean) => emit('update:modelValue', val)"
    @open="emit('open')"
    @opened="emit('opened')"
    @close="emit('close')"
    @closed="emit('closed')"
    class="glass-dialog-wrapper"
  >
    <LiquidGlassPanel
      :border-radius="28"
      :bezel-width="4"
      :glass-thickness="8"
      :refractive-index="1.8"
      :blur="15"
      :scale-ratio="1.2"
      :specular-opacity="0.9"
      :specular-saturation="2.5"
      :background-color="'rgba(255, 255, 255, 0.55)'"
      :background-opacity="1"
      :shadow="'0 30px 80px rgba(90, 110, 140, 0.35), 0 12px 32px rgba(90, 110, 140, 0.2)'"
      :border-width="2"
      :border-color="'rgba(255, 255, 255, 0.85)'"
      :content-padding="'0'"
      :center-blur-amount="12"
      :gradient-blur-size="50"
      :hover-light="true"
      class="glass-dialog-panel"
    >
      <div class="glass-dialog-content">
        <slot></slot>
      </div>
    </LiquidGlassPanel>

    <template #footer v-if="$slots.footer">
      <slot name="footer"></slot>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { LiquidGlassPanel } from '@sapryniukt/vue-liquid-glass'

interface Props {
  modelValue: boolean
  title?: string
  width?: string | number
  top?: string
  modal?: boolean
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
  showClose?: boolean
  center?: boolean
  alignCenter?: boolean
  destroyOnClose?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  width: '50%',
  top: '15vh',
  modal: true,
  closeOnClickModal: true,
  closeOnPressEscape: true,
  showClose: true,
  center: false,
  alignCenter: false,
  destroyOnClose: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'open'): void
  (e: 'opened'): void
  (e: 'close'): void
  (e: 'closed'): void
}>()
</script>

<style scoped>
/* 让 el-dialog 背景透明，LiquidGlassPanel 成为实际视觉容器 */
.glass-dialog-wrapper :deep(.el-dialog) {
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  overflow: visible !important;
}

.glass-dialog-wrapper :deep(.el-dialog__header) {
  background: transparent !important;
  border-bottom: none !important;
  padding: 0 0 12px 0 !important;
  margin-right: 0 !important;
}

.glass-dialog-wrapper :deep(.el-dialog__title) {
  color: #000000 !important;
  font-weight: 900 !important;
  font-size: 20px !important;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.8) !important;
}

.glass-dialog-wrapper :deep(.el-dialog__headerbtn) {
  background: rgba(255, 255, 255, 0.6) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(255, 255, 255, 0.7) !important;
  border-radius: 999px !important;
  width: 36px !important;
  height: 36px !important;
  top: 0 !important;
  right: 0 !important;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}

.glass-dialog-wrapper :deep(.el-dialog__headerbtn:hover) {
  background: rgba(255, 100, 100, 0.35) !important;
  transform: scale(1.15) rotate(90deg) !important;
}

.glass-dialog-wrapper :deep(.el-dialog__close) {
  color: #1d1d1f !important;
  font-size: 18px !important;
  font-weight: 800 !important;
}

.glass-dialog-wrapper :deep(.el-dialog__body) {
  background: transparent !important;
  padding: 0 !important;
  color: #1a1a1a !important;
  font-size: 15px !important;
  line-height: 1.6 !important;
}

.glass-dialog-wrapper :deep(.el-dialog__footer) {
  background: transparent !important;
  border-top: none !important;
  padding: 16px 0 0 0 !important;
  gap: 12px !important;
}

/* LiquidGlassPanel 容器 */
.glass-dialog-panel {
  overflow: hidden !important;
}

.glass-dialog-content {
  position: relative !important;
  z-index: 2 !important;
  padding: 28px !important;
}
</style>
