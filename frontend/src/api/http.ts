import axios from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 全局 axios 实例:统一 baseURL、超时、错误处理。
 * 开发模式经 vite proxy 转发到 FastAPI,生产模式同源。
 */
const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    // 激活拦截(403 + 特定标识)由路由守卫处理,这里只负责通用错误提示
    const status = error.response?.status
    const data = error.response?.data
    // 后端业务错误有两种形态: {code:1, msg} 或 FastAPI 默认 {detail}
    const msg = data?.msg ?? data?.detail
    if (msg) {
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } else if (status === 500) {
      ElMessage.error('服务器内部错误,请重试')
    } else if (!status) {
      ElMessage.error('无法连接服务器,请检查程序是否已启动')
    }
    return Promise.reject(error)
  },
)

/** GET 请求辅助:直接返回 data 字段 */
export function get<T = any>(url: string, params?: Record<string, any>): Promise<T> {
  return http.get(url, { params }).then((r) => r.data)
}

/** POST 请求辅助 */
export function post<T = any>(url: string, data?: any): Promise<T> {
  return http.post(url, data).then((r) => r.data)
}

/** PUT 请求辅助 */
export function put<T = any>(url: string, data?: any): Promise<T> {
  return http.put(url, data).then((r) => r.data)
}

/** DELETE 请求辅助 */
export function del<T = any>(url: string): Promise<T> {
  return http.delete(url).then((r) => r.data)
}

export default http
