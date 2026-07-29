# -*- coding: utf-8 -*-
"""
导出当日板块热度数据为 JSON（供看板 Widget 使用）
复用 main.py 的数据管线，但不生成 Excel、不推送飞书
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import load_config, prepare_data, score_stocks
from modules.heat_tracker import compute_heat_scores, load_history
import pandas as pd


def main():
    date_str = datetime.now().strftime("%Y%m%d")
    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    config = load_config()

    print(f"[导出] 日期: {date_fmt}")
    data, loader = prepare_data(config, date_fmt, save_spot=False)
    if data.get("watchlist") is None:
        print("[ERR] 数据加载失败")
        return 1

    scored_list = score_stocks(data, config)
    loader.set_watchlist(data["watchlist"])
    data["summary"] = loader.load_concept_summary()
    data["sectors"] = loader.load_all_sectors()

    # 热度分计算（会无条件落盘今日历史；history 键统一用 YYYYMMDD）
    data["summary"] = compute_heat_scores(data["summary"], data["sectors"], date_str)

    # === 组装看板 JSON ===
    history = load_history()
    sorted_dates = sorted(history.keys())
    recent_dates = sorted_dates[-15:]  # 最近15个交易日的热度曲线

    # 每个板块的历史热度序列
    sector_series = {}
    for d in recent_dates:
        for s in history.get(d, []):
            name = s.get("板块", "")
            if name and "热度分" in s:
                sector_series.setdefault(name, []).append({"date": d, "heat": s["热度分"]})

    sectors_out = []
    for _, row in data["summary"].iterrows():
        name = str(row.get("板块", ""))
        # 个股明细（去重，按总得分降序，取前12只）
        stocks = []
        df_sec = data["sectors"].get(name)
        if df_sec is not None and not df_sec.empty:
            df_dedup = df_sec.drop_duplicates(subset=["代码"]) if "代码" in df_sec.columns else df_sec
            df_dedup = df_dedup.sort_values("总得分", ascending=False).head(12)
            for _, r in df_dedup.iterrows():
                stocks.append({
                    "代码": str(r.get("代码", "")),
                    "名称": str(r.get("名称", "")),
                    "涨跌幅": round(float(r.get("涨跌幅", 0) or 0), 2),
                    "总得分": int(r.get("总得分", 0) or 0),
                    "成交额亿": round(float(r.get("成交额", 0) or 0) / 1e8, 2),
                    "涨停": int(r.get("涨停", 0) or 0) if "涨停" in r else (1 if float(r.get("涨跌幅", 0) or 0) >= 9.5 else 0),
                })
        sectors_out.append({
            "板块": name,
            "热度分": float(row.get("热度分", 0) or 0),
            "趋势": str(row.get("趋势", "➡️平稳")),
            "涨停数": int(row.get("涨停数", 0) or 0),
            "股票数量": int(row.get("股票数量", 0) or 0),
            "上涨家数占比": float(row.get("上涨家数占比%", 0) or 0),
            "涨幅>3%占比": float(row.get("涨幅>3%占比%", 0) or 0),
            "成交额放大倍数": float(row.get("成交额放大倍数", 1) or 1),
            "成交额总额亿": float(row.get("成交额总额(亿)", 0) or 0),
            "前排率": float(row.get("前排率%", 0) or 0),
            "历史": sector_series.get(name, []),
            "个股": stocks,
        })

    # 全局统计
    watchlist_df = data["watchlist"]
    df_pool = watchlist_df[watchlist_df["韭研概念"].str.strip().ne("")]
    out = {
        "date": date_fmt,
        "pool_count": int(len(df_pool)),
        "market_success": int(df_pool["涨跌幅"].notna().sum()) if "涨跌幅" in df_pool.columns else 0,
        "actual_data_dates": ", ".join(sorted(data.get("actual_data_dates", set()))),
        "sectors": sectors_out,
    }

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"heat_dashboard_{date_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[OK] 看板数据已导出: {out_path}")
    print(f"     板块数: {len(sectors_out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
