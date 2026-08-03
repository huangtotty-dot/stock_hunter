#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块 JSON 自动同步工具 v1.0
从 watchlist_jiuyan.json 自动生成/更新根目录下的板块 JSON 文件
（如 电力.json、半导体.json 等），保持与主数据源一致。

用法：
  python scripts/sync_sector_json.py             # 同步所有分类
  python scripts/sync_sector_json.py --dry-run   # 预览，不写入
  python scripts/sync_sector_json.py -c 电力 半导体  # 只同步指定分类
  python scripts/sync_sector_json.py --list      # 列出所有分类
"""
import os
import sys
import json
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "watchlist_jiuyan.json")


def load_watchlist() -> dict:
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_sectors(watchlist: dict) -> dict:
    """
    从 watchlist 中提取各分类的标的列表。

    返回 {category_name: [{name, code, jiuyan_category, jiuyan_concept}, ...]}
    """
    sectors = defaultdict(list)

    for code, info in watchlist.items():
        if not isinstance(info, dict):
            continue

        name = info.get("name", "")

        # 收集所有 category/concept 对（同时处理新旧格式）
        pairs = []

        # 新格式：numbered pairs
        for i in range(1, 10):
            cat = info.get(f"jiuyan_category{i}", "")
            concept = info.get(f"jiuyan_concept{i}", "")
            if cat and str(cat).strip():
                pairs.append((str(cat).strip(), str(concept).strip()))

        # 旧格式回退
        if not pairs:
            cat = str(info.get("jiuyan_category", ""))
            concept = str(info.get("jiuyan_concept", ""))
            if cat and cat.strip():
                for c in cat.split("|"):
                    c = c.strip()
                    if c:
                        pairs.append((c, concept.strip()))

        # 加入各分类
        for cat, concept in pairs:
            sectors[cat].append({
                "name": name,
                "code": code,
                "jiuyan_category": cat,
                "jiuyan_concept": concept.split("|") if "|" in concept else ([concept] if concept else []),
            })

    return dict(sectors)


def save_sector_json(sector_name: str, stocks: list, base_dir: str, dry_run: bool = False):
    """保存单个板块 JSON 文件"""
    # 文件名安全化：替换路径不合法字符
    safe_name = sector_name.replace("/", "-").replace("\\", "-").replace(":", "-")
    filepath = os.path.join(base_dir, f"{safe_name}.json")

    if dry_run:
        print(f"  [DRY-RUN] {safe_name}.json: {len(stocks)} 只标的")
        return

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {safe_name}.json: {len(stocks)} 只标的")


def list_existing_sector_files(base_dir: str) -> list:
    """列出根目录下已有的板块 JSON 文件（排除 watchlist_jiuyan.json）"""
    existing = []
    for f in os.listdir(base_dir):
        if f.endswith(".json") and f != "watchlist_jiuyan.json" and f != "config.json" and f != "config.sample.json":
            filepath = os.path.join(base_dir, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, list) and len(data) > 0:
                    if "jiuyan_category" in data[0]:
                        existing.append(f.replace(".json", ""))
            except Exception:
                pass
    return existing


def main():
    parser = argparse.ArgumentParser(description="板块 JSON 自动同步工具")
    parser.add_argument("-c", "--categories", nargs="*", help="指定要同步的分类（不指定则全部）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入")
    parser.add_argument("--list", action="store_true", help="列出所有可导出的分类")
    parser.add_argument("--clean", action="store_true", help="删除 watchlist 中不存在的旧板块文件")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("[加载] watchlist_jiuyan.json ...")
    watchlist = load_watchlist()
    sectors = extract_sectors(watchlist)

    if args.list:
        print(f"\n=== 可导出的分类（共 {len(sectors)} 个）===\n")
        for name, stocks in sorted(sectors.items(), key=lambda x: -len(x[1])):
            print(f"  {name}: {len(stocks)} 只标的")
        return 0

    target = args.categories if args.categories else list(sectors.keys())

    print(f"\n[同步] {'预览模式 ' if args.dry_run else ''}共 {len(target)} 个分类...\n")

    saved = 0
    for cat in sorted(target):
        if cat not in sectors:
            print(f"  [WARN] 分类 '{cat}' 在 watchlist 中不存在，跳过")
            continue
        stocks = sectors[cat]
        save_sector_json(cat, stocks, base_dir, dry_run=args.dry_run)
        saved += 1

    # 清理旧板块文件
    if args.clean and not args.dry_run:
        existing = list_existing_sector_files(base_dir)
        for old_name in existing:
            if old_name not in sectors:
                old_path = os.path.join(base_dir, f"{old_name}.json")
                os.remove(old_path)
                print(f"  [DEL] 已删除: {old_name}.json（watchlist 中不存在）")

    print(f"\n[完成] 已{'预览' if args.dry_run else '同步'} {saved} 个板块文件")


if __name__ == "__main__":
    sys.exit(main())
