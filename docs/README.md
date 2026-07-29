# 韭研概念打分报告生成器

> **版本**：v8.0  
> **路径**：`E:\04_实战资料\report_gen\`  
> **用途**：每日自动生成韭研概念打分报告 Excel（含概念总排名、详细个股排名、TOP5、板块明细）

---

## 目录结构

```
E:\04_实战资料\report_gen\
├── main.py              # 主入口：编排全部流程
├── config.json          # 全局配置：板块、颜色、评分参数
├── modules\
│   ├── data_loader.py   # 数据加载：从 data/ 目录读取 CSV/JSON
│   ├── scorer.py        # 评分计算：D1-D8 + 概念叠加分
│   ├── ranker.py        # 排名生成：概念排名 + TOP5 去重跨板块
│   ├── styler.py        # 样式渲染：表头颜色 #4472C4 + 白字
│   ├── reporter.py      # 报告组装：将所有数据写入各 Sheet
│   └── validator.py     # 验证器：5 项交叉验证清单
├── data\
│   ├── 概念总排名.csv   # 概念板块汇总数据
│   ├── 详细个股排名.csv # 细分概念 + 个股数据
│   └── {板块名}.csv      # 各板块明细数据（如 PCB.csv、半导体.csv）
├── templates\
│   └── template_v8.xlsx # 可选：Excel 模板（留空结构）
├── output\
│   └── 韭研概念打分报告_YYYYMMDD_v8.xlsx  # 输出文件
├── docs\
│   ├── VERSION.md       # 版本管理文档
│   └── README.md        # 本文件
└── tests\
    └── test_validator.py # 单元测试（可选）
```

---

## 快速开始

### 1. 准备数据

将每日原始数据放入 `data/` 目录：

```
data/
├── 概念总排名.csv      # 概念板块汇总（用于 Sheet 1）
├── 详细个股排名.csv    # 细分概念 + 个股（用于 Sheet 2）
├── PCB.csv            # PCB 板块明细（用于 Sheet PCB）
├── 半导体.csv          # 半导体板块明细
└── ...
```

CSV 格式要求：
- 第一行为表头
- 包含字段：排名、板块、细分、代码、名称、得分、D1涨停、D2强度...D8活跃、成交额等
- 编码：UTF-8（带 BOM）或 GBK

### 2. 运行生成

```bash
cd E:\04_实战资料\report_gen
python main.py
```

输出文件：`output/韭研概念打分报告_YYYYMMDD_v8.xlsx`

### 3. 自定义配置

修改 `config.json`：

```json
{
  "sheets": {
    "sectors": ["PCB", "半导体", "电池", "光刻机", "新材料"]
  },
  "style": {
    "header_bg": "4472C4",
    "header_font": "FFFFFF"
  }
}
```

---

## 模块详解

### data_loader.py

职责：从 `data/` 目录读取 CSV/JSON，转换为 Pandas DataFrame。

关键接口：
```python
from modules.data_loader import DataLoader
loader = DataLoader(data_dir="data")
df_summary = loader.load_concept_summary()     # 加载概念总排名
df_detail = loader.load_detail_ranking()      # 加载详细个股排名
df_sector = loader.load_sector("PCB")         # 加载指定板块
```

扩展：新增数据源时，继承 `DataLoaderBase` 实现 `load()` 方法。

### scorer.py

职责：对每只标的计算 D1-D8 维度得分 + 概念叠加分。

关键接口：
```python
from modules.scorer import ConceptScorer
scorer = ConceptScorer()
score, details = scorer.compute(stock_data)
# details: {"D1涨停": 8, "D2强度": 6, ..., "概念叠加": 3}
```

### ranker.py

职责：按总得分排序，生成 TOP5（去重 + 跨板块覆盖）。

关键接口：
```python
from modules.ranker import Top5Ranker
ranker = Top5Ranker(max_same_sector=2, min_diversity=3)
top5_list = ranker.select(stock_list)  # 返回 5 条记录
```

### styler.py

职责：统一 Excel 表头样式（`#4472C4` + 白字）。

关键接口：
```python
from modules.styler import ExcelStyler
styler = ExcelStyler()
styler.apply_header_style(ws, row=1)   # 对指定行应用表头样式
styler.apply_title_style(ws, row=2)   # 对标题行应用标题样式
```

### reporter.py

职责：将所有数据组装到 Excel 各 Sheet。

关键接口：
```python
from modules.reporter import ReportBuilder
builder = ReportBuilder(config_path="config.json")
builder.build_all(df_summary, df_detail, top5_list, sector_data)
builder.save(output_path)
```

### validator.py

职责：生成后执行 5 项交叉验证。

关键接口：
```python
from modules.validator import ReportValidator
validator = ReportValidator(checks=["top5_count", "header_color", "score_consistency"])
ok, msg = validator.validate(workbook)
```

---

## 版本迭代

详见 `docs/VERSION.md`。

| 版本 | 关键变更 |
|------|---------|
| v8.0 | 模块化架构、TOP5 强制 5 条、表头统一 `#4472C4` |
| v8.1（计划） | 支持从数据库直接读取数据、新增动态图表 |
| v9.0（计划） | 引入 AI 自动概念分类、支持多语言输出 |

---

## 常见问题

**Q: 新增一个板块（如 "卫星互联网"）需要改哪些文件？**  
A: 只需两步：
1. 在 `config.json` 的 `sheets.sectors` 中追加 `"卫星互联网"`
2. 在 `data/` 目录下放置 `卫星互联网.csv`

**Q: 表头颜色想换成其他颜色？**  
A: 修改 `config.json` 的 `style.header_bg` 和 `style.header_font`，无需改代码。

**Q: 评分维度想从 D1-D8 扩展到 D1-D10？**  
A: 
1. 在 `config.json` 的 `scoring.dimensions` 追加新维度
2. 在 `scorer.py` 中新增对应的计算函数（参考现有 D1-D8 实现）

---

*维护：量化选股系统*  
*版本：v8.0*
