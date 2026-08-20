# -*- coding: utf-8 -*-
"""
数据分析 API
============
考试概览、当日数据概览、提交率趋势、已交/未交名单、
小组排行榜、环比趋势对比、学生预警
"""

import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.deps import get_class_id, get_db, get_body
from app.utils import grade_label

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/exam-overview")
def api_analytics_exam_overview(exam_name: str = "", date: str = "",
                                cid: int = Depends(get_class_id),
                                db: sqlite3.Connection = Depends(get_db)):
    """考试成绩概览统计"""

    if not exam_name or not date:
        return JSONResponse({"code": 1, "msg": "请指定考试名称和日期"}, status_code=400)
    rows = db.execute("""
        SELECT e.score, e.grade, s.group_id, g.name as group_name, g.color as group_color
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
    """, (exam_name, date, cid)).fetchall()
    if not rows:
        return {"code": 0, "data": {"total": 0, "avg_score": 0, "max_score": 0,
                                    "min_score": 0, "group_stats": []}}

    scores = [r["score"] for r in rows]
    total = len(scores)
    avg_score = round(sum(scores) / total, 1)
    max_score = max(scores)
    min_score = min(scores)
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rows:
        g = r["grade"]
        if g in grade_counts:
            grade_counts[g] += 1

    # 分组统计
    group_map = {}
    for r in rows:
        gname = r["group_name"] or "未分组"
        if gname not in group_map:
            group_map[gname] = {
                "name": gname,
                "color": r["group_color"] or "",
                "scores": [],
                "count": 0}
        group_map[gname]["scores"].append(r["score"])
        group_map[gname]["count"] += 1
    group_stats = []
    for gn, gd in group_map.items():
        gs = gd["scores"]
        group_stats.append({
            "group_name": gn, "color": gd["color"], "count": gd["count"],
            "avg_score": round(sum(gs) / len(gs), 1),
            "max_score": max(gs), "min_score": min(gs),
        })
    group_stats.sort(key=lambda x: x["avg_score"], reverse=True)

    return {"code": 0, "data": {
        "exam_name": exam_name, "date": date, "total": total,
        "avg_score": avg_score, "max_score": max_score, "min_score": min_score,
        "grade_counts": grade_counts, "group_stats": group_stats,
    }}


@router.get("/analytics/overview")
def api_analytics_overview(date: str | None = None, homework_type_id: int = 0,
                           cid: int = Depends(get_class_id),
                           db: sqlite3.Connection = Depends(get_db)):
    """数据概览：当天统计 + 分组对比"""

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""

    # 当天各等级人数 — 子查询按学生去重取最优等级，避免多作业种类重复计数
    grades_params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    grades = db.execute(f"""
        SELECT best_grade, COUNT(*) as cnt FROM (
            SELECT MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                    WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END) as grade_rank,
                   CASE MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                         WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END)
                       WHEN 1 THEN 'A' WHEN 2 THEN 'B' WHEN 3 THEN 'C' WHEN 4 THEN 'L' ELSE 'X'
                   END as best_grade
            FROM homework h JOIN students s ON h.student_id = s.id
            WHERE h.date = ? AND s.class_id = ?{hw_filter}
            GROUP BY h.student_id
        ) GROUP BY best_grade
    """, grades_params).fetchall()
    grade_counts = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for g in grades:
        grade_counts[g["best_grade"]] = g["cnt"]

    # 总人数
    total = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE class_id=?",
        (cid,
         )).fetchone()["c"]
    # 未登记人数（当天没有homework记录的学生）
    recorded_params = (
        date, cid) if hw_type_id == 0 else (
        date, cid, hw_type_id)
    recorded = db.execute(f"""
        SELECT COUNT(DISTINCT h.student_id) as c
        FROM homework h JOIN students s ON h.student_id = s.id
        WHERE h.date = ? AND s.class_id = ?{hw_filter}
    """, recorded_params).fetchone()["c"]
    unrecorded = total - recorded

    # 分组对比
    groups = db.execute(
        "SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order",
        (cid,
         )).fetchall()
    group_comparison = []
    for g in groups:
        gstudents = db.execute(
            "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?",
            (g["id"],
             cid)).fetchone()["c"]
        ga_params = (
            date,
            g["id"],
            cid) if hw_type_id == 0 else (
            date,
            g["id"],
            cid,
            hw_type_id)
        g_a = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, ga_params).fetchone()["c"]
        # 已提交（A/B/C）人数，用于计算 missing
        g_submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade IN ('A','B','C','L') AND s.group_id=? AND s.class_id=?{hw_filter}
        """, (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)).fetchone()["c"]
        group_comparison.append({
            "group_id": g["id"], "group_name": g["name"], "color": g["color"],
            "total": gstudents, "a_count": g_a,
            "missing": gstudents - g_submitted,
            "a_rate": round(g_a / gstudents * 100, 1) if gstudents > 0 else 0,
        })

    return {
        "code": 0,
        "data": {
            "date": date, "total_students": total,
            "grade_counts": grade_counts, "unrecorded": unrecorded,
            "group_comparison": group_comparison,
        }
    }


@router.get("/analytics/trend")
def api_analytics_trend(days: int = 14, homework_type_id: int = 0,
                        cid: int = Depends(get_class_id),
                        db: sqlite3.Connection = Depends(get_db)):
    """近期趋势：最近N天作业提交率"""

    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    total = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE class_id=?",
        (cid,
         )).fetchone()["c"]
    trend = []
    for i in range(days - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        trend_params = (d, cid) if hw_type_id == 0 else (d, cid, hw_type_id)
        submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade!='X' AND s.class_id=?{hw_filter}
        """, trend_params).fetchone()["c"]
        rate = round(submitted / total * 100, 1) if total > 0 else 0
        trend.append({"date": d, "submitted": submitted,
                     "total": total, "rate": rate})
    return {"code": 0, "data": trend}


@router.get("/analytics/submitted")
def api_analytics_submitted(date: str | None = None, homework_type_id: int = 0,
                            grade: str = "",
                            cid: int = Depends(get_class_id),
                            db: sqlite3.Connection = Depends(get_db)):
    """获取今日已交学生名单"""

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    grade_filter = grade.strip().upper()
    grade_condition = ""
    hw_type_condition = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    params = [date, cid]
    if grade_filter in ("A", "B", "C"):
        grade_condition = " AND h.grade = ?"
        params.insert(1, grade_filter)
    if hw_type_id > 0:
        params.append(hw_type_id)
    rows = db.execute(f"""
        SELECT h.student_id, s.name as student_name, s.student_code, h.grade,
               g.name as group_name, g.color as group_color
        FROM homework h
        JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE h.date = ?{grade_condition} AND h.grade != 'X' AND s.class_id = ?{hw_type_condition}
        ORDER BY s.group_id, s.sort_order
    """, params).fetchall()
    return {"code": 0, "data": [{
        "student_id": r["student_id"], "student_name": r["student_name"],
        "student_code": r["student_code"] or "",
        "grade": r["grade"], "grade_label": grade_label(r["grade"]),
        "group_name": r["group_name"] or "未分组", "group_color": r["group_color"] or "",
    } for r in rows], "total": len(rows)}


@router.get("/analytics/missing")
def api_analytics_missing(date: str | None = None, homework_type_id: int = 0,
                          cid: int = Depends(get_class_id),
                          db: sqlite3.Connection = Depends(get_db)):
    """获取今日未交学生名单（含未登记）"""

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    all_students = db.execute(
        "SELECT s.id, s.name, s.student_code, s.group_id, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order", (cid,)).fetchall()
    submitted_ids = set()
    missing_params = (
        date, cid) if hw_type_id == 0 else (
        date, cid, hw_type_id)
    rows = db.execute(
        f"SELECT h.student_id FROM homework h "
        f"JOIN students s ON h.student_id = s.id "
        f"WHERE h.date = ? AND h.grade != 'X' AND s.class_id = ?{hw_filter}",
        missing_params
    ).fetchall()
    for r in rows:
        submitted_ids.add(r["student_id"])
    missing = [{"student_id": s["id"],
                "student_name": s["name"],
                "student_code": s["student_code"] or "",
                "group_name": s["group_name"] or "未分组",
                "group_color": s["group_color"] or "",
                } for s in all_students if s["id"] not in submitted_ids]
    return {"code": 0, "data": missing, "total": len(missing)}


# ---- 新增分析 API (v1.4) ----
@router.get("/analytics/group-ranking")
def api_analytics_group_ranking(
        date: str | None = None,
        homework_type_id: int = 0,
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """小组排行榜：按A率降序"""

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    groups = db.execute(
        "SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order",
        (cid,)
    ).fetchall()
    ranking = []
    for g in groups:
        gstudents = db.execute(
            "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?",
            (g["id"],
             cid)).fetchone()["c"]
        if gstudents == 0:
            continue
        ga_params = (
            date,
            g["id"],
            cid) if hw_type_id == 0 else (
            date,
            g["id"],
            cid,
            hw_type_id)
        a_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, ga_params).fetchone()[0]
        gb_params = (
            date,
            g["id"],
            cid) if hw_type_id == 0 else (
            date,
            g["id"],
            cid,
            hw_type_id)
        b_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='B' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, gb_params).fetchone()[0]
        gc_params = (
            date,
            g["id"],
            cid) if hw_type_id == 0 else (
            date,
            g["id"],
            cid,
            hw_type_id)
        c_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='C' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, gc_params).fetchone()[0]
        # 已提交人数：至少有1条 A/B/C 记录的学生（去重）
        submitted = db.execute(f"""

        SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade IN ('A','B','C','L') AND s.group_id=? AND s.class_id=?{hw_filter}
        """, (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)).fetchone()[0]
        total_x = gstudents - submitted
        submit_cnt = submitted
        ranking.append(
            {
                "group_id": g["id"],
                "group_name": g["name"],
                "color": g["color"],
                "total": gstudents,
                "a_count": a_cnt,
                "b_count": b_cnt,
                "c_count": c_cnt,
                "x_count": total_x,
                "submit_count": submit_cnt,
                "a_rate": round(
                    a_cnt / gstudents * 100,
                    1) if gstudents > 0 else 0,
                "submit_rate": round(
                    submit_cnt / gstudents * 100,
                    1) if gstudents > 0 else 0,
                "avg_score": round(
                    (a_cnt * 3 + b_cnt * 2 + c_cnt * 1) / gstudents,
                    1) if gstudents > 0 else 0,
            })
    ranking.sort(key=lambda x: x["a_rate"], reverse=True)
    return {"code": 0, "data": ranking, "date": date}


@router.get("/analytics/trend-compare")
def api_analytics_trend_compare(
        period: str = "week",
        homework_type_id: int = 0,
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """环比趋势对比：本周vs上周 或 本月vs上月"""

    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    total = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE class_id=?",
        (cid,
         )).fetchone()["c"]

    days = 7 if period == "week" else 30
    today = datetime.now().date()

    def build_trend(offset_days):
        result = []
        for i in range(days - 1, -1, -1):
            d = (today - timedelta(days=offset_days + i)).strftime("%Y-%m-%d")
            trend_params = (
                d, cid) if hw_type_id == 0 else (
                d, cid, hw_type_id)
            submitted = db.execute(f"""
                SELECT COUNT(DISTINCT h.student_id) FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade!='X' AND s.class_id=?{hw_filter}
            """, trend_params).fetchone()[0]
            rate = round(submitted / total * 100, 1) if total > 0 else 0
            result.append({"date": d[5:], "rate": rate})
        return result

    current = build_trend(0)
    previous = build_trend(days)
    current_avg = round(sum(d["rate"] for d in current) /
                        len(current), 1) if current else 0
    previous_avg = round(
        sum(d["rate"] for d in previous) / len(previous), 1) if previous else 0
    change = round(current_avg - previous_avg, 1)

    return {
        "code": 0,
        "data": {
            "current": current,
            "previous": previous,
            "current_avg": current_avg,
            "previous_avg": previous_avg,
            "change": change,
            "period": period,
            "total_students": total,
        }}


@router.get("/analytics/student-alerts")
def api_analytics_student_alerts(days: int = 14, homework_type_id: int = 0,
                                 cid: int = Depends(get_class_id),
                                 db: sqlite3.Connection = Depends(get_db)):
    """学生预警：连续未交 + 进步追踪"""

    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""

    students = db.execute(
        "SELECT s.id, s.name, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id=g.id WHERE s.class_id=? ORDER BY s.id",
        (cid,)
    ).fetchall()

    def grade_num(g):
        return {"A": 3, "B": 2, "C": 1}.get(g, 0)
    at_risk = []
    improving = []

    for s in students:
        # 参数顺序按原 Flask 实现原样保留
        alert_params = (
            s["id"], days) if hw_type_id == 0 else (
            s["id"], days, hw_type_id)
        rows = db.execute(f"""
            SELECT h.date, h.grade FROM homework h
            WHERE h.student_id=?{hw_filter} ORDER BY h.date DESC LIMIT ?
        """, alert_params).fetchall()
        if len(rows) < 3:
            continue
        grades = [r["grade"] for r in rows]  # most recent first

        # 连续未交检测
        consecutive_x = 0
        for g in grades:
            if g == "X":
                consecutive_x += 1
            else:
                break
        if consecutive_x >= 3:
            at_risk.append({
                "student_id": s["id"], "student_name": s["name"],
                "group_name": s["group_name"] or "未分组",
                "consecutive_x": consecutive_x,
                "last_grades": grades[:consecutive_x],
            })

        # 进步检测：近5次记录趋势上升
        if len(grades) >= 5:
            recent5 = grades[:5]
            # 将等级转为数值 (X/请假未参与进步判断)
            nums = [grade_num(g) for g in recent5 if g not in ("X", "L")]
            if len(nums) >= 3 and nums[0] > nums[-1] and nums[0] >= 2:
                improving.append({
                    "student_id": s["id"], "student_name": s["name"],
                    "group_name": s["group_name"] or "未分组",
                    "from_grade": recent5[-1], "to_grade": recent5[0],
                    "recent_grades": recent5,
                })

    improving.sort(
        key=lambda x: grade_num(
            x["to_grade"]) -
        grade_num(
            x["from_grade"]),
        reverse=True)

    return {"code": 0, "data": {
        "at_risk": at_risk, "improving": improving[:10]}}
