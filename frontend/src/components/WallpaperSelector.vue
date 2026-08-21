<template>
  <div class="wallpaper-selector">
    <h3 class="section-title">🎨 壁纸设置</h3>
    <p class="section-desc">选择你喜欢的壁纸风格，支持渐变、图片和动态视频</p>

    <!-- 预设壁纸网格 -->
    <div class="wallpaper-grid">
      <div
        v-for="preset in wallpaperPresets"
        :key="preset.id"
        class="wallpaper-card"
        :class="{ active: wallpaperStore.currentWallpaperId === preset.id }"
        @click="selectWallpaper(preset.id)"
      >
        <div class="wallpaper-thumbnail" :style="{ background: preset.thumbnail }">
          <!-- 视频图标 -->
          <div v-if="preset.type === 'video'" class="video-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          </div>
          <!-- 自定义图片图标 -->
          <div v-if="preset.id === 'custom-image'" class="custom-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <circle cx="8.5" cy="8.5" r="1.5"></circle>
              <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
          </div>
          <!-- 自定义视频图标 -->
          <div v-if="preset.id === 'custom-video'" class="custom-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
              <polygon points="23 7 16 12 23 17 23 7"></polygon>
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
          </div>
        </div>
        <div class="wallpaper-info">
          <div class="wallpaper-name">{{ preset.name }}</div>
          <div class="wallpaper-desc">{{ preset.description }}</div>
        </div>
        <div v-if="wallpaperStore.currentWallpaperId === preset.id" class="active-badge">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
      </div>
    </div>

    <!-- 自定义图片上传 -->
    <div v-if="wallpaperStore.currentWallpaperId === 'custom-image'" class="custom-upload-section">
      <div class="upload-area" @click="triggerImageInput" @dragover.prevent @drop.prevent="handleImageDrop">
        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          style="display: none"
          @change="handleImageSelect"
        />
        <div v-if="!wallpaperStore.customImage" class="upload-placeholder">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <p>点击或拖拽图片到这里上传</p>
          <p class="upload-hint">支持 JPG、PNG、WebP 格式</p>
        </div>
        <div v-else class="upload-preview">
          <img :src="wallpaperStore.customImage" alt="自定义壁纸预览" />
          <div class="preview-overlay">
            <button class="change-btn" @click.stop="triggerImageInput">更换图片</button>
            <button class="remove-btn" @click.stop="removeCustomImage">移除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 自定义视频上传 -->
    <div v-if="wallpaperStore.currentWallpaperId === 'custom-video'" class="custom-upload-section">
      <div class="upload-area" @click="triggerVideoInput" @dragover.prevent @drop.prevent="handleVideoDrop">
        <input
          ref="videoInput"
          type="file"
          accept="video/*"
          style="display: none"
          @change="handleVideoSelect"
        />
        <div v-if="!wallpaperStore.customVideoUrl" class="upload-placeholder">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <polygon points="23 7 16 12 23 17 23 7"></polygon>
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
          </svg>
          <p>点击或拖拽视频到这里上传</p>
          <p class="upload-hint">支持 MP4、WebM、OGG 格式，建议 1080p 以下</p>
        </div>
        <div v-else class="upload-preview">
          <video :src="wallpaperStore.customVideoUrl" muted loop autoplay playsinline></video>
          <div class="preview-overlay">
            <div class="video-name">{{ wallpaperStore.customVideoName }}</div>
            <button class="change-btn" @click.stop="triggerVideoInput">更换视频</button>
            <button class="remove-btn" @click.stop="removeCustomVideo">移除</button>
          </div>
        </div>
      </div>
      <p class="video-notice">💡 注意：自定义视频不会保存到本地，刷新页面后需要重新选择</p>
    </div>

    <!-- 视频设置（仅视频壁纸时显示） -->
    <div v-if="wallpaperStore.isVideoWallpaper" class="video-settings">
      <h4 class="settings-subtitle">🎬 视频设置</h4>
      <div class="settings-row">
        <label>静音播放</label>
        <el-switch v-model="wallpaperStore.videoMuted" @change="wallpaperStore.saveToStorage()" />
      </div>
      <div class="settings-row">
        <label>循环播放</label>
        <el-switch v-model="wallpaperStore.videoLoop" @change="wallpaperStore.saveToStorage()" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useWallpaperStore, wallpaperPresets } from '../stores/wallpaper'

const wallpaperStore = useWallpaperStore()
const imageInput = ref<HTMLInputElement | null>(null)
const videoInput = ref<HTMLInputElement | null>(null)

const selectWallpaper = (id: string) => {
  wallpaperStore.setWallpaper(id)
}

// 图片上传
const triggerImageInput = () => {
  imageInput.value?.click()
}

const handleImageSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    processImage(file)
  }
}

const handleImageDrop = (event: DragEvent) => {
  const file = event.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    processImage(file)
  }
}

const processImage = (file: File) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    const result = e.target?.result as string
    wallpaperStore.setCustomImage(result)
  }
  reader.readAsDataURL(file)
}

const removeCustomImage = () => {
  wallpaperStore.clearCustomImage()
}

// 视频上传
const triggerVideoInput = () => {
  videoInput.value?.click()
}

const handleVideoSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    processVideo(file)
  }
}

const handleVideoDrop = (event: DragEvent) => {
  const file = event.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('video/')) {
    processVideo(file)
  }
}

const processVideo = (file: File) => {
  const videoUrl = URL.createObjectURL(file)
  wallpaperStore.setCustomVideo(videoUrl, file.name)
}

const removeCustomVideo = () => {
  wallpaperStore.clearCustomVideo()
}
</script>

<style scoped>
.wallpaper-selector {
  margin-bottom: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: var(--text, #1a1a1a);
}

.section-desc {
  font-size: 14px;
  color: var(--text-light, #666);
  margin: 0 0 20px 0;
}

.wallpaper-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.wallpaper-card {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(10px);
}

.wallpaper-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
}

.wallpaper-card.active {
  border-color: #4a90d9;
  box-shadow: 0 0 0 3px rgba(74, 144, 217, 0.2);
}

.wallpaper-thumbnail {
  height: 90px;
  position: relative;
}

.video-icon,
.custom-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.3);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wallpaper-info {
  padding: 12px;
}

.wallpaper-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text, #1a1a1a);
  margin-bottom: 4px;
}

.wallpaper-desc {
  font-size: 12px;
  color: var(--text-light, #666);
  line-height: 1.4;
}

.active-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #4a90d9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.custom-upload-section {
  margin-top: 16px;
}

.upload-area {
  border: 2px dashed #ccc;
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.3);
}

.upload-area:hover {
  border-color: #4a90d9;
  background: rgba(74, 144, 217, 0.05);
}

.upload-placeholder {
  color: var(--text-light, #666);
}

.upload-placeholder p {
  margin: 12px 0 4px 0;
  font-size: 14px;
}

.upload-hint {
  font-size: 12px !important;
  color: #999 !important;
}

.upload-preview {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
}

.upload-preview img,
.upload-preview video {
  width: 100%;
  max-height: 200px;
  object-fit: cover;
  display: block;
}

.preview-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.upload-preview:hover .preview-overlay {
  opacity: 1;
}

.video-name {
  color: white;
  font-size: 14px;
  margin-bottom: 8px;
}

.change-btn,
.remove-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.change-btn {
  background: #4a90d9;
  color: white;
}

.change-btn:hover {
  background: #3a7bc8;
}

.remove-btn {
  background: #ff4757;
  color: white;
}

.remove-btn:hover {
  background: #e84118;
}

.video-notice {
  font-size: 12px;
  color: #999;
  margin-top: 12px;
  text-align: center;
}

.video-settings {
  margin-top: 20px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  backdrop-filter: blur(10px);
}

.settings-subtitle {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  color: var(--text, #1a1a1a);
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.settings-row label {
  font-size: 14px;
  color: var(--text, #1a1a1a);
}
</style>
