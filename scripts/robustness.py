# 第 8 步：稳健性检验 → outputs/robustness.csv
#
# 把 run_tests.py 里的每一项比较，换不同的指标口径和样本再跑一遍，看结论变不变。
# 每格是"控制大版本系列和促销后"的效应，后面的星号表示 p 值：*** < 0.01，** < 0.05，* < 0.10。
# 判定原则：换多种合理口径都成立 → 主要发现；只在少数口径下成立 → 只说"有较弱的迹象"。
#
# 先要跑完 compute_metrics.py 的三种设置（game_7d、game_14d、total_7d）。
# 运行：在项目文件夹里输入  py scripts\robustness.py   （要几分钟）

N_SHUFFLE = 2000      # 比主分析少一些，节省时间

import csv
from pathlib import Path

from run_tests import load_phases, make_tests, run_one, flag, OUT, ROOT
from stats_tools import controlled_coef

# 每种口径：(名字, 指标文件, 用哪个中日差, 主样本的条件, 对编码的改动)
in_main = lambda r: r["in_main"] == "1"


def promo_1x_zero(r):
    """敏感性：1.x 的两位主推（丹恒•饮月、镜流）改记 0"""
    if r["version"].startswith("1."):
        r["promoted"] = "0"
    return r


VARIANTS = [
    ("主分析", "metrics_game_7d.csv", "climb_diff", in_main),
    ("两周", "metrics_game_14d.csv", "climb_diff", in_main),
    ("总榜", "metrics_total_7d.csv", "climb_diff", in_main),
    ("峰值", "metrics_game_7d.csv", "peak_diff", in_main),
    ("第3–14天", "metrics_game_7d.csv", "late_diff", in_main),
    ("剔除撞车", "metrics_game_7d.csv", "climb_diff", lambda r: in_main(r) and r["collision"] == "0"),
    ("剔除长池", "metrics_game_7d.csv", "climb_diff",
     lambda r: in_main(r) and r["has_long_banner"] == "0" and r["carryover_five"] == ""),
    ("剔除1.x", "metrics_game_7d.csv", "climb_diff", lambda r: in_main(r) and not r["version"].startswith("1.")),
    ("放回赠送", "metrics_game_7d.csv", "climb_diff",
     lambda r: r["phase_kind"] in ("新角色", "新角色(赠送本体)")),
    ("剔除饮月", "metrics_game_7d.csv", "climb_diff", lambda r: in_main(r) and r["new_five"] != "丹恒•饮月"),
    ("1.x主推记0", "metrics_game_7d.csv", "climb_diff", in_main, promo_1x_zero),
]


def extra_tests(phases, main_filter):
    """只在稳健性里做的几项：剧情分的另外两种口径、强度分三档，以及把 T1 拆开的两项"""
    main = [r for r in phases if main_filter(r)]
    non_promo = [r for r in main if r["promoted"] == "0"]
    pick = lambda groups: [r for r in main if r["type_group"] in groups]
    return [
        # T1 拆开：上半 T0 偏国区，是因为"上半"、因为"T0"，还是两者叠在一起？
        ("T1b", "拆 T1：上半非 T0 vs 下半", pick(("上半非T0", "下半")),
         flag(lambda r: r["type_group"] == "上半非T0"), "", "group"),
        ("T1c", "拆 T1：上半 T0 vs 上半非 T0", pick(("上半T0", "上半非T0")),
         flag(lambda r: r["type_group"] == "上半T0"), "", "group"),
        ("F4b", "铺垫分·累计口径（2 分以上的行数）", main, lambda r: int(r["story_pre_n2"]), "", "score"),
        ("F4c", "铺垫分·远近口径", main, lambda r: int(r["story_pre_decay"]), "", "score"),
        ("F5b", "非主推·累计口径", non_promo, lambda r: int(r["story_pre_n2"]), "", "score"),
        ("F1b", "强度三档（2 = T0，1 = T1，0 = T2）", main, lambda r: 2 - int(r["strength"]), "", "score"),
    ]


def stars(p):
    if p is None:
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


table = {}     # 编号 → {口径: 结果}
names = {}
for vname, mfile, outcome, mfilter, *change in VARIANTS:
    phases = load_phases(mfile, outcome)
    if change:
        phases = [change[0](r) for r in phases]
    tests = make_tests(phases, mfilter) + extra_tests(phases, mfilter)
    for t in tests:
        code = t[0]
        if code == "R1" and vname == "放回赠送":
            continue
        res = run_one(t, N_SHUFFLE, with_raw=False)
        names[code] = t[1]
        table.setdefault(code, {})[vname] = res
    print(f"完成：{vname}")

order = list(names)
cols = [v[0] for v in VARIANTS]
with open(OUT / "robustness.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["编号", "比较"] + cols + ["各口径里 p<0.10 的个数", "方向和主分析一致的个数"])
    for code in order:
        cells, sig, same = [], 0, 0
        base = table[code].get("主分析", {}).get("控制后")
        for c in cols:
            r = table[code].get(c)
            if not r or r["控制后"] is None:
                cells.append("")
                continue
            e, p = r["控制后"], r["控制后p"]
            cells.append(f"{e:+.2f}{stars(p)}")
            sig += p < 0.10
            same += base is not None and (e > 0) == (base > 0)
        w.writerow([code, names[code]] + cells + [sig, same])

print(f"\n写出 {(OUT / 'robustness.csv').relative_to(ROOT)}。")
print("每格 = 控制大版本系列和促销后的效应；*** p<0.01  ** p<0.05  * p<0.10")
print(f"{'编号':<5}" + "".join(f"{c:>9}" for c in cols) + "  比较")
for code in order:
    line = f"{code:<5}"
    for c in cols:
        r = table[code].get(c)
        cell = ""
        if r and r["控制后"] is not None:
            cell = f"{r['控制后']:+.2f}" + stars(r["控制后p"])
        line += f"{cell:>9}"
    print(line + "  " + names[code])


# ---------- 逐个剔除：主要结果是不是靠某一期撑着 ----------
print("\n逐个剔除（主分析口径）：每次去掉一期重算控制后效应，看最小值和最大值各是去掉哪一期时出现的")
phases = load_phases()
LOO = ("T1", "T3", "F2", "F5", "F7")
for t in make_tests(phases):
    if t[0] not in LOO:
        continue
    code, name, sample, xf, expect, kind = t
    full = controlled_coef([r["y"] for r in sample], [xf(r) for r in sample],
                           [r["series"] for r in sample], [int(r["promo"]) for r in sample])
    effects = []
    for i in range(len(sample)):
        rest = sample[:i] + sample[i + 1:]
        e = controlled_coef([r["y"] for r in rest], [xf(r) for r in rest],
                            [r["series"] for r in rest], [int(r["promo"]) for r in rest])
        if e is not None:
            effects.append((e, sample[i]["new_five"]))
    lo, hi = min(effects), max(effects)
    print(f"  {code} {name}：全样本 {full:+.2f}；逐个剔除后 {lo[0]:+.2f}（去掉{lo[1]}）到 {hi[0]:+.2f}（去掉{hi[1]}）")
