# 投诉积压与排班分析摘要（自动生成，可重跑）

- 分析基准日：`2026-02-23`
- 投影周期：2026-W09, 2026-W10, 2026-W11, 2026-W12
- 估计为供人员核查的区间值；资料缺失按保守口径处理，不等于低风险

## 1. 当前队列

- 未结个案 14 件：等内部判断 9 件，等消费者补件 5 件；已结 5 件

| 类别 | 内部待办 | 外部等待 | 未结独立家庭 | 负责团队 | 路由依据 |
|---|---|---|---|---|---|
| advice | 1 | 0 | 1 | T-3 | historical_closed_cases_only |
| refund | 1 | 5 | 6 | T-1 | observed_on_open_cases |
| renewal | 7 | 0 | 6 | T-2 | observed_on_open_cases |

## 2. 到达预测（每周期件数，低/中/高）

| 类别 | 依据 | 低 | 中 | 高 | 独立家庭(中) | 历史趋势斜率 |
|---|---|---|---|---|---|---|
| advice | trend | 8 | 19 | 22 | 16 | 1.4 |
| refund | trend | 12 | 24 | 28 | 19 | 1.4 |
| renewal | no_history | 7 | 7 | 7 | 7 | 0.0 |

## 3. 历史办案过程与人均周产能

| 团队 | 专长 | 依据 | 单件天数(低/中/高) | 人均周产能(低/中/高) | 备注 |
|---|---|---|---|---|---|
| T-1 | refund | censored_segments_only | 0.71/4.29/8.36 | 0.42/0.99/6.68 | 仅观察到未结案的截断区间，高端天数已放大处理 |
| T-2 | advice | censored_segments_only | 1.29/5.77/10.74 | 0.33/0.74/3.67 | 仅观察到未结案的截断区间，高端天数已放大处理 |
| T-3 | unknown | closed_cases | 3.0/3/3.5 | 1.0/1.42/1.58 |  |

## 4. 分周期积压投影（期末内部积压）

| 周期 | 类别 | 团队 | 情景 | 新增 | 补件回流 | 内部需求 | 估计产能 | 期末内部积压 | 期末外部等待 | 标记 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-W09 | advice | T-3 | pessimistic | 22 | 0 | 23 |  | 23 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W09 | advice | T-3 | central | 19 | 0 | 20 |  | 20 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W09 | advice | T-3 | optimistic | 8 | 0 | 9 |  | 9 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W10 | advice | T-3 | pessimistic | 22 | 0 | 45 |  | 45 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W10 | advice | T-3 | central | 19 | 0 | 39 |  | 39 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W10 | advice | T-3 | optimistic | 8 | 0 | 17 |  | 17 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W11 | advice | T-3 | pessimistic | 22 | 0 | 67 |  | 67 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W11 | advice | T-3 | central | 19 | 0 | 58 |  | 58 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W11 | advice | T-3 | optimistic | 8 | 0 | 25 |  | 25 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W12 | advice | T-3 | pessimistic | 22 | 0 | 89 |  | 89 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W12 | advice | T-3 | central | 19 | 0 | 77 |  | 77 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W12 | advice | T-3 | optimistic | 8 | 0 | 33 |  | 33 | 0 | no_planned_capacity;capacity_not_quantifiable |
| 2026-W09 | refund | T-1 | pessimistic | 28 | 5 | 34 | 0.84 | 33 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W09 | refund | T-1 | central | 24 | 5 | 30 | 1.98 | 28 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W09 | refund | T-1 | optimistic | 12 | 5 | 18 | 13.36 | 5 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W10 | refund | T-1 | pessimistic | 28 | 0 | 61 | 0.84 | 60 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W10 | refund | T-1 | central | 24 | 0 | 52 | 1.98 | 50 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W10 | refund | T-1 | optimistic | 12 | 0 | 17 | 13.36 | 4 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W11 | refund | T-1 | pessimistic | 28 | 0 | 88 | 0.84 | 87 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W11 | refund | T-1 | central | 24 | 0 | 74 | 1.98 | 72 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W11 | refund | T-1 | optimistic | 12 | 0 | 16 | 13.36 | 3 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W12 | refund | T-1 | pessimistic | 28 | 0 | 115 | 0.84 | 114 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W12 | refund | T-1 | central | 24 | 0 | 96 | 1.98 | 94 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W12 | refund | T-1 | optimistic | 12 | 0 | 15 | 13.36 | 2 | 0 | capacity_extrapolated_from_2026-W08 |
| 2026-W09 | renewal | T-2 | pessimistic | 7 | 0 | 14 | 0.99 | 13 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W09 | renewal | T-2 | central | 7 | 0 | 14 | 2.22 | 12 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W09 | renewal | T-2 | optimistic | 7 | 0 | 14 | 11.01 | 3 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W10 | renewal | T-2 | pessimistic | 7 | 0 | 20 | 0.99 | 19 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W10 | renewal | T-2 | central | 7 | 0 | 19 | 2.22 | 17 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W10 | renewal | T-2 | optimistic | 7 | 0 | 10 | 11.01 | 0 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W11 | renewal | T-2 | pessimistic | 7 | 0 | 26 | 0.99 | 25 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W11 | renewal | T-2 | central | 7 | 0 | 24 | 2.22 | 22 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W11 | renewal | T-2 | optimistic | 7 | 0 | 7 | 11.01 | 0 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W12 | renewal | T-2 | pessimistic | 7 | 0 | 32 | 0.99 | 31 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W12 | renewal | T-2 | central | 7 | 0 | 29 | 2.22 | 27 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |
| 2026-W12 | renewal | T-2 | optimistic | 7 | 0 | 7 | 11.01 | 0 | 0 | capacity_extrapolated_from_2026-W08;arrival_forecast_from_case_log_fallback |

## 5. 人员安排建议（相对最近一期已排人数）

| 类别 | 团队 | 情景 | 已排人数 | 跟上来量需人 | 清积压加人 | 建议人数 | 缺口 | 依据标记 |
|---|---|---|---|---|---|---|---|---|
| advice | T-3 | pessimistic | 未知 | 22.0 | 0.25 | 22 | 无法比较 | team_missing_from_capacity_schedule |
| advice | T-3 | central | 未知 | 13.38 | 0.18 | 14 | 无法比较 | team_missing_from_capacity_schedule |
| advice | T-3 | optimistic | 未知 | 5.06 | 0.16 | 5 | 无法比较 | team_missing_from_capacity_schedule |
| refund | T-1 | pessimistic | 2 | 69.64 | 0.6 | 70 | 68 | throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |
| refund | T-1 | central | 2 | 25.51 | 0.25 | 26 | 24 | throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |
| refund | T-1 | optimistic | 2 | 1.98 | 0.04 | 2 | 0 | throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |
| renewal | T-2 | pessimistic | 3 | 21.21 | 5.3 | 27 | 24 | arrival_forecast_from_case_log_fallback;throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |
| renewal | T-2 | central | 3 | 9.46 | 2.36 | 12 | 9 | arrival_forecast_from_case_log_fallback;throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |
| renewal | T-2 | optimistic | 3 | 1.91 | 0.48 | 2 | -1 | arrival_forecast_from_case_log_fallback;throughput_based_on_censored_segments;planned_people_latest_known_2026-W08 |

## 6. 数据缺口与质量标记

- 缺口（gap）3 条，警告（warning）3 条，详见 `data_quality_flags.csv`
  - [gap] no_events · complaint:C-3 — 时间线标记: no_events
  - [gap] arrival_category_missing · category:renewal — 到达汇总缺少该类别，预测仅来自投诉台账提交数（弱兜底），台账样本 7 件
  - [gap] team_missing_from_capacity_schedule · team:T-3 — 该团队有处置事件但无任何排班人数，产能无法量化
  - [warning] specialty_label_mismatch · team:T-2 — 排班专长标注为 advice，实际处置类别为 ['renewal']
  - [warning] censored_segments_only · team:T-1 — 只有未结案截断样本，高端办案天数已放大，见产能估计表
  - [warning] censored_segments_only · team:T-2 — 只有未结案截断样本，高端办案天数已放大，见产能估计表

## 7. 重跑方式

更新 `data/` 后执行：

```bash
python3 -I run_analysis.py --data-dir data --output-dir outputs
```
