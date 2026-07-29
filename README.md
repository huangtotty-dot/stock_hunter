# stock_hunter

韭研概念打分报告生成器 — 以 watchlist_jiuyan.json 为数据源，自动获取实时行情，生成多维度概念评分 Excel 报告。

## 功能

- 加载韭研自选股数据 (watchlist_jiuyan.json)
- 从腾讯财经获取实时/历史行情
- D1-D9 多维度评分 + 概念叠加分
- 生成概念总排名、详细个股排名、TOP5、板块明细
- 输出为格式化 Excel 报告

## 用法

```bash
python main.py [--date YYYYMMDD] [--data-dir ./data] [--output ./output]
```

## 配置

复制 `config.sample.json` 为 `config.json`，按需修改配置。

## 项目结构

```
stock_hunter/
├── main.py                    # 主入口
├── config.json                # 配置（含飞书密钥，已 gitignore）
├── config.sample.json         # 配置示例
├── watchlist_jiuyan.json      # 韭研自选股数据源
├── modules/
│   ├── data_loader.py         # 数据加载
│   ├── market_data.py         # 行情获取
│   ├── scorer.py              # 评分计算
│   ├── ranker.py              # 排名生成
│   ├── reporter.py            # 报告组装
│   ├── styler.py              # Excel 样式渲染
│   ├── validator.py           # 报告验证
│   └── push_feishu.py         # 飞书推送
├── data/                      # 概念 CSV + 行情快照
├── templates/                 # Excel 模板
├── output/                    # 生成报告（gitignored）
└── docs/                      # 文档
```
