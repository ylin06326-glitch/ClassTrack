<template>
  <div class="lg-segmented" :class="{ 'lg-segmented--compact': compact }">
    <!-- 滑轨（背景轨道） -->
    <div class="lg-segmented__track">
      <!-- 药丸形液态玻璃滑块 -->
      <div
        ref="thumbRef"
        class="lg-segmented__thumb"
        :class="[`grade-${activeGrade?.toLowerCase() || 'default'}`, { dragging: isDragging }]"
        :style="thumbStyle"
      >
        <!-- 顶部高光层 -->
        <div class="lg-segmented__thumb-highlight"></div>
      </div>

      <!-- 选项按钮 -->
      <div
        v-for="(item, index) in items"
        :key="item.value"
        class="lg-segmented__item"
        :class="{ active: modelValue === item.value }"
        @click="select(item.value)"
        @pointerdown="onPointerDown($event, index)"
      >
        <span class="lg-segmented__label">{{ item.label }}</span>
      </div>
    </div>
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
  const track = thumbRef.value?.parentElement
  if (!track) return
  const items = track.querySelectorAll('.lg-segmented__item')
  const activeIndex = props.items.findIndex((i) => i.value === props.modelValue)
  if (activeIndex < 0 || !items[activeIndex]) return
  const item = items[activeIndex] as HTMLElement
  const trackRect = track.getBoundingClientRect()
  const itemRect = item.getBoundingClientRect()
  thumbLeft.value = itemRect.left - trackRect.left
  thumbWidth.value = itemRect.width
}

function onPointerDown(_e: PointerEvent, _index: number) {
  // 预留拖拽功能
}

onMounted(() => {
  nextTick(() => {
    updateThumb()
  })
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
}

.lg-segmented--compact {
  transform: scale(0.92);
  transform-origin: left center;
}

/* 滑轨（背景轨道） */
.lg-segmented__track {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 4px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  box-shadow:
    inset 0 1px 3px rgba(0, 0, 0, 0.04),
    inset 0 -1px 1px rgba(255, 255, 255, 0.5);
}

.lg-segmented--compact .lg-segmented__track {
  padding: 3px;
  border-radius: 12px;
}

/* 药丸形液态玻璃滑块 */
.lg-segmented__thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  z-index: 1;
  border-radius: 10px;
  /* 液态玻璃效果 */
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.65) 0%,
    rgba(255, 255, 255, 0.45) 50%,
    rgba(255, 255, 255, 0.55) 100%
  );
  backdrop-filter: blur(20px) saturate(180%) brightness(1.15) contrast(1.05);
  -webkit-backdrop-filter: blur(20px) saturate(180%) brightness(1.15) contrast(1.05);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-bottom: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.12),
    0 1px 4px rgba(0, 0, 0, 0.08),
    0 0 12px rgba(255, 255, 255, 0.3),
    /* 顶部高光 */
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.9),
    /* 底部反光 */
    inset 0 -1.5px 3px rgba(0, 0, 0, 0.04),
    /* 侧边高光 */
    inset 1px 0 1px rgba(255, 255, 255, 0.5),
    inset -1px 0 1px rgba(255, 255, 255, 0.4);
  transition: left 0.5s cubic-bezier(0.34, 1.56, 0.64, 1),
              width 0.5s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.3s ease,
              background 0.4s ease,
              box-shadow 0.4s ease;
  overflow: hidden;
  will-change: transform, left, width;
}

.lg-segmented--compact .lg-segmented__thumb {
  top: 3px;
  bottom: 3px;
  border-radius: 9px;
}

/* 滑块顶部高光层 */
.lg-segmented__thumb-highlight {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60%;
  border-radius: 10px 10px 0 0;
  background:
    radial-gradient(ellipse 70% 60% at 28% 15%, rgba(255, 255, 255, 0.75) 0%, transparent 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.25) 0%, transparent 100%);
  pointer-events: none;
  z-index: 2;
}

.lg-segmented--compact .lg-segmented__thumb-highlight {
  border-radius: 9px 9px 0 0;
}

.lg-segmented__thumb.dragging {
  transition: none !important;
  transform: scale(1.05, 0.95);
}

/* 选项按钮 */
.lg-segmented__item {
  position: relative;
  z-index: 2;
  padding: 7px 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: rgba(60, 70, 85, 0.55);
  border-radius: 10px;
  transition: color 0.3s ease, transform 0.15s ease;
  font-family: inherit;
  white-space: nowrap;
  user-select: none;
}

.lg-segmented--compact .lg-segmented__item {
  padding: 5px 12px;
  font-size: 12px;
  min-width: 36px;
  text-align: center;
  border-radius: 9px;
}

.lg-segmented__item:hover {
  color: rgba(60, 70, 85, 0.8);
}

.lg-segmented__item:active {
  transform: scale(0.96);
}

.lg-segmented__item.active {
  color: #1d1d1f;
  font-weight: 600;
}

/* 等级颜色（滑块动态染色） */
.lg-segmented__thumb.grade-a {
  background: linear-gradient(
    135deg,
    rgba(111, 174, 131, 0.5) 0%,
    rgba(111, 174, 131, 0.35) 50%,
    rgba(111, 174, 131, 0.45) 100%
  );
  border-color: rgba(111, 174, 131, 0.5);
  box-shadow:
    0 4px 16px rgba(111, 174, 131, 0.3),
    0 0 12px rgba(111, 174, 131, 0.2),
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-b {
  background: linear-gradient(
    135deg,
    rgba(106, 162, 196, 0.5) 0%,
    rgba(106, 162, 196, 0.35) 50%,
    rgba(106, 162, 196, 0.45) 100%
  );
  border-color: rgba(106, 162, 196, 0.5);
  box-shadow:
    0 4px 16px rgba(106, 162, 196, 0.3),
    0 0 12px rgba(106, 162, 196, 0.2),
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-c {
  background: linear-gradient(
    135deg,
    rgba(224, 180, 92, 0.5) 0%,
    rgba(224, 180, 92, 0.35) 50%,
    rgba(224, 180, 92, 0.45) 100%
  );
  border-color: rgba(224, 180, 92, 0.5);
  box-shadow:
    0 4px 16px rgba(224, 180, 92, 0.3),
    0 0 12px rgba(224, 180, 92, 0.2),
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-l {
  background: linear-gradient(
    135deg,
    rgba(159, 140, 201, 0.5) 0%,
    rgba(159, 140, 201, 0.35) 50%,
    rgba(159, 140, 201, 0.45) 100%
  );
  border-color: rgba(159, 140, 201, 0.5);
  box-shadow:
    0 4px 16px rgba(159, 140, 201, 0.3),
    0 0 12px rgba(159, 140, 201, 0.2),
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.85);
}
.lg-segmented__thumb.grade-x {
  background: linear-gradient(
    135deg,
    rgba(216, 137, 168, 0.5) 0%,
    rgba(216, 137, 168, 0.35) 50%,
    rgba(216, 137, 168, 0.45) 100%
  );
  border-color: rgba(216, 137, 168, 0.5);
  box-shadow:
    0 4px 16px rgba(216, 137, 168, 0.3),
    0 0 12px rgba(216, 137, 168, 0.2),
    inset 0 1.5px 1.5px rgba(255, 255, 255, 0.85);
}
</style>
