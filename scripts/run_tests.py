# 第 7 步：各项比较 → outputs/tests_<指标文件名>.csv，并在屏幕上打印结果
#
# 读入 data/analysis_phases.csv（编码）和 data/metrics_game_7d.csv（名次指标）
# 统计方法的大白话说明写在 scripts/stats_tools.py 开头
# 运行：在项目文件夹里输入  py scripts\run_tests.py
#
# 结果怎么读（每一行是一项比较）：
#   差距       A 组的中日差平均 − B 组的中日差平均（正数 = A 组相对更偏日本）
#   p          纯靠运气出现这么大差距的概率，越小越不像运气
#   控制后     同一大版本系列、同样促销条件下的差距（分数类变量 = 每高 1 分差多少）。这是主结果，因为研究设计定了要控制大版本系列和促销
#   核对       换成核对指标（市场内百分位，日 − 国）后的差距和 p
#   预期       事先写下的方向：+ = 预期偏日本，− = 预期偏中国，空 = 不预设

# ====== 设置 ======
METRICS_FILE = "metrics_game_7d.csv"   # 稳健性时可换成 metrics_game_14d.csv、metrics_total_7d.csv
N_SHUFFLE = 10000                       # 打乱次数
# ==================

import csv
import statistics as st
from pathlib import Path

from stats_tools import compare_groups, controlled_effect, rank_correlation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------- 1. 合并编码和指标 ----------
def load_phases(metrics_file=METRICS_FILE, outcome="climb_diff"):
    """把编码表和名次指标按期对上；y = 要比较的中日差（默认是主指标）"""
    coding = read_csv(DATA / "analysis_phases.csv")
    metrics = {r["phase_no"]: r for r in read_csv(DATA / metrics_file)}
    phases = []
    for c in coding:
        m = metrics[c["phase_no"]]
        if m.get(outcome, "") == "":
            continue
        row = dict(c)
        row["y"] = float(m[outcome])
        row["y_check"] = float(m["pct_diff_series"]) if m.get("pct_diff_series") else None   # 核对指标
        phases.append(row)
    return phases


def flag(cond):
    return lambda r: int(cond(r))


# ---------- 2. 要做的比较 ----------
def make_tests(phases, main_filter=lambda r: r["in_main"] == "1"):
    """每项：(编号, 名字, 样本, A 组的条件, 预期方向, 类型)  类型：group = 两组比，score = 分数"""
    main = [r for r in phases if main_filter(r)]
    rerun = [r for r in phases if r["phase_kind"] == "纯复刻" and r["window_short"] == "0"]
    return [
        # 按类型（米哈游的排法）
        ("T1", "上半 T0 vs 下半", [r for r in main if r["type_group"] in ("上半T0", "下半")],
         flag(lambda r: r["type_group"] == "上半T0"), "", "group"),
        ("T2", "上半 T0 内部：铺垫分 ≥2 vs ≤1", [r for r in main if r["type_group"] == "上半T0"],
         flag(lambda r: int(r["story_pre_max"]) >= 2), "", "group"),
        ("T3", "SP vs 非 SP", main, flag(lambda r: r["sp"] == "1"), "", "group"),
        # 按因素
        ("F1", "强度 T0 vs 非 T0", main, flag(lambda r: r["T0"] == "1"), "", "group"),
        ("F2", "主推 vs 非主推", main, flag(lambda r: r["promoted"] == "1"), "", "group"),
        ("F3", "上半 vs 下半", main, flag(lambda r: r["half"] == "上半"), "", "group"),
        ("F4", "铺垫分（0–3）", main, lambda r: int(r["story_pre_max"]), "", "score"),
        ("F5", "铺垫分（0–3），只看非主推", [r for r in main if r["promoted"] == "0"],
         lambda r: int(r["story_pre_max"]), "", "score"),
        ("F6", "当期分（0–3）", main, lambda r: int(r["story_cur_max"]), "", "score"),
        ("F7", "日配 A 档 vs 其他", main, flag(lambda r: r["jp_va_A"] == "1"), "+", "group"),
        ("F8", "国配 A 档 vs 其他", main, flag(lambda r: r["cn_va_A"] == "1"), "−", "group"),
        ("F9", "男性 vs 女性", main, flag(lambda r: r["male"] == "1"), "", "group"),
        ("F10", "同位体 vs 其他", main, flag(lambda r: r["isomorph"] == "1"), "−", "group"),
        # 期层面
        ("P1", "撞车期 vs 其他", main, flag(lambda r: r["collision"] == "1"), "", "group"),
        ("P2", "有开满整版本的长池 vs 其他", main, flag(lambda r: r["has_long_banner"] == "1"), "", "group"),
        ("P3", "带加强复刻 vs 其他（描述）", main, flag(lambda r: r["buffed_rerun"] != ""), "", "group"),
        ("R1", "纯复刻期 vs 新角色期", main + rerun, flag(lambda r: r["phase_kind"] == "纯复刻"), "−", "group"),
    ]


# ---------- 3. 逐项计算 ----------
def run_one(test, n_shuffle, with_raw=True):
    code, name, sample, xf, expect, kind = test
    y = [r["y"] for r in sample]
    x = [xf(r) for r in sample]
    groups = [r["series"] for r in sample]          # 大版本系列
    promo = [int(r["promo"]) for r in sample]
    res = {"编号": code, "比较": name, "预期": expect, "样本期数": len(sample), "类型": kind}
    if kind == "group":
        res["A组期数"] = sum(x)
        res["B组期数"] = len(x) - sum(x)
    else:
        res["A组期数"] = res["B组期数"] = ""
        res["各分数的平均"] = "  ".join(
            f"{s}分 {st.mean(v for v, xx in zip(y, x) if xx == s):+.2f}(n={x.count(s)})"
            for s in sorted(set(x)))
    if with_raw:
        test_fn = compare_groups if kind == "group" else rank_correlation   # 分数类用秩相关
        res["差距"], res["p"] = test_fn(y, x, n_shuffle)
        yc = [r["y_check"] for r in sample]
        if all(v is not None for v in yc):
            res["核对"], res["核对p"] = test_fn(yc, x, n_shuffle)
        else:
            res["核对"] = res["核对p"] = None     # 纯复刻期没有核对指标
    res["控制后"], res["控制后p"] = controlled_effect(y, x, groups, promo, n_shuffle)
    return res


def fmt(v, nd=2, sign=True):
    if v is None:
        return "—"
    return f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"


def fmt_p(p):
    if p is None:
        return "—"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


if __name__ == "__main__":
    phases = load_phases()
    results = []
    for test in make_tests(phases):
        res = run_one(test, N_SHUFFLE)
        results.append(res)
        code, name, kind = res["编号"], res["比较"], res["类型"]
        head = f"{code:<4}{name}（{res['样本期数']} 期" + (f"，A 组 {res['A组期数']}）" if kind == "group" else "）")
        print(head)
        label = "差距" if kind == "group" else "秩相关"
        print(f"     {label} {fmt(res['差距'])}  p={fmt_p(res['p'])} | "
              f"控制后 {fmt(res['控制后'])}  p={fmt_p(res['控制后p'])} | "
              f"核对 {fmt(res['核对'])}  p={fmt_p(res['核对p'])}"
              + (f" | 预期 {res['预期']}" if res["预期"] else ""))
        if kind == "score":
            print(f"     {res['各分数的平均']}")

    # ---------- 4. 写出 ----------
    out_path = OUT / f"tests_{METRICS_FILE.replace('metrics_', '').replace('.csv', '')}.csv"
    fields = ["编号", "比较", "预期", "样本期数", "A组期数", "B组期数", "差距", "p",
              "控制后", "控制后p", "核对", "核对p", "各分数的平均"]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="", extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    print(f"\n写出 {out_path.relative_to(ROOT)}。共 {len(results)} 项比较；"
          f"即使全都没关系，按 p<0.05 也平均会有 {len(results) * 0.05:.1f} 项靠运气\"显著\"。")
    print("分数类（F4–F6）的\"差距\"是秩相关，\"控制后\"是每高 1 分中日差高多少，两者单位不同。")
