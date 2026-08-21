<template>
  <Teleport to="body">
    <Transition name="glass-message-box">
      <div v-if="visible" class="glass-message-box-overlay" @click.self="onCancel">
        <div class="glass-message-box-wrapper interactive-glass">
          <LiquidGlassPanel
            :border-radius="28"
            :bezel-width="3"
            :glass-thickness="5"
            :refractive-index="2.0"
            :blur="glassStore.effectiveBlur"
            :scale-ratio="1.2"
            :specular-opacity="0.9"
            :specular-saturation="4.0"
            :background-opacity="glassStore.opacity"
            :shadow="'0 30px 80px rgba(90, 110, 140, 0.4), 0 12px 32px rgba(90, 110, 140, 0.25)'"
            :border-width="2"
            :border-color="'rgba(255, 255, 255, 0.9)'"
            :content-padding="'0'"
            :hover-light="true"
            class="glass-message-box-panel"
          >
            <div class="glass-message-box-content">
              <!-- 鏍囬鏍?-->
              <div class="gm-header">
                <span class="gm-title">{{ title }}</span>
                <button class="gm-close-btn" @click="onCancel">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>

              <!-- 鍐呭鍖?-->
              <div class="gm-body">
                <div v-if="icon" class="gm-icon">{{ icon }}</div>
                <div class="gm-message">
                  <p v-for="(line, i) in messageLines" :key="i">{{ line }}</p>
                </div>
              </div>

              <!-- 杈撳叆妗嗭紙prompt 妯″紡锛?-->
              <div v-if="mode === 'prompt'" class="gm-input-wrapper">
                <input
                  ref="inputRef"
                  v-model="localInputValue"
                  class="gm-input"
                  :placeholder="inputPlaceholder"
                  @keyup.enter="onConfirm"
                  @keyup.esc="onCancel"
                />
              </div>

              <!-- 鎸夐挳鍖?- 浣跨敤 GlassButton锛堝紑婧愬簱 LiquidGlassButton锛?-->
              <div class="gm-btns">
                <GlassButton
                  v-if="mode !== 'alert'"
                  type="default"
                  size="default"
                  @click="onCancel"
                >
                  {{ cancelButtonText }}
                </GlassButton>
                <GlassButton
                  type="primary"
                  size="default"
                  @click="onConfirm"
                >
                  {{ confirmButtonText }}
                </GlassButton>
              </div>
            </div>
          </LiquidGlassPanel>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { LiquidGlassPanel } from '@sapryniukt/vue-liquid-glass'
import GlassButton from './GlassButton.vue'
import { useGlassStore } from '@/stores/glass'

const glassStore = useGlassStore()

export type MessageBoxMode = 'confirm' | 'prompt' | 'alert'

interface Props {
  visible: boolean
  mode?: MessageBoxMode
  title?: string
  message?: string
  icon?: string
  inputValue?: string
  inputPlaceholder?: string
  confirmButtonText?: string
  cancelButtonText?: string
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'confirm',
  title: '提示',
  message: '',
  icon: '',
  inputValue: '',
  inputPlaceholder: '请输入',
  confirmButtonText: '纭畾',
  cancelButtonText: '取消',
})

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', value?: string): void
  (e: 'cancel'): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const localInputValue = ref(props.inputValue)

const messageLines = computed(() => {
  return props.message.split('\n').filter(line => line.trim() !== '')
})

watch(() => props.visible, (val) => {
  if (val && props.mode === 'prompt') {
    localInputValue.value = props.inputValue
    nextTick(() => {
      inputRef.value?.focus()
      inputRef.value?.select()
    })
  }
})

function onConfirm() {
  if (props.mode === 'prompt') {
    emit('confirm', localInputValue.value)
  } else {
    emit('confirm')
  }
  emit('update:visible', false)
}

function onCancel() {
  emit('cancel')
  emit('update:visible', false)
}
</script>

<style scoped>
/* 鍙繚鐣欏竷灞€鐩稿叧鐨?CSS锛屾牱寮忓畬鍏ㄤ緷璧栧紑婧愬簱 */
.glass-message-box-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.glass-message-box-wrapper {
  width: 100%;
  max-width: 440px;
}

.glass-message-box-panel {
  overflow: hidden !important;
}

.glass-message-box-content {
  position: relative;
  z-index: 2;
}

.gm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.gm-title {
  font-size: 20px;
  font-weight: 900;
  color: #000000;
  letter-spacing: -0.02em;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.8);
}

.gm-close-btn {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #1d1d1f;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.gm-close-btn:hover {
  background: rgba(255, 100, 100, 0.3);
  transform: scale(1.15) rotate(90deg);
}

.gm-body {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px 24px;
}

.gm-icon {
  font-size: 28px;
  flex-shrink: 0;
  line-height: 1;
}

.gm-message {
  flex: 1;
  color: #1a1a1a;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.7;
  text-shadow: 0 1px 1px rgba(255, 255, 255, 0.6);
}

.gm-message p {
  margin: 0;
}

.gm-input-wrapper {
  padding: 0 24px 16px;
}

.gm-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 16px;
  font-weight: 500;
  color: #1a1a1a;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 2px solid rgba(255, 255, 255, 0.8);
  border-radius: 14px;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.gm-input:focus {
  border-color: rgba(106, 162, 196, 0.8);
  box-shadow: 0 0 0 4px rgba(106, 162, 196, 0.15);
  background: rgba(255, 255, 255, 0.85);
}

.gm-btns {
  display: flex;
  gap: 12px;
  padding: 16px 24px 22px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.gm-btns :deep(.glass-button-wrapper) {
  flex: 1;
}

.glass-message-box-panel {
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.4s ease;
}

/* 浜や簰鍙樺舰锛氭偓鍋滄椂杞诲井涓婃诞鏀惧ぇ */
.interactive-glass:hover .glass-message-box-panel {
  transform: translateY(-4px) scale(1.01);
}

/* 浜や簰鍙樺舰锛氱偣鍑?鎸変笅鏃舵尋鍘嬪彉褰?*/
.interactive-glass:active .glass-message-box-panel {
  transform: scale(0.98) translateY(2px);
  transition: transform 0.1s ease-out;
}

/* 鍔ㄧ敾 */
.glass-message-box-enter-active,
.glass-message-box-leave-active {
  transition: opacity 0.3s ease;
}

.glass-message-box-enter-active .glass-message-box-wrapper,
.glass-message-box-leave-active .glass-message-box-wrapper {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.glass-message-box-enter-from,
.glass-message-box-leave-to {
  opacity: 0;
}

.glass-message-box-enter-from .glass-message-box-wrapper,
.glass-message-box-leave-to .glass-message-box-wrapper {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}
</style>

