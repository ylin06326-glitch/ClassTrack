import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 液态玻璃效果参数 Store
 * 允许用户在设置中自由调节液态玻璃的程度
 */
export const useGlassStore = defineStore('glass', () => {
  // 是否启用液态玻璃效果
  const enabled = ref(true)

  // 液态玻璃整体强度 (0-100)
  const intensity = ref(70)

  // 背景透明度 (0-1)，0=完全透明，1=完全不透明
  const opacity = ref(0.35)

  // 模糊程度 (0-50)
  const blur = ref(25)

  // 折射率 (1-3)
  const refractiveIndex = ref(2.2)

  // 高光强度 (0-1)
  const specularOpacity = ref(1.0)

  // 从 localStorage 加载保存的设置
  function loadFromStorage() {
    try {
      const saved = localStorage.getItem('classtrack_glass_settings')
      if (saved) {
        const data = JSON.parse(saved)
        if (typeof data.enabled === 'boolean') enabled.value = data.enabled
        if (typeof data.intensity === 'number') intensity.value = data.intensity
        if (typeof data.opacity === 'number') opacity.value = data.opacity
        if (typeof data.blur === 'number') blur.value = data.blur
        if (typeof data.refractiveIndex === 'number') refractiveIndex.value = data.refractiveIndex
        if (typeof data.specularOpacity === 'number') specularOpacity.value = data.specularOpacity
      }
    } catch (e) {
      console.warn('Failed to load glass settings:', e)
    }
  }

  // 保存到 localStorage
  function saveToStorage() {
    try {
      localStorage.setItem('classtrack_glass_settings', JSON.stringify({
        enabled: enabled.value,
        intensity: intensity.value,
        opacity: opacity.value,
        blur: blur.value,
        refractiveIndex: refractiveIndex.value,
        specularOpacity: specularOpacity.value,
      }))
    } catch (e) {
      console.warn('Failed to save glass settings:', e)
    }
  }

  // 重置为默认值
  function resetDefaults() {
    enabled.value = true
    intensity.value = 70
    opacity.value = 0.35
    blur.value = 25
    refractiveIndex.value = 2.2
    specularOpacity.value = 1.0
    saveToStorage()
  }

  // 计算后的背景颜色（根据透明度）
  const backgroundColor = computed(() => {
    const alpha = enabled.value ? opacity.value : 0.9
    return `rgba(255, 255, 255, ${alpha})`
  })

  // 计算后的模糊值（根据强度）
  const effectiveBlur = computed(() => {
    if (!enabled.value) return 0
    return Math.round(blur.value * (intensity.value / 100))
  })

  // 计算后的折射率（根据强度）
  const effectiveRefractiveIndex = computed(() => {
    if (!enabled.value) return 1.0
    return 1.0 + (refractiveIndex.value - 1.0) * (intensity.value / 100)
  })

  // 计算后的缩放比例（折射强度）
  const effectiveScaleRatio = computed(() => {
    if (!enabled.value) return 0
    return 1.8 * (intensity.value / 100)
  })

  // 计算后的高光不透明度
  const effectiveSpecularOpacity = computed(() => {
    if (!enabled.value) return 0
    return specularOpacity.value * (intensity.value / 100)
  })

  // 初始化时加载
  loadFromStorage()

  return {
    // 状态
    enabled,
    intensity,
    opacity,
    blur,
    refractiveIndex,
    specularOpacity,
    // 计算属性
    backgroundColor,
    effectiveBlur,
    effectiveRefractiveIndex,
    effectiveScaleRatio,
    effectiveSpecularOpacity,
    // 方法
    loadFromStorage,
    saveToStorage,
    resetDefaults,
  }
})
