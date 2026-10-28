# 第 6 步：用每日名次算各期的指标 → data/metrics_<榜单>_<天数>d.csv（一行 = 一期，共 65 期）
#
# 读入：
#   data/analysis_phases.csv       上一步的分析表（用它的期的类型、是否进主分析）
#   data/raw 里的星铁日区、国区 iPhone 畅销榜每日名次
# 运行：在项目文件夹里输入  py scripts\compute_metrics.py
#
# 名次一律取对数再比，也就是按"倍数"看：从第 20 名爬到第 10 名，和从第 4 名爬到第 2 名，算爬了一样多。
# 每个指标都是"日区 − 国区"，正数 = 这一期在日本相对更强。

# ====== 要算的几种设置（一次运行全部算完）======
# 每一行：(开池后看几天, 用哪个榜)。第一行是主分析，后两行是稳健性检验。
RUNS = [
    (7, "游戏(畅销)"),     # 主分析：首周、游戏榜
    (14, "游戏(畅销)"),    # 稳健性：两周
    (7, "总榜(畅销)"),     # 稳健性：总榜
]
WINDOW_DAYS, CHART = RUNS[0]   # 下面的函数用这两个值；每种设置运行前会被替换
# =============================================

import csv
import math
import statistics as st
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
DATA_END = date(2026, 10, 24)    # 10-25 及之后只是导出时刻的快照，不用

RANK_FILES = {
    "jp": RAW / "qimai_jp_iphone_rank_2023-04-01_2026-10-25.csv",
    "cn": RAW / "qimai_cn_iphone_rank_2023-04-01_2026-10-25.csv",
}


def load_ranks(path):
    """读一个市场的每日名次，返回 {日期: 名次}；空值（掉出前 200 名）跳过"""
    ranks = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["时间"])
            if r[CHART] and d <= DATA_END:
                ranks[d] = int(r[CHART])
    return ranks


def days_from(start, first, last, stop):
    """开池日之后第 first 天到第 last 天（开池当天 = 第 0 天），到 stop 那天之前截断"""
    out = []
    for k in range(first, last + 1):
        d = start + timedelta(days=k)
        if d >= stop:
            break
        out.append(d)
    return out


def mean_log(values):
    return st.mean(math.log(v) for v in values) if values else None


def market_metrics(ranks, start, stop):
    """一期在一个市场里的各项指标"""
    pre = [ranks[start - timedelta(days=k)] for k in range(1, 8) if start - timedelta(days=k) in ranks]
    win = [ranks[d] for d in days_from(start, 0, WINDOW_DAYS - 1, stop) if d in ranks]
    d01 = [ranks[d] for d in days_from(start, 0, 1, stop) if d in ranks]
    late = [ranks[d] for d in days_from(start, 2, 13, stop) if d in ranks]   # 第 3–14 天
    if not pre or not win:
        return {}
    base = math.log(st.median(pre))
    m = {
        "pre7": st.median(pre),                         # 开池前 7 天名次中位数（基准）
        "best_d0d1": min(d01),                          # 开池当天和次日的最好名次
        "top1_days": sum(r == 1 for r in win),          # 窗口内第 1 名的天数
        "mean_rank": round(math.exp(mean_log(win)), 1), # 窗口内的平均名次（按倍数平均）
        "climb": base - mean_log(win),                  # 主指标：窗口平均名次比基准爬了多少
        "peak_climb": base - math.log(min(d01)),        # 补充：峰值爬升（受第 1 名封顶影响）
        "late_climb": base - mean_log(late) if late else None,   # 补充：第 3–14 天
        "n_days": len(win),
    }
    return m


def percentile_within(rows, market, group_key):
    """核对指标：在各自市场里给卡池排队，越强百分位越高（0–1）。
    排队规则：先比最好名次，并列再比登顶天数，再比平均名次；完全并列的取平均名次。"""
    groups = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r)
    out = {}
    for g in groups.values():
        key = lambda r: (r[f"{market}_best_d0d1"], -r[f"{market}_top1_days"], r[f"{market}_mean_rank"])
        g = sorted(g, key=key)
        n = len(g)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and key(g[j + 1]) == key(g[i]):
                j += 1
            avg_pos = (i + j) / 2
            for r in g[i:j + 1]:
                out[r["phase_no"]] = round(1 - (avg_pos + 0.5) / n, 4)
            i = j + 1
    return out


# ---------- 秩相关（打印核对时用） ----------
def spearman(xs, ys):
    """秩相关：两列数字的"排名"有多一致，1 = 完全一致，0 = 无关"""
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            for k in range(i, j + 1):
                r[s[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den


def run(window, chart):
    """按一种设置算完全部指标并写出文件"""
    global WINDOW_DAYS, CHART
    WINDOW_DAYS, CHART = window, chart

    # ---------- 1. 读入 ----------
    with open(DATA / "analysis_phases.csv", encoding="utf-8-sig", newline="") as f:
        phases = list(csv.DictReader(f))
    ranks = {m: load_ranks(p) for m, p in RANK_FILES.items()}

    # ---------- 2. 逐期计算 ----------
    starts = [date.fromisoformat(p["start_date"]) for p in phases]
    rows = []
    for i, p in enumerate(phases):
        start = starts[i]
        nxt = starts[i + 1] if i + 1 < len(starts) else DATA_END + timedelta(days=1)
        stop = min(nxt, DATA_END + timedelta(days=1))     # 遇到下一期开池或数据截止就截断
        row = {k: p[k] for k in ("phase_no", "start_date", "year", "series", "version", "half",
                                 "new_five", "phase_kind", "in_main")}
        row["gap_to_next"] = (nxt - start).days
        # 开池前 7 天是否压在上一期的首周里（上一期开池不到 14 天）
        row["pre7_overlap_prev"] = int(i > 0 and (start - starts[i - 1]).days < 14)
        for m in ("jp", "cn"):
            for k, v in market_metrics(ranks[m], start, stop).items():
                row[f"{m}_{k}"] = round(v, 4) if isinstance(v, float) else v
        if "jp_climb" in row and "cn_climb" in row:
            row["climb_diff"] = round(row["jp_climb"] - row["cn_climb"], 4)
            row["peak_diff"] = round(row["jp_peak_climb"] - row["cn_peak_climb"], 4)
            if row["jp_late_climb"] is not None and row["cn_late_climb"] is not None:
                row["late_diff"] = round(row["jp_late_climb"] - row["cn_late_climb"], 4)
        rows.append(row)

    # ---------- 3. 核对指标：主分析 51 期在各自市场里的百分位，日 − 国 ----------
    main = [r for r in rows if r["in_main"] == "1"]
    for label, gk in (("all", lambda r: "all"), ("series", lambda r: r["series"])):
        pj = percentile_within(main, "jp", gk)
        pc = percentile_within(main, "cn", gk)
        for r in main:
            r[f"pct_diff_{label}"] = round(pj[r["phase_no"]] - pc[r["phase_no"]], 4)

    # ---------- 4. 写出 ----------
    tag = {"游戏(畅销)": "game", "总榜(畅销)": "total"}[CHART]
    out_path = DATA / f"metrics_{tag}_{WINDOW_DAYS}d.csv"
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)

    # ---------- 5. 打印核对 ----------
    print(f"写出 {out_path.relative_to(ROOT)}：榜单 {CHART}，开池后 {WINDOW_DAYS} 天")
    ok = [r for r in main if "climb_diff" in r]
    print(f"主分析 {len(main)} 期，算出指标的 {len(ok)} 期；窗口被下一期截断的：",
          [(r["start_date"], r["jp_n_days"]) for r in ok if r["jp_n_days"] < WINDOW_DAYS] or "无")
    print(f"开池两天内到第 1 名的期数：日区 {sum(r['jp_best_d0d1'] == 1 for r in ok)}，国区 {sum(r['cn_best_d0d1'] == 1 for r in ok)}")
    d = [r["climb_diff"] for r in ok]
    print(f"爬升差（日 − 国）：平均 {st.mean(d):+.2f}，中位数 {st.median(d):+.2f}，标准差 {st.stdev(d):.2f}")
    for y in sorted({r["series"] for r in ok}):
        g = [r["climb_diff"] for r in ok if r["series"] == y]
        print(f"  {y}：{len(g)} 期，平均 {st.mean(g):+.2f}")
    print(f"主指标和核对指标的秩相关：全时段 {spearman(d, [r['pct_diff_all'] for r in ok]):.2f}，"
          f"同一大版本系列内 {spearman(d, [r['pct_diff_series'] for r in ok]):.2f}")


for window, chart in RUNS:
    run(window, chart)
    print()
