# -*- coding: utf-8 -*-
"""
watchlist_jiuyan.json 深度体检
维度1 分类正确性：错标/异常代码/退市股/字段一致性
维度2 逻辑一致性：分类粒度/概念命名规范/层级混乱
维度3 查阅复杂度：标签分布/影子标签/嵌套重复
"""
import os
import sys
import json
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(BASE, "watchlist_jiuyan.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

VALID_PREFIXES = ("000", "001", "002", "003", "300", "301",
                  "600", "601", "603", "605", "688", "689")

total = len(data)
tagged = 0
stats = {
    "bad_code": [],            # 代码格式异常（无法取行情）
    "no_name": [],
    "legacy_only": [],         # 只有旧版单字段标签
    "numbered_only": 0,
    "both_fields": 0,
    "shadowed": [],            # 旧字段与编号字段分类不一致（旧字段被遮蔽）
    "empty_concept": [],       # 有分类但概念为空
    "pipe_in_pair": [],        # 编号对里 concept 仍含 | 分隔
    "dup_pairs": [],           # 同一股票出现重复的 category/concept 对
    "st_stocks": [],
}
cat_counter = Counter()          # 分类 -> 标的数（按编号对+旧字段回退，与loader一致）
concept_counter = Counter()      # 完整 concept 值 -> 出现次数
concept_style = Counter()        # 命名风格: dash/underscore/plain/pipe
subconcept_map = defaultdict(set)  # "-" 前半 -> 归属 category 集合（查跨分类同名子概念）
cat_multi_dist = Counter()       # 每只股票的分类个数分布

for code, info in data.items():
    if not isinstance(info, dict):
        continue
    name = info.get("name", "")
    if not name:
        stats["no_name"].append(code)
    if name.startswith(("ST", "*ST")):
        stats["st_stocks"].append((code, name))
    if not (len(code) == 6 and code.isdigit() and code.startswith(VALID_PREFIXES)):
        # 收集有标签的异常代码
        has_tag = any(str(info.get(f"jiuyan_category{i}", "")).strip() for i in range(1, 10)) or str(info.get("jiuyan_category", "")).strip()
        if has_tag:
            stats["bad_code"].append((code, name))

    # 收集编号对
    pairs = []
    for i in range(1, 10):
        cat = str(info.get(f"jiuyan_category{i}", "")).strip()
        con = str(info.get(f"jiuyan_concept{i}", "")).strip()
        if cat:
            pairs.append((cat, con))
    legacy_cat = str(info.get("jiuyan_category", "")).strip()
    legacy_con = str(info.get("jiuyan_concept", "")).strip()

    if pairs and legacy_cat:
        stats["both_fields"] += 1
        # 影子标签：旧字段分类不在编号对分类中 → loader 会忽略旧字段
        pair_cats = {c for c, _ in pairs}
        legacy_cats = {c.strip() for c in legacy_cat.split("|") if c.strip()}
        shadow = legacy_cats - pair_cats
        if shadow:
            stats["shadowed"].append((code, name, legacy_cat, legacy_con, sorted(pair_cats)))
    elif legacy_cat:
        stats["legacy_only"].append((code, name, legacy_cat, legacy_con))

    if not pairs and not legacy_cat:
        continue
    tagged += 1

    if pairs:
        stats["numbered_only"] += 1
        eff_pairs = pairs
    else:
        cats = [c.strip() for c in legacy_cat.split("|") if c.strip()]
        eff_pairs = [(c, legacy_con) for c in cats]

    # 去重检测
    if len(set(eff_pairs)) != len(eff_pairs):
        stats["dup_pairs"].append((code, name, eff_pairs))

    cat_multi_dist[len({c for c, _ in eff_pairs})] += 1

    for cat, con in eff_pairs:
        cat_counter[cat] += 1
        if not con:
            stats["empty_concept"].append((code, name, cat))
        if "|" in con:
            stats["pipe_in_pair"].append((code, name, cat, con))
        concept_counter[con] += 1
        if "-" in con:
            concept_style["dash"] += 1
            subconcept_map[con.split("-")[0].strip()].add(cat)
        elif "_" in con:
            concept_style["underscore"] += 1
        elif "|" in con:
            concept_style["pipe"] += 1
        else:
            concept_style["plain"] += 1

# ============ 输出 ============
print("=" * 64)
print(f"总标的: {total} | 有标签: {tagged} ({tagged/total*100:.1f}%) | 无标签: {total-tagged}")
print(f"标签字段形态: 纯编号对 {stats['numbered_only']} | 编号+旧字段并存 {stats['both_fields']} | 纯旧字段 {len(stats['legacy_only'])}")

print("\n--- 维度1 分类正确性 ---")
print(f"[异常代码] 有标签但代码无法取行情: {len(stats['bad_code'])} 只")
for c, n in stats["bad_code"][:20]:
    print(f"   {c} {n}")
print(f"[ST股] {len(stats['st_stocks'])} 只（有标签池内）")
print(f"[有分类但概念为空] {len(stats['empty_concept'])} 条")
for c, n, cat in stats["empty_concept"][:10]:
    print(f"   {c} {n} [{cat}]")

print("\n--- 维度2 逻辑一致性 ---")
print(f"[分类数] {len(cat_counter)} 个一级分类，标的分布:")
for cat, cnt in cat_counter.most_common():
    print(f"   {cat:<12} {cnt:>4} 只")
print(f"\n[概念命名风格] '-'分层: {concept_style['dash']} | '_'连接: {concept_style['underscore']} | 无分隔: {concept_style['plain']} | 含'|'嵌套: {concept_style['pipe']}")
print(f"[唯一概念值] {len(concept_counter)} 个")
# 跨分类同名子概念
cross = {k: v for k, v in subconcept_map.items() if len(v) > 1}
print(f"[跨分类同名子概念] {len(cross)} 个（同一子概念名出现在多个一级分类下）:")
for k, v in sorted(cross.items()):
    print(f"   {k} -> {sorted(v)}")

print("\n--- 维度3 查阅复杂度 ---")
print(f"[影子标签] 旧字段与编号字段分类不一致（旧字段被loader忽略）: {len(stats['shadowed'])} 只")
for c, n, lc, lcon, pc in stats["shadowed"][:15]:
    print(f"   {c} {n} 旧字段[{lc}|{lcon}] 被忽略, 实际生效分类{pc}")
print(f"[编号对中仍含'|'] {len(stats['pipe_in_pair'])} 条（双层嵌套）")
for c, n, cat, con in stats["pipe_in_pair"][:10]:
    print(f"   {c} {n} [{cat}] {con[:60]}")
print(f"[重复对] {len(stats['dup_pairs'])} 只")
print(f"[分类个数分布] " + " | ".join(f"{k}个分类:{v}只" for k, v in sorted(cat_multi_dist.items())))
