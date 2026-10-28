# 《崩坏：星穹铁道》中日两区限定卡池表现差异分析

用七麦数据的 iPhone 游戏畅销榜每日名次，比较 2023-04 至 2026-10（1.x 至 4.6）51 期新角色卡池在日区和国区的相对表现。同一期卡池在两区同一天开，两边各自比开池前爬升了多少再相减，得到"中日差"，再按卡池类型和角色特征分组比较。

本仓库是报告的代码和数据部分，报告正文另附。

## 主要结论（详见报告）
- 上半开池的 T0 新角色：开池前一周，国区名次相对日区掉得更深；开池后两边的相对位置和下半卡池一样。
- 主推角色：国区相对更好，集中在开池第一周；受 1.3 丹恒·饮月一期影响较大。
- 4.x 整体日区相对更好，主要来自国区开池拉动没有随大盘下滑而变大。
- 结论只针对 iPhone 畅销榜名次，是关联，不是因果。

## 文件夹
| 位置 | 内容 |
| --- | --- |
| `scripts/` | Python 脚本，按下面的顺序运行；`stats_tools.py` 是统计工具（置换检验、控制变量、最小二乘），只用标准库 |
| `data/raw/` | B 站 wiki 整理的卡池表（`wiki_*.tsv`）。七麦导出的名次和收入预估（`qimai_*.csv`）不公开，见下 |
| `data/manual/` | 作者的人工编码表（强度、主推、剧情打分、声优档位、角色加强），说明见其中的 `README.md` |
| `data/` | 脚本生成的中间表：期表、分析表、各期名次指标 |
| `outputs/` | 结果表和图（图的编号和报告一致） |

## 运行
需要 Python 3，以及 `openpyxl`（读 Excel）和 `matplotlib`（出图）。

| 步骤 | 脚本 | 产出 | 需要七麦原始数据 |
| --- | --- | --- | --- |
| 1 | `build_banner_table.py` | `data/phases.csv`、`data/banners_detail.csv` | 是 |
| 2 | `add_zzz_collision.py` | 和绝区零同日开池的标记 | 是 |
| 3 | `add_genshin_collision.py` | 和原神同日开池的标记 | 是 |
| 4 | `check_cloud_and_sisters.py` | 附加核对，只打印结果 | 是 |
| 5 | `build_analysis_table.py` | `data/analysis_phases.csv` | 否 |
| 6 | `compute_metrics.py` | `data/metrics_*.csv` | 是 |
| 7 | `run_tests.py` | `outputs/tests_game_7d.csv` | 否 |
| 8 | `robustness.py` | `outputs/robustness.csv` | 否 |
| 9 | `series_drift.py` | `outputs/series_drift.csv` | 是 |
| 10 | `baseline_effect.py` | `outputs/baseline_effect.csv` | 是 |
| 11 | `make_figures.py` | `outputs/fig1`–`fig4` | 是 |
| 12 | `split_pre_post.py` | `outputs/split_pre_post.csv` | 否 |

在仓库根目录运行，例如 `python scripts/run_tests.py`。仓库里已附第 1–6 步的产出，不需要原始数据也能运行第 5、7、8、12 步，复现主要比较。

## 数据说明
- 名次来自七麦数据（qimai.cn），2023-04-01 至 2026-10-24，星铁日区、国区 iPhone 畅销榜的每日最后一次快照。原始导出文件不随代码公开；从七麦导出同一时段的"游戏(畅销)"和"总榜(畅销)"名次，按各脚本开头写的文件名放进 `data/raw/`，即可重跑全部步骤。
- 卡池日期来自 B 站 wiki，2026-10-25 读取。

## AI 辅助
资料检索和整理由 Gemini、千问、Claude 分别完成并交叉验证，最终编码由作者确定；分析代码由 Claude 按作者的研究设计编写，作者在本机运行并核对结果。
