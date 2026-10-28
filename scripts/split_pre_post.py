# 第 12 步：把中日差拆成"开池前"和"开池后"两段 → outputs/split_pre_post.csv，并打印结果
#
# 为什么要拆（10-28 外部审阅提出，Claude 核实）：
#   首周爬升 = 开池前名次 → 开池后名次爬了多少倍。中日差 = 日区爬升 − 国区爬升，可以精确写成
#       中日差 = 开池前的"日/国名次比" − 开池后的"日/国名次比"（都取对数）
#   打个比方：两人同时到终点，起点靠后的那个"跑得更远"。只看跑了多远，分不清是他跑得快，还是起点靠后。
#   拆开后：开池前那段为负 = 国区开池前相对日区更冷（名次掉得更深）；开池后那段为正 = 开池后日区相对国区名次更靠后。
#
# 本脚本做三件事：
#   A. 主要比较的中日差拆成开池前、开池后两段（都控制大版本系列和促销，p 值做法同 run_tests.py）
#   B. 把两边开池前名次直接当控制变量，看效应还剩多少
#   C. 4.x 漂移按市场分开：考虑开池前名次后，日区、国区 4.x 的爬升比 3.x 多还是少
#
# 先跑完 compute_metrics.py 的主分析设置。运行：py scripts\split_pre_post.py

N_SHUFFLE = 5000

import csv
import math
import random
import statistics as st

from run_tests import load_phases, make_tests, OUT, DATA
from stats_tools import controlled_effect, ols

phases = load_phases()
with open(DATA / "metrics_game_7d.csv", encoding="utf-8-sig", newline="") as f:
    metrics = {r["phase_no"]: r for r in csv.DictReader(f)}
for r in phases:
    m = metrics[r["phase_no"]]
    r["jp_pre"], r["cn_pre"] = float(m["jp_pre7"]), float(m["cn_pre7"])
    r["jp_climb"], r["cn_climb"] = float(m["jp_climb"]), float(m["cn_climb"])
    r["pre"] = math.log(r["jp_pre"] / r["cn_pre"])     # 开池前：日/国名次比（对数）
    r["post"] = r["pre"] - r["y"]                        # 开池后：日/国名次比（对数），使 中日差 = 开池前 − 开池后
    r["post_late"] = r["pre"] - float(m["late_diff"])    # 第 3–14 天的开池后名次比

KEEP = ("T1", "F2", "F3", "F1", "T3", "F5", "F7")
tests = [t for t in make_tests(phases) if t[0] in KEEP]


def with_baseline(sample, x, n=N_SHUFFLE):
    """控制大版本系列、促销，再加两边开池前名次（对数）；p 值在同一系列内打乱 x"""
    y = [r["y"] for r in sample]
    ctrl = [[int(r["series"] == s) for r in sample] for s in sorted({r["series"] for r in sample})[1:]]
    ctrl += [[int(r["promo"]) for r in sample], [math.log(r["jp_pre"]) for r in sample],
             [math.log(r["cn_pre"]) for r in sample]]
    ctrl = [c for c in ctrl if len(set(c)) > 1]          # 去掉在这个样本里全一样的列（例如没有促销期）
    obs = ols(y, [x] + ctrl)[1]
    rng = random.Random(1)
    groups = {}
    for i, r in enumerate(sample):
        groups.setdefault(r["series"], []).append(i)
    hit = 0
    for _ in range(n):
        xp = x[:]
        for idx in groups.values():
            vals = [x[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                xp[i] = v
        hit += abs(ols(y, [xp] + ctrl)[1]) >= abs(obs) - 1e-12
    return obs, (hit + 1) / (n + 1)


rows = []
print("A/B. 中日差拆成开池前、开池后两段（控制大版本系列和促销）；最后两列 = 再控制两边开池前名次")
print("   编号  比较                        中日差(p)       开池前(p)       开池后(p)    | 控制开池前名次后(p)")
for code, name, sample, xf, expect, kind in tests:
    x = [xf(r) for r in sample]
    grp, promo = [r["series"] for r in sample], [int(r["promo"]) for r in sample]
    res = {}
    for comp in ("y", "pre", "post"):
        res[comp] = controlled_effect([r[comp] for r in sample], x, grp, promo, N_SHUFFLE)
    res["base"] = with_baseline(sample, x)
    f = lambda e: f"{e[0]:+.2f}({e[1]:.3f})"
    print(f"   {code:<5} {name:<24} {f(res['y']):>14}  {f(res['pre']):>14}  {f(res['post']):>14}  | {f(res['base']):>14}")
    rows.append({"编号": code, "比较": name, "中日差": res["y"][0], "中日差p": res["y"][1],
                 "开池前": res["pre"][0], "开池前p": res["pre"][1], "开池后": res["post"][0], "开池后p": res["post"][1],
                 "控制开池前名次后": res["base"][0], "控制开池前名次后p": res["base"][1]})
    if code in ("T1", "F2"):
        late = controlled_effect([r["post_late"] for r in sample], x, grp, promo, N_SHUFFLE)
        print(f"         └ 第 3–14 天的开池后那段：{f(late)}")
        rows[-1]["第3–14天开池后"] = late[0]
        rows[-1]["第3–14天开池后p"] = late[1]

# ---------- C. 4.x 漂移按市场分开 ----------
main = [r for r in phases if r["in_main"] == "1"]
print("\nC. 各市场：爬升 ~ ln(开池前名次) + 大版本系列 + 促销；看 4.x 比 3.x 多爬还是少爬")
for side, label in (("jp", "日区"), ("cn", "国区")):
    y = [r[side + "_climb"] for r in main]
    dums = [[int(r["series"] == s) for r in main] for s in ("2.x", "3.x", "4.x")]
    b = ols(y, [[math.log(r[side + "_pre"]) for r in main]] + dums + [[int(r["promo"]) for r in main]])
    a3 = [r for r in main if r["series"] == "3.x"]
    a4 = [r for r in main if r["series"] == "4.x"]
    raw = st.mean(r[side + "_climb"] for r in a4) - st.mean(r[side + "_climb"] for r in a3)
    base = st.mean(math.log(r[side + "_pre"]) for r in a4) - st.mean(math.log(r[side + "_pre"]) for r in a3)
    print(f"   {label}：4.x 比 3.x 爬升多 {raw:+.2f}，开池前名次低了 {base:.2f}（对数）；"
          f"考虑开池前名次后 4.x 比 3.x {b[4] - b[3]:+.2f}（开池前名次每低一倍多爬 {b[1] * math.log(2):.2f}）")
    rows.append({"编号": f"4.x-{label}", "比较": "4.x 比 3.x（考虑开池前名次后）", "中日差": b[4] - b[3],
                 "开池前": base, "开池后": raw})

cols = ["编号", "比较", "中日差", "中日差p", "开池前", "开池前p", "开池后", "开池后p",
        "控制开池前名次后", "控制开池前名次后p", "第3–14天开池后", "第3–14天开池后p"]
with open(OUT / "split_pre_post.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, restval="")
    w.writeheader()
    for r in rows:
        w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
print("\n写出 outputs/split_pre_post.csv（4.x 那两行：中日差列 = 考虑起点后的差，开池前列 = 起点变化，开池后列 = 原始爬升变化）")
