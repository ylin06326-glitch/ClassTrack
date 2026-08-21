// 壁纸管理 Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface WallpaperPreset {
  id: string
  name: string
  nameEn: string
  description: string
  type: 'gradient' | 'image' | 'custom'
  cssClass?: string
  thumbnail: string // 缩略图颜色或描述
}

// 预设壁纸列表
export const wallpaperPresets: WallpaperPreset[] = [
  {
    id: 'morandi-breathing',
    name: '莫兰迪呼吸灯',
    nameEn: 'Morandi Breathing',
    description: '低饱和度莫兰迪色系，缓慢流畅流动',
    type: 'gradient',
    cssClass: 'wallpaper-morandi',
    thumbnail: 'linear-gradient(135deg, #b4c3d2, #beb4c8, #cdc3b9)'
  },
  {
    id: 'apple-sunset',
    name: '苹果日落',
    nameEn: 'Apple Sunset',
    description: '橙红渐变，温暖日落氛围',
    type: 'gradient',
    cssClass: 'wallpaper-sunset',
    thumbnail: 'linear-gradient(135deg, #ff6b6b, #ffa500, #ffd93d)'
  },
  {
    id: 'apple-aurora',
    name: '苹果极光',
    nameEn: 'Apple Aurora',
    description: '蓝绿渐变，极光流动效果',
    type: 'gradient',
    cssClass: 'wallpaper-aurora',
    thumbnail: 'linear-gradient(135deg, #00d4ff, #00ff88, #7b2ff7)'
  },
  {
    id: 'apple-ocean',
    name: '苹果海洋',
    nameEn: 'Apple Ocean',
    description: '深蓝渐变，宁静海洋氛围',
    type: 'gradient',
    cssClass: 'wallpaper-ocean',
    thumbnail: 'linear-gradient(135deg, #0077b6, #00b4d8, #90e0ef)'
  },
  {
    id: 'apple-mountain',
    name: '苹果山脉',
    nameEn: 'Apple Mountain',
    description: '蓝紫渐变，山脉剪影氛围',
    type: 'gradient',
    cssClass: 'wallpaper-mountain',
    thumbnail: 'linear-gradient(135deg, #2d1b69, #5b3a8c, #8e7cc3)'
  },
  {
    id: 'pure-black',
    name: '纯黑极简',
    nameEn: 'Pure Black',
    description: '纯黑背景，极简省电风格',
    type: 'gradient',
    cssClass: 'wallpaper-black',
    thumbnail: 'linear-gradient(135deg, #000000, #1a1a1a, #000000)'
  },
  {
    id: 'custom',
    name: '自定义图片',
    nameEn: 'Custom Image',
    description: '上传你自己的图片作为壁纸',
    type: 'custom',
    thumbnail: 'linear-gradient(135deg, #666, #999, #666)'
  }
]

export const useWallpaperStore = defineStore('wallpaper', () => {
  // 当前壁纸 ID
  const currentWallpaperId = ref<string>('morandi-breathing')

  // 自定义图片（base64）
  const customImage = ref<string>('')

  // 从 localStorage 加载
  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem('classtrack-wallpaper')
      if (saved) {
        const data = JSON.parse(saved)
        currentWallpaperId.value = data.currentWallpaperId || 'morandi-breathing'
        customImage.value = data.customImage || ''
      }
    } catch (e) {
      console.warn('加载壁纸设置失败', e)
    }
  }

  // 保存到 localStorage
  const saveToStorage = () => {
    try {
      localStorage.setItem('classtrack-wallpaper', JSON.stringify({
        currentWallpaperId: currentWallpaperId.value,
        customImage: customImage.value
      }))
    } catch (e) {
      console.warn('保存壁纸设置失败', e)
    }
  }

  // 设置壁纸
  const setWallpaper = (id: string) => {
    currentWallpaperId.value = id
    saveToStorage()
  }

  // 设置自定义图片
  const setCustomImage = (imageBase64: string) => {
    customImage.value = imageBase64
    currentWallpaperId.value = 'custom'
    saveToStorage()
  }

  // 清除自定义图片
  const clearCustomImage = () => {
    customImage.value = ''
    if (currentWallpaperId.value === 'custom') {
      currentWallpaperId.value = 'morandi-breathing'
    }
    saveToStorage()
  }

  // 当前壁纸信息
  const currentWallpaper = computed(() => {
    return wallpaperPresets.find(p => p.id === currentWallpaperId.value) || wallpaperPresets[0]
  })

  // 当前壁纸 CSS 类
  const currentCssClass = computed(() => {
    if (currentWallpaperId.value === 'custom' && customImage.value) {
      return 'wallpaper-custom'
    }
    return currentWallpaper.value.cssClass || ''
  })

  // 初始化加载
  loadFromStorage()

  return {
    currentWallpaperId,
    customImage,
    currentWallpaper,
    currentCssClass,
    wallpaperPresets,
    setWallpaper,
    setCustomImage,
    clearCustomImage,
    loadFromStorage
  }
})
