# 统计工具（被 run_tests.py 等脚本调用，自己不单独运行）
#
# 只用 Python 自带的功能，不需要装包。用到三种方法，都用"打乱标签"算 p 值：
#
# 1. 两组比平均（compare_groups）
#    例：主推的 11 期，中日差平均比非主推的 40 期低 0.27。
#    问题是：如果"主推"其实和中日差毫无关系，随便挑 11 期，平均也可能差这么多吗？
#    做法：把"主推"这个标签在 51 期里随机重新分配一万次，每次都算一遍差距。
#    p 值 = 随机分配下差距（不论正负）大于等于真实差距的比例。
#    p = 0.05 就是"纯靠运气，一百次里大约五次能差这么多"。
#
# 2. 控制大版本系列和促销后再比（controlled_effect）
#    问题：4.x 整体偏向日本，如果某一组的期刚好多在 4.x，这一组看起来就会偏日本，
#    但那是大版本系列造成的，不是这一组本身。
#    做法：先把"每个大版本系列（1.x/2.x/3.x/4.x）的整体水平"和"促销期"的影响从中日差里扣掉，
#    也从分组标签里扣掉，再看剩下的部分有没有关系（这就是回归里"加控制变量"的意思）。
#    算 p 值时只在同一系列的期之间打乱标签，保证每个系列的组成不变。
#    结果读作："同一大版本系列、同样促销条件下，这一组比另一组高多少"。
#    （星铁按"一年一个星球"策划，大版本系列和自然年在主分析的 51 期里完全重合。）
#
# 3. 分数和中日差有没有一起变（rank_correlation，用于剧情分这类 0–3 的分数）
#    秩相关：把两列都换成排名再看一致程度。+1 = 分数越高中日差越高，0 = 没关系，−1 = 反过来。
#    p 值同样靠打乱分数算。

import math
import random
import statistics as st


def _mean_diff(y, x):
    a = [v for v, g in zip(y, x) if g == 1]
    b = [v for v, g in zip(y, x) if g == 0]
    return st.mean(a) - st.mean(b)


def compare_groups(y, x, n_shuffle, seed=1):
    """y：每期的中日差；x：每期是否属于 A 组（1/0）。返回 (A 组平均 − B 组平均, p 值)"""
    obs = _mean_diff(y, x)
    rnd = random.Random(seed)
    xs = list(x)
    hits = 0
    for _ in range(n_shuffle):
        rnd.shuffle(xs)
        if abs(_mean_diff(y, xs)) >= abs(obs) - 1e-12:
            hits += 1
    return obs, hits / n_shuffle


def _solve(a, b):
    """解线性方程组 a·z = b（高斯消元）"""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-12:
            raise ValueError("控制变量之间完全重合")
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def residual_maker(groups, promo):
    """返回一个矩阵 M：M 乘任何一列数字，就把其中"各系列水平 + 促销"能解释的部分扣掉"""
    levels = sorted(set(groups))
    cols = [[1.0] * len(groups)]                                   # 截距
    cols += [[1.0 if g == lv else 0.0 for g in groups] for lv in levels[1:]]   # 大版本系列
    if len(set(promo)) > 1:
        cols.append([float(v) for v in promo])                      # 促销
    # 去掉在这个样本里全是 0 的列（例如某个系列没有促销期）
    cols = [c for c in cols if any(c)]
    k, n = len(cols), len(groups)
    ctc = [[sum(cols[i][t] * cols[j][t] for t in range(n)) for j in range(k)] for i in range(k)]
    # P = C (C'C)^-1 C'，M = I − P
    inv_cols = []
    for t in range(n):
        inv_cols.append(_solve(ctc, [cols[i][t] for i in range(k)]))
    P = [[sum(cols[i][s] * inv_cols[t][i] for i in range(k)) for t in range(n)] for s in range(n)]
    return [[(1.0 if s == t else 0.0) - P[s][t] for t in range(n)] for s in range(n)]


def _apply(M, v):
    return [sum(mi * vi for mi, vi in zip(row, v)) for row in M]


def controlled_coef(y, x, groups, promo):
    """只算控制大版本系列和促销后的效应，不算 p 值（逐个剔除时用）"""
    M = residual_maker(groups, promo)
    ry, rx = _apply(M, y), _apply(M, x)
    den = sum(v * v for v in rx)
    return None if den < 1e-12 else sum(a * b for a, b in zip(rx, ry)) / den


def controlled_effect(y, x, groups, promo, n_shuffle, seed=1):
    """控制大版本系列和促销后的效应。x 可以是 1/0，也可以是分数。
    返回 (效应, p 值)；x 是 1/0 时效应 = 同等条件下 A 组比 B 组高多少；x 是分数时 = 每高 1 分高多少。"""
    M = residual_maker(groups, promo)
    ry = _apply(M, y)

    def coef(xv):
        rx = _apply(M, xv)
        den = sum(v * v for v in rx)
        if den < 1e-12:
            return None
        return sum(a * b for a, b in zip(rx, ry)) / den

    obs = coef(x)
    if obs is None:
        return None, None
    # 只在同一系列内打乱
    idx_by_group = {}
    for i, g in enumerate(groups):
        idx_by_group.setdefault(g, []).append(i)
    rnd = random.Random(seed)
    xs = list(x)
    hits = 0
    valid = 0
    for _ in range(n_shuffle):
        for idx in idx_by_group.values():
            vals = [xs[i] for i in idx]
            rnd.shuffle(vals)
            for i, v in zip(idx, vals):
                xs[i] = v
        c = coef(xs)
        if c is None:
            continue
        valid += 1
        if abs(c) >= abs(obs) - 1e-12:
            hits += 1
    return obs, hits / valid


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def _pearson(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def rank_correlation(y, x, n_shuffle, seed=1):
    """秩相关和它的 p 值"""
    ry, rx = _ranks(y), _ranks(x)
    obs = _pearson(ry, rx)
    rnd = random.Random(seed)
    xs = list(rx)
    hits = 0
    for _ in range(n_shuffle):
        rnd.shuffle(xs)
        if abs(_pearson(ry, xs)) >= abs(obs) - 1e-12:
            hits += 1
    return obs, hits / n_shuffle


def ols(y, cols):
    """最小二乘：y = b0 + b1·cols[0] + b2·cols[1] + …，返回 [b0, b1, b2, …]
    读法：b1 = 其他列都不变时，cols[0] 每多 1，y 平均多多少"""
    X = [[1.0] * len(y)] + [[float(v) for v in c] for c in cols]
    k = len(X)
    xtx = [[sum(X[i][t] * X[j][t] for t in range(len(y))) for j in range(k)] for i in range(k)]
    xty = [sum(X[i][t] * y[t] for t in range(len(y))) for i in range(k)]
    return _solve(xtx, xty)
