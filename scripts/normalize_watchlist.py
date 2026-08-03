# -*- coding: utf-8 -*-
"""
watchlist 全局归一化（P0 整改，2026-07-29 复盘后执行）

1. 全部标签统一迁移到编号对 jiuyan_category{i}/jiuyan_concept{i}
   - 旧版单字段 jiuyan_category/jiuyan_concept 迁移后清空（删除键）
   - 概念中的 "|" 拆分为独立编号对
   - 重复对去重
2. 影子标签裁决（见 docs/复盘报告_watchlist分类体系_20260729.md 1.1）：
   - MERGE_LEGACY: 旧字段有效，并入编号对
   - 其余并存股票：编号对为准，旧字段随清空丢弃
3. 异常代码（港股/北交所）标签隔离到 data/excluded_non_ashare.json
4. ST 股现用名同步
"""
import os
import sys
import json
import shutil
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(BASE, "watchlist_jiuyan.json")
EXCLUDED = os.path.join(BASE, "data", "excluded_non_ashare.json")

VALID_PREFIXES = ("000", "001", "002", "003", "300", "301",
                  "600", "601", "603", "605", "688", "689")

# 影子标签裁决：旧字段并入编号对（其余并存股票的旧字段直接丢弃）
MERGE_LEGACY = {"000530", "300408", "600673", "002131"}

# ST 现用名同步
ST_RENAME = {
    "603517": "ST绝味",
    "002719": "ST麦趣",
    "600187": "*ST国中",
    "600735": "ST新华锦",
    "000610": "*ST西旅",
    "002717": "*ST岭南",
}


def collect_pairs(info, include_legacy: bool):
    """收集全部 category/concept 对（拆分 |，去重保序）"""
    pairs = []
    seen = set()

    def add(cat, con):
        cat, con = cat.strip(), con.strip()
        if not cat:
            return
        key = (cat, con)
        if key not in seen:
            seen.add(key)
            pairs.append(key)

    for i in range(1, 10):
        cat = str(info.get(f"jiuyan_category{i}", "")).strip()
        con = str(info.get(f"jiuyan_concept{i}", "")).strip()
        if cat:
            cons = [c.strip() for c in con.split("|")] if con else [""]
            for c in cons:
                add(cat, c)

    if include_legacy:
        legacy_cat = str(info.get("jiuyan_category", "")).strip()
        legacy_con = str(info.get("jiuyan_concept", "")).strip()
        if legacy_cat:
            cats = [c.strip() for c in legacy_cat.split("|") if c.strip()]
            cons = [c.strip() for c in legacy_con.split("|")] if legacy_con else [""]
            for cat in cats:
                for c in cons:
                    add(cat, c)
    return pairs


def is_valid_code(code: str) -> bool:
    return len(code) == 6 and code.isdigit() and code.startswith(VALID_PREFIXES)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = WATCHLIST + f".bak_normalize_{ts}"
    shutil.copy2(WATCHLIST, backup)
    print(f"[备份] {backup}")

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        data = json.load(f)

    excluded = {}
    n_excluded = 0
    n_migrated_legacy = 0
    n_merged_shadow = 0
    n_pipe_split = 0
    n_dup_removed = 0
    n_renamed = 0
    overflow = []

    for code, info in list(data.items()):
        if not isinstance(info, dict):
            continue

        # 3. 异常代码隔离（只隔离有标签的）
        if not is_valid_code(code):
            has_tag = any(str(info.get(f"jiuyan_category{i}", "")).strip() for i in range(1, 10)) \
                      or str(info.get("jiuyan_category", "")).strip()
            if has_tag:
                excluded[code] = info
                del data[code]
                n_excluded += 1
            continue

        # 4. ST 更名同步
        if code in ST_RENAME and info.get("name") != ST_RENAME[code]:
            info["name"] = ST_RENAME[code]
            n_renamed += 1

        had_legacy = bool(str(info.get("jiuyan_category", "")).strip())
        had_numbered = any(str(info.get(f"jiuyan_category{i}", "")).strip() for i in range(1, 10))

        # 纯旧字段股票必须带上旧字段收集（那是它们唯一的标签来源）；
        # 并存股票只在裁决合并名单里才带旧字段，否则以编号对为准
        include_legacy = (not had_numbered) or (code in MERGE_LEGACY)

        pairs = collect_pairs(info, include_legacy=include_legacy)

        if not had_numbered and not had_legacy:
            # 无标签股票：顺手清空可能存在的空旧字段键
            info.pop("jiuyan_category", None)
            info.pop("jiuyan_concept", None)
            continue

        # 编号对不存在时从旧字段迁移
        if not had_numbered and had_legacy:
            n_migrated_legacy += 1
        if include_legacy and had_legacy and had_numbered:
            n_merged_shadow += 1
        # | 拆分计数：新对数 > 原字段数 的差额
        orig_field_cnt = sum(
            1 for i in range(1, 10) if str(info.get(f"jiuyan_category{i}", "")).strip()
        ) + (1 if (include_legacy and had_legacy) else 0)
        if not had_numbered:
            orig_field_cnt = 1  # 纯旧字段视为1个字段来源
        if len(pairs) > orig_field_cnt:
            n_pipe_split += len(pairs) - orig_field_cnt

        # 重写编号对（超过9对的记录并截断）
        for i in range(1, 10):
            info.pop(f"jiuyan_category{i}", None)
            info.pop(f"jiuyan_concept{i}", None)
        if len(pairs) > 9:
            overflow.append((code, info.get("name", ""), len(pairs)))
            pairs = pairs[:9]
        for i, (cat, con) in enumerate(pairs, 1):
            info[f"jiuyan_category{i}"] = cat
            info[f"jiuyan_concept{i}"] = con

        # 清空旧字段
        info.pop("jiuyan_category", None)
        info.pop("jiuyan_concept", None)

    # 保存隔离名单
    if excluded:
        with open(EXCLUDED, "w", encoding="utf-8") as f:
            json.dump(excluded, f, ensure_ascii=False, indent=2)

    with open(WATCHLIST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[归一化完成]")
    print(f"  纯旧字段迁移到编号对: {n_migrated_legacy} 只")
    print(f"  影子标签合并（裁决保留）: {n_merged_shadow} 只")
    print(f"  '|' 拆分新增编号对: {n_pipe_split} 条")
    print(f"  异常代码隔离: {n_excluded} 只 -> data/excluded_non_ashare.json")
    print(f"  ST 更名同步: {n_renamed} 只")
    print(f"  超过9对被截断: {len(overflow)} 只 {overflow if overflow else ''}")
    print(f"  watchlist 总标的: {len(data)} 只")
    return 0


if __name__ == "__main__":
    sys.exit(main())
