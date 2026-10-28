# -*- coding: utf-8 -*-
r"""
第3步：整理原神的角色活动祈愿（限定角色池），并给星铁的每一期标上"是否和原神撞车"。

运行顺序（不能反）：
  py scripts\build_banner_table.py
  py scripts\add_zzz_collision.py
  py scripts\add_genshin_collision.py

输入（data/raw/）：
  wiki_genshin_wishes_raw.tsv           B站 wiki 原神「往期祈愿」页的角色活动祈愿（2026-10-25 读取，1.0 至 7.2）
  qimai_genshin_jp/cn_iphone_rank_*.csv  （可选）七麦原神名次。有这两个文件就用名次核对日期，没有就跳过
输入（data/）：
  phases.csv                             前两步生成的星铁分期表
输出（data/）：
  gi_phases.csv                          原神一行 = 一期（只保留 2023-04-01 至 2026-10-24）
  phases.csv                             在原表上加几列原神撞车信息（覆盖写回）
"""
import csv, re, os, glob, math, statistics as st, datetime as dt
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data")
FIRST, LAST = "2023-04-01", "2026-10-24"   # 和七麦数据的范围一致


def to_date(s):
    """'2023/05/02 17:59' 或 '2022/6/21 18:00:00' -> date"""
    y, m, d = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", s.strip()).groups()
    return dt.date(int(y), int(m), int(d))


# ---------- 1. 读 wiki 表。wiki 是新的在上，倒过来就是时间顺序 ----------
rows = list(csv.DictReader(open(os.path.join(RAW_DIR, "wiki_genshin_wishes_raw.tsv"), encoding="utf-8"), delimiter="\t"))
rows.reverse()

# ---------- 2. 定开池日期 ----------
# 上半常写成"X版本更新后"。版本更新日 = 上一个半期结束日的次日。
# 再用"上半一般开 20 天"交叉核对，对不上的打印出来人工看。
banners = []
for i, r in enumerate(rows):
    start_txt, end_txt = [x.strip() for x in r["时间"].split("~")]
    end = to_date(end_txt)
    if "版本更新后" in start_txt:
        prev_end = max(b["end"] for b in banners if b["version"] != r["版本"])
        start = prev_end + dt.timedelta(days=1)
        derived = True
    else:
        start, derived = to_date(start_txt), False
    m = re.match(r"「(.*)·(.+?)\((.)\)」", r["5星角色"])
    banners.append(dict(version=r["版本"], start=start, end=end, name=m.group(2), element=m.group(3), derived=derived))

print("[核对1] 推算出来的版本更新日，和「上半开 20 天」对不上的：")
bad = [b for b in banners if b["derived"] and str(b["start"]) >= FIRST and (b["end"] - b["start"]).days != 20]
for b in bad:
    print(" ", b["version"], b["start"], "~", b["end"], b["name"])
print("  无" if not bad else "")

# ---------- 3. 新/复刻：按时间顺序，第一次出现 = 新 ----------
seen, gi = set(), OrderedDict()
for b in sorted(banners, key=lambda b: b["start"]):
    s = str(b["start"])
    is_new = b["name"] not in seen
    seen.add(b["name"])
    if not (FIRST <= s <= LAST):
        continue
    p = gi.setdefault(s, OrderedDict(start_date=s, version=b["version"], new_five="", rerun_five=""))
    key = "new_five" if is_new else "rerun_five"
    p[key] = "、".join(x for x in [p[key], b["name"]] if x)

# ---------- 4. （可选）用七麦原神名次核对日期 ----------
def load_rank(pattern):
    fs = glob.glob(os.path.join(RAW_DIR, pattern))
    if not fs:
        return None
    out = {}
    for row in list(csv.reader(open(fs[0], encoding="utf-8-sig")))[1:]:
        if row[2]:
            out[row[0]] = int(row[2])
    return out


GJP, GCN = load_rank("qimai_genshin_jp_iphone_rank_*.csv"), load_rank("qimai_genshin_cn_iphone_rank_*.csv")
for p in gi.values():
    for tag, X in (("jp", GJP), ("cn", GCN)):
        val = ""
        if X:
            d0 = dt.date.fromisoformat(p["start_date"])
            pre = [X[k] for k in ((d0 - dt.timedelta(i)).isoformat() for i in range(1, 8)) if k in X]
            post = [X[k] for k in ((d0 + dt.timedelta(i)).isoformat() for i in range(0, 2)) if k in X]
            if pre and post:
                val = round(math.log(st.median(pre) / min(post)), 2)
        p[f"{tag}_jump_log"] = val

with open(os.path.join(OUT_DIR, "gi_phases.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(next(iter(gi.values())).keys()))
    w.writeheader()
    w.writerows(gi.values())

# ---------- 5. 给星铁每一期标原神撞车 ----------
gi_dates = {dt.date.fromisoformat(s): p for s, p in gi.items()}
hsr = list(csv.DictReader(open(os.path.join(OUT_DIR, "phases.csv"), encoding="utf-8-sig")))
for p in hsr:
    d0 = dt.date.fromisoformat(p["start_date"])
    same = gi_dates.get(d0)
    near = [(d - d0).days for d in gi_dates if abs((d - d0).days) <= 2]
    p["gi_same_day"] = int(same is not None)                    # 同一天开池
    p["gi_within_2d"] = int(bool(near))                         # 前后2天内开池（含同一天）
    p["gi_gap_days"] = min(near, key=abs) if near else ""        # 原神比星铁晚几天（负数=早）
    p["gi_same_day_new"] = same["new_five"] if same else ""      # 撞车那期原神的新角色

with open(os.path.join(OUT_DIR, "phases.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(hsr[0].keys()))
    w.writeheader()
    w.writerows(hsr)

print("原神期数（2023-04-01 至 2026-10-24）:", len(gi))
if GJP and GCN:
    print("\n[核对2] 原神开池当天和次日，两边名次都没明显跳升的期：")
    for p in gi.values():
        if p["jp_jump_log"] != "" and p["jp_jump_log"] < 0.5 and p["cn_jump_log"] < 0.5:
            print(" ", p["start_date"], p["version"], "新:", p["new_five"] or "-", "复刻:", p["rerun_five"] or "-")
else:
    print("\n[核对2] 没有原神七麦名次文件，日期未经名次核对。")
print("\n星铁和原神同一天开池的期：")
for p in hsr:
    if p["gi_same_day"] == 1:
        print(" ", p["start_date"], "星铁", p["version"], p["half"], "新:", p["new_five"] or "-",
              "| 原神新:", p["gi_same_day_new"] or "-")
print("\n前后2天内开池（不含同一天）：")
for p in hsr:
    if p["gi_within_2d"] == 1 and p["gi_same_day"] == 0:
        print(" ", p["start_date"], "星铁", p["version"], p["half"], "相差", p["gi_gap_days"], "天")
