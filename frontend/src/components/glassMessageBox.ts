import { createApp, h, type App } from 'vue'
import GlassMessageBox from './GlassMessageBox.vue'
import type { MessageBoxMode } from './GlassMessageBox.vue'

interface MessageBoxOptions {
  mode?: MessageBoxMode
  title?: string
  message?: string
  icon?: string
  inputValue?: string
  inputPlaceholder?: string
  confirmButtonText?: string
  cancelButtonText?: string
}

let currentApp: App | null = null
let container: HTMLElement | null = null

function cleanup() {
  if (currentApp) {
    currentApp.unmount()
    currentApp = null
  }
  if (container && container.parentNode) {
    container.parentNode.removeChild(container)
    container = null
  }
}

function show(options: MessageBoxOptions): Promise<string | boolean> {
  return new Promise((resolve, reject) => {
    // 清理之前的实例
    cleanup()

    // 创建容器
    container = document.createElement('div')
    document.body.appendChild(container)

    let visible = true

    const vnode = h(GlassMessageBox, {
      visible: visible,
      mode: options.mode || 'confirm',
      title: options.title || '提示',
      message: options.message || '',
      icon: options.icon || '',
      inputValue: options.inputValue || '',
      inputPlaceholder: options.inputPlaceholder || '请输入',
      confirmButtonText: options.confirmButtonText || '确定',
      cancelButtonText: options.cancelButtonText || '取消',
      'onUpdate:visible': (val: boolean) => {
        visible = val
      },
      onConfirm: (value?: string) => {
        cleanup()
        if (options.mode === 'prompt') {
          resolve(value || '')
        } else {
          resolve(true)
        }
      },
      onCancel: () => {
        cleanup()
        reject(new Error('cancel'))
      },
    })

    currentApp = createApp({
      render: () => vnode,
    })
    currentApp.mount(container)
  })
}

export const glassMessageBox = {
  confirm(message: string, title?: string, options?: Partial<MessageBoxOptions>): Promise<boolean> {
    return show({
      ...options,
      mode: 'confirm',
      message,
      title: title || '确认操作',
      icon: options?.icon || '⚠️',
    }) as Promise<boolean>
  },

  prompt(message: string, title?: string, options?: Partial<MessageBoxOptions>): Promise<string> {
    return show({
      ...options,
      mode: 'prompt',
      message,
      title: title || '请输入',
      icon: options?.icon || '📝',
    }) as Promise<string>
  },

  alert(message: string, title?: string, options?: Partial<MessageBoxOptions>): Promise<boolean> {
    return show({
      ...options,
      mode: 'alert',
      message,
      title: title || '提示',
      icon: options?.icon || 'ℹ️',
    }) as Promise<boolean>
  },
}

export default glassMessageBox
