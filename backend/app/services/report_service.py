# -*- coding: utf-8 -*-
"""
AI 报告导出服务(纯函数,无 FastAPI 依赖)
========================================
从 Flask main.py api_ai_export_excel / api_ai_export_word 1:1 迁移:
- build_ai_excel: 三 Sheet Excel(作业概览/小组对比/趋势数据),pandas ExcelWriter(openpyxl)
- build_ai_word_doc: 手写 Word 兼容 HTML(xmlns:o/w 命名空间 + 内联样式 + 统计卡片 + 表格)
"""

from pathlib import Path

import pandas as pd


def build_ai_excel(export_data: dict, title: str, out_path: Path) -> None:
    """将当前 AI 对话的数据导出为 Excel

    title 参数与原 Flask 接口签名一致(原实现读取后未参与文件名,此处同样保留不用)。
    """
    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")
    grade_counts = export_data.get("grade_counts", {})
    group_data = export_data.get("group_data", [])
    trend = export_data.get("trend", [])

    with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
        # Sheet 1: 概览
        overview_data = {
            "班级": [class_name],
            "统计日期": [date_str],
            "A(优秀)": [grade_counts.get("A", 0)],
            "B(良好)": [grade_counts.get("B", 0)],
            "C(待改进)": [grade_counts.get("C", 0)],
            "未交": [grade_counts.get("X", 0)],
            "未登记": [grade_counts.get("未登记", 0)],
        }
        pd.DataFrame(overview_data).to_excel(writer, sheet_name="作业概览", index=False)

        # Sheet 2: 小组对比
        if group_data:
            gd = [{
                "小组": g["name"], "人数": g["total"],
                "A人数": g.get("a_count", 0), "A率(%)": g.get("a_rate", 0),
                "未交人数": g.get("missing", 0),
            } for g in group_data]
            pd.DataFrame(gd).to_excel(writer, sheet_name="小组对比", index=False)

        # Sheet 3: 趋势
        if trend:
            td = [{"日期": t["date"], "提交率(%)": t["rate"]} for t in trend]
            pd.DataFrame(td).to_excel(writer, sheet_name="趋势数据", index=False)

        # 调整列宽
        for ws in writer.sheets.values():
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)


def build_ai_word_doc(export_data: dict, reply: str, viz_html: str, out_path: Path) -> None:
    """将当前 AI 对话的数据导出为 Word(HTML格式,Word可直接打开)

    viz_html 参数与原 Flask 接口签名一致(原实现读取后未使用,此处同样保留不用)。
    """
    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")
    grade_counts = export_data.get("grade_counts", {})
    group_data = export_data.get("group_data", [])
    trend = export_data.get("trend", [])
    total = export_data.get("total_students", 0)

    # 构建 Word 兼容的 HTML 文档
    html_parts = ["""<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:w="urn:schemas-microsoft-com:office:word"
xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="UTF-8">
<style>
body { font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; color: #333; padding: 20px; }
h1 { color: #7EB5D6; border-bottom: 2px solid #7EB5D6; padding-bottom: 8px; }
h2 { color: #5D5A5A; margin-top: 20px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th { background: #7EB5D6; color: #fff; padding: 8px; text-align: left; }
td { padding: 6px 8px; border: 1px solid #ddd; }
.stat-box { display: inline-block; padding: 10px 16px; margin: 6px;
  border-radius: 8px; background: #f0f7fb; text-align: center; }
.stat-num { font-size: 24px; font-weight: bold; color: #7EB5D6; }
.stat-label { font-size: 12px; color: #888; }
</style></head><body>"""]

    html_parts.append(f"<h1>📊 ClassTrack AI 分析报告</h1>")
    html_parts.append(f"<p><strong>班级：</strong>{class_name} &nbsp; <strong>日期：</strong>{date_str} &nbsp; <strong>学生总数：</strong>{total}人</p>")

    # 统计卡片
    html_parts.append('<div style="margin:16px 0">')
    for label, key, color in [("A 优秀", "A", "#7EB5D6"), ("B 良好", "B", "#A8D5BA"),
                               ("C 待改进", "C", "#F4C97E"), ("未交", "X", "#E8A0BF")]:
        html_parts.append(f'<div class="stat-box"><div class="stat-num" style="color:{color}">{grade_counts.get(key, 0)}</div><div class="stat-label">{label}</div></div>')
    html_parts.append('</div>')

    # 小组对比表
    if group_data:
        html_parts.append("<h2>📋 小组对比</h2>")
        html_parts.append('<table><tr><th>小组</th><th>人数</th><th>A人数</th><th>A率</th><th>未交</th></tr>')
        for g in group_data:
            html_parts.append(f'<tr><td>{g["name"]}</td><td>{g["total"]}</td><td>{g.get("a_count", 0)}</td><td>{g.get("a_rate", 0)}%</td><td>{g.get("missing", 0)}</td></tr>')
        html_parts.append('</table>')

    # 趋势表
    if trend:
        html_parts.append("<h2>📈 趋势数据</h2>")
        html_parts.append('<table><tr><th>日期</th><th>提交率</th></tr>')
        for t in trend:
            html_parts.append(f'<tr><td>{t["date"]}</td><td>{t["rate"]}%</td></tr>')
        html_parts.append('</table>')

    # AI 分析
    if reply:
        html_parts.append(f"<h2>🤖 AI 分析</h2><p>{reply}</p>")

    html_parts.append("<p style='margin-top:30px;color:#aaa;font-size:11px'>由 ClassTrack AI 助手自动生成</p>")
    html_parts.append("</body></html>")

    full_html = "\n".join(html_parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_html)
