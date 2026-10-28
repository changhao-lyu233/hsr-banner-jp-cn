# -*- coding: utf-8 -*-
r"""
第2步：整理绝区零的独家频段（限定代理人卡池），并给星铁的每一期标上"是否和绝区零撞车"。

先运行 build_banner_table.py，再运行本脚本：
  py scripts\build_banner_table.py
  py scripts\add_zzz_collision.py

输入（data/raw/）：
  wiki_zzz_channels_raw.tsv             B站 wiki 绝区零「调频」页的历史限定频段（2026-10-25 读取）
  zzz_channels_supplement.tsv           wiki 还没收录的 3.3 上半，手工从新闻补（带来源）
  qimai_zzz_jp/cn_iphone_rank_*.csv      七麦：绝区零日区、国区 iPhone 畅销榜每日名次
输入（data/）：
  phases.csv                             上一步生成的星铁分期表
输出（data/）：
  zzz_phases.csv                         绝区零一行 = 一期
  phases.csv                             在原表上加几列撞车信息（覆盖写回）
"""
import csv, re, os, glob, math, statistics as st, datetime as dt
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data")

# 绝区零版本更新日期（B站 wiki 绝区零「版本新增内容」页，2026-10-25 读取）
ZZZ_VERSION_DATE = {
    "1.0": "2024-07-04", "1.1": "2024-08-14", "1.2": "2024-09-25", "1.3": "2024-11-06",
    "1.4": "2024-12-18", "1.5": "2025-01-22", "1.6": "2025-03-12", "1.7": "2025-04-23",
    "2.0": "2025-06-06", "2.1": "2025-07-16", "2.2": "2025-09-04", "2.3": "2025-10-15",
    "2.4": "2025-11-26", "2.5": "2025-12-30", "2.6": "2026-02-06", "2.7": "2026-03-24",
    "2.8": "2026-05-06", "3.0": "2026-06-17", "3.1": "2026-07-29", "3.2": "2026-09-09",
    "3.3": "2026-10-21",   # wiki 还没收录，来自新闻报道，见 zzz_channels_supplement.tsv
}


def load_rank(pattern):
    fn = glob.glob(os.path.join(RAW_DIR, pattern))[0]
    out = {}
    for row in list(csv.reader(open(fn, encoding="utf-8-sig")))[1:]:
        if row[2]:
            out[row[0]] = int(row[2])
    return out


# ---------- 1. 绝区零卡池 -> 按开池日期合并成期 ----------
rows = list(csv.DictReader(open(os.path.join(RAW_DIR, "wiki_zzz_channels_raw.tsv"), encoding="utf-8"), delimiter="\t"))
# wiki 还没收录的最新卡池，手工从新闻补的（每行都写了来源）
rows += list(csv.DictReader(open(os.path.join(RAW_DIR, "zzz_channels_supplement.tsv"), encoding="utf-8"), delimiter="\t"))
banners = []
for r in rows:
    ver = r["版本"][:3]
    start_txt = r["时间"].split("~")[0].strip()
    if "版本更新后" in start_txt or "公测开启后" in start_txt:
        start = ZZZ_VERSION_DATE[ver]
    else:
        start = start_txt.split()[0].replace("/", "-")
    agents = re.findall(r"\[(.+?)（", r["S级代理人"])
    banners.append((start, ver, r["版本"][3:] or "全版本", agents))

banners.sort()
seen, zzz = set(), OrderedDict()
for start, ver, half, agents in banners:
    p = zzz.setdefault(start, OrderedDict(start_date=start, version=ver, half=half, new_agent="", rerun_agent=""))
    for a in agents:
        key = "new_agent" if a not in seen else "rerun_agent"
        p[key] = "、".join(x for x in [p[key], a] if x)
        seen.add(a)

# 用绝区零自己的名次核对日期（和星铁同一种做法）
ZJP = load_rank("qimai_zzz_jp_iphone_rank_*.csv")
ZCN = load_rank("qimai_zzz_cn_iphone_rank_*.csv")


def jump(X, start):
    d0 = dt.date.fromisoformat(start)
    pre = [X[k] for k in ((d0 - dt.timedelta(i)).isoformat() for i in range(1, 8)) if k in X]
    post = [X[k] for k in ((d0 + dt.timedelta(i)).isoformat() for i in range(0, 2)) if k in X]
    if not pre or not post:
        return "", "", ""
    return int(st.median(pre)), min(post), round(math.log(st.median(pre) / min(post)), 2)


for p in zzz.values():
    for tag, X in (("jp", ZJP), ("cn", ZCN)):
        a, b, c = jump(X, p["start_date"])
        p[f"{tag}_pre7_median"], p[f"{tag}_best_d0d1"], p[f"{tag}_jump_log"] = a, b, c

with open(os.path.join(OUT_DIR, "zzz_phases.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(next(iter(zzz.values())).keys()))
    w.writeheader()
    w.writerows(zzz.values())

# ---------- 2. 给星铁每一期标撞车 ----------
zzz_dates = {dt.date.fromisoformat(s): p for s, p in zzz.items()}
hsr = list(csv.DictReader(open(os.path.join(OUT_DIR, "phases.csv"), encoding="utf-8-sig")))
for p in hsr:
    d0 = dt.date.fromisoformat(p["start_date"])
    same = zzz_dates.get(d0)
    near = [(d - d0).days for d in zzz_dates if abs((d - d0).days) <= 2]
    p["zzz_same_day"] = int(same is not None)                       # 同一天开池
    p["zzz_within_2d"] = int(bool(near))                            # 前后2天内开池
    p["zzz_gap_days"] = min(near, key=abs) if near else ""           # 绝区零比星铁晚几天（负数=早）
    p["zzz_same_day_new"] = same["new_agent"] if same else ""        # 撞车那期绝区零的新角色

with open(os.path.join(OUT_DIR, "phases.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(hsr[0].keys()))
    w.writeheader()
    w.writerows(hsr)

print("绝区零期数:", len(zzz))
print("\n[核对] 绝区零开池当天和次日，两边名次都没明显跳升的期：")
for p in zzz.values():
    if p["jp_jump_log"] != "" and p["jp_jump_log"] < 0.5 and p["cn_jump_log"] < 0.5:
        print(" ", p["start_date"], p["version"], p["half"], "新:", p["new_agent"] or "-", "复刻:", p["rerun_agent"] or "-")
# 核对B：名次单日大跳升、却不在任何开池日（当天或次日）——如果有，多半是 wiki 漏了卡池
zstarts = [dt.date.fromisoformat(s) for s in zzz]
print("\n[核对B] 绝区零单日名次变好2.5倍以上、却不在开池当天或次日的日子：")
for tag, X in (("日区", ZJP), ("国区", ZCN)):
    hits = []
    for d, v in X.items():
        d0 = dt.date.fromisoformat(d)
        prev = X.get((d0 - dt.timedelta(1)).isoformat())
        if prev and math.log(prev / v) >= 0.9:
            gaps = [(d0 - s).days for s in zstarts if (d0 - s).days >= 0]
            if not gaps or min(gaps) > 1:
                hits.append(d)
    print(" ", tag, hits if hits else "无")
print("\n星铁和绝区零同一天开池的期：")
for p in hsr:
    if p["zzz_same_day"] == 1:
        print(" ", p["start_date"], "星铁", p["version"], p["half"], "新:", p["new_five"] or "-",
              "| 绝区零新:", p["zzz_same_day_new"] or "-")
print("\n前后2天内开池（不含同一天）：")
for p in hsr:
    if p["zzz_within_2d"] == 1 and p["zzz_same_day"] == 0:
        print(" ", p["start_date"], "星铁", p["version"], p["half"], "相差", p["zzz_gap_days"], "天")
