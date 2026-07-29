# 版本管理文档

> **文档类型**：版本管理  
> **维护路径**：`E:\04_实战资料\report_gen\docs\VERSION.md`  
> **关联文件**：`config.json`

---

## 版本概览

| 版本 | 日期 | 状态 | 主要变更 |
|------|------|------|---------|
| v8.0 | 2026-06-17 | 当前 | 模块化脚本架构初始化，TOP5 强制 5 条，表头统一深蓝 `#4472C4` |
| v7.0 | 2026-06-16 | 已归档 | 首次报告生成，TOP5 仅输出 1 条，表头颜色混用 |

---

## v8.0 版本说明

### 新增模块（8 个独立单元）

| 模块 | 文件 | 职责 | 扩展接口 |
|------|------|------|---------|
| 配置中心 | `config.json` | 全局参数、板块列表、颜色定义 | 新增板块直接改 JSON |
| 数据加载 | `modules/data_loader.py` | 从 CSV/JSON/DataFrame 读取原始数据 | 支持自定义数据源适配器 |
| 评分计算 | `modules/scorer.py` | D1-D8 维度打分 + 概念叠加分 | 新增维度继承 ScorerBase |
| 排名生成 | `modules/ranker.py` | 概念排名 + TOP5 生成 | 自定义排名策略继承 RankerBase |
| 样式渲染 | `modules/styler.py` | Excel 表头颜色、对齐、字体 | 新增主题继承 StyleBase |
| 报告组装 | `modules/reporter.py` | 将所有数据组装到各 Sheet | 新增输出格式继承 ReporterBase |
| 验证器 | `modules/validator.py` | 交叉验证清单（5 项） | 新增验证规则继承 ValidatorBase |
| 主入口 | `main.py` | 编排流程、命令行参数 | 支持 CLI 和 API 两种调用 |

### 版本变更点（v7 → v8）

| 变更项 | v7 状态 | v8 修复/升级 | 影响模块 |
|--------|---------|-------------|---------|
| TOP5 数据行数 | 仅 1 条（炬芯-U） | 强制 5 条，去重排序 | `ranker.py` |
| 表头颜色 | 浅蓝 `#B4C7E7` / 中蓝 `#5B9BD5` 混用 | 统一深蓝 `#4472C4` + 白字 | `styler.py` |
| 字体颜色 | 部分表头默认黑字 | 全部表头强制白字 `#FFFFFF` | `styler.py` |
| 六维融合 | 无 | 引入 equity-researcher 六维分析作为前置筛选 | `data_loader.py` |
| TOP5 板块覆盖 | 无明确要求 | 鼓励跨 3+ 板块，同板块最多 2 个 | `ranker.py` |
| 复核机制 | 无 | 新增 5 项交叉验证清单 + 异常处理表 | `validator.py` |
| 模块化架构 | 单文件脚本 | 8 模块独立，支持热插拔扩展 | 全部 |

---

## 版本变更日志（按时间倒序）

### 2026-06-17 v8.0
- [x] 初始化模块化脚本架构
- [x] 修复 TOP5 仅输出 1 条的问题 → 强制填充 5 条
- [x] 统一表头颜色为 `#4472C4` + 白字 `#FFFFFF`
- [x] 引入六维加权企业评分作为前置筛选（得分 ≥ 60 入池）
- [x] 新增 TOP5 板块覆盖规则（同板块 ≤ 2 个）
- [x] 新增 5 项交叉验证清单
- [x] 设计扩展接口（Base 类），支持后续新增板块/维度/验证规则

### 2026-06-16 v7.0
- [x] 首次生成韭研概念打分报告
- [x] 支持 D1-D8 八维评分 + 概念叠加分
- [x] 输出 1-概念总排名 / 2-详细个股排名 / 3-TOP5 / 板块明细

---

## 扩展接口规范

### 新增评分维度

```python
from modules.scorer import ScorerBase

class D9MyDimension(ScorerBase):
    def compute(self, stock_data: dict) -> tuple[int, str]:
        score = self._calculate(stock_data)
        detail = f"D9维度={score}"
        return score, detail
```

在 `config.json` 的 `scoring.dimensions` 中追加 `"D9MyDimension"`，主入口会自动加载。

### 新增板块

```python
# 在 config.json 的 sheets.sectors 中追加板块名称
"sectors": [..., "新材料", "卫星互联网"]
```

在 `data/` 目录下放置对应板块的数据文件（如 `新材料_20260617.csv`），`data_loader.py` 会自动扫描匹配。

### 新增验证规则

```python
from modules.validator import ValidatorBase

class MyValidator(ValidatorBase):
    def validate(self, workbook) -> tuple[bool, str]:
        # 验证逻辑
        return True, "通过"
```

在 `config.json` 的 `validation.cross_checks` 中追加规则名称，主入口会自动调用。

---

## 兼容性说明

| 版本 | 向下兼容 | 数据格式 | 配置文件 |
|------|---------|---------|---------|
| v8.0 | 不兼容 v7（单文件→模块化） | 新增 `data/` 目录结构 | 新增 `config.json` |
| v8.1（计划中） | 兼容 v8.0 | 保持 CSV + JSON | 追加字段即可 |

---

*文档维护：量化选股系统*  
*最后更新：2026-06-17*
