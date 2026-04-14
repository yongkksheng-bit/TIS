# TIS 数据库资产分类清单

> **报告日期**: 2026-04-14
> **数据截止**: 查询时刻数据库实时状态
> **报告级别**: 数据库资产总览（Table / Para / 胜负 / 智慧）

---

## 一、资产总览

| 指标 | 数值 | 状态 |
|------|------|------|
| `knowledge_chunks` 总数 | **101** | ✅ |
| 含向量（embedding）的 chunk | **101 / 101** | ✅ 100% 向量化 |
| 含 source_type 的 chunk | **101 / 101** | ✅ |
| 含 win_signal 的 chunk | **101 / 101** | ✅ |
| 含 token_count 的 chunk | **0 / 101** | ⚠️ 待 V3 Pipeline 首次运行后填充 |
| 含 llm_insights 的 chunk | **0 / 101** | ⚠️ `enable_llm_insights=False` 未激活 |
| 含 has_table 的 chunk | **0 / 101** | ⚠️ V3 Pipeline 尚未对历史数据重跑 |

---

## 二、按来源类型分类（source_type）

| source_type | chunk 数量 | 占比 | 向量完整度 | win_signal 完整度 |
|-------------|-----------|------|-----------|-----------------|
| `historical_tender` | **101** | 100% | 101/101 ✅ | 101/101 ✅ |

> **注**: 当前数据库仅来源类型为 `historical_tender` 的 chunk，无 `historical_bid` / `standard_cert` 类型数据。`historical_bids` 表目前仅有 1 条记录（试运行数据），尚未完成切片入库流程。

---

## 三、按胜负信号分类（win_signal）

| win_signal | chunk 数量 | 占比 | 情报价值 |
|------------|-----------|------|---------|
| `neutral`（中性） | **75** | 74.3% | ⚠️ 参考用，不含明确胜负信息 |
| `positive`（中标） | **26** | 25.7% | ✅ **高价值**，中标 DNA，可作为 RAG 正面证据 |
| `negative`（流标） | **0** | 0% | ⚠️ **数据空洞**，无流标参照，定价博弈缺少对比基准 |

> **关键缺口**: `negative = 0` 意味着双轨 RAG 的"负极"（流标教训）完全缺失。Phase 4 组装时若启用 `use_dual_track_rag=True`，将只能从 `neutral` chunk 中推断失败模式，而非真实流标案例。

---

## 四、按评分维度标签分类（scoring_dimension_tags）

> TOP10 维度（每个 chunk 可同时打多个标签）

| 排名 | 维度标签 | chunk 命中数 | 占比 | 质量评级 |
|------|---------|------------|------|---------|
| 🥇 1 | **配送能力** | 88 | 87.1% | ⭐⭐⭐⭐⭐ |
| 🥈 2 | **服务方案** | 86 | 85.1% | ⭐⭐⭐⭐⭐ |
| 🥉 3 | **食材溯源** | 76 | 75.2% | ⭐⭐⭐⭐ |
| 4 | **企业资质** | 76 | 75.2% | ⭐⭐⭐⭐ |
| 5 | **技术方案** | 69 | 68.3% | ⭐⭐⭐⭐ |
| 6 | **卫生保障** | 67 | 66.3% | ⭐⭐⭐ |
| 7 | **冷链管理** | 58 | 57.4% | ⭐⭐⭐ |
| 8 | **报价合理性** | 42 | 41.6% | ⭐⭐⭐ |
| 9 | **评分标准** | 35 | 34.7% | ⭐⭐ |
| 10 | **历史业绩** | 28 | 27.7% | ⭐⭐ |

> **注**: `报价合理性` 和 `评分标准` 标签覆盖率偏低（<50%），意味着针对这两个维度的 RAG 召回可能召回不足。

---

## 五、按内容形态分类（has_table）

| has_table | chunk 数量 | 占比 | 说明 |
|-----------|-----------|------|------|
| `True` | **0** | 0% | ⚠️ 无表格 chunk 入库 |
| `False` | **0** | 0% | ⚠️ 标签未生成 |

> **根因**: V3 Pipeline 尚未对历史数据执行。当前 101 条 chunk 来自旧的 V1/V2 pipeline（无表格解析逻辑）。Phase 4 启动前需重跑 V3 Pipeline 对历史 DOCX 文件进行重切片，届时 `has_table=True` 的 chunk 将开始填充。

---

## 六、智慧洞察分类（llm_insights）

| llm_insights 状态 | chunk 数量 | 占比 |
|------------------|-----------|------|
| 未提取（NULL） | **101** | 100% |
| 已提取但为空 | **0** | 0% |
| 有智慧洞察 | **0** | 0% |

> **激活条件**: `HistoricalChunker(enable_llm_insights=True)` 时对新切片数据调用 DeepSeek 提取 `{core_pain_points, technical_indicators, competitive_advantages}`。Phase 4 启动后应默认开启。

---

## 七、historical_tenders 表

| 字段 | 数值 |
|------|------|
| 总标书数 | **2** |
| 有中标人的标书 | **0**（winning_bidder 全部 NULL） |
| 有预算金额的标书 | **0**（budget_amount 全部 NULL） |
| 覆盖地区数 | **0**（region 全部 NULL） |
| 覆盖项目类型数 | **0**（project_type 全部 NULL） |

> **注**: 2 份标书为试运行导入样例，字段未填充完整。真实历史标书入库需通过 V3 Pipeline 的 `run_import.py` 批量处理真实 DOCX 文件。

---

## 八、historical_bids 表

| 字段 | 数值 |
|------|------|
| 总投标记录数 | **1** |
| 有 price_gap 的记录 | **1 / 1** ✅ |
| 平均 price_gap | **0.00%**（唯一记录：中标报价=中标价） |
| price_gap_bucket=winning | **1** |
| 中标数（our_bid_status=won） | **1** |
| 流标数（our_bid_status=lost） | **0** |

> **注**: 仅 1 条试运行数据（中标），price_gap=0% 表示报价正好等于中标价。**无真实 price_gap 分布数据**，`price_benchmark.py` 的 MarketHeatContext 无法从 DB 中获取真实市场竞争数据。

---

## 九、内部复盘表（internal_postmortems）

| 字段 | 数值 |
|------|------|
| 总复盘记录数 | **0** |
| 有废弃原因 | **0** |
| 有改进措施 | **0** |

> **注**: `internal_postmortems` 表尚未写入任何记录。需在 Phase 4/6 中标后分析流程完善后，才会开始积累流标复盘数据。

---

## 十、资产健康度综合评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **数据量** | ⭐⭐☆☆☆（2/5） | 仅 2 份标书，101 chunks |
| **向量完整度** | ⭐⭐⭐⭐⭐（5/5） | 101/101 100% 向量化 |
| **胜负覆盖** | ⭐⭐⭐☆☆（3/5） | positive 有数据，negative=0（严重缺口） |
| **维度覆盖** | ⭐⭐⭐⭐☆（4/5） | 10 维全覆盖，配送/服务/溯源最全 |
| **表格数据** | ⭐☆☆☆☆（1/5） | has_table 全0，160+表格待入库 |
| **智慧洞察** | ⭐☆☆☆☆（1/5） | llm_insights 全0，未激活 LLM |
| **价格情报** | ⭐☆☆☆☆（1/5） | price_gap 仅 1 条样本，无分布 |
| **复盘数据** | ⭐☆☆☆☆（1/5） | 0 条复盘记录 |

### 综合评级：⭐⭐☆☆☆（2.4/5）— 冷启动早期阶段

---

## 十一、Phase 4 行动建议

| 优先级 | 行动项 | 预期效果 |
|--------|--------|---------|
| 🔴 P0 | **重跑 V3 Pipeline** 对 2 份真实 DOCX 执行重切片，激活 `has_table=True` | 表格资产从 0→N |
| 🔴 P0 | **接入 `enable_llm_insights=True`**，DeepSeek 提取 101 条 chunk 的智慧洞察 | 智慧洞察从 0→101 |
| 🟡 P1 | **导入第 3~10 份真实历史标书**，扩大 data seed | 数据量 2→10+ |
| 🟡 P1 | **激活 negative 样本采集**：历史流标案例入库 | negative 从 0→N |
| 🟡 P1 | **填充 historical_tenders.budget_amount / winning_bidder 字段** | MarketHeatContext 有真实数据 |
| 🟢 P2 | **积累 internal_postmortems 复盘记录** | 智慧库形成闭环 |
