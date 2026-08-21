<template>
  <LiquidGlassInput
    :model-value="modelValue"
    :placeholder="placeholder"
    :type="inputType"
    :size="lgSize"
    :disabled="disabled"
    :radius="999"
    @update:model-value="(val: string) => emit('update:modelValue', val)"
    @focus="emit('focus')"
    @blur="emit('blur')"
    class="glass-input-wrapper"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LiquidGlassInput } from '@sapryniukt/vue-liquid-glass'

interface Props {
  modelValue?: string
  placeholder?: string
  type?: 'text' | 'email' | 'password' | 'search' | 'url' | 'tel'
  size?: 'large' | 'default' | 'small'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '',
  type: 'text',
  size: 'default',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'focus'): void
  (e: 'blur'): void
}>()

const inputType = computed(() => props.type)

const lgSize = computed(() => {
  switch (props.size) {
    case 'large': return 'large'
    case 'small': return 'small'
    default: return 'medium'
  }
})
</script>

<style scoped>
.glass-input-wrapper {
  width: 100%;
}

.glass-input-wrapper :deep(input) {
  font-family: inherit !important;
}
</style>
