// 壁纸管理 Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface WallpaperPreset {
  id: string
  name: string
  nameEn: string
  description: string
  type: 'gradient' | 'image' | 'video' | 'custom'
  cssClass?: string
  videoUrl?: string
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
    id: 'video-ocean',
    name: '海洋视频',
    nameEn: 'Ocean Video',
    description: '宁静海洋波浪动态视频',
    type: 'video',
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-waves-in-the-water-1164-large.mp4',
    thumbnail: 'linear-gradient(135deg, #0077b6, #00b4d8, #90e0ef)'
  },
  {
    id: 'video-sunset',
    name: '日落视频',
    nameEn: 'Sunset Video',
    description: '温暖日落天空动态视频',
    type: 'video',
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-sunset-over-the-ocean-4073-large.mp4',
    thumbnail: 'linear-gradient(135deg, #ff6b6b, #ffa500, #ffd93d)'
  },
  {
    id: 'video-aurora',
    name: '极光视频',
    nameEn: 'Aurora Video',
    description: '绚丽极光流动动态视频',
    type: 'video',
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-aurora-borealis-in-the-night-sky-4075-large.mp4',
    thumbnail: 'linear-gradient(135deg, #00d4ff, #00ff88, #7b2ff7)'
  },
  {
    id: 'custom-image',
    name: '自定义图片',
    nameEn: 'Custom Image',
    description: '上传你自己的图片作为壁纸',
    type: 'image',
    thumbnail: 'linear-gradient(135deg, #666, #999, #666)'
  },
  {
    id: 'custom-video',
    name: '自定义视频',
    nameEn: 'Custom Video',
    description: '上传你自己的视频作为壁纸',
    type: 'video',
    thumbnail: 'linear-gradient(135deg, #333, #666, #333)'
  }
]

export const useWallpaperStore = defineStore('wallpaper', () => {
  // 当前壁纸 ID
  const currentWallpaperId = ref<string>('morandi-breathing')

  // 自定义图片（base64）
  const customImage = ref<string>('')

  // 自定义视频（Object URL，刷新后需重新选择）
  const customVideoUrl = ref<string>('')
  const customVideoName = ref<string>('')

  // 视频设置
  const videoMuted = ref<boolean>(true)
  const videoLoop = ref<boolean>(true)

  // 从 localStorage 加载
  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem('classtrack-wallpaper')
      if (saved) {
        const data = JSON.parse(saved)
        currentWallpaperId.value = data.currentWallpaperId || 'morandi-breathing'
        customImage.value = data.customImage || ''
        customVideoName.value = data.customVideoName || ''
        videoMuted.value = data.videoMuted !== false
        videoLoop.value = data.videoLoop !== false
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
        customImage: customImage.value,
        customVideoName: customVideoName.value,
        videoMuted: videoMuted.value,
        videoLoop: videoLoop.value
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
    currentWallpaperId.value = 'custom-image'
    saveToStorage()
  }

  // 设置自定义视频
  const setCustomVideo = (videoUrl: string, videoName: string) => {
    // 释放之前的 Object URL
    if (customVideoUrl.value) {
      URL.revokeObjectURL(customVideoUrl.value)
    }
    customVideoUrl.value = videoUrl
    customVideoName.value = videoName
    currentWallpaperId.value = 'custom-video'
    saveToStorage()
  }

  // 清除自定义视频
  const clearCustomVideo = () => {
    if (customVideoUrl.value) {
      URL.revokeObjectURL(customVideoUrl.value)
    }
    customVideoUrl.value = ''
    customVideoName.value = ''
    if (currentWallpaperId.value === 'custom-video') {
      currentWallpaperId.value = 'morandi-breathing'
    }
    saveToStorage()
  }

  // 清除自定义图片
  const clearCustomImage = () => {
    customImage.value = ''
    if (currentWallpaperId.value === 'custom-image') {
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
    if (currentWallpaperId.value === 'custom-image' && customImage.value) {
      return 'wallpaper-custom'
    }
    if (currentWallpaperId.value.startsWith('video-')) {
      return 'wallpaper-video'
    }
    return currentWallpaper.value.cssClass || ''
  })

  // 当前视频 URL
  const currentVideoUrl = computed(() => {
    if (currentWallpaperId.value === 'custom-video') {
      return customVideoUrl.value
    }
    const preset = wallpaperPresets.find(p => p.id === currentWallpaperId.value)
    if (preset && preset.type === 'video') {
      return (preset as any).videoUrl || ''
    }
    return ''
  })

  // 是否是视频壁纸
  const isVideoWallpaper = computed(() => {
    return currentWallpaperId.value.startsWith('video-')
  })

  // 初始化加载
  loadFromStorage()

  return {
    currentWallpaperId,
    customImage,
    customVideoUrl,
    customVideoName,
    videoMuted,
    videoLoop,
    currentWallpaper,
    currentCssClass,
    currentVideoUrl,
    isVideoWallpaper,
    wallpaperPresets,
    setWallpaper,
    setCustomImage,
    setCustomVideo,
    clearCustomImage,
    clearCustomVideo,
    loadFromStorage,
    saveToStorage
  }
})
