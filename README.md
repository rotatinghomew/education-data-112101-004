# 教育服务投诉处理时效与积压预测

本地资料用于理解投诉处理时效与积压变化所涉及的记录关系。文件均为合成数据，标识符不对应真实个人、机构或账号。

## 目录

- `data/`：UTF-8 编码、首行为字段名的逗号分隔资料。空字段表示资料未提供，不代表数值为零或业务状态已否定。
- `analysis/`：可重跑的分析包（仅 Python 标准库），把投诉类别、证据完整度、关联反馈、处理阶段、历史到达与排班容量组合成积压压力与人员安排估计。
- `tests/`：资料可读性测试与分析口径单元测试。
- `docs/methodology.md`：完整口径与方法说明（等待归属、去重、预测情景、产能与建议的追溯方式）。
- `outputs/`：分析产物（CSV 明细、Markdown 摘要、建议审计 JSON），随数据更新重跑覆盖。

日期使用 ISO 8601 写法；时间字段为空时表示该记录没有提供时间。金额和计数字段以文本保存，具体解释须结合字段名及记录上下文。

## 运行与检查

需要 Python 3.11 或更高版本，无第三方运行依赖。

```bash
# 生成/刷新分析结果
python3 -I run_analysis.py --data-dir data --output-dir outputs

# 运行全部测试（隔离模式入口）
python3 -I run_tests.py
# 或使用 unittest 发现
python3 -m unittest discover -s tests
```

## 分析能力概览

- **当前队列**：区分“等内部判断”与“等消费者补件”，内部处理天数与外部等待天数分别累计；无事件个案保持内部待办并标记缺口，不会误判为外部等待或低风险。
- **证据与去重**：被取代证据不参与完整度判断；仅 confirmed 的同户关联自动并簇，未复核的相似措辞进入复核队列；影响范围按独立家庭去重，重复反馈不重复计数。
- **到达与产能**：历史到达按趋势+残差给出低/中/高预测；排班人数不等于产能，人均产能由各类别历史办案区间估计，截断样本与无观察团队均显式标注不确定性。
- **多周期投影**：未来若干 ISO 周按三情景滚动模拟积压结转、补件回流与产能消耗，队列恒等式可逐行核对。
- **优先级与建议**：优先级为供核查的加权估计，资料缺失走保守下限；每条人员建议附带由到达、处理与状态事实组成的审计链（`recommendation_audit.json`）。

## 数据文件

- `data/complaints.csv`
- `data/events.csv`
- `data/links.csv`
- `data/evidence.csv`
- `data/arrivals.csv`
- `data/capacity.csv`

## 输出文件（`outputs/`）

| 文件 | 内容 |
|---|---|
| `case_states.csv` | 每个个案的当前阶段、等待归属与内/外部耗时拆解 |
| `evidence_summary.csv` | 证据综合状态（含取代关系） |
| `household_clusters.csv` / `link_review_queue.csv` | 家庭簇去重结果与待复核关联 |
| `arrival_forecast.csv` | 各类别低/中/高到达预测与依据 |
| `throughput_estimate.csv` | 历史办案天数与人均周产能三档估计 |
| `current_backlog.csv` | 分类别内部/外部积压与独立家庭数 |
| `priority_ranking.csv` | 未结个案优先级、因子贡献与提示标记 |
| `backlog_projection.csv` | 分周期分情景的积压滚动投影 |
| `staffing_recommendation.csv` | 人员安排建议与相对已排人数的缺口 |
| `data_quality_flags.csv` | 数据缺口、口径警告与保守处理说明 |
| `recommendation_audit.json` | 每条建议的触发事实链与参数 |
| `summary.md` | 面向主管的摘要报告 |
