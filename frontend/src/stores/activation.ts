import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post } from '@/api/http'

export interface ActivationStatus {
  activated: boolean
  reason: string
  machine_code: string
}

/**
 * 激活状态 store:全局唯一,路由守卫据此拦截未激活访问。
 *
 * 后端契约(与旧版 Flask 一致):
 * - GET /activation/status   → { code:0, data:{activated, reason, machine_code} }
 * - GET /activation/fingerprint → { code:0, data:{machine_code, fingerprint_export, cpu, disk} }
 * - POST /activation/verify  body={file_content} → { code:0|1, msg, data:{activated,...} }
 */
export const useActivationStore = defineStore('activation', () => {
  const activated = ref(false)
  const reason = ref('')
  const machineCode = ref('')
  const checked = ref(false)

  async function checkStatus(): Promise<ActivationStatus> {
    try {
      const res = await get<{ code: number; data: ActivationStatus }>('/activation/status')
      if (res.code === 0 && res.data) {
        activated.value = res.data.activated
        reason.value = res.data.reason
        machineCode.value = res.data.machine_code
      } else {
        activated.value = false
      }
    } catch {
      // 接口异常时视为未激活,由激活页重试
      activated.value = false
    }
    checked.value = true
    return { activated: activated.value, reason: reason.value, machine_code: machineCode.value }
  }

  async function getFingerprint() {
    const res = await get<{
      code: number
      data: { machine_code: string; fingerprint_export: string; cpu: string; disk: string }
    }>('/activation/fingerprint')
    return {
      fingerprint: res.data?.fingerprint_export || '',
      machine_code: res.data?.machine_code || '',
    }
  }

  async function verifyKey(key: string): Promise<{ success: boolean; message: string }> {
    const res = await post<{ code: number; msg: string; data?: ActivationStatus }>(
      '/activation/verify',
      { file_content: key },
    )
    return {
      success: res.code === 0 && !!res.data?.activated,
      message: res.msg || res.data?.reason || '校验失败',
    }
  }

  return { activated, reason, machineCode, checked, checkStatus, getFingerprint, verifyKey }
})
