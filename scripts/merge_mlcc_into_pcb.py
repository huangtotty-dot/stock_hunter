# -*- coding: utf-8 -*-
"""
任务1：将 MLCC 分类并入 PCB 作为其子概念
- jiuyan_category{i} == "MLCC" → "PCB"
- 对应 concept 规范化为 "MLCC-xxx" 格式（detail 排名按 "-" 拆分取前半作为子概念）
- 同时处理旧版单字段 jiuyan_category/jiuyan_concept
- 先备份再保存
"""
import os
import sys
import json
import shutil
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(BASE, "watchlist_jiuyan.json")


def normalize_mlcc_concept(concept: str) -> str:
    """统一为 MLCC-xxx 格式"""
    c = (concept or "").strip()
    if not c:
        return "MLCC"
    if c.startswith("MLCC"):
        return c
    if "MLCC" in c:
        # 如 "AI领域MLCC" → "MLCC-AI领域"
        rest = c.replace("MLCC", "").strip("-_ ")
        return f"MLCC-{rest}" if rest else "MLCC"
    return f"MLCC-{c}"


def main():
    # 备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = WATCHLIST + f".bak_{ts}"
    shutil.copy2(WATCHLIST, backup)
    print(f"[备份] {backup}")

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        data = json.load(f)

    merged = []  # (code, name, 原category字段, 原concept, 新concept)

    for code, info in data.items():
        if not isinstance(info, dict):
            continue
        # 多 category 字段
        for i in range(1, 10):
            cat_key = f"jiuyan_category{i}"
            concept_key = f"jiuyan_concept{i}"
            if str(info.get(cat_key, "")).strip() == "MLCC":
                old_concept = str(info.get(concept_key, "")).strip()
                new_concept = normalize_mlcc_concept(old_concept)
                info[cat_key] = "PCB"
                info[concept_key] = new_concept
                merged.append((code, info.get("name", ""), cat_key, old_concept, new_concept))
        # 旧版单字段
        if str(info.get("jiuyan_category", "")).strip() == "MLCC":
            old_concept = str(info.get("jiuyan_concept", "")).strip()
            new_concept = normalize_mlcc_concept(old_concept)
            info["jiuyan_category"] = "PCB"
            info["jiuyan_concept"] = new_concept
            merged.append((code, info.get("name", ""), "jiuyan_category", old_concept, new_concept))

    with open(WATCHLIST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[合并完成] 共 {len(merged)} 条 MLCC 标签并入 PCB：")
    for code, name, key, old_c, new_c in merged:
        print(f"  {code} {name} [{key}] concept: {old_c or '(空)'} -> {new_c}")

    # 验证：不应再存在 MLCC 分类
    remain = 0
    for code, info in data.items():
        if not isinstance(info, dict):
            continue
        for i in range(1, 10):
            if str(info.get(f"jiuyan_category{i}", "")).strip() == "MLCC":
                remain += 1
        if str(info.get("jiuyan_category", "")).strip() == "MLCC":
            remain += 1
    print(f"\n[验证] 残留 MLCC 分类: {remain} 条（应为 0）")
    return 0 if remain == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
