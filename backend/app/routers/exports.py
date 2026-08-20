# -*- coding: utf-8 -*-
"""
报表导出 API
============
考试成绩 Excel、分组名单 Excel、学生台账 Excel、全班作业汇总 Excel、
学生个人作业报表(JSON)
"""

import sqlite3
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.config import ensure_data_dir
from app.deps import get_class_id, get_db, get_body
from app.utils import grade_label

router = APIRouter(prefix="/api", tags=["exports"])

TEMP_DIR = ensure_data_dir() / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/export/exam-scores")
def api_export_exam_scores(exam_name: str = "", date: str = "",
                           cid: int = Depends(get_class_id),
                           db: sqlite3.Connection = Depends(get_db)):
    """导出考试成绩为 Excel"""

    if not exam_name or not date:
        return JSONResponse({"code": 1, "msg": "请指定考试名称和日期"}, status_code=400)
    rows = db.execute("""
        SELECT s.name as student_name, s.student_code, e.score, e.total_score, e.grade,
               g.name as group_name
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
        ORDER BY g.name, s.sort_order
    """, (exam_name, date, cid)).fetchall()
    export_df = pd.DataFrame([{
        "学生姓名": r["student_name"], "学号": r["student_code"] or "",
        "所属分组": r["group_name"] or "未分组",
        "分数": r["score"], "满分": r["total_score"], "等第": r["grade"],
    } for r in rows])
    if export_df.empty:
        export_df = pd.DataFrame([{"学生姓名": "暂无数据"}])
    cls_name = db.execute(
    "SELECT name FROM classes WHERE id=?", (cid,)).fetchone()["name"]
    safe_exam = exam_name.replace("/", "_").replace("\\", "_")
    file_path = TEMP_DIR / \
        f"考试成绩_{cls_name}_{safe_exam}_{
    datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="考试成绩", index=False)
        ws = writer.sheets["考试成绩"]
        for col, w in zip(["A", "B", "C", "D", "E", "F"],
                          [18, 14, 14, 10, 10, 8]):
                            ws.column_dimensions[col].width = w
    return FileResponse(
        str(file_path),
        filename=f"考试成绩_{cls_name}_{safe_exam}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/export/groups")
def api_export_groups(cid: int = Depends(get_class_id),
                      db: sqlite3.Connection = Depends(get_db)):
    """导出分组名单 Excel"""

    groups = db.execute(
        "SELECT id, name FROM groups_info WHERE class_id=? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    rows = []
    for g in groups:
        students = db.execute(
            "SELECT name FROM students WHERE group_id=? AND class_id=? ORDER BY sort_order, id",
            (g["id"], cid)
        ).fetchall()
        for s in students:
            rows.append({"学生姓名": s["name"], "所属分组": g["name"]})
    # 未分组学生
    unassigned = db.execute(
        "SELECT name FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    for s in unassigned:
        rows.append({"学生姓名": s["name"], "所属分组": "未分组"})

    export_df = pd.DataFrame(rows) if rows else pd.DataFrame(
        [{"学生姓名": "暂无学生", "所属分组": ""}])
    cls_name = db.execute(
    "SELECT name FROM classes WHERE id=?", (cid,)).fetchone()["name"]
    file_path = TEMP_DIR / \
        f"分组名单_{cls_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="分组名单", index=False)
        ws = writer.sheets["分组名单"]
        for col, w in zip(["A", "B"], [18, 18]):
            ws.column_dimensions[col].width = w
    return FileResponse(
        str(file_path),
        filename=f"分组名单_{cls_name}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/student/{sid}/report")
def api_student_report(sid: int, db: sqlite3.Connection = Depends(get_db)):
    """获取学生个人作业报表（所有日期的等级记录）"""

    student = db.execute(
    "SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)
    rows = db.execute("""
        SELECT h.date, h.grade FROM homework h
        WHERE h.student_id = ? ORDER BY h.date DESC
    """, (sid,)).fetchall()
    records = [{"date": r["date"], "grade": r["grade"],
        "grade_label": grade_label(r["grade"])} for r in rows]
    stats = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for r in rows:
        stats[r["grade"]] = stats.get(r["grade"], 0) + 1
    return {"code": 0, "data": {
        "student_id": student["id"], "student_name": student["name"],
        "records": records, "stats": stats,
        "total": len(records),
    }}


@router.get("/export/student/{sid}")
def api_export_student(sid: int, start: str = "", end: str = "",
                       db: sqlite3.Connection = Depends(get_db)):
    """导出学生作业台账 Excel"""

    student = db.execute(
    "SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)
    if start and end:
        rows = db.execute("""
            SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ? AND h.date >= ? AND h.date <= ?
            ORDER BY h.date
        """, (sid, start, end)).fetchall()
    else:
        rows = db.execute("""

        SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ? ORDER BY h.date
        """, (sid,)).fetchall()

    export_df = pd.DataFrame([{
        "学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
        "登记日期": r["date"], "作业评级": grade_label(r["grade"]),
    } for r in rows])
    if export_df.empty:
        export_df = pd.DataFrame(
            [{"学生姓名": student["name"], "所属分组": "", "登记日期": "", "作业评级": "暂无记录"}])
    if rows:
        stats = {}
        for r in rows:
            stats[r["grade"]] = stats.get(r["grade"], 0) + 1
        summary = pd.DataFrame([
            {"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""},
            {"学生姓名": "统计汇总", "所属分组": "", "登记日期": "",
             "作业评级": f"A:{stats.get('A', 0)}次 B:{stats.get('B', 0)}次 C:{stats.get('C', 0)}次 请假:{stats.get('L', 0)}次 未交:{stats.get('X', 0)}次"},
        ])
        export_df = pd.concat([export_df, summary], ignore_index=True)

    file_path = TEMP_DIR / \
        f"学生台账_{
    student['name']}_{
        datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="作业台账", index=False)
        ws = writer.sheets["作业台账"]
        for col, w in zip(["A", "B", "C", "D"], [18, 14, 14, 25]):
            ws.column_dimensions[col].width = w
    return FileResponse(
        str(file_path),
        filename=f"学生台账_{student['name']}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/export/class")
def api_export_class(start: str = "", end: str = "",
                     cid: int = Depends(get_class_id),
                     db: sqlite3.Connection = Depends(get_db)):
    """导出全班作业汇总 Excel"""

    base_sql = """
        SELECT h.date, h.grade, s.name as student_name, g.name as group_name
        FROM homework h JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE s.class_id = ?
    """
    if start and end:
        rows = db.execute(base_sql + " AND h.date >= ? AND h.date <= ? ORDER BY s.group_id, s.sort_order, h.date",
                          (cid, start, end)).fetchall()
    else:
        rows = db.execute(base_sql + " ORDER BY s.group_id, s.sort_order, h.date",
                          (cid,)).fetchall()

    export_data = [{"学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
                    "登记日期": r["date"], "作业评级": grade_label(r["grade"])} for r in rows]
    export_df = pd.DataFrame(export_data)
    if export_df.empty:
        export_df = pd.DataFrame([{"学生姓名": "暂无记录", "所属分组": "", "登记日期": "", "作业评级": ""}])
    if rows:
        student_stats = {}
        for r in rows:
            n = r["student_name"]
            if n not in student_stats:
                student_stats[n] = {"group": r["group_name"] or "未分组", "A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
            student_stats[n][r["grade"]] += 1
        summary_data = [
            {"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""},
            {"学生姓名": "=== 全班统计汇总 ===", "所属分组": "", "登记日期": "",
             "作业评级": f"共 {len(student_stats)} 名学生"},
        ]
        for name, stats in student_stats.items():
            total = stats["A"] + stats["B"] + stats["C"] + stats["L"] + stats["X"]
            summary_data.append({
                "学生姓名": name, "所属分组": stats["group"],
                "登记日期": f"共{total}次",
                "作业评级": f"A:{stats['A']} B:{stats['B']} C:{stats['C']} 请假:{stats['L']} 未交:{stats['X']}",
            })
        export_df = pd.concat([export_df, pd.DataFrame(summary_data)], ignore_index=True)

    file_path = TEMP_DIR / f"全班台账_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="全班作业汇总", index=False)
        ws = writer.sheets["全班作业汇总"]
        for col, w in zip(["A", "B", "C", "D"], [18, 14, 14, 35]):
            ws.column_dimensions[col].width = w
    return FileResponse(
        str(file_path),
        filename=f"全班作业汇总_{start}_{end}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
