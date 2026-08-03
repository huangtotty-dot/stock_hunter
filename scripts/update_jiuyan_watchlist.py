#!/usr/bin/env python3
"""
Parse the user-provided sector classification CSV data and update
watchlist_jiuyan.json with jiuyan_categoryN / jiuyan_conceptN fields.

Hierarchy:
- "智能电网", "电力设备", "电力运营", "电力建设", "火电灵活性改造" → all under "电力"
  Concept format: "原一级分类-二级分类-三级分类"
- "央企" and "北交所" → kept as top-level categories

Dedup:
- When adding concepts under "电力", check against existing legacy & numbered slots
- If concepts share keywords, merge instead of creating duplicate slots
"""

import json
import re
import os

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), '..', 'watchlist_jiuyan.json')

RAW_DATA = """\
一级分类,二级分类,三级分类,相关个股
央企,,,中国能建 大唐发电 绿发电力 节能风电 华电能源 中国电建 桂冠电力 华电辽能 南网能源 长源电力 上海电力 华电国际 国投电力 华能国际 国电电力 湖北能源 龙源电力 黔源电力 南网科技 三峡水利 中国核电 明星电力 华能水电 电投产融 华电新能 长江电力 中国广核 华能水电 南网储能 三峡能源 涪陵电力 西昌电力 惠天热电 电投水电 电投绿能 银星能源 华银电力 太阳能
电力设备,变压器,,思源电气 三变科技 华明装备 昇辉科技 扬电科技 明阳电气 特变电工 保变电气 中国西电 江苏华辰 金盘科技 伊戈尔
电力设备,绝缘子,,大连电瓷 神马电力
电力设备,智能电表,,科陆电子 九洲集团 炬华科技 迦南智能 林洋能源 万胜智能 三星医疗 海兴电力 西力科技
智能电网,输变配电,输电,平高电气 中国能建 中国西电 许继电气 永福股份
智能电网,输变配电,变电,国电南自 国电南瑞 特变电工 积成电子 江苏华辰
智能电网,输变配电,配电,金智科技 许继电气 四方股份 金盘科技 国电南瑞
智能电网,用户侧,智能电表,威胜信息(2023年中标量与威胜控股合并第一) 鼎信通讯(中标量前三) 三星医疗(中标量前三) 科陆电子 海兴电力 炬华科技 迦南智能
智能电网,用户侧,计量终端,三星医疗 华立科技 煜邦电力
智能电网,用户侧,通信模块,林洋能源 科陆电子 海兴电力 三星医疗 东软载波 许继电气 友讯达
智能电网,用户侧,外置断路器,正泰电器 未来电器 天正电气
智能电网,用户侧,智能调度,远光软件 东方电子 恒华科技 积成电子 金现代
智能电网,虚拟电厂,技术支持,中恒电气 泽宇智能 国能日新 东方电子 国电南瑞
智能电网,虚拟电厂,硬件供应,万胜智能 众智科技 迦南智能
智能电网,虚拟电厂,综合服务,科远智慧 九洲集团 芯能科技 新中港 朗新集团 珈伟新能 国网信通 四方股份 安科瑞
智能电网,虚拟电厂,负荷聚合商,东方电子 智光电气 吉电股份 积成电子 华自科技 恒实科技 朗新集团 苏文电能 国能日新 国电南自 南网科技 金智科技 南网能源
电力运营,绿电,,金房能源 江苏新能 川能动力 韶能股份 银星能源 立新能源 华能国际 吉电股份 华电国际 浙江新能 中闽能源 三峡能源
电力运营,水电,,甘肃能源 闽东电力 黔源电力 华能水电 桂冠电力 明星电力 西昌电力 三峡能源 乐山电力 长江电力 广安爱众
电力运营,核电,,中国广核 中国核电 福能股份
电力运营,火电,,皖能电力 豫能股份 华能国际 上海电力 华电国际 华银电力 国电电力 内蒙华电 国投电力 大唐发电 建投能源
电力运营,其他,,湖南发展 百通能源 长青集团 京能热力 廊坊发展 广西能源 大连热电 郴电国际 杭州热电 世茂能源 新中港
电力建设,EPC,,中国能建 中国电建 平高电气
电力建设,其他服务,,永福股份 苏文电能
火电灵活性改造,,,龙源技术 盛德鑫泰 华电科工 青达环保 东方电气
北交所,,,雅达股份 派诺科技 殷图网联 球冠电缆 亿能电力 灿能电力"""

# Categories that should be placed under "电力" as parent
POWER_SUB_CATEGORIES = {
    "智能电网", "电力设备", "电力运营", "电力建设", "火电灵活性改造",
}

# Direct code mapping for stocks where name matching fails
CODE_OVERRIDES = {
    "三星医疗": "601567",
    "国能日新": "301162",
    "朗新集团": "300682",
    "豫能股份": "001896",
    "内蒙华电": "600863",
    "吉电股份": "000875",
    "明阳电气": "301291",
}

# 北交所 stock codes (need to create entries)
BEIJIAO_STOCKS = {
    "雅达股份": "430556",
    "派诺科技": "831175",
    "殷图网联": "835508",
    "球冠电缆": "834682",
    "亿能电力": "837046",
    "灿能电力": "870299",
}


def parse_raw_data(raw: str) -> list[dict]:
    """Parse the CSV-like data into a list of {category1, category2, category3, stocks}."""
    records = []
    lines = raw.strip().split('\n')
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        if len(parts) < 4:
            print(f"WARNING: skipping malformed line: {line}")
            continue
        cat1 = parts[0].strip()
        cat2 = parts[1].strip()
        cat3 = parts[2].strip()
        stocks_str = ','.join(parts[3:]).strip()
        stock_names = re.findall(r'[一-鿿\w]+(?:\([^)]*\))?', stocks_str)
        clean_names = [sn.strip() for sn in stock_names if sn.strip()]
        records.append({
            'category1': cat1,
            'category2': cat2,
            'category3': cat3,
            'stocks': clean_names,
        })
    return records


def clean_stock_name(name: str) -> str:
    """Remove parenthetical notes from stock name for matching."""
    return re.sub(r'\([^)]*\)', '', name).strip()


def build_target_category_and_concept(cat1: str, cat2: str, cat3: str) -> tuple[str, str]:
    """
    Determine the final category and concept.
    - 央企, 北交所 → kept as top-level
    - 智能电网, 电力设备, 电力运营, 电力建设, 火电灵活性改造 → under "电力"
    """
    # Build the raw concept from sub-categories
    parts = [p for p in [cat2, cat3] if p]
    raw_concept = '-'.join(parts) if parts else ''

    if cat1 in POWER_SUB_CATEGORIES:
        # Place under "电力" parent
        if raw_concept:
            concept = f"{cat1}-{raw_concept}"
        else:
            concept = cat1  # e.g., "火电灵活性改造"
        return ("电力", concept)
    else:
        # Keep as-is (央企, 北交所)
        return (cat1, raw_concept)


def find_stock_codes(clean_name: str, name_to_codes: dict, watchlist: dict) -> list:
    """Find stock code(s) for a given stock name."""
    codes = name_to_codes.get(clean_name, [])
    if not codes and clean_name in CODE_OVERRIDES:
        code = CODE_OVERRIDES[clean_name]
        if code in watchlist:
            codes = [code]
    if not codes:
        normalized = clean_name.replace(' ', '').replace('　', '')
        for name, code_list in name_to_codes.items():
            if name.replace(' ', '').replace('　', '') == normalized:
                codes = code_list
                break
    return codes


def create_stock_entry(code: str, name: str) -> dict:
    return {
        "name": name,
        "sector": "",
        "business_summary": "",
        "concept_boards": [],
        "industry_boards": [],
        "primary_source": "jiuyan",
        "updated_at": "2026-08-03",
    }


def extract_keywords(concept: str) -> set:
    """Extract meaningful keywords from a concept string for dedup comparison."""
    # Remove common separators and symbols, then extract 2+ char Chinese words
    cleaned = re.sub(r'[|\-（）()/、，,.·\s]+', ' ', concept)
    words = set()
    for w in cleaned.split():
        w = w.strip()
        if len(w) >= 2:
            words.add(w)
    return words


def concepts_overlap(c1: str, c2: str) -> bool:
    """Check if two concept strings have keyword overlap."""
    if not c1 or not c2:
        return False
    kw1 = extract_keywords(c1)
    kw2 = extract_keywords(c2)
    return bool(kw1 & kw2)


def merge_concepts(old_concept: str, new_concept: str) -> str:
    """Merge two overlapping concepts, keeping unique parts."""
    old_parts = set(old_concept.split('-'))
    new_parts = [p for p in new_concept.split('-') if p]
    merged = list(old_parts)
    for np in new_parts:
        if np not in old_parts:
            merged.append(np)
    return '-'.join(merged)


def get_all_slots(entry: dict) -> dict:
    """
    Get all existing slots.
    Returns {slot_num: (category, concept)} for numbered slots.
    Also checks legacy unnumbered slot.
    """
    slots = {}
    for key, value in entry.items():
        m = re.match(r'jiuyan_category(\d+)', key)
        if m:
            num = int(m.group(1))
            concept_key = f'jiuyan_concept{num}'
            slots[num] = (value, entry.get(concept_key, ''))
    return slots


def main():
    print(f"Loading watchlist from {WATCHLIST_PATH}...")
    with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
        watchlist = json.load(f)
    print(f"Loaded {len(watchlist)} entries.")

    # Build name -> [codes] mapping
    name_to_codes = {}
    for code, entry in watchlist.items():
        name = entry.get('name', '')
        if name:
            name_to_codes.setdefault(name, []).append(code)

    records = parse_raw_data(RAW_DATA)
    print(f"Parsed {len(records)} classification records.")

    stats = {
        'matched': 0,
        'not_found': [],
        'added_new_slot': 0,
        'merged_into_existing': 0,
        'skipped_exact_dup': 0,
        'filled_empty_concept': 0,
        'created': 0,
    }

    for rec in records:
        raw_cat1 = rec['category1']
        cat2 = rec['category2']
        cat3 = rec['category3']
        stocks = rec['stocks']

        # Determine target category and concept
        target_cat, target_concept = build_target_category_and_concept(raw_cat1, cat2, cat3)

        for stock_raw in stocks:
            clean_name = clean_stock_name(stock_raw)

            codes = find_stock_codes(clean_name, name_to_codes, watchlist)

            # Create 北交所 entries if needed
            if not codes and clean_name in BEIJIAO_STOCKS:
                code = BEIJIAO_STOCKS[clean_name]
                if code not in watchlist:
                    watchlist[code] = create_stock_entry(code, clean_name)
                    name_to_codes.setdefault(clean_name, []).append(code)
                    stats['created'] += 1
                    print(f"Created new entry: {code} {clean_name}")
                codes = [code]

            if not codes:
                stats['not_found'].append(f"{stock_raw} -> {clean_name}")
                continue

            stats['matched'] += 1

            for code in codes:
                entry = watchlist[code]
                slots = get_all_slots(entry)

                # ---- Step 1: Check exact duplicate ----
                exact_dup = False
                for slot_num, (slot_cat, slot_concept) in slots.items():
                    if slot_cat == target_cat and slot_concept == target_concept:
                        exact_dup = True
                        break
                # Also check legacy unnumbered slot
                if (entry.get('jiuyan_category', '') == target_cat and
                        entry.get('jiuyan_concept', '') == target_concept):
                    exact_dup = True
                if exact_dup:
                    stats['skipped_exact_dup'] += 1
                    continue

                # ---- Step 2: Fill empty-concept slot ----
                empty_slot = None
                for slot_num, (slot_cat, slot_concept) in slots.items():
                    if slot_cat == target_cat and not slot_concept and target_concept:
                        empty_slot = slot_num
                        break
                if empty_slot is not None:
                    entry[f'jiuyan_concept{empty_slot}'] = target_concept
                    stats['filled_empty_concept'] += 1
                    continue

                # ---- Step 3: Legacy overlap check (only for "电力") ----
                # If a legacy (unnumbered) "电力" slot already covers this concept (keyword
                # overlap), skip — the legacy data is treated as authoritative for dedup.
                if target_cat == "电力" and target_concept:
                    legacy_cat = entry.get('jiuyan_category', '')
                    legacy_concept = entry.get('jiuyan_concept', '')
                    if legacy_cat == '电力' and concepts_overlap(legacy_concept, target_concept):
                        stats['skipped_exact_dup'] += 1
                        continue

                # ---- Step 4: Add as new slot ----
                existing_nums = set(slots.keys())
                next_num = 1
                while next_num in existing_nums:
                    next_num += 1

                if next_num > 6:
                    print(f"WARNING: {code} ({entry['name']}) has 6 slots, skipping {target_cat}/{target_concept}")
                    continue

                entry[f'jiuyan_category{next_num}'] = target_cat
                entry[f'jiuyan_concept{next_num}'] = target_concept
                stats['added_new_slot'] += 1

    # Print statistics
    print(f"\n=== Results ===")
    print(f"Matched stocks (total lookups): {stats['matched']}")
    print(f"Added new slots:          {stats['added_new_slot']}")
    print(f"Merged into existing:     {stats['merged_into_existing']}")
    print(f"Filled empty concept:     {stats['filled_empty_concept']}")
    print(f"Skipped (exact dup):      {stats['skipped_exact_dup']}")
    print(f"Created (new entries):    {stats['created']}")
    print(f"Not found ({len(stats['not_found'])}):")
    for nf in stats['not_found']:
        print(f"  - {nf}")

    print(f"\nSaving updated watchlist to {WATCHLIST_PATH}...")
    with open(WATCHLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)
    print("Done!")


if __name__ == '__main__':
    main()
