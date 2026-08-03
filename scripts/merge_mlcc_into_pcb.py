#!/usr/bin/env python3
"""
将 MLCC 概念归入 PCB 作为子概念。
- 所有 jiuyan_category = "MLCC" (numbered + legacy) → "PCB"
- concept 加前缀 "MLCC-" (如 "AI领域MLCC" → "MLCC-AI领域MLCC")
- Legacy 条目迁移到 numbered slot
- 去重：同一股票已有相同 (PCB, concept) 则跳过
"""
import json
import re
import os
import shutil
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(BASE, "watchlist_jiuyan.json")


def normalize_mlcc_concept(concept: str) -> str:
    """统一为 MLCC-xxx 格式"""
    c = (concept or "").strip()
    if not c:
        return "MLCC"
    if c.startswith("MLCC-"):
        return c
    if "MLCC" in c:
        rest = c.replace("MLCC", "").strip("-_ ")
        return f"MLCC-{rest}" if rest else "MLCC"
    return f"MLCC-{c}"


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = WATCHLIST + f".bak_{ts}"
    shutil.copy2(WATCHLIST, backup)
    print(f"[备份] {backup}")

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    stats = {"numbered": 0, "legacy": 0, "skip_dup": 0}

    for code, entry in watchlist.items():
        if not isinstance(entry, dict):
            continue

        # ── 处理 numbered slots ──
        for i in range(1, 10):
            cat_key = f"jiuyan_category{i}"
            concept_key = f"jiuyan_concept{i}"
            if str(entry.get(cat_key, "")).strip() == "MLCC":
                old_concept = str(entry.get(concept_key, "")).strip()
                new_concept = normalize_mlcc_concept(old_concept)

                # 检查是否已有相同的 (PCB, new_concept)
                dup = False
                for j in range(1, 10):
                    if j != i and entry.get(f"jiuyan_category{j}") == "PCB" and \
                       entry.get(f"jiuyan_concept{j}") == new_concept:
                        dup = True
                        break
                if dup:
                    del entry[cat_key]
                    del entry[concept_key]
                    stats["skip_dup"] += 1
                    print(f"  [numbered skip] {code} {entry['name']}: PCB/{new_concept} 已存在")
                else:
                    entry[cat_key] = "PCB"
                    entry[concept_key] = new_concept
                    stats["numbered"] += 1
                    print(f"  [numbered] {code} {entry['name']}: MLCC/{old_concept or '(空)'} -> PCB/{new_concept}")

        # ── 处理 legacy slot ──
        legacy_cat = str(entry.get("jiuyan_category", "")).strip()
        if legacy_cat == "MLCC" or ("MLCC" in legacy_cat.split("|") if legacy_cat else False):
            legacy_concept = str(entry.get("jiuyan_concept", "")).strip()
            new_concept = normalize_mlcc_concept(legacy_concept)

            # 找下一个可用 slot
            existing_nums = set()
            for key in entry:
                m = re.match(r"jiuyan_category(\d+)", key)
                if m:
                    existing_nums.add(int(m.group(1)))

            # 去重
            dup = False
            for j in existing_nums:
                if entry.get(f"jiuyan_category{j}") == "PCB" and \
                   entry.get(f"jiuyan_concept{j}") == new_concept:
                    dup = True
                    break

            if dup:
                entry["jiuyan_category"] = ""
                entry["jiuyan_concept"] = ""
                stats["skip_dup"] += 1
                print(f"  [legacy skip] {code} {entry['name']}: PCB/{new_concept} 已存在")
            else:
                next_num = 1
                while next_num in existing_nums:
                    next_num += 1
                if next_num <= 6:
                    entry[f"jiuyan_category{next_num}"] = "PCB"
                    entry[f"jiuyan_concept{next_num}"] = new_concept
                    entry["jiuyan_category"] = ""
                    entry["jiuyan_concept"] = ""
                    stats["legacy"] += 1
                    print(f"  [legacy] {code} {entry['name']}: MLCC/{legacy_concept or '(空)'} -> slot{next_num} PCB/{new_concept}")
                else:
                    print(f"  [WARN] {code} {entry['name']}: 无可用 slot，跳过")

    with open(WATCHLIST, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

    print(f"\n=== 结果 ===")
    print(f"Numbered 迁移: {stats['numbered']}")
    print(f"Legacy 迁移:   {stats['legacy']}")
    print(f"跳过重复:     {stats['skip_dup']}")

    # 验证
    remain = 0
    for code, entry in watchlist.items():
        if not isinstance(entry, dict):
            continue
        for i in range(1, 10):
            if str(entry.get(f"jiuyan_category{i}", "")).strip() == "MLCC":
                remain += 1
        if str(entry.get("jiuyan_category", "")).strip() == "MLCC":
            remain += 1
    print(f"[验证] 残留 MLCC: {remain} 条（应为 0）")
    return 0 if remain == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
