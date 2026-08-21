/**
 * 弹簧动画与手势物理工具函数
 * 基于 Apple WWDC 2018 "Designing Fluid Interfaces" 设计原则
 */

import { ref, onUnmounted } from 'vue'

/**
 * 弹簧动画参数（Apple 设计友好参数）
 * damping: 阻尼比，1.0 = 临界阻尼，<1.0 = 有弹性
 * response: 响应时间（秒），越小越快
 */
export interface SpringConfig {
  damping: number
  response: number
}

/** 默认弹簧配置（Apple 标准） */
export const DEFAULT_SPRING: SpringConfig = {
  damping: 1.0,
  response: 0.4,
}

/** 动量交互弹簧配置（有轻微弹性） */
export const MOMENTUM_SPRING: SpringConfig = {
  damping: 0.8,
  response: 0.4,
}

/**
 * Apple 标准动量投影函数
 * @param initialVelocity 初始速度（px/s）
 * @param decelerationRate 减速率，0.998 = 正常滚动感
 * @returns 投影的位移（px）
 */
export function projectMomentum(
  initialVelocity: number,
  decelerationRate: number = 0.998
): number {
  return (initialVelocity / 1000) * decelerationRate / (1 - decelerationRate)
}

/**
 * 橡皮筋边界函数
 * 越接近边界，跟随越少——真实物体在停止前会减速
 * @param overshoot 超出边界的距离
 * @param dimension 容器尺寸
 * @param constant 常数，0.55 = Apple 标准
 * @returns 橡皮筋后的实际位移
 */
export function rubberband(
  overshoot: number,
  dimension: number,
  constant: number = 0.55
): number {
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot))
}

/**
 * 速度追踪器
 * 记录最近的位置+时间戳，用于计算释放速度
 */
export class VelocityTracker {
  private history: { x: number; y: number; t: number }[] = []
  private maxHistory = 5

  /** 记录一个位置点 */
  track(x: number, y: number) {
    const now = performance.now()
    this.history.push({ x, y, t: now })
    if (this.history.length > this.maxHistory) {
      this.history.shift()
    }
  }

  /** 计算当前速度（px/s） */
  getVelocity(): { vx: number; vy: number } {
    if (this.history.length < 2) {
      return { vx: 0, vy: 0 }
    }
    const first = this.history[0]
    const last = this.history[this.history.length - 1]
    const dt = (last.t - first.t) / 1000 // 转换为秒
    if (dt === 0) return { vx: 0, vy: 0 }
    return {
      vx: (last.x - first.x) / dt,
      vy: (last.y - first.y) / dt,
    }
  }

  /** 清空历史 */
  reset() {
    this.history = []
  }
}

/**
 * 简易弹簧动画（使用 requestAnimationFrame）
 * 支持：可中断、速度传递、从当前值开始
 */
export function useSpring(initialValue: number = 0) {
  const value = ref(initialValue)
  let animationId: number | null = null
  let currentValue = initialValue
  let targetValue = initialValue
  let currentVelocity = 0
  let config: SpringConfig = { ...DEFAULT_SPRING }

  /** 弹簧物理步进（使用半隐式欧拉积分） */
  function step() {
    if (animationId === null) return

    // Apple 弹簧参数转换为物理参数
    const stiffness = Math.pow(2 * Math.PI / config.response, 2)
    const damping = 4 * Math.PI * config.damping / config.response

    // 半隐式欧拉积分
    const dt = 1 / 60 // 假设 60fps
    const force = -stiffness * (currentValue - targetValue) - damping * currentVelocity
    currentVelocity += force * dt
    currentValue += currentVelocity * dt

    // 检查是否已经接近目标（速度和位移都很小）
    const displacement = Math.abs(currentValue - targetValue)
    if (displacement < 0.01 && Math.abs(currentVelocity) < 0.01) {
      currentValue = targetValue
      currentVelocity = 0
      value.value = currentValue
      animationId = null
      return
    }

    value.value = currentValue
    animationId = requestAnimationFrame(step)
  }

  /**
   * 设置新目标（可中断，从当前值和当前速度开始）
   * @param target 目标值
   * @param velocity 初始速度（px/s），用于速度传递
   * @param springConfig 弹簧配置
   */
  function to(
    target: number,
    velocity: number = 0,
    springConfig?: SpringConfig
  ) {
    if (springConfig) {
      config = { ...springConfig }
    }
    targetValue = target
    currentVelocity = velocity
    if (animationId === null) {
      animationId = requestAnimationFrame(step)
    }
  }

  /** 立即设置值（无动画） */
  function set(val: number) {
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
    currentValue = val
    targetValue = val
    currentVelocity = 0
    value.value = val
  }

  /** 停止动画 */
  function stop() {
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  /** 获取当前速度 */
  function getVelocity() {
    return currentVelocity
  }

  /** 获取当前值 */
  function getValue() {
    return currentValue
  }

  onUnmounted(() => {
    stop()
  })

  return {
    value,
    to,
    set,
    stop,
    getVelocity,
    getValue,
  }
}

/**
 * 吸附到最近的吸附点
 * @param value 当前值
 * @param snapPoints 吸附点数组
 * @returns 最近的吸附点
 */
export function nearestSnapPoint(value: number, snapPoints: number[]): number {
  let nearest = snapPoints[0]
  let minDist = Math.abs(value - nearest)
  for (const point of snapPoints) {
    const dist = Math.abs(value - point)
    if (dist < minDist) {
      minDist = dist
      nearest = point
    }
  }
  return nearest
}

/**
 * 归一化速度（用于弹簧 API 需要相对速度的情况）
 * @param gestureVelocity 手势速度（px/s）
 * @param targetValue 目标值
 * @param currentValue 当前值
 * @returns 归一化速度
 */
export function normalizeVelocity(
  gestureVelocity: number,
  targetValue: number,
  currentValue: number
): number {
  const distance = targetValue - currentValue
  if (distance === 0) return 0
  return gestureVelocity / distance
}
