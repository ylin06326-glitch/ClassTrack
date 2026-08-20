/**
 * 作业等级体系(前后端约定):
 * A 优秀(绿) / B 中等(蓝) / C 待改进(黄) / L 请假(紫) / X 未交(粉)
 * 无记录默认视为 X(未交)
 */
export const VALID_GRADES = ['A', 'B', 'C', 'L', 'X'] as const
export type Grade = (typeof VALID_GRADES)[number]

export const GRADE_META: Record<Grade, { label: string; color: string; textColor: string }> = {
  A: { label: 'A', color: '#A8D5BA', textColor: '#2D6A3F' },
  B: { label: 'B', color: '#7EB5D6', textColor: '#2D5A7A' },
  C: { label: 'C', color: '#F4C97E', textColor: '#7A6510' },
  L: { label: '请假', color: '#C5B3E6', textColor: '#5B4A8A' },
  X: { label: '未交', color: '#E8A0BF', textColor: '#8A4A5A' },
}

/** 徽章显示文案:显示"未交/请假",其余原样 */
export function gradeDisplayLabel(grade: string): string {
  return GRADE_META[grade as Grade]?.label ?? '未交'
}

/** 服务端 grade_label 等价(报表用):A/B/C 原样,L→请假,X→未交 */
export function gradeLabel(grade: string): string {
  return ({ A: 'A', B: 'B', C: 'C', L: '请假', X: '未交' } as Record<string, string>)[grade] ?? '未交'
}

/** 分组循环色(与后端 GROUP_COLORS 一致) */
export const GROUP_COLORS = [
  '#7EB5D6', '#E8A0BF', '#A8D5BA', '#F4C97E',
  '#C4B5D6', '#F0B8A0', '#8EC8C0', '#D4A8C8',
  '#9DC8E0', '#F2C8DA', '#B8D8C8', '#F8DCA0',
]

export function groupColor(index: number): string {
  return GROUP_COLORS[index % GROUP_COLORS.length]
}

/** 动物头像 emoji(20 种,按姓名 hash 选取,与旧版一致) */
const ANIMALS = ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🐔', '🐧', '🐦', '🦉', '🦄']

export function animalAvatar(name: string): string {
  let hash = 0
  for (const ch of name) {
    hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  }
  return ANIMALS[hash % ANIMALS.length]
}

/** 提交 = A/B/C/L;未交 = X 或无记录 */
export function isSubmitted(grade: string): boolean {
  return grade === 'A' || grade === 'B' || grade === 'C' || grade === 'L'
}

/** 均分映射(智能分组/统计用):A=3 B=2 C=1 X=0,L 不计入 */
export const GRADE_SCORE: Record<string, number> = { A: 3, B: 2, C: 1, X: 0 }
