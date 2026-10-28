# 第 11 步：出图 → outputs/fig1_… 到 fig4_…（PNG）
#
# 需要 matplotlib（py -m pip install matplotlib）。先跑完 compute_metrics.py、robustness.py、series_drift.py。
# 运行：py scripts\make_figures.py
#
# 配色：日区一律蓝色，国区一律橙色；中日差为正（偏日本）用蓝，为负（偏中国）用橙。
# 角色名里的间隔号：数据里是"•"，图上显示成更细的"·"。

import csv
import math
import statistics as st
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # 只存图，不弹窗
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator, FixedFormatter

ROOT = Path(__file__).resolve().parents[1]
DATA, RAW, OUT = ROOT / "data", ROOT / "data" / "raw", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

JP, CN = "#2a78d6", "#eb6834"              # 日区蓝、国区橙（已用配色检查工具验证可区分）
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"

plt.rcParams.update({
    # Windows 用微软雅黑，其他系统用思源黑体
    "font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"写出 outputs/{name}")


phases = {r["phase_no"]: r for r in read_csv(DATA / "analysis_phases.csv")}
metrics = read_csv(DATA / "metrics_game_7d.csv")
main = [m for m in metrics if m["in_main"] == "1"]

# ---------- 图 1：每日名次 ----------
def daily(path):
    out = {}
    for r in read_csv(path):
        d = date.fromisoformat(r["时间"])
        if r["游戏(畅销)"] and date(2023, 4, 26) <= d <= date(2026, 10, 24):
            out[d] = int(r["游戏(畅销)"])
    return out


jp = daily(RAW / "qimai_jp_iphone_rank_2023-04-01_2026-10-25.csv")
cn = daily(RAW / "qimai_cn_iphone_rank_2023-04-01_2026-10-25.csv")
fig, ax = plt.subplots(figsize=(10, 4.2))
for series, color, label in ((jp, JP, "日区"), (cn, CN, "国区")):
    ds = sorted(series)
    ax.plot(ds, [series[d] for d in ds], color=color, linewidth=1.0, label=label)
    ax.annotate(label, (ds[-1], series[ds[-1]]), xytext=(6, 0), textcoords="offset points",
                color=INK2, va="center", fontsize=10)
ax.set_yscale("log")
ax.invert_yaxis()
ticks = [1, 2, 5, 10, 20, 50, 100, 200]
ax.yaxis.set_major_locator(FixedLocator(ticks))
ax.yaxis.set_major_formatter(FixedFormatter([str(t) for t in ticks]))
ax.yaxis.set_minor_locator(FixedLocator([]))
ax.set_ylabel("名次（对数刻度，越往上越好）")
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
for m in main:   # 底部小刻度 = 主分析 51 期的开池日
    ax.axvline(date.fromisoformat(m["start_date"]), ymin=0, ymax=0.03, color=INK2, linewidth=0.8)
ax.legend(loc="lower left", frameon=False, ncol=2)
ax.set_title("星铁 iPhone 游戏畅销榜每日名次（底部刻度 = 51 期新角色卡池开池日）", loc="left", fontsize=11)
save(fig, "fig1_rank_trend.png")

# ---------- 图 3（报告里的编号）：每期的中日差 ----------
fig, ax = plt.subplots(figsize=(10, 4.6))
xs = [date.fromisoformat(m["start_date"]) for m in main]
ys = [float(m["climb_diff"]) for m in main]
for x, y in zip(xs, ys):
    c = JP if y > 0 else CN
    ax.vlines(x, 0, y, color=c, linewidth=2)
    ax.plot(x, y, "o", color=c, markersize=5)
ax.axhline(0, color=INK2, linewidth=0.8)
for yr in ("1.x", "2.x", "3.x", "4.x"):   # 各大版本系列的平均（灰色横线）
    g = [(x, y) for x, y, m in zip(xs, ys, main) if phases[m["phase_no"]]["series"] == yr]
    ax.hlines(st.mean(y for _, y in g), min(x for x, _ in g), max(x for x, _ in g),
              color=INK2, linewidth=1.5, linestyles="--")
    ax.text(min(x for x, _ in g), -1.52, f"{yr} 平均 {st.mean(y for _, y in g):+.2f}",
            fontsize=8, color=INK2)
order = sorted(range(len(ys)), key=lambda i: ys[i])
for i in order[:3] + order[-3:]:              # 两头各标 3 期的角色名
    ax.annotate(main[i]["new_five"].replace("•", "·"), (xs[i], ys[i]), xytext=(5, 2 if ys[i] > 0 else 4),
                textcoords="offset points", fontsize=8, color=INK)
ax.set_ylim(-1.6, 0.95)
ax.set_ylabel("首周爬升差（日 − 国）")
ax.text(1.01, 0.97, "↑ 偏日本", transform=ax.transAxes, color=JP, va="top", fontsize=9)
ax.text(1.01, 0.03, "↓ 偏中国", transform=ax.transAxes, color=CN, va="bottom", fontsize=9)
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.set_title("51 期新角色卡池：首周爬升的中日差（虚线 = 各大版本系列平均；0.69 ≈ 相对多爬一倍）", loc="left", fontsize=11)
save(fig, "fig3_phase_diff.png")

# ---------- 图 2（报告里的编号）：各项比较在不同口径下的效应 ----------
rob = read_csv(OUT / "robustness.csv")
show = ["T1", "F1", "F3", "F2", "T3", "F5", "F6", "F7", "F8", "F9", "F10"]
rob = {r["编号"]: r for r in rob}
variants = [k for k in next(iter(rob.values())) if k not in ("编号", "比较") and not k.startswith(("各口径", "方向"))]
fig, ax = plt.subplots(figsize=(9, 5.4))
for row, code in enumerate(reversed(show)):
    r = rob[code]
    vals = []
    for v in variants:
        cell = r[v].rstrip("*")
        if cell:
            vals.append((v, float(cell), r[v].count("*")))
    others = [x for v, x, s in vals if v != "主分析"]
    ax.hlines(row, min(others), max(others), color=GRID, linewidth=6)          # 灰条 = 各口径范围
    ax.plot(others, [row] * len(others), "o", color=INK2, markersize=3, alpha=0.6)
    main_v = [(x, s) for v, x, s in vals if v == "主分析"][0]
    c = JP if main_v[0] > 0 else CN
    ax.plot(main_v[0], row, "o", color=c, markersize=9)
    ax.annotate(f"{main_v[0]:+.2f}{'*' * main_v[1]}", (main_v[0], row), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=8, color=INK)
    label = r["比较"].replace("•", "·") + ("（每 1 分）" if code in ("F5", "F6") else "")
    ax.text(-0.02, row, label, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=9)
ax.set_yticks([])
ax.axvline(0, color=INK2, linewidth=0.8)
ax.set_xlabel("控制大版本系列和促销后的效应（日 − 国）　← 偏中国 | 偏日本 →")
ax.set_title("各项比较：大圆点 = 主分析，灰条 = 换 10 种口径后的范围（* p<0.10，** p<0.05，*** p<0.01）",
             loc="left", fontsize=10)
save(fig, "fig2_robustness.png")

# ---------- 图 4：大版本系列漂移拆开看 ----------
yd = [r for r in read_csv(OUT / "series_drift.csv") if r["系列"] in ("1.x", "2.x", "3.x", "4.x")]
yrs = [r["系列"] for r in yd]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
for col, color, label in (("日区爬升", JP, "日区"), ("国区爬升", CN, "国区")):
    vals = [float(r[col]) for r in yd]
    a1.plot(yrs, vals, "-o", color=color, linewidth=2, markersize=6, label=label)
    a1.annotate(label, (yrs[-1], vals[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK2)
a1.set_title("首周爬升（各系列平均）", loc="left", fontsize=10)
a1.legend(frameon=False, loc="upper left")
for col, color, label in (("日区开池前名次", JP, "日区"), ("国区开池前名次", CN, "国区")):
    vals = [float(r[col]) for r in yd]
    a2.plot(yrs, vals, "-o", color=color, linewidth=2, markersize=6, label=label)
    a2.annotate(label, (yrs[-1], vals[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK2)
a2.invert_yaxis()
a2.set_title("开池前 7 天名次（各系列中位数，越往上越好）", loc="left", fontsize=10)
a2.legend(frameon=False, loc="lower left")
fig.suptitle("大版本系列漂移：4.x 偏日本，主要是日区的爬升突然变大；国区延续缓慢下降", x=0.01, ha="left", fontsize=11)
fig.tight_layout()
save(fig, "fig4_series_drift.png")
