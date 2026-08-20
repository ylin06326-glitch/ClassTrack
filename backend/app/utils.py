# -*- coding: utf-8 -*-
"""
通用辅助函数
============
- 学生名单 Excel/文本解析
- 作业等级文案映射
- 分组颜色
- 考试 Excel 智能解析(_parse_exam_excel)
- AI Key 混淆编码
"""

import base64
import re
from pathlib import Path

import pandas as pd

from app.database import GROUP_COLORS


def get_group_color(group_index: int) -> str:
    return GROUP_COLORS[group_index % len(GROUP_COLORS)]


def grade_label(grade: str) -> str:
    return {"A": "A", "B": "B", "C": "C", "L": "请假", "X": "未交"}.get(grade, "未交")


def parse_excel_students(file_path: str) -> list:
    """解析Excel文件中的学生名单,返回 [{name, code}]"""
    file_ext = Path(file_path).suffix.lower()
    try:
        if file_ext == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
        elif file_ext == ".xls":
            df = pd.read_excel(file_path, engine="xlrd", dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)
    except Exception:
        df = pd.read_excel(file_path, dtype=str, engine=None)
    if df.empty:
        return []

    # 查找姓名列
    name_col = None
    for col in df.columns:
        if any(kw in str(col).lower().strip() for kw in
               ["姓名", "名字", "学生", "name", "学生姓名"]):
            name_col = col
            break
    if name_col is None:
        name_col = df.columns[0]

    # 查找学号列
    code_col = None
    for col in df.columns:
        if any(kw in str(col).lower().strip() for kw in
               ["学号", "编号", "id", "code", "工号"]):
            code_col = col
            break
    # 如果没找到命名列,检查第一列是否全是数字(自动识别为学号)
    if code_col is None and len(df.columns) >= 2:
        first_col = df.columns[0]
        try:
            numeric_count = 0
            total = 0
            for v in df[first_col]:
                vs = str(v).strip() if pd.notna(v) else ""
                if vs and vs not in ("nan", "None", ""):
                    total += 1
                    if vs.isdigit():
                        numeric_count += 1
            # 如果超过80%是纯数字,认为是学号列
            if total > 0 and numeric_count / total >= 0.8:
                code_col = first_col
        except Exception:
            pass

    results = []
    seen_names = set()
    for _, row in df.iterrows():
        vs = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        if not vs or vs in ("nan", "None", ""):
            continue
        if vs in ("姓名", "名字", "学生姓名", "学生", "name", "序号", "编号"):
            continue
        if vs in seen_names:
            continue
        seen_names.add(vs)
        code = ""
        if code_col and pd.notna(row[code_col]):
            code = str(row[code_col]).strip()
            if code in ("nan", "None"):
                code = ""
        results.append({"name": vs, "code": code})
    return results


def parse_text_names(text: str) -> list:
    """解析纯文字学生名单(仅用作后端兜底——前端已解析,正常不应走此路径)
    按换行/逗号/顿号分割,但不用空格分割(避免把"001 张三"拆成两个人)"""
    # 只按换行、逗号、顿号、中文逗号分割,不按空格分割
    parts = re.split(r'[\n\r,，、]+', text.strip())
    names = []
    for p in parts:
        p = p.strip()
        if p and p not in names:
            names.append(p)
    return names


EXAM_GRADE_MAP = [
    (90, "A"),   # >= 90 → A
    (75, "B"),   # >= 75 → B
    (60, "C"),   # >= 60 → C
    (0, "X"),    # < 60  → X (未达标)
]


def _parse_exam_excel(file_path: str) -> dict:
    """
    智能解析考试 Excel,自动识别列结构。
    支持易卷通等常见阅卷平台的导出格式。
    返回: {classes: [{name, students: [{name, code, score, grade}]}], raw_rows, detected_columns}
    """
    file_ext = Path(file_path).suffix.lower()
    try:
        if file_ext == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
        elif file_ext == ".xls":
            df = pd.read_excel(file_path, engine="xlrd", dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)
    except Exception:
        df = pd.read_excel(file_path, dtype=str, engine=None)

    if df.empty:
        return {"error": "Excel 文件为空", "classes": [], "detected_columns": []}

    # 清理列名
    df.columns = [str(c).strip() for c in df.columns]

    # ---- 智能检测列 ----
    col_map = {"name": None, "code": None, "class_name": None, "score": None, "grade_letter": None}

    for col in df.columns:
        cl = col.lower().replace(" ", "")
        # 姓名列
        if not col_map["name"] and any(kw in cl for kw in ["姓名", "名字", "学生姓名", "学生", "name"]):
            col_map["name"] = col
        # 学号/考号列
        if not col_map["code"] and any(kw in cl for kw in ["学号", "考号", "编号", "id", "code", "准考证"]):
            col_map["code"] = col
        # 班级列
        if not col_map["class_name"] and any(kw in cl for kw in ["班级", "班", "class", "行政班", "教学班"]):
            col_map["class_name"] = col
        # 分数列
        if not col_map["score"] and any(kw in cl for kw in ["成绩", "分数", "得分", "总分", "score", "总成绩", "卷面"]):
            col_map["score"] = col
        # 等第列(可能已有 A/B/C/D 等)
        if not col_map["grade_letter"] and any(kw in cl for kw in ["等第", "等级", "grade", "评级", "档次"]):
            col_map["grade_letter"] = col

    # 兜底:如果没识别到姓名列,用第一列
    if not col_map["name"] and len(df.columns) > 0:
        col_map["name"] = df.columns[0]
    # 兜底:如果没识别到分数列,尝试找纯数字列
    if not col_map["score"]:
        for col in df.columns:
            if col == col_map["name"]:
                continue
            try:
                numeric_count = sum(1 for v in df[col] if str(v).strip().replace(".", "").replace("-", "").isdigit())
                if numeric_count > len(df) * 0.5:
                    col_map["score"] = col
                    break
            except Exception:
                pass

    # ---- 解析数据 ----
    students = []
    for _, row in df.iterrows():
        name = str(row[col_map["name"]]).strip() if col_map["name"] and pd.notna(row[col_map["name"]]) else ""
        if not name or name in ("nan", "None", "", "姓名", "学生姓名", "名字"):
            continue

        code = ""
        if col_map["code"] and pd.notna(row[col_map["code"]]):
            code = str(row[col_map["code"]]).strip()
            if code in ("nan", "None"):
                code = ""

        class_name = ""
        if col_map["class_name"] and pd.notna(row[col_map["class_name"]]):
            class_name = str(row[col_map["class_name"]]).strip()
            if class_name in ("nan", "None"):
                class_name = ""
            # 统一班级格式:去掉"班"字,如 "高一1班" → "高一1"
            class_name = class_name.replace(" ", "")

        # 解析分数
        score = None
        if col_map["score"] and pd.notna(row[col_map["score"]]):
            try:
                score_str = str(row[col_map["score"]]).strip()
                score = float(score_str)
            except (ValueError, TypeError):
                score = None

        # 解析等第
        letter = ""
        if col_map["grade_letter"] and pd.notna(row[col_map["grade_letter"]]):
            letter = str(row[col_map["grade_letter"]]).strip().upper()
            if letter in ("nan", "NONE"):
                letter = ""

        # 根据分数映射等第
        if not letter and score is not None:
            for threshold, g in EXAM_GRADE_MAP:
                if score >= threshold:
                    letter = g
                    break

        students.append({
            "name": name,
            "code": code,
            "class_name": class_name,
            "score": score,
            "score_display": str(int(score)) if score is not None and score == int(score) else (
                str(score) if score is not None else ""),
            "grade": letter,
        })

    if not students:
        return {"error": "未能从 Excel 中识别出有效学生数据", "classes": [], "detected_columns": list(df.columns)}

    # ---- 按班级分组 ----
    class_groups = {}
    for s in students:
        cn = s["class_name"] or "未识别班级"
        if cn not in class_groups:
            class_groups[cn] = []
        class_groups[cn].append(s)

    classes_result = []
    for cn, sts in class_groups.items():
        # 统计
        stats = {"A": 0, "B": 0, "C": 0, "X": 0, "total": len(sts)}
        scores_list = []
        for s in sts:
            if s["grade"] in stats:
                stats[s["grade"]] += 1
            if s["score"] is not None:
                scores_list.append(s["score"])
        avg_score = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
        max_score = max(scores_list) if scores_list else 0
        min_score = min(scores_list) if scores_list else 0

        classes_result.append({
            "class_name": cn,
            "student_count": len(sts),
            "stats": stats,
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "students": sts,
        })

    # 按总人数排序(最多的班级排前面)
    classes_result.sort(key=lambda c: c["student_count"], reverse=True)

    return {
        "classes": classes_result,
        "total_students": len(students),
        "detected_columns": list(df.columns),
        "column_mapping": {k: v for k, v in col_map.items() if v},
    }


def calc_exam_grade(score: float, total: float) -> str:
    """服务端等第计算(成绩入库路径):≥90 A、≥75 B、≥60 C、否则 D"""
    if total <= 0:
        return ""
    pct = score / total * 100
    if pct >= 90:
        return "A"
    elif pct >= 75:
        return "B"
    elif pct >= 60:
        return "C"
    return "D"


# ============================================================
# AI Key 混淆(仅 Base64 混淆,非加密)
# ============================================================
def ai_key_encode(raw: str) -> str:
    """标准 Base64 编码(仅混淆,防明文字符串搜索)"""
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def ai_key_decode(encoded: str) -> str:
    """Base64 解码;失败时原样返回(兼容旧明文数据)"""
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return encoded
