/**
 * 纯文字名单解析(7 种模式,每行 = 一名学生):
 *   001 张三 / 张三 001(数字+空格)
 *   001-张三 / 张三-001
 *   张三(001)
 *   Tab 分隔(Excel 粘贴)
 *   逗号/顿号多记录
 *   纯姓名
 * 自动清洗「学号:/姓名:/编号:/No.」前缀;跳过表头行;按姓名去重。
 */
export interface ParsedRecord {
  name: string
  code: string
}

const HEADER_NAMES = new Set(['姓名', '名字', '学生姓名', '学生', 'name', '序号', '编号'])

function cleanName(raw: string): string {
  let s = raw.trim()
  // 清洗前缀
  s = s.replace(/^(学号|姓名|名字|编号|No\.|NO\.|no\.)\s*[:：]\s*/i, '')
  return s.trim()
}

function parseLine(line: string, out: ParsedRecord[]) {
  const t = line.trim()
  if (!t) return
  // Tab 分隔(Excel 粘贴):学号\t姓名 或 姓名\t学号
  if (t.includes('\t')) {
    const parts = t.split('\t').map((p) => p.trim()).filter(Boolean)
    if (parts.length >= 2) {
      const numIdx = parts.findIndex((p) => /^\d+$/.test(p))
      const nameIdx = numIdx === 0 ? 1 : 0
      out.push({ name: cleanName(parts[nameIdx]), code: numIdx >= 0 ? parts[numIdx] : '' })
      return
    }
  }
  // 逗号/顿号多记录
  if (/[,，、]/.test(t)) {
    const parts = t.split(/[,，、]+/).map((p) => p.trim()).filter(Boolean)
    if (parts.length >= 2) {
      for (const p of parts) parseLine(p, out)
      return
    }
  }
  // 001-张三 / 张三-001
  let m = t.match(/^(\d+)\s*[-–]\s*(.+)$/)
  if (m) {
    out.push({ name: cleanName(m[2]), code: m[1] })
    return
  }
  m = t.match(/^(.+?)\s*[-–]\s*(\d+)$/)
  if (m) {
    out.push({ name: cleanName(m[1]), code: m[2] })
    return
  }
  // 张三(001)
  m = t.match(/^(.+?)\s*[(（]\s*(\d+)\s*[)）]\s*$/)
  if (m) {
    out.push({ name: cleanName(m[1]), code: m[2] })
    return
  }
  // 001 张三 / 张三 001(数字+空格)
  m = t.match(/^(\d+)\s+(.+)$/)
  if (m) {
    out.push({ name: cleanName(m[2]), code: m[1] })
    return
  }
  m = t.match(/^(.+?)\s+(\d+)$/)
  if (m && !/^\d/.test(t)) {
    out.push({ name: cleanName(m[1]), code: m[2] })
    return
  }
  // 纯姓名
  out.push({ name: cleanName(t), code: '' })
}

export function parseTextNames(text: string): ParsedRecord[] {
  const out: ParsedRecord[] = []
  for (const line of text.split(/\r?\n/)) {
    parseLine(line, out)
  }
  // 按姓名去重 + 过滤表头/空名
  const seen = new Set<string>()
  const result: ParsedRecord[] = []
  for (const r of out) {
    if (!r.name || HEADER_NAMES.has(r.name)) continue
    if (seen.has(r.name)) continue
    seen.add(r.name)
    result.push(r)
  }
  return result
}
