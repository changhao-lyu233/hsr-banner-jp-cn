# -*- coding: utf-8 -*-
r"""
附加核对（不改任何表，只打印结果）：
  A. 云·星穹铁道（只有国区）分走了多少国区 iPhone 收入？开池那一周是不是分走得更多？
  B. 撞车当天，星铁的名次有没有被自家其他游戏（原神、绝区零、云星铁）"机械地"挤下去？

先按顺序跑完前三个脚本，再运行：
  py scripts\check_cloud_and_sisters.py

注意：七麦收入预估是按名次档位赋值的，而且高名次有封顶。星铁本体在开池日常被封顶，
所以 A 里"开池周云星铁占比"会被高估一些，只能看量级。
"""
import csv, glob, os, statistics as st, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
LAST = "2026-10-24"


def rank(pattern):
    out = {}
    for r in list(csv.reader(open(glob.glob(os.path.join(RAW, pattern))[0], encoding="utf-8-sig")))[1:]:
        if r[2] and r[0] <= LAST:
            out[r[0]] = int(r[2])
    return out


def revenue(pattern):
    """七麦收入预估；小于 100 美元的是明显的异常值（如 1、2、3），去掉"""
    out = {}
    for r in list(csv.reader(open(glob.glob(os.path.join(RAW, pattern))[0], encoding="utf-8-sig")))[1:]:
        if r[1] and int(r[1]) >= 100 and r[0] <= LAST:
            out[r[0]] = int(r[1])
    return out


phases = list(csv.DictReader(open(os.path.join(ROOT, "data", "phases.csv"), encoding="utf-8-sig")))
days = lambda d0, a, b: [(d0 + dt.timedelta(i)).isoformat() for i in range(a, b)]

# ---------- A. 云星铁占国区 iPhone 收入的比例 ----------
main_v, cloud_v = revenue("qimai_cn_iphone_revenue_est_usd_*"), revenue("qimai_cloudhsr_cn_iphone_revenue_est_usd_*")
print("[A] 云星铁 /（星铁本体 + 云星铁）的国区 iPhone 收入预估占比")
for y in ("2024", "2025", "2026"):
    ds = [d for d in main_v if d.startswith(y) and d in cloud_v]
    m, c = sum(main_v[d] for d in ds), sum(cloud_v[d] for d in ds)
    print(f"  {y}年（{len(ds)}天）：{100 * c / (m + c):.1f}%")


def share(ds):
    ds = [d for d in ds if d in main_v and d in cloud_v]
    if len(ds) < 4:
        return None
    m, c = sum(main_v[d] for d in ds), sum(cloud_v[d] for d in ds)
    return c / (m + c)


pre, post = [], []
for p in phases:
    d0 = dt.date.fromisoformat(p["start_date"])
    a, b = share(days(d0, -7, 0)), share(days(d0, 0, 8))
    if a is not None and b is not None:
        pre.append(a)
        post.append(b)
print(f"  按期算（{len(pre)}期）：开池前一周中位 {100 * st.median(pre):.1f}%，开池后一周中位 {100 * st.median(post):.1f}%")

# ---------- B. 自家游戏的机械挤占 ----------
H = {"日区": rank("qimai_jp_iphone_rank_*"), "国区": rank("qimai_cn_iphone_rank_*")}
S = {"日区": [rank("qimai_genshin_jp_iphone_rank_*"), rank("qimai_zzz_jp_iphone_rank_*")],
     "国区": [rank("qimai_genshin_cn_iphone_rank_*"), rank("qimai_zzz_cn_iphone_rank_*"),
              rank("qimai_cloudhsr_cn_iphone_rank_*")]}
print("\n[B] 自家游戏排在星铁前面的影响")
for m in H:
    lost = [d for d, v in H[m].items() if v == 2 and any(X.get(d) == 1 for X in S[m])]
    print(f"  {m}：星铁排第2、而第1是自家游戏的天数 = {len(lost)}")
print("  撞车期：开池当天和次日的最好名次（原始 -> 去掉排在前面的自家游戏后）")
for p in phases:
    if p.get("zzz_same_day") == "1" or p.get("gi_same_day") == "1":
        d0 = dt.date.fromisoformat(p["start_date"])
        out = []
        for m in H:
            cand = [(H[m][d], H[m][d] - sum(1 for X in S[m] if X.get(d) and X[d] < H[m][d]))
                    for d in days(d0, 0, 2) if d in H[m]]
            b = min(cand)
            out.append(f"{m} {b[0]}->{b[1]}")
        print("   ", p["start_date"], "  ".join(out))
