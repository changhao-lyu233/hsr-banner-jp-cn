# 第 9 步：大版本系列的漂移 → outputs/series_drift.csv，并打印结果
#
# 现象：4.x（2026 年）的新角色期整体偏向日本，1.x–3.x 接近 0。
# 主分析已经控制了大版本系列，所以这个漂移不会污染各项比较；这里单独看它是什么、能不能解释。
# 星铁按"一年一个星球"策划内容和宣发，所以按大版本系列（1.x/2.x/3.x/4.x）分组，而不是按自然年。
#
# 三步：
#   A. 拆开看：是日区爬得更多了，还是国区爬得更少了？两边开池前的名次怎么变的？
#   B. 起点和构成：把两边开池前的名次、卡池类型的构成分别考虑进去后，4.x 的偏向还剩多少？
#   C. 云星铁：国区有一部分充值转到了云星铁上，只看星铁本体会不会低估国区的爬升？
#
# 先跑完 compute_metrics.py 的主分析设置。运行：py scripts\series_drift.py

import csv
import math
import statistics as st
from datetime import date, timedelta

from run_tests import load_phases, OUT, ROOT
from stats_tools import ols, compare_groups

RAW = ROOT / "data" / "raw"
DATA_END = date(2026, 10, 24)
LAST = "4.x"     # 要解释的那个系列

phases = load_phases()
main = [r for r in phases if r["in_main"] == "1"]
metrics = {}
with open(ROOT / "data" / "metrics_game_7d.csv", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        metrics[r["phase_no"]] = r
for r in main:
    m = metrics[r["phase_no"]]
    for k in ("jp_climb", "cn_climb", "jp_pre7", "cn_pre7", "jp_mean_rank", "cn_mean_rank"):
        r[k] = float(m[k])

rows_out = []

# ---------- A. 按大版本系列拆开 ----------
print("A. 按大版本系列拆开（主分析 51 期，首周口径）")
print("   系列  期数  中日差   日区爬升  国区爬升 | 开池前名次中位数 日/国 | 首周平均名次 日/国")
for s in sorted({r["series"] for r in main}):
    g = [r for r in main if r["series"] == s]
    line = {
        "系列": s, "期数": len(g),
        "中日差": st.mean(r["y"] for r in g),
        "日区爬升": st.mean(r["jp_climb"] for r in g), "国区爬升": st.mean(r["cn_climb"] for r in g),
        "日区开池前名次": st.median(r["jp_pre7"] for r in g), "国区开池前名次": st.median(r["cn_pre7"] for r in g),
        "日区首周名次": st.median(r["jp_mean_rank"] for r in g), "国区首周名次": st.median(r["cn_mean_rank"] for r in g),
    }
    rows_out.append(line)
    print(f"   {s}  {len(g):>4}  {line['中日差']:+.2f}    {line['日区爬升']:.2f}      {line['国区爬升']:.2f}   |"
          f"   {line['日区开池前名次']:>5.0f} / {line['国区开池前名次']:<5.0f}        |"
          f"  {line['日区首周名次']:>5.1f} / {line['国区首周名次']:<5.1f}")
d_last = [int(r["series"] == LAST) for r in main]
obs, p = compare_groups([r["y"] for r in main], d_last, 10000)
print(f"   {LAST} vs 其他系列：中日差高 {obs:+.2f}，p={p:.3f}")
# 是不是靠个别期撑着：4.x 里有几期为正；逐个去掉 4.x 的一期，重算"4.x vs 其他"（控制促销）
g_last = [r for r in main if r["series"] == LAST]
loo = []
for r in g_last:
    rest = [x for x in main if x is not r]
    b = ols([x["y"] for x in rest], [[int(x["series"] == LAST) for x in rest], [int(x["promo"]) for x in rest]])[1]
    loo.append((b, r["new_five"]))
print(f"   {LAST} 的 {len(g_last)} 期里 {sum(r['y'] > 0 for r in g_last)} 期为正；逐个去掉一期后，"
      f"{min(loo)[0]:+.2f}（去掉{min(loo)[1]}）到 {max(loo)[0]:+.2f}（去掉{max(loo)[1]}）")
rows_out.append({"系列": "逐个剔除", "中日差": min(loo)[0], "日区爬升": max(loo)[0]})

# ---------- B. 起点 ----------
y = [r["y"] for r in main]
promo = [int(r["promo"]) for r in main]
lj = [math.log(r["jp_pre7"]) for r in main]
lc = [math.log(r["cn_pre7"]) for r in main]
b0 = ols(y, [d_last, promo])
b1 = ols(y, [d_last, promo, lj, lc])
print(f"\nB. {LAST} 的偏向：只控制促销 {b0[1]:+.2f}；再把两边开池前的名次也考虑进去 {b1[1]:+.2f}")
rows_out.append({"系列": "起点检查", "中日差": b0[1], "日区爬升": b1[1]})
# 构成：4.x 的 10 期里 6 期是 SP，上半 T0 只有 1 期。偏向会不会只是卡池类型的构成不同？
types = [[int(r["type_group"] == k) for r in main] for k in ("上半T0", "上半非T0", "SP")]
b2 = ols(y, [d_last, promo] + types)
print(f"   把卡池类型（上半 T0、上半非 T0、下半、SP）的构成也考虑进去：{b2[1]:+.2f}")
rows_out.append({"系列": "构成检查", "中日差": b2[1]})

# ---------- C. 云星铁 ----------
def revenue(path):
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            v = r["收入预估~iPhone"]
            d = date.fromisoformat(r["日期"])
            if v and int(v) >= 100 and d <= DATA_END:     # 小于 100 美元的是明显的异常值
                out[d] = int(v)
    return out


hsr = revenue(RAW / "qimai_cn_iphone_revenue_est_usd_2023-04-01_2026-10-24.csv")
cloud = revenue(RAW / "qimai_cloudhsr_cn_iphone_revenue_est_usd_2023-01-01_2026-10-24.csv")


def rev_climb(series, start, stop):
    pre = [series[start - timedelta(days=k)] for k in range(1, 8) if start - timedelta(days=k) in series]
    win = [series[start + timedelta(days=k)] for k in range(7)
           if start + timedelta(days=k) < stop and start + timedelta(days=k) in series]
    if len(pre) < 5 or len(win) < 5:
        return None
    return st.mean(math.log(v) for v in win) - math.log(st.median(pre))


starts = sorted(date.fromisoformat(r["start_date"]) for r in phases)
print("\nC. 云星铁：国区首周收入预估的涨幅（取对数），只算星铁本体 vs 本体 + 云星铁（云星铁数据从 2024-05 起）")
extra = {}
pairs = []
both_all = {d: hsr[d] + cloud[d] for d in hsr if d in cloud}
hsr_only = {d: v for d, v in hsr.items() if d in cloud}
for r in main:
    s = date.fromisoformat(r["start_date"])
    if s < date(2024, 5, 15):
        continue
    nxt = min([d for d in starts if d > s], default=DATA_END + timedelta(days=1))
    a = rev_climb(hsr_only, s, nxt)
    b = rev_climb(both_all, s, nxt)
    if a is None or b is None:
        continue
    extra.setdefault(r["series"], []).append(b - a)
    pairs.append((r, a, b))
for s, v in sorted(extra.items()):
    print(f"   {s}：{len(v)} 期，加上云星铁后涨幅平均变化 {st.mean(v):+.3f}（约 {100 * (math.exp(st.mean(v)) - 1):+.1f}%）")
    rows_out.append({"系列": f"云星铁 {s}", "期数": len(v), "中日差": st.mean(v)})
# 把收入涨幅换算成名次爬升：用星铁本体的"名次爬升 vs 收入涨幅"的关系
k = ols([r["cn_climb"] for r, a, b in pairs], [[a for r, a, b in pairs]])[1]
adj = [(r, r["y"] - k * (b - a)) for r, a, b in pairs]
for lab, cond in ((LAST, lambda r: r["series"] == LAST), ("其他系列", lambda r: r["series"] != LAST)):
    raw_v = [r["y"] for r, v in adj if cond(r)]
    adj_v = [v for r, v in adj if cond(r)]
    print(f"   {lab}（{len(raw_v)} 期）：中日差平均 {st.mean(raw_v):+.2f}，国区加上云星铁后 {st.mean(adj_v):+.2f}")
print(f"   （换算：国区收入涨幅每多 1，名次爬升约多 {k:.2f}）")

with open(OUT / "series_drift.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["系列", "期数", "中日差", "日区爬升", "国区爬升", "日区开池前名次",
                                      "国区开池前名次", "日区首周名次", "国区首周名次"], restval="")
    w.writeheader()
    for r in rows_out:
        w.writerow({k2: (round(v, 4) if isinstance(v, float) else v) for k2, v in r.items()})
print(f"\n写出 {(OUT / 'series_drift.csv').relative_to(ROOT)}")
