<template>
  <div class="lg-segmented" :class="{ 'lg-segmented--compact': compact }">
    <div
      v-for="(item, index) in items"
      :key="item.value"
      class="lg-segmented__item"
      :class="{
        active: modelValue === item.value,
        [`grade-${item.value.toLowerCase()}`]: item.value,
      }"
      @click="select(item.value)"
      @pointerdown="onPointerDown($event, index)"
    >
      <span class="lg-segmented__label">{{ item.label }}</span>
    </div>
    <!-- 液态玻璃滑块 -->
    <div
      ref="thumbRef"
      class="lg-segmented__thumb"
      :class="[`grade-${activeGrade?.toLowerCase() || 'default'}`, { dragging: isDragging }]"
      :style="thumbStyle"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'

interface SegmentedItem {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  items: SegmentedItem[]
  compact?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const thumbRef = ref<HTMLElement | null>(null)
const thumbLeft = ref(0)
const thumbWidth = ref(0)
const isDragging = ref(false)

const activeGrade = computed(() => props.modelValue)

const thumbStyle = computed(() => ({
  left: `${thumbLeft.value}px`,
  width: `${thumbWidth.value}px`,
}))

function select(value: string) {
  emit('update:modelValue', value)
}

function updateThumb() {
  const container = thumbRef.value?.parentElement
  if (!container) return
  const items = container.querySelectorAll('.lg-segmented__item')
  const activeIndex = props.items.findIndex((i) => i.value === props.modelValue)
  if (activeIndex < 0 || !items[activeIndex]) return
  const item = items[activeIndex] as HTMLElement
  const containerRect = container.getBoundingClientRect()
  const itemRect = item.getBoundingClientRect()
  thumbLeft.value = itemRect.left - containerRect.left
  thumbWidth.value = itemRect.width
}

function onPointerDown(_e: PointerEvent, _index: number) {
  // 可以扩展为拖拽切换
}

onMounted(() => {
  nextTick(() => {
    updateThumb()
  })
  // 监听窗口大小变化
  window.addEventListener('resize', updateThumb)
})

watch(
  () => props.modelValue,
  () => {
    nextTick(() => updateThumb())
  }
)
</script>

<style scoped>
.lg-segmented {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  background: rgba(0, 0, 0, 0.025);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  position: relative;
}

.lg-segmented--compact {
  padding: 3px;
  gap: 1px;
  border-radius: 10px;
}

.lg-segmented__item {
  position: relative;
  z-index: 2;
  padding: 6px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: rgba(60, 70, 85, 0.65);
  border-radius: 8px;
  transition: color 0.3s ease;
  font-family: inherit;
  white-space: nowrap;
}

.lg-segmented--compact .lg-segmented__item {
  padding: 4px 10px;
  font-size: 12px;
  min-width: 32px;
  text-align: center;
}

.lg-segmented__item:hover {
  color: rgba(60, 70, 85, 0.9);
}

.lg-segmented__item.active {
  color: #1d1d1f;
  font-weight: 600;
}

/* 液态玻璃滑块 */
.lg-segmented__thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  z-index: 1;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(18px) saturate(180%) brightness(1.1);
  -webkit-backdrop-filter: blur(18px) saturate(180%) brightness(1.1);
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow:
    0 3px 12px rgba(0, 0, 0, 0.12),
    0 1px 4px rgba(0, 0, 0, 0.08),
    inset 0 1px 1px rgba(255, 255, 255, 0.9),
    inset 0 -1px 2px rgba(0, 0, 0, 0.04);
  transition: left 0.45s cubic-bezier(0.34, 1.56, 0.64, 1),
              width 0.45s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.3s ease,
              background 0.4s ease,
              box-shadow 0.4s ease;
  overflow: hidden;
}

.lg-segmented--compact .lg-segmented__thumb {
  top: 3px;
  bottom: 3px;
  border-radius: 7px;
}

.lg-segmented__thumb::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60%;
  border-radius: 8px 8px 0 0;
  background:
    radial-gradient(ellipse 70% 60% at 28% 15%, rgba(255, 255, 255, 0.7) 0%, transparent 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.25) 0%, transparent 100%);
  pointer-events: none;
  z-index: 2;
}

.lg-segmented__thumb.dragging {
  transition: none !important;
  transform: scale(1.05, 0.95);
}

/* 等级颜色 */
.lg-segmented__thumb.grade-a {
  background: rgba(111, 174, 131, 0.45);
  border-color: rgba(111, 174, 131, 0.5);
  box-shadow:
    0 3px 12px rgba(111, 174, 131, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-b {
  background: rgba(106, 162, 196, 0.45);
  border-color: rgba(106, 162, 196, 0.5);
  box-shadow:
    0 3px 12px rgba(106, 162, 196, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-c {
  background: rgba(224, 180, 92, 0.45);
  border-color: rgba(224, 180, 92, 0.5);
  box-shadow:
    0 3px 12px rgba(224, 180, 92, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-l {
  background: rgba(159, 140, 201, 0.45);
  border-color: rgba(159, 140, 201, 0.5);
  box-shadow:
    0 3px 12px rgba(159, 140, 201, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-x {
  background: rgba(216, 137, 168, 0.45);
  border-color: rgba(216, 137, 168, 0.5);
  box-shadow:
    0 3px 12px rgba(216, 137, 168, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.85);
}
</style>
