<template>
  <Teleport to="body">
    <Transition name="glass-dialog-fade">
      <div v-if="modelValue" class="glass-dialog-overlay" @click.self="onOverlayClick">
        <Transition name="glass-dialog-zoom" appear @enter="onEnter">
          <div v-if="modelValue" class="glass-dialog-container interactive-glass" :style="containerStyle">
            <LiquidGlassPanel
              :width="560"
              :border-radius="32"
              :bezel-width="40"
              :glass-thickness="120"
              :refractive-index="1.5"
              :blur="1"
              :scale-ratio="0.4"
              :specular-opacity="0.4"
              :specular-saturation="8"
              :background-color="'rgba(255, 255, 255, 0.15)'"
              :background-opacity="1"
              :shadow="'0 30px 80px rgba(90, 110, 140, 0.4), 0 12px 32px rgba(90, 110, 140, 0.25)'"
              :border-width="2"
              :border-color="'rgba(255, 255, 255, 0.9)'"
              :content-padding="'0'"
              :center-blur-amount="3"
              :gradient-blur-size="60"
              :hover-light="true"
              class="glass-dialog-panel"
            >
              <div class="glass-dialog-inner">
                <!-- 标题栏 -->
                <div class="glass-dialog-header" v-if="title || showClose">
                  <h3 class="glass-dialog-title">{{ title }}</h3>
                  <button v-if="showClose" class="glass-dialog-close" @click="close">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>

                <!-- 内容区 -->
                <div class="glass-dialog-body">
                  <slot></slot>
                </div>

                <!-- 底部按钮区 -->
                <div v-if="$slots.footer" class="glass-dialog-footer">
                  <slot name="footer"></slot>
                </div>
              </div>
            </LiquidGlassPanel>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick } from 'vue'
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
  width: '560px',
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

const containerStyle = computed(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width,
  marginTop: props.top,
}))

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function onEnter(el: Element) {
  // 强制刷新 LiquidGlassPanel 的尺寸检测
  nextTick(() => {
    const panel = el.querySelector('.glass-dialog-panel') as HTMLElement | null
    if (panel) {
      // 触发 reflow，确保 offsetWidth > 0
      void panel.offsetWidth
    }
  })
}

function onOverlayClick() {
  if (props.closeOnClickModal) {
    close()
  }
}
</script>

<style scoped>
.glass-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}

.glass-dialog-container {
  position: relative;
  width: 560px;
  max-width: calc(100vw - 40px);
  max-height: calc(100vh - 40px);
}

/* 确保 LiquidGlassPanel 有明确尺寸，不会被尺寸检测隐藏 */
.glass-dialog-panel {
  width: 100% !important;
  min-height: 200px !important;
  display: block !important;
  visibility: visible !important;
}

.glass-dialog-panel :deep(*) {
  visibility: visible !important;
}

.glass-dialog-inner {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  width: 100%;

}

.glass-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);

}

.glass-dialog-title {
  margin: 0;
  font-size: 20px;
  font-weight: 900;
  color: #000000;
  letter-spacing: -0.02em;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.8);
}

.glass-dialog-close {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #1d1d1f;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.glass-dialog-close:hover {
  background: rgba(255, 100, 100, 0.35);
  transform: scale(1.15) rotate(90deg);
}

.glass-dialog-body {
  padding: 20px 24px;
  color: #1a1a1a;
  font-size: 15px;
  line-height: 1.6;
  overflow-y: auto;

  max-height: calc(100vh - 200px);
}

.glass-dialog-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 24px 22px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.glass-dialog-panel {
  width: 100%;
  min-height: 200px;
  overflow: hidden !important;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.4s ease;
}

/* 交互变形：悬停时轻微上浮放大 */
.interactive-glass:hover .glass-dialog-panel {
  transform: translateY(-4px) scale(1.01);
}

/* 交互变形：点击/按下时挤压变形 */
.interactive-glass:active .glass-dialog-panel {
  transform: scale(0.98) translateY(2px);
  transition: transform 0.1s ease-out;
}

/* 动画 */
.glass-dialog-fade-enter-active,
.glass-dialog-fade-leave-active {
  transition: opacity 0.3s ease;
}

.glass-dialog-fade-enter-from,
.glass-dialog-fade-leave-to {
  opacity: 0;
}

.glass-dialog-zoom-enter-active,
.glass-dialog-zoom-leave-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.glass-dialog-zoom-enter-from,
.glass-dialog-zoom-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}
</style>
