# -*- coding: utf-8 -*-
r"""
第1步：整理卡池表，并用七麦名次核对卡池日期。

输入（data/raw/）：
  wiki_warps_raw.tsv                 B站 wiki「历史跃迁」页的角色活动跃迁（2026-10-25 读取）
  qimai_jp_iphone_rank_*.csv          七麦：星铁日区 iPhone 畅销榜每日名次
  qimai_cn_iphone_rank_*.csv          七麦：星铁国区 iPhone 畅销榜每日名次
输出（data/）：
  banners_detail.csv   一行 = 一个角色卡池（同一期可能同时开 2~3 个池）
  phases.csv           一行 = 一期（同一个开池日期），这是分析的基本单位

运行方法（在项目文件夹 C:\work\hsr-banner 里）：
  py scripts\build_banner_table.py
"""
import csv, re, datetime as dt, statistics as st, glob, os, math
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根目录
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data")

# 版本更新日期（B站 wiki「版本新增内容」页，2026-10-25 读取）
VERSION_DATE = {
    "1.0": "2023-04-26", "1.1": "2023-06-07", "1.2": "2023-07-19", "1.3": "2023-08-30",
    "1.4": "2023-10-11", "1.5": "2023-11-15", "1.6": "2023-12-27",
    "2.0": "2024-02-06", "2.1": "2024-03-27", "2.2": "2024-05-08", "2.3": "2024-06-19",
    "2.4": "2024-07-31", "2.5": "2024-09-10", "2.6": "2024-10-23", "2.7": "2024-12-04",
    "3.0": "2025-01-15", "3.1": "2025-02-26", "3.2": "2025-04-09", "3.3": "2025-05-21",
    "3.4": "2025-07-02", "3.5": "2025-08-13", "3.6": "2025-09-24", "3.7": "2025-11-05",
    "3.8": "2025-12-17", "4.0": "2026-02-13", "4.1": "2026-03-25", "4.2": "2026-04-22",
    "4.3": "2026-06-01", "4.4": "2026-07-15", "4.5": "2026-08-26", "4.6": "2026-09-28",
}


def parse_people(s):
    """'千冶•刃（虚无•火） 青雀（智识•量子）' -> [('千冶•刃','虚无','火'), ...]"""
    return re.findall(r"(\S+?)（(\S+?)•(\S+?)）", s or "")


def load_rank(pattern):
    """读七麦导出的名次表，只取「游戏(畅销)」这一列。返回 {日期: 名次}"""
    fn = glob.glob(os.path.join(RAW_DIR, pattern))[0]
    out = {}
    for row in list(csv.reader(open(fn, encoding="utf-8-sig")))[1:]:
        if row[2]:
            out[row[0]] = int(row[2])
    return out


# ---------- 1. 读 wiki 原始表，一行一个卡池 ----------
rows = list(csv.DictReader(open(os.path.join(RAW_DIR, "wiki_warps_raw.tsv"), encoding="utf-8"), delimiter="\t"))
detail = []
for r in rows:
    ver, half = r["版本"][:3], r["版本"][3:]          # 例：4.6下半 -> 4.6 / 下半
    start_txt, end_txt = [x.strip() for x in r["时间"].split("~")]
    if "版本更新后" in start_txt or "正式开服后" in start_txt:
        start = VERSION_DATE[ver]                     # 上半期从版本更新当天开始
    else:
        start = start_txt.split()[0].replace("/", "-")
    collab = (end_txt == "长期")                      # 联动池是长期池
    fives, fours = parse_people(r["5星角色"]), parse_people(r["4星角色"])
    detail.append(OrderedDict(
        version=ver, half=("联动" if collab else half), start_date=start, end_text=end_txt,
        banner_name=r["卡池名"], n_five=len(fives),
        banner_type=("联动" if collab else ("集录(多UP复刻)" if len(fives) > 1 else "单UP")),
        five_star="、".join(f[0] for f in fives),
        five_paths="、".join(f[1] for f in fives),
        five_elements="、".join(f[2] for f in fives),
        four_star="、".join(f[0] for f in fours),
    ))

# ---------- 2. 按时间顺序判断：第一次出现 = 新，之后 = 复刻 ----------
detail.sort(key=lambda d: (d["start_date"], d["banner_name"]))
seen = set()
for d in detail:
    names = d["five_star"].split("、")
    d["new_or_rerun"] = "、".join("新" if n not in seen else "复刻" for n in names)
    d["has_new_five"] = int("新" in d["new_or_rerun"])
    seen.update(names)

# ---------- 2b. 标出"开满整个版本"的长池 ----------
# 有些上半的新角色池一直开到版本结束（如昔涟、真珠），下半开新池时它还在。
# 判断方法：结束日期晚于下一个开池日，就说明它跨到了下一期。
# 联动池是插在半期中间开的，不算"下一期"，否则上半的普通池会被误判成长池。
starts = sorted({d["start_date"] for d in detail if d["banner_type"] != "联动"})
for d in detail:
    m = re.match(r"(\d{4})/(\d{2})/(\d{2})", d["end_text"])
    d["end_date"] = "-".join(m.groups()) if m else ""      # 联动池写"长期"，没有结束日
    d["spans_next_phase"] = int(bool(d["end_date"]) and any(d["start_date"] < s < d["end_date"] for s in starts))

# ---------- 3. 合并成「期」：同一开池日期为一期 ----------
phases = OrderedDict()
for d in detail:
    p = phases.setdefault(d["start_date"], OrderedDict(
        start_date=d["start_date"], version=d["version"], half=d["half"],
        n_banners=0, new_five="", rerun_five="", has_collab=0, has_jilu=0,
        has_long_banner=0, carryover_five=""))
    p["n_banners"] += 1
    p["has_long_banner"] = max(p["has_long_banner"], d["spans_next_phase"])   # 本期有开满整个版本的池
    for name, s in zip(d["five_star"].split("、"), d["new_or_rerun"].split("、")):
        key = "new_five" if s == "新" else "rerun_five"
        p[key] = "、".join(x for x in [p[key], name] if x)
    p["has_collab"] = max(p["has_collab"], int(d["banner_type"] == "联动"))
    p["has_jilu"] = max(p["has_jilu"], int(d["banner_type"].startswith("集录")))

# 本期开池时，还有哪些之前开的长池没结束
for p in phases.values():
    left = [d["five_star"] for d in detail
            if d["spans_next_phase"] and d["start_date"] < p["start_date"] < d["end_date"]]
    p["carryover_five"] = "、".join(left)

# ---------- 4. 用七麦名次核对日期 ----------
JP = load_rank("qimai_jp_iphone_rank_*.csv")
CN = load_rank("qimai_cn_iphone_rank_*.csv")


def jump(X, start):
    """开池前7天名次中位数 -> 开池当天和次日的最好名次；jump_log 越大，跳得越高"""
    d0 = dt.date.fromisoformat(start)
    pre = [X[k] for k in ((d0 - dt.timedelta(i)).isoformat() for i in range(1, 8)) if k in X]
    post = [X[k] for k in ((d0 + dt.timedelta(i)).isoformat() for i in range(0, 2)) if k in X]
    if not pre or not post:
        return "", "", ""
    return int(st.median(pre)), min(post), round(math.log(st.median(pre) / min(post)), 2)


for p in phases.values():
    for tag, X in (("jp", JP), ("cn", CN)):
        a, b, c = jump(X, p["start_date"])
        p[f"{tag}_pre7_median"], p[f"{tag}_best_d0d1"], p[f"{tag}_jump_log"] = a, b, c


def write(fn, data):
    with open(os.path.join(OUT_DIR, fn), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)


write("banners_detail.csv", detail)
write("phases.csv", list(phases.values()))
print("角色卡池:", len(detail), "个；期数:", len(phases))

# 核对A：开池日前后两边都没明显跳升的期（可能是日期错，也可能只是复刻太弱）
print("\n[核对A] 开池当天和次日两边名次都没明显跳升的期：")
for p in phases.values():
    if p["jp_jump_log"] != "" and p["jp_jump_log"] < 0.5 and p["cn_jump_log"] < 0.5:
        print(" ", p["start_date"], p["version"], p["half"], "新:", p["new_five"] or "-", "复刻:", p["rerun_five"] or "-")

# 核对B：名次单日大跳升却不在任何开池日（当天或次日）——如果有，可能漏了卡池
starts = [dt.date.fromisoformat(s) for s in phases]
print("\n[核对B] 单日名次变好2.5倍以上、却不在开池当天或次日的日子：")
for tag, X in (("日区", JP), ("国区", CN)):
    hits = []
    for d, v in X.items():
        d0 = dt.date.fromisoformat(d)
        prev = X.get((d0 - dt.timedelta(1)).isoformat())
        if prev and math.log(prev / v) >= 0.9:
            gaps = [(d0 - s).days for s in starts if (d0 - s).days >= 0]
            if not gaps or min(gaps) > 1:
                hits.append(d)
    print(" ", tag, hits if hits else "无")
