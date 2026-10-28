# 第 10 步：起点效应 → outputs/baseline_effect.csv，并打印结果
#
# 现象：开池前名次越低，开池那一周爬得越多；这个关系日区比国区强得多。
# 问题：这是真实的玩家行为（日服开池受平时冷热的牵制更小），还是测量造成的假象？
# 可能的假象有两个，这个脚本逐一排除：
#   1. 天花板：日区开池后常被"钉"在第 1 名，爬升就机械地跟着起点走。
#      → 只看第 3–14 天（名次大多已离开第 1），以及看登顶后停留多久（"轨迹"）。
#   2. 均值回归：开池前 7 天的名次有随机波动，碰巧排得差的，之后自然反弹，看起来像"起点低爬得多"。
#      → 把基准换成 14 天（摊薄波动），或用另一段不重叠的日子（开池前第 8–14 天）来量起点。
#
# 结论（10-28）：不加控制时日区的起点效应明显比国区强；但控制大版本系列后两边几乎一样，
# 说明差别来自系列之间的长期变化，不是同一时期里两边玩家行为不同。
#
# 读法："每低一倍" = 开池前名次从第 20 名变成第 40 名，首周爬升多多少（取对数后的单位）。
# 区间：把 51 期有放回地重抽 4000 次，每次重算，取中间 95%（自助法）；区间不含 0 = 不像巧合。
#
# 先跑完 compute_metrics.py 的主分析设置。运行：py scripts\baseline_effect.py

N_BOOT = 4000

import csv
import math
import random
import statistics as st
from datetime import date, timedelta

from run_tests import OUT, ROOT
from stats_tools import ols

RAW = ROOT / "data" / "raw"
DATA_END = date(2026, 10, 24)
LN2 = math.log(2)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_ranks(path):
    out = {}
    for r in read_csv(path):
        d = date.fromisoformat(r["时间"])
        if r["游戏(畅销)"] and d <= DATA_END:
            out[d] = int(r["游戏(畅销)"])
    return out


ranks = {"jp": load_ranks(RAW / "qimai_jp_iphone_rank_2023-04-01_2026-10-25.csv"),
         "cn": load_ranks(RAW / "qimai_cn_iphone_rank_2023-04-01_2026-10-25.csv")}
coding = {r["phase_no"]: r for r in read_csv(ROOT / "data" / "analysis_phases.csv")}
allm = read_csv(ROOT / "data" / "metrics_game_7d.csv")
starts = sorted(date.fromisoformat(r["start_date"]) for r in allm)
main = []
for r in allm:
    if r["in_main"] != "1":
        continue
    row = {"name": r["new_five"], "series": coding[r["phase_no"]]["series"], "promo": coding[r["phase_no"]]["promo"]}
    s = date.fromisoformat(r["start_date"])
    prev = max([d for d in starts if d < s], default=None)
    row["gap_prev"] = (s - prev).days if prev else 999
    for m in ("jp", "cn"):
        R = ranks[m]
        week = [R[s + timedelta(days=k)] for k in range(7) if s + timedelta(days=k) in R]
        wk = st.mean(math.log(v) for v in week)
        pre7 = st.median(R[s - timedelta(days=k)] for k in range(1, 8))
        pre14 = st.median(R[s - timedelta(days=k)] for k in range(1, 15))
        far = st.median(R[s - timedelta(days=k)] for k in range(8, 15))    # 开池前第 8–14 天
        row[m] = {
            "x7": math.log(pre7), "x14": math.log(pre14), "xfar": math.log(far),
            "climb": float(r[f"{m}_climb"]),                 # 主指标：7 天基准
            "climb14": math.log(pre14) - wk,                 # 14 天基准
            "late": float(r[f"{m}_late_climb"]),             # 第 3–14 天
            "top1": int(r[f"{m}_top1_days"]), "mean_rank": float(r[f"{m}_mean_rank"]),
        }
    main.append(row)


def slope(rows, m, y, x, controls=False):
    ys = [r[m][y] for r in rows]
    cols = [[r[m][x] for r in rows]]
    if controls:   # 控制大版本系列和促销
        levels = sorted({r["series"] for r in rows})
        cols += [[1.0 if r["series"] == lv else 0.0 for r in rows] for lv in levels[1:]]
        cols.append([float(r["promo"]) for r in rows])
    return ols(ys, cols)[1] * LN2


def check(label, rows, y, x, controls=False):
    jp, cn = slope(rows, "jp", y, x, controls), slope(rows, "cn", y, x, controls)
    rnd = random.Random(1)
    diffs = []
    for _ in range(N_BOOT):
        s = [rnd.choice(rows) for _ in rows]
        try:
            diffs.append(slope(s, "jp", y, x, controls) - slope(s, "cn", y, x, controls))
        except ValueError:
            continue
    diffs.sort()
    lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]
    print(f"  {label}（{len(rows)} 期）：日区 {jp:+.2f}，国区 {cn:+.2f}，差 {jp - cn:+.2f}，95% 区间 [{lo:+.2f}, {hi:+.2f}]")
    return {"检查": label, "期数": len(rows), "日区": jp, "国区": cn, "日−国": jp - cn, "区间下限": lo, "区间上限": hi}


out = []
clean = [r for r in main if r["gap_prev"] > 20]     # 开池前第 8–14 天不压在上一期首周里
CHECKS = [
    ("主口径（7 天基准）", main, "climb", "x7"),
    ("排除天花板：只看第 3–14 天", main, "late", "x7"),
    ("排除均值回归：基准换成 14 天", main, "climb14", "x14"),
    ("排除均值回归：起点改用开池前第 8–14 天量", clean, "climb", "xfar"),
]
for controls, title in ((False, "不加控制"), (True, "控制大版本系列和促销（同一系列内比较）")):
    print(f"开池前名次每低一倍，首周爬升多多少 —— {title}：")
    for label, rows, y, x in CHECKS:
        res = check(label, rows, y, x, controls)
        res["检查"] = f"{title}｜{label}"
        out.append(res)
    print()
print("读法：不加控制时日区明显更强；但在同一大版本系列内，两边几乎一样。")
print("     差别来自系列之间的长期变化（国区大盘下滑时开池表现跟着下滑，日区守住了），和 series_drift.py 是同一件事。")

print("\n轨迹（描述，未控制系列）：日区开池后登顶过的期，按起点分成两半")
cap = [r for r in main if r["jp"]["top1"] >= 1]
cut = st.median(r["jp"]["x7"] for r in cap)
for lab, g in (("起点较低的一半", [r for r in cap if r["jp"]["x7"] >= cut]),
               ("起点较高的一半", [r for r in cap if r["jp"]["x7"] < cut])):
    line = {"检查": f"轨迹：{lab}", "期数": len(g),
            "日区": st.median(math.exp(r["jp"]["x7"]) for r in g),
            "国区": st.mean(r["jp"]["top1"] for r in g),
            "日−国": st.median(r["jp"]["mean_rank"] for r in g)}
    out.append(line)
    print(f"  {lab}（{len(g)} 期）：开池前中位第 {line['日区']:.0f} 名，平均在第 1 名停 {line['国区']:.1f} 天，"
          f"首周平均名次中位第 {line['日−国']:.1f} 名")

with open(OUT / "baseline_effect.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["检查", "期数", "日区", "国区", "日−国", "区间下限", "区间上限"], restval="")
    w.writeheader()
    for r in out:
        w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
print(f"\n写出 {(OUT / 'baseline_effect.csv').relative_to(ROOT)}"
      "（轨迹几行的三列依次是：开池前名次中位数、登顶天数平均、首周平均名次中位数）")
