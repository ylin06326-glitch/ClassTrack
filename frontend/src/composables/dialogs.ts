/**
 * 全局弹窗服务(MainLayout 提供,各 Tab 注入使用):
 *  - confirm: 确认操作弹窗(旧版「⚠️ 确认操作」Modal)
 *  - showDetail: 详情列表弹窗(已交/未交/全班名单等)
 *  - showStudentReport: 学生个人作业报表弹窗
 */
import { inject, type InjectionKey } from 'vue'

export interface DetailItem {
  label: string
  sub?: string
  /** 等级(A/B/C/L/X),存在则显示等级徽章 */
  grade?: string
  gradeLabel?: string
  /** 学生ID,存在则条目可点击打开学生个人报表 */
  sid?: number
}

export interface DialogApi {
  /** 确认操作,返回用户是否点击「确认」 */
  confirm: (msg: string, title?: string) => Promise<boolean>
  /** 打开详情列表弹窗 */
  showDetail: (title: string, summary: string, items: DetailItem[]) => void
  /** 打开学生个人作业报表弹窗(内部调用 /student/{sid}/report) */
  showStudentReport: (sid: number, name: string) => void
}

export const DIALOG_KEY: InjectionKey<DialogApi> = Symbol('classtrack-dialogs')

/** 在 Tab 视图内获取全局弹窗能力(由 MainLayout 注入) */
export function useDialogs(): DialogApi {
  const api = inject(DIALOG_KEY)
  if (!api) throw new Error('useDialogs 必须在 MainLayout 内使用')
  return api
}
