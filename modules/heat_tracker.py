# -*- coding: utf-8 -*-
"""
板块热度追踪模块
职责：
1. 无条件每日落盘历史板块数据（不再依赖飞书推送）
2. 计算板块热度分（0-100）
3. 输出趋势标签：🔥加速 / 📈升温 / ➡️平稳 / 📉退潮 / 🧊冰点
"""
import os
import json
def _avg(values: list) -> float:
    """安全计算平均值，空列表返回 0"""
    return sum(values) / len(values) if values else 0.0
import pandas as pd
from typing import Dict, List, Optional


def _history_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "history", "daily_summary.json")


def load_history() -> dict:
    path = _history_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_daily_summary(date_str: str, sectors: list) -> None:
    """无条件保存当日板块数据到 history"""
    path = _history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    history = load_history()
    history[date_str] = sectors
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def compute_heat_scores(
    summary_df: pd.DataFrame,
    sectors_dict: Dict[str, pd.DataFrame],
    date_str: str,
) -> pd.DataFrame:
    """
    计算各板块热度分（0-100），合并到 summary_df 并返回。

    热度分构成：
      - 涨停密度：30 分（涨停数占总股票比，归一化）
      - 上涨广度：20 分（上涨家数占比）
      - 强涨广度：20 分（涨幅>3%家数占比）
      - 量能放大：20 分（今日成交额 / 5日均额）
      - 前排强度：10 分（D1/D2 前排率）
    """
    if summary_df is None or summary_df.empty or "板块" not in summary_df.columns:
        return summary_df

    history = load_history()
    heat_rows = []

    for _, row in summary_df.iterrows():
        sector_name = str(row.get("板块", ""))
        if not sector_name or sector_name not in sectors_dict:
            heat_rows.append(_empty_heat_row(sector_name))
            continue

        df = sectors_dict[sector_name]
        total = max(len(df), 1)

        # --- 原始指标 ---
        limit_up_count = int(row.get("涨停数", 0))
        up_count = int((df.get("涨停率%", 0) > 0).sum())
        strong_up_count = int((df.get("涨停率%", 0) > 3).sum())
        amount_total = float(df.get("成交额", 0).sum() or 0)
        front_count = int(
            ((df.get("D1强势形态且新高", 0) > 0) | (df.get("D2强势形态", 0) > 0)).sum()
        )

        up_ratio = up_count / total
        strong_up_ratio = strong_up_count / total
        front_ratio = front_count / total

        # 成交额放大倍数：今日 / 5日均额
        past_entries = history.get(date_str, [])
        past_amounts = []
        if past_entries:
            sorted_dates = sorted(history.keys())
            idx = sorted_dates.index(date_str) if date_str in sorted_dates else -1
            for i in range(max(0, idx - 5), idx):
                day_data = history.get(sorted_dates[i], [])
                for s in day_data:
                    if s.get("板块") == sector_name and s.get("成交额总额", 0) > 0:
                        past_amounts.append(s["成交额总额"])
        avg_amount_5d = _avg(past_amounts) if past_amounts else amount_total
        amount_amplify = amount_total / max(avg_amount_5d, 1)

        # --- 热度分计算 ---
        # 涨停密度 (0-30)
        limit_density = limit_up_count / total
        limit_score = min(limit_density * 150, 30)

        # 上涨广度 (0-20)
        up_score = up_ratio * 20

        # 强涨广度 (0-20)
        strong_up_score = strong_up_ratio * 20

        # 量能放大 (0-20): 放大倍数 1x→0分, 2x→10分, 3x+→20分
        amount_score = min(max((amount_amplify - 1) * 10, 0), 20)

        # 前排强度 (0-10)
        front_score = front_ratio * 10

        heat_score = round(min(limit_score + up_score + strong_up_score + amount_score + front_score, 100), 1)

        # --- 趋势计算 ---
        trend = _compute_trend(sector_name, heat_score, history, date_str)

        heat_rows.append({
            "板块": sector_name,
            "热度分": heat_score,
            "趋势": trend,
            "涨停密度分": round(limit_score, 1),
            "上涨广度分": round(up_score, 1),
            "强涨广度分": round(strong_up_score, 1),
            "量能放大分": round(amount_score, 1),
            "前排强度分": round(front_score, 1),
            "上涨家数占比%": round(up_ratio * 100, 1),
            "涨幅>3%占比%": round(strong_up_ratio * 100, 1),
            "成交额放大倍数": round(amount_amplify, 2),
            "成交额总额(亿)": round(amount_total / 1e8, 2),
        })

    heat_df = pd.DataFrame(heat_rows)

    # 合并到 summary_df
    merged = summary_df.merge(heat_df, on="板块", how="left")

    # 重组列顺序：排名 板块 热度分 趋势 细分数量 股票数量 平均分 前排率% 涨停数 ...
    preferred_cols = ["排名", "板块", "热度分", "趋势", "细分数量", "股票数量",
                      "平均分", "前排率%", "后排率%", "涨停数",
                      "上涨家数占比%", "涨幅>3%占比%", "成交额放大倍数", "成交额总额(亿)",
                      "最强细分", "最强细分得分", "前三强"]
    cols = [c for c in preferred_cols if c in merged.columns] + \
           [c for c in merged.columns if c not in preferred_cols]
    merged = merged[cols]

    # 按热度分降序重排排名
    if "热度分" in merged.columns:
        merged = merged.sort_values("热度分", ascending=False).reset_index(drop=True)
        merged["排名"] = range(1, len(merged) + 1)

    # 无条件保存历史（含扩展字段）
    _save_sector_history(date_str, merged, heat_rows)

    return merged


def _compute_trend(sector: str, current_score: float, history: dict, today: str) -> str:
    """计算趋势标签"""
    sorted_dates = sorted(history.keys())
    if today not in sorted_dates:
        idx = len(sorted_dates)
    else:
        idx = sorted_dates.index(today)

    scores_3d = _get_past_scores(sector, history, sorted_dates, idx - 1, 3)
    scores_5d = _get_past_scores(sector, history, sorted_dates, idx - 1, 5)

    slope_3d = current_score - _avg(scores_3d) if scores_3d else 0
    slope_5d = current_score - _avg(scores_5d) if scores_5d else 0
    slope = (slope_3d * 0.6 + slope_5d * 0.4) if scores_3d and scores_5d \
            else (slope_3d if scores_3d else slope_5d)
    # 使用第一天对比（跨更长周期）
    if scores_5d:
        slope_long = current_score - scores_5d[0]
        slope = slope * 0.5 + slope_long * 0.5

    if slope >= 15:
        return "🔥加速"
    elif slope >= 5:
        return "📈升温"
    elif slope >= -5:
        return "➡️平稳"
    elif slope >= -15:
        return "📉退潮"
    else:
        return "🧊冰点"


def _get_past_scores(sector: str, history: dict, sorted_dates: list, end_idx: int, count: int) -> list:
    """获取板块历史热度分"""
    scores = []
    for i in range(max(0, end_idx - count + 1), end_idx + 1):
        date_key = sorted_dates[i]
        day_data = history.get(date_key, [])
        for s in day_data:
            if s.get("板块") == sector and s.get("热度分", 0) > 0:
                scores.append(s["热度分"])
    return scores


def _save_sector_history(date_str: str, summary_df: pd.DataFrame, heat_rows: list) -> None:
    """保存带热度分的完整板块历史"""
    sectors = []
    for hr in heat_rows:
        sector_name = hr.get("板块", "")
        # 找到 summary 中对应行补全信息
        match = summary_df[summary_df["板块"] == sector_name] if "板块" in summary_df.columns else pd.DataFrame()
        entry = {
            "板块": sector_name,
            "热度分": hr.get("热度分", 0),
            "趋势": hr.get("趋势", "➡️平稳"),
            "平均分": float(match.iloc[0]["平均分"]) if not match.empty and "平均分" in match.columns else 0,
            "涨停数": int(hr.get("涨停数", 0)) if "涨停数" in hr else (
                int(match.iloc[0]["涨停数"]) if not match.empty and "涨停数" in match.columns else 0
            ),
            "股票数量": int(hr.get("股票数量", 0)) if "股票数量" in hr else (
                int(match.iloc[0]["股票数量"]) if not match.empty and "股票数量" in match.columns else 0
            ),
            "前排率%": float(hr.get("前排率%", 0)) if "前排率%" in hr else 0,
            "成交额总额(亿)": hr.get("成交额总额(亿)", 0),
            "成交额放大倍数": hr.get("成交额放大倍数", 1.0),
            "上涨家数占比%": hr.get("上涨家数占比%", 0),
        }
        sectors.append(entry)
    save_daily_summary(date_str, sectors)


def _empty_heat_row(sector_name: str) -> dict:
    return {
        "板块": sector_name,
        "热度分": 0,
        "趋势": "➡️平稳",
        "涨停密度分": 0, "上涨广度分": 0, "强涨广度分": 0,
        "量能放大分": 0, "前排强度分": 0,
        "上涨家数占比%": 0, "涨幅>3%占比%": 0,
        "成交额放大倍数": 1.0, "成交额总额(亿)": 0,
    }
