#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多维选股 CLI 工具 v1.0
用法：
  # 按分类筛选
  python scripts/screen_stocks.py -c 电力 -c 央企

  # 按概念关键词筛选
  python scripts/screen_stocks.py -C 智能电网

  # 涨停 + 最低得分
  python scripts/screen_stocks.py -c 电力 --limit-up --min-score 20

  # 交集分析
  python scripts/screen_stocks.py --intersect --top-cats 8

  # 查某标的的分类
  python scripts/screen_stocks.py --stock 000400

  # 导出 CSV
  python scripts/screen_stocks.py -c 电力 -C 变压器 -o result.csv
"""
import os
import sys
import argparse
import pandas as pd

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.screener import WatchlistScreener


def format_output(df: pd.DataFrame, top: int = None, show_concepts: bool = True):
    """格式化打印筛选结果"""
    if df.empty:
        print("\n[!] 无匹配结果")
        return

    if top:
        df = df.head(top)

    # 去重（同一代码可能出现多次因为多 category）
    display_cols = ["代码", "名称"]
    if show_concepts and "韭研分类" in df.columns:
        display_cols.append("韭研分类")
        display_cols.append("韭研概念")
    for col in ["总得分", "涨跌幅", "涨停", "成交额"]:
        if col in df.columns:
            display_cols.append(col)

    display_cols = [c for c in display_cols if c in df.columns]

    # 按代码分组，合并概念
    if "韭研分类" in df.columns and "韭研概念" in df.columns:
        grouped_rows = []
        seen_codes = set()
        for _, row in df.iterrows():
            code = row["代码"]
            if code in seen_codes:
                continue
            seen_codes.add(code)
            code_df = df[df["代码"] == code]
            cats = code_df["韭研分类"].unique()
            concepts = code_df["韭研概念"].unique()
            r = {
                "代码": code,
                "名称": row["名称"],
                "韭研分类": " | ".join(c for c in cats if c),
                "韭研概念": " | ".join(c for c in concepts if c),
            }
            for col in ["总得分", "涨跌幅", "涨停", "成交额"]:
                if col in df.columns:
                    val = code_df[col].iloc[0]
                    r[col] = val
            grouped_rows.append(r)
        display_df = pd.DataFrame(grouped_rows)
    else:
        display_df = df[display_cols].drop_duplicates(subset=["代码"])

    # 格式化成交额为亿
    if "成交额" in display_df.columns:
        display_df["成交额(亿)"] = display_df["成交额"].apply(
            lambda x: f"{x/1e8:.2f}" if pd.notna(x) and x > 0 else "-"
        )
        display_df = display_df.drop(columns=["成交额"])

    print(f"\n[*] 共 {len(df)} 条匹配记录（{df['代码'].nunique()} 只不重复标的）\n")
    print(display_df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(
        description="多维选股 CLI — 基于韭研公社分类体系",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  screen_stocks.py -c 电力                          # 电力板块所有标的
  screen_stocks.py -c 电力 -c 央企                   # 同时属于电力+央企的标的
  screen_stocks.py -C 变压器                         # 概念中含"变压器"的标的
  screen_stocks.py -c 电力 -C 智能电网 --limit-up     # 电力+智能电网+今日涨停
  screen_stocks.py --intersect                       # 显示各分类交集矩阵
  screen_stocks.py --stock 601868                    # 查看某标的的分类详情
  screen_stocks.py -c 电力 --top 10 -o result.csv    # TOP10导出
        """,
    )

    # 筛选参数
    parser.add_argument("-c", "--category", action="append", dest="categories",
                        help="按一级分类筛选（可重复，AND逻辑）")
    parser.add_argument("-C", "--concept", action="append", dest="concepts",
                        help="按概念关键词筛选（可重复，OR逻辑）")
    parser.add_argument("--mode", choices=["AND", "OR"], default="AND",
                        help="categories 与 concepts 之间的逻辑 (默认: AND)")

    # 行情过滤
    parser.add_argument("--limit-up", action="store_true", help="仅涨停标的")
    parser.add_argument("--min-score", type=float, help="最低得分")
    parser.add_argument("--min-change", type=float, help="最低涨跌幅%%")
    parser.add_argument("--min-volume", type=float, help="最低成交额（亿元）")

    # 输出控制
    parser.add_argument("--top", type=int, default=None, help="取前 N 条")
    parser.add_argument("--sort-by", choices=["score", "change", "volume", "code"],
                        default="score", help="排序方式")
    parser.add_argument("-o", "--output", type=str, help="导出 CSV 文件路径")
    parser.add_argument("--no-concepts", action="store_true", help="不显示概念列")
    parser.add_argument("--exclude-st", action="store_true", default=True,
                        help="排除ST (默认: 是)")

    # 分析模式
    parser.add_argument("--intersect", action="store_true", help="显示交集分析矩阵")
    parser.add_argument("--top-cats", type=int, default=10, help="交集分析: 取前N个分类")
    parser.add_argument("--bridge", nargs=2, metavar=("CAT_A", "CAT_B"),
                        help="查看两个分类的交集标的详情")
    parser.add_argument("--stock", type=str, help="查看某标的所属的所有分类")
    parser.add_argument("--stats", action="store_true", help="显示各分类统计")

    args = parser.parse_args()

    # 初始化
    screener = WatchlistScreener()

    # ── 分析模式 ──
    if args.stats:
        print("=== 各分类标的数量统计 ===\n")
        print(screener.category_stats().to_string())
        return 0

    if args.intersect:
        print(f"=== 前 {args.top_cats} 大分类交集矩阵 ===\n")
        df = screener.intersect(top_categories=args.top_cats)
        if df.empty:
            print("无交集数据")
        else:
            for _, row in df.iterrows():
                print(f"\n[*] {row['分类A']} & {row['分类B']}: {row['交集数量']}只")
                # 截取显示
                stocks = str(row["交集标的"])
                if len(stocks) > 300:
                    stocks = stocks[:300] + "..."
                print(f"   {stocks}")
        return 0

    if args.bridge:
        cat_a, cat_b = args.bridge
        print(f"\n=== {cat_a} ∩ {cat_b} 交集标的 ===\n")
        df = screener.bridge_stocks(cat_a, cat_b)
        if df.empty:
            print(f"\n[!] {cat_a} & {cat_b}: 无交集标的")
        else:
            for _, row in df.iterrows():
                code = row["代码"]
                stock_df = screener.get_stock_categories(code)
                cats = stock_df["韭研分类"].unique()
                concepts = stock_df["韭研概念"].unique()
                print(f"  {code} {row['名称']}")
                print(f"    分类: {' | '.join(c for c in cats if c)}")
                print(f"    概念: {' | '.join(c for c in concepts if c)}")
            print(f"\n共 {df['代码'].nunique()} 只标的")
        return 0

    if args.stock:
        code = args.stock.strip()
        df = screener.get_stock_categories(code)
        if df.empty:
            print(f"[!] 未找到代码 {code}")
            # 尝试按名称查找
            for c, info in screener._raw.items():
                if info.get("name", "") == code:
                    df = screener.get_stock_categories(c)
                    code = c
                    break
        if df.empty:
            print(f"   该标的无韭研分类数据")
        else:
            name = df["名称"].iloc[0]
            print(f"\n=== {code} {name} 的分类标签 ===\n")
            for _, row in df.iterrows():
                cat = row["韭研分类"]
                concept = row["韭研概念"]
                if cat:
                    print(f"  [{cat}]" + (f" -> {concept}" if concept else ""))
                else:
                    print(f"  (无分类标签)")
        return 0

    # ── 筛选模式 ──
    if not args.categories and not args.concepts:
        parser.print_help()
        print("\n[!] 请至少指定 --category 或 --concept，或使用分析模式 (--stats/--intersect/--stock)")
        return 1

    # 转换成交额单位：亿 → 元
    min_volume = args.min_volume * 1e8 if args.min_volume else None

    df = screener.filter(
        categories=args.categories,
        concepts=args.concepts,
        mode=args.mode,
        min_score=args.min_score,
        limit_up_only=args.limit_up,
        min_change=args.min_change,
        min_volume=min_volume,
        exclude_st=args.exclude_st,
    )

    # 排序
    sort_map = {
        "score": "总得分",
        "change": "涨跌幅",
        "volume": "成交额",
        "code": "代码",
    }
    sort_col = sort_map.get(args.sort_by, "总得分")
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    # 输出
    format_output(df, top=args.top, show_concepts=not args.no_concepts)

    # 导出
    if args.output:
        screener.to_csv(df, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
