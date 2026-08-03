# -*- coding: utf-8 -*-
"""
任务2：为 watchlist_jiuyan.json 新增"食品消费"概念分类（与 PCB/光通信 并行）
数据源：韭研公社《食品消费(241210)》产业链图（data/new_concept_ref.png，2026-07-29 提取）

流程：
1. 概念映射表（二级-三级）内置于 CONCEPT_MAP
2. 按名称匹配 watchlist 现有标的（全角A/空格归一化）
3. 未匹配的用腾讯 smartbox 接口解析代码（校验名称完全一致）
4. --apply 时写回：已存在标的追加 category/concept 对；新标的创建最小条目
5. 北交所标的跳过（行情接口不支持 bj 市场）

用法：
  python scripts/tag_food_consumption.py          # 干跑，只出匹配报告
  python scripts/tag_food_consumption.py --apply  # 实际写入
"""
import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(BASE, "watchlist_jiuyan.json")
CATEGORY = "食品消费"

# ================= 概念映射（来自韭研公社 食品消费(241210) 图） =================
CONCEPT_ROWS = {
    "食品-休闲食品": "良品铺子 三只松鼠 洽洽食品 盐津铺子 五芳斋 劲仔食品 好想你 甘源食品 有友食品 桂发祥 青岛食品 广州酒家 来伊份 金字火腿 朗源股份",
    "食品-卤制品": "绝味食品 煌上煌 紫燕食品",
    "食品-烘焙食品": "桃李面包 立高食品 元祖股份 一鸣食品 麦趣尔 南侨食品 海融科技 巴比食品",
    "食品-预制菜": "味知香 惠发食品 安井食品 全聚德 金陵饭店 春雪食品 国联水产 海欣食品",
    "食品-植物蛋白": "承德露露 养元饮品 海南椰岛 祖名股份 维维股份",
    "饮料-功能饮料": "东鹏饮料",
    "饮料-乳酸菌": "燕塘乳业 均瑶健康",
    "饮料-酒类": "酒鬼酒 皇台酒业 永顺泰 舍得酒业 水井坊",
    "饮料-果汁": "国投中鲁 安德利 国中水务",
    "乳业-常温奶": "伊利股份 皇氏集团 天润乳业 李子园 品渥食品 庄园牧场 燕塘乳业 麦趣尔",
    "乳业-鲜奶": "一鸣食品 光明乳业 三元股份 新乳业 阳光乳业",
    "乳业-奶酪": "妙可蓝多",
    "乳业-炼乳": "熊猫乳品",
    "餐饮-酒楼饭店老字号": "同庆楼 西安饮食 全聚德 广州酒家",
    "餐饮-酒店": "华天酒店 君亭酒店 锦江酒店 首旅酒店 金陵饭店",
    "免税概念-运营商": "中国中免 王府井 格力地产 海汽集团 海南发展",
    "免税概念-物业": "上海机场 白云机场 海南机场",
    "免税概念-海南": "海峡股份 海南发展 海汽集团 海南高速",
    "免税概念-曾申请/探索/合作": "南宁百货 中百集团 东百集团 海印股份 百联股份 友好集团 新华锦 居然之家 众信旅游",
    "百货零售-全国": "永辉超市 中央商场 大商股份 *ST人乐 ST步步高",
    "百货零售-上海": "徐家汇 益民集团 新世界 上海九百 百联股份",
    "百货零售-浙江": "三江购物 杭州解百 宁波中百 百大集团",
    "百货零售-山东": "家家悦 银座股份",
    "百货零售-湖南": "通程控股 友阿股份",
    "百货零售-湖北": "中百集团 武商集团 汉商集团",
    "百货零售-福建": "东百集团 新华都",
    "百货零售-南京": "中央商场 南京商旅",
    "百货零售-北京": "王府井 翠微股份 华联股份",
    "百货零售-广东": "广百股份 海印股份",
    "百货零售-辽宁": "大商股份 中兴商业 大连友谊",
    "百货零售-四川": "红旗连锁 茂业商业",
    "百货零售-其他": "国光连锁 合肥百货 重庆百货 新华百货 南宁百货 汇嘉时代 国芳集团 欧亚集团 中兴商业 彩虹股份",
    "文旅旅游-冰雪经济": "长白山 大连圣亚 三特索道 峨眉山A 亚泰集团 晶雪节能 冰山冷热 莱茵体育",
    "文旅旅游-各地区旅游": "长白山 大连圣亚 曲江文旅 西安旅游 九华旅游 丽江股份 云南旅游 峨眉山A 黄山旅游 张家界 三峡旅游 西域旅游 天目湖 西藏旅游 桂林旅游 三特索道 岭南股份 宋城演义 亚泰集团",
}
BJ_STOCKS = "美之高 海达尔 盖世食品 太湖雪 鸿智科技"  # 北交所，行情接口不支持，跳过

# 已逐一经 smartbox 代码直连验证的更名映射（2026-07-29 验证）
# 格式: 图中名称 -> (代码, 现用名)
MANUAL_ALIAS = {
    "格力地产": ("600185", "珠免集团"),
    "西安旅游": ("000610", "*ST西旅"),
    "重庆百货": ("600729", "重百集团"),
    "合肥百货": ("000417", "合百集团"),
    "居然之家": ("000785", "居然智家"),
    "莱茵体育": ("000558", "天府文旅"),
    "海南椰岛": ("600238", "*ST椰岛"),
    "宋城演义": ("300144", "宋城演艺"),  # 图中"演义"为笔误
}

# 退市/退市整理期标的：不新增（行情与交易均无意义）
DELISTED = {"*ST人乐": "002336 已退市（人乐退）"}

VALID_PREFIXES = ("000", "001", "002", "003", "300", "301",
                  "600", "601", "603", "605", "688", "689")


def norm_name(name: str) -> str:
    """归一化公司名：全角A→A、去空格、*统一"""
    n = (name or "").strip()
    n = n.replace("Ａ", "A").replace("Ｂ", "B")
    n = n.replace(" ", "").replace("　", "")
    return n


def build_concept_map():
    """公司名 -> [概念列表]（去重保序）"""
    m = {}
    for concept, names in CONCEPT_ROWS.items():
        for name in names.split():
            m.setdefault(name, [])
            if concept not in m[name]:
                m[name].append(concept)
    return m


def _decode_name(raw: str) -> str:
    """smartbox 返回的名称含 \\uXXXX 字面量，需二次解码"""
    if "\\u" in raw:
        try:
            return raw.encode("utf-8").decode("unicode_escape")
        except Exception:
            return raw
    return raw


def _strip_st(n: str) -> str:
    n = norm_name(n)
    if n.startswith("*ST"):
        return n[3:]
    if n.startswith("ST"):
        return n[2:]
    return n


def _name_match(target: str, candidate: str) -> bool:
    """精确 或 ST更名/简称变更（互相包含且较短者>=2字）"""
    t, c = _strip_st(target), _strip_st(candidate)
    if t == c:
        return True
    short, long_ = (t, c) if len(t) <= len(c) else (c, t)
    return len(short) >= 2 and short in long_


def _smartbox_query(q: str):
    """单次查询，返回 [(code, market, name)]"""
    url = "https://smartbox.gtimg.cn/s3/?v=2&q=" + urllib.parse.quote(q) + "&t=gp"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("gbk", errors="replace")
    except Exception:
        return []
    payload = text.split("=", 1)[-1].strip().strip(";").strip('"')
    if payload == "N":
        return []
    out = []
    for item in payload.split("^"):
        parts = item.split("~")
        if len(parts) >= 3:
            out.append((parts[1], parts[0], _decode_name(parts[2])))
    return out


def resolve_code_smartbox(name: str):
    """按名称解析 A 股代码：精确 → 去ST前缀 → 逐字缩短（处理 ST摘帽/更名）"""
    queries = [name, _strip_st(name)]
    q = _strip_st(name)
    while len(q) > 2:
        q = q[:-1]
        queries.append(q)
    seen = set()
    for q in queries:
        if q in seen or not q:
            continue
        seen.add(q)
        for code, market, sname in _smartbox_query(q):
            if not (code.startswith(VALID_PREFIXES) and len(code) == 6):
                continue
            if _name_match(name, sname):
                return code, f"{market}（匹配为 {sname}）"
        time.sleep(0.1)
    return None, "未找到同名/可确认更名的标的"


def main():
    apply_mode = "--apply" in sys.argv
    concept_map = build_concept_map()
    total_names = len(concept_map)
    print(f"[映射] 图中公司 {total_names} 家（不含北交所 {len(BJ_STOCKS.split())} 家），概念 {len(CONCEPT_ROWS)} 个")

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 名称索引（归一化）
    name_index = {}
    for code, info in data.items():
        if isinstance(info, dict) and info.get("name"):
            name_index.setdefault(norm_name(info["name"]), code)

    matched_existing = []   # (name, code, concepts)
    resolved_new = []       # (name, code, note, concepts)
    unmatched = []          # (name, reason)

    for name, concepts in concept_map.items():
        if name in DELISTED:
            unmatched.append((name, f"跳过：{DELISTED[name]}"))
            continue
        code = name_index.get(norm_name(name))
        if code:
            matched_existing.append((name, code, concepts))
            continue
        # 已验证的更名映射优先
        if name in MANUAL_ALIAS:
            alias_code, alias_name = MANUAL_ALIAS[name]
            if alias_code in data:
                matched_existing.append((name, alias_code, concepts))
            else:
                resolved_new.append((name, alias_code, f"sh/sz（已验证更名: {alias_name}）", concepts))
            continue
        code2, msg = resolve_code_smartbox(name)
        time.sleep(0.15)
        if code2:
            resolved_new.append((name, code2, msg, concepts))
        else:
            unmatched.append((name, msg))

    print(f"\n[匹配结果]")
    print(f"  已在 watchlist: {len(matched_existing)} 家")
    print(f"  新增解析成功: {len(resolved_new)} 家")
    for name, code, note, concepts in resolved_new:
        print(f"    + {name} -> {code} {note} | {' | '.join(concepts)}")
    print(f"  未匹配: {len(unmatched)} 家")
    for name, msg in unmatched:
        print(f"    - {name}: {msg}")

    if not apply_mode:
        print("\n[干跑模式] 未写入。确认无误后加 --apply 执行写入。")
        return 0

    # ===== 写入 =====
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = WATCHLIST + f".bak_food_{ts}"
    shutil.copy2(WATCHLIST, backup)
    print(f"\n[备份] {backup}")

    today = datetime.now().strftime("%Y-%m-%d")
    appended = 0
    created = 0

    def add_pairs(info, concepts):
        """向一只标的追加 食品消费 category/concept 对，返回新增对数"""
        # 收集已有对，去重
        existing = set()
        max_i = 0
        for i in range(1, 10):
            cat = str(info.get(f"jiuyan_category{i}", "")).strip()
            con = str(info.get(f"jiuyan_concept{i}", "")).strip()
            if cat:
                existing.add((cat, con))
                max_i = max(max_i, i)
        added = 0
        for concept in concepts:
            if (CATEGORY, concept) in existing:
                continue
            max_i += 1
            if max_i > 9:
                break
            info[f"jiuyan_category{max_i}"] = CATEGORY
            info[f"jiuyan_concept{max_i}"] = concept
            existing.add((CATEGORY, concept))
            added += 1
        info["updated_at"] = today
        return added

    for name, code, concepts in matched_existing:
        appended += add_pairs(data[code], concepts)

    for name, code, note, concepts in resolved_new:
        if code in data:
            appended += add_pairs(data[code], concepts)
            continue
        info = {
            "name": name,
            "sector": "",
            "business_summary": "",
            "concept_boards": [],
            "industry_boards": [],
            "primary_source": "韭研公社-食品消费(241210)",
            "updated_at": today,
        }
        add_pairs(info, concepts)
        data[code] = info
        created += 1

    with open(WATCHLIST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[写入完成]")
    print(f"  已存在标的追加标签对: {appended} 条（{len(matched_existing)} 家）")
    print(f"  新增标的: {created} 家")
    print(f"  watchlist 总标的: {len(data)} 只")

    # 多概念公司示例
    multi = [(n, c) for n, _, c in matched_existing if len(c) > 1] + \
            [(n, c) for n, _, _, c in resolved_new if len(c) > 1]
    print(f"\n[多细分概念公司] {len(multi)} 家，示例：")
    for n, c in multi[:10]:
        print(f"  {n}: {' | '.join(c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
