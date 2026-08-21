/**
 * 音效反馈系统
 * 使用 Web Audio API 生成简短音效，不需要音频文件
 * 基于 Apple 多模态反馈设计原则：视觉、声音、触觉在同一帧触发
 */

import { ref } from 'vue'

// 全局音效启用状态
const soundEnabled = ref(true)
const hapticEnabled = ref(true)

// AudioContext 懒加载
let audioContext: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!audioContext) {
    try {
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    } catch (e) {
      console.warn('Web Audio API not supported')
      return null
    }
  }
  // 恢复被浏览器暂停的 AudioContext
  if (audioContext.state === 'suspended') {
    audioContext.resume()
  }
  return audioContext
}

/**
 * 播放一个简单的音调
 */
function playTone(
  frequency: number,
  duration: number,
  type: OscillatorType = 'sine',
  volume: number = 0.1,
  attack: number = 0.005,
  release: number = 0.05
) {
  if (!soundEnabled.value) return
  const ctx = getAudioContext()
  if (!ctx) return

  const now = ctx.currentTime
  const oscillator = ctx.createOscillator()
  const gainNode = ctx.createGain()

  oscillator.type = type
  oscillator.frequency.setValueAtTime(frequency, now)

  // ADSR 包络（简短的 attack 和 release）
  gainNode.gain.setValueAtTime(0, now)
  gainNode.gain.linearRampToValueAtTime(volume, now + attack)
  gainNode.gain.exponentialRampToValueAtTime(0.001, now + duration + release)

  oscillator.connect(gainNode)
  gainNode.connect(ctx.destination)

  oscillator.start(now)
  oscillator.stop(now + duration + release)
}

/**
 * 触觉反馈（移动端振动）
 */
function vibrate(pattern: number | number[]) {
  if (!hapticEnabled.value) return
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    navigator.vibrate(pattern)
  }
}

/**
 * 音效类型定义
 */
export type SoundType =
  | 'click'      // 按钮点击
  | 'success'    // 操作成功
  | 'error'      // 错误/警告
  | 'toggle'     // 开关切换
  | 'slider'     // 滑块移动
  | 'popup'      // 弹窗出现
  | 'dismiss'    // 弹窗消失
  | 'tab'        // Tab 切换

/**
 * 播放指定类型的音效 + 触觉反馈
 */
export function playSound(type: SoundType) {
  switch (type) {
    case 'click':
      // 短促的 "tick" 声
      playTone(800, 0.02, 'sine', 0.08)
      vibrate(5)
      break

    case 'success':
      // 上升音调，愉悦感
      playTone(523.25, 0.08, 'sine', 0.1) // C5
      setTimeout(() => playTone(659.25, 0.1, 'sine', 0.1), 60) // E5
      vibrate([10, 30, 10])
      break

    case 'error':
      // 下降音调，警告感
      playTone(311.13, 0.1, 'sawtooth', 0.08) // Eb4
      setTimeout(() => playTone(233.08, 0.15, 'sawtooth', 0.08), 80) // Bb3
      vibrate([20, 50, 20])
      break

    case 'toggle':
      // 开关 "click" 声
      playTone(1200, 0.015, 'square', 0.05)
      vibrate(8)
      break

    case 'slider':
      // 滑块轻微 "tick" 声
      playTone(600, 0.01, 'sine', 0.04)
      break

    case 'popup':
      // 弹窗出现，上升音调
      playTone(440, 0.05, 'sine', 0.08) // A4
      setTimeout(() => playTone(554.37, 0.08, 'sine', 0.08), 30) // C#5
      vibrate(15)
      break

    case 'dismiss':
      // 弹窗消失，下降音调
      playTone(554.37, 0.05, 'sine', 0.06) // C#5
      setTimeout(() => playTone(440, 0.08, 'sine', 0.06), 30) // A4
      vibrate(10)
      break

    case 'tab':
      // Tab 切换
      playTone(700, 0.02, 'sine', 0.06)
      vibrate(6)
      break
  }
}

/**
 * 音效设置 composable
 */
export function useSoundSettings() {
  function setSoundEnabled(enabled: boolean) {
    soundEnabled.value = enabled
    localStorage.setItem('classtrack-sound-enabled', String(enabled))
  }

  function setHapticEnabled(enabled: boolean) {
    hapticEnabled.value = enabled
    localStorage.setItem('classtrack-haptic-enabled', String(enabled))
  }

  // 从 localStorage 加载
  if (typeof window !== 'undefined') {
    const savedSound = localStorage.getItem('classtrack-sound-enabled')
    if (savedSound !== null) {
      soundEnabled.value = savedSound === 'true'
    }
    const savedHaptic = localStorage.getItem('classtrack-haptic-enabled')
    if (savedHaptic !== null) {
      hapticEnabled.value = savedHaptic === 'true'
    }
  }

  return {
    soundEnabled,
    hapticEnabled,
    setSoundEnabled,
    setHapticEnabled,
    playSound,
  }
}

/**
 * 初始化音效（需要在用户首次交互后调用，解锁 AudioContext）
 */
export function initSound() {
  getAudioContext()
}
