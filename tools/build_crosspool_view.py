# -*- coding: utf-8 -*-
"""build_crosspool_view.py — 生成**跨池因子视图** `docs/factor_library_crosspool.md`（2026-09-14）

## 为什么需要它（用户之问：「全A有效的是不是应该放进来？」）

调研结论：
  · `docs/factor_library.md`（全A 轨道）**最后更新 09-13 19:23** —— 因为 `all` 轨道的 state
    (`engine/loop_state.pkl`) mtime 就是 **09-13 15:46** ⇒ **全A 轨道自那以后没再跑过**，
    之后的算力全在 `1000/300/500` **池轨道**上 ⇒ 全A 库当然不新增。
  · 而**池轨道入库的 14 个因子，标签全部含 `all`**（`_all` 后缀 = **全A 口径通过**）
    ⇒ 它们**个个都过了全A**，只是被写进了 `factor_library_{pool}.md`（**池隔离**，§8.42）⇒ 全A 视角看不见。

⇒ 用户判断正确。但**不能直接把它们 append 进 `factor_library.md`**，原因有两条（都是硬伤）：
  ① `factor_library.md` 是 **append-only + 编号连续（F01..F41）**，其「当前 N 个入库」由 `_lib_sync`
     按 **`len(bank)`** 重写 ⇒ 手工插入的行会让**文档行数 ≠ state.bank 数**（§8.44 那个坑的翻版），
     且下次全A 轨道一跑，计数就被覆盖、编号就错位。
  ② **同一式子会在多个池被独立"发现"**（每个池有自己的 bank 与 decorr 宇宙）——
     实测 `corr100(cs_scale(mf_x_sell), mf_l_sell)` 同时是 **300:F02 / 500:F01 / 1000:F01**。
     直接合并会**重复入场**，且看不出"它到底在哪些池有效"。

⇒ 所以本脚本生成一个**独立的、可重复生成的派生视图**（不是 append-only 日志、不占编号、不被引擎改写）。

## 它额外解决的问题：**池标签的"并集修正"**

池库文件自己写着警告：
  > ⚠ 池标签是「在这些池上测出来的」⇒ **不同代的标签不能直接比**。
  > 典型陷阱：只测 300/500 时，因子会被标成 `csi_all_only`（"只有全A通过 ⇒ 小盘溢价嫌疑"）
  > —— **其实只是没测 1000**。

实测正是如此：`corr100(cs_scale(mf_x_sell), mf_l_sell)` 在 **300 库**被标 `csi_all_only`（负面），
在 **1000 库**被标 `csi1000_all`（正面）—— 同一个式子两种结论。
⇒ 本视图把各池「测过的池」**取并集**后，用 `loop_pools.derive_tag`（**单一事实源**）**重算标签** ⇒
   得到**不受"测了哪些池"影响**的标签，并给出「旧标签 → 新标签」对照。

## 输出
  · `docs/factor_library_crosspool.md`
      - 摘要（含「其中已在全A 库中的有几个」—— 直接回答"放进来会不会重复"）
      - 表A **全A 有效**（重算标签为 `all3`/`csi*_all`/`csi_all_only`），按全A Calmar 降序
      - 表B **仅池内有效**（`csi*_only` / `csi300_500` 等）
      - 跨池重复清单 + 标签修正对照表

## ★ 口径：以**文档**为主，state.bank 只作"仍在库?"的核对
第一版用 `state.bank` 当唯一口径，结果 `唯一因子 11 = 各池 bank 之和(2+3+6)` ⇒ **去重没起作用**。
原因：**恰恰是那几个跨池重复的因子，属于"曾入库但 state 丢了"的情况**（300/500 的
`corr100(cs_scale(mf_x_sell), mf_l_sell)` 只在**文档**里、不在 bank）⇒ 用 bank 当口径会**漏掉它们**。
⇒ 改为以 `factor_library_{pool}.md`（**append-only 的入库历史**）为主口径，
   `state.bank` 只用来标「**仍在 bank?**」一列。（与 `tools/backfill_library_pool.py`
   的取向一致：那里是"以 bank 为准，**不重复补录**"；这里是"以文档为准，**不遗漏历史**"。）

## 用法
    python tools/build_crosspool_view.py              # 生成（默认 300,500,1000）
    python tools/build_crosspool_view.py --print      # 同时把摘要打到屏幕
"""
import argparse
import csv
import io
import os
import pickle
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)

import loop_pools as LP       # noqa: E402  ★ 标签单一事实源

BT = '`'


def _state_bank(tag):
    """该池**真正入库**的表达式集合（唯一口径 = state 的 `bank`）。

    ⚠ 不用 archive 的 `passed=True` 代替（§8.44 实测）：过 L2 后还有 `[FSA] 通过但不入库`
      与 `[收益流去重] 不入库` 两道闸门 ⇒ `passed=True` 会**多于** bank。
    ⚠ 读 state 前必须把引擎的类注入 `__main__`（pkl 是引擎以 `__main__` 身份存的，
      `Node` 记作 `__main__.Node`），否则 `Can't get attribute 'Node'`。
    """
    sfx = '' if tag == 'all' else '_' + tag
    sf = os.path.join(ENG, 'loop_state{}.pkl'.format(sfx))
    if not os.path.exists(sf):
        return set()
    try:
        import loop_engine as LE
        for n in dir(LE):
            if n[:1].isupper() and isinstance(getattr(LE, n), type):
                setattr(sys.modules['__main__'], n, getattr(LE, n))
    except Exception:
        pass
    try:
        st = pickle.load(open(sf, 'rb'))
        return {str(x) for x in (st.get('bank', []) or [])}
    except Exception as e:
        print('  [!] 读 {} 失败: {}: {}'.format(sf, type(e).__name__, e))
        return set()


def _archive(tag):
    p = os.path.join(DOCS, 'loop_archive{}.csv'.format('' if tag == 'all' else '_' + tag))
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding='utf-8-sig')
    except Exception as e:
        print('  [!] 读 {} 失败: {}'.format(p, type(e).__name__))
        return pd.DataFrame()


def _poolobs(tag):
    p = os.path.join(DOCS, 'loop_pool_obs{}.csv'.format('' if tag == 'all' else '_' + tag))
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding='utf-8-sig')
    except Exception as e:
        print('  [!] 读 {} 失败: {}'.format(p, type(e).__name__))
        return pd.DataFrame()


def parse_library(pool):
    """解析 `docs/factor_library_{pool}.md` → [{no, gen, expr, tag}]。

    ★ 这是**入库历史的主口径**（append-only），含"曾入库但 state 丢了"的条目 ——
      而那几个恰恰是跨池重复的（见模块 docstring 的「口径」一节），漏掉它们就去不了重。
    """
    import re
    f = os.path.join(DOCS, 'factor_library_{}.md'.format(pool))
    if not os.path.exists(f):
        return []
    t = io.open(f, encoding='utf-8').read()
    # ⚠ `re.split` 带**捕获组**时返回 `[前段, 捕获1, 段1, 捕获2, 段2, ...]`
    #   ⇒ 必须**步长 2** 取（`parts[k]`=编号, `parts[k+1]`=正文）。
    #   初版写成 `for blk in re.split(...)[1:]` 把正文当整块 ⇒ 编号全变成 `?`。
    parts = re.split(r'\n### (F\d+) · ', t)
    out = []
    for k in range(1, len(parts) - 1, 2):
        no, body = parts[k], parts[k + 1]
        m_g = re.search(r'gen(\d+) 入库', body)
        m_e = re.search(r'```\n([^\n]+)', body)
        m_t = re.search(r'池标签：\*\*' + BT + r'?([^' + BT + r'\*\n]+)', body)
        # ★ 符号 `sign`（2026-09-14, §1.23）：明细块里由 `_lib_sync` 写入 /
        #   `tools/backfill_library_sign.py` 回填。两种形态都覆盖：
        #     `- **符号 \`sign\`：\`-1\`**（★ ...）`   ← 有值
        #     `- 符号 \`sign\`：**未记录**（...）`     ← 未落地（不臆造）
        m_s = re.search(r'符号 ' + BT + r'sign' + BT + r'：\*{0,2}' + BT + r'?([+\-]?\d+)', body)
        if not m_e:
            continue
        out.append(dict(no=no,
                        gen=int(m_g.group(1)) if m_g else None,
                        expr=m_e.group(1).strip(),
                        tag=m_t.group(1).strip() if m_t else None,
                        sign=int(m_s.group(1)) if m_s else None))
    return out


def load_strip(pool):
    """`docs/loop_strip_style_{pool}.csv` → {(gen, expr): row}（**剥风格**对照，2026-09-14 加）。

    ★ 为什么必须收进来：池轨道的**入库判定没有经过剥风格这道关**（`run_tracks.py` 传了
      `--strip_style` 但没传 `--min_strip_calmar`，后者默认 -1 = **只记录不拦**）
      ⇒ 池库里混进了**纯风格因子**（实测 7/14 剥完风格 Calmar 转负）。
      本视图是"下游要读的完整表"，**必须把风格暴露一并呈现**，否则会误导。
    """
    p = os.path.join(DOCS, 'loop_strip_style_{}.csv'.format(pool))
    if not os.path.exists(p):
        return {}
    out = {}
    try:
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')):
            try:
                out[(int(r['gen']), r['expr'])] = r
            except Exception:
                continue
    except Exception:
        return {}
    return out


def strip_verdict(sr):
    """由剥风格记录给出判定档位（与 `tools/check_strip_style_pool.py` 同一套标准）。"""
    if not sr:
        return 'D', '无记录'
    sc, sa = _san(sr.get('strip_calmar')), _san(sr.get('strip_ann_ex'))
    if not np.isfinite(sc):
        return 'D', '无记录'
    if (np.isfinite(sa) and sa <= 0) or sc <= 0:
        return 'C', '纯风格'
    if sc >= 0.30:
        return 'A', '独立有效'
    return 'B', '弱独立'


def _sign_cell(v):
    """`sign`（**方向**）的表格单元格。

    ★ 为什么要单列（2026-09-14, §1.23）：引擎求值时对 `sign<0` 的候选**取负**
    （让"值越大越好"）。下游拿到因子值 h5 **直接排序选股、不乘 `sign`**
    ⇒ **方向反了、组合反向选股** ✗（精选池实测 7 个里 6 个 `sign=-1`）⇒ 必须显式给出。
    ⚠ 缺失时写「未记录」，**绝不臆造**（roadmap §8.45 铁律）。
    """
    if v is None:
        return '未记录'
    return '**`%+d`**' % int(v) if int(v) < 0 else '**`+%d`**' % int(v)


def collect(pools):
    """把各池**文档里的入库因子**汇成 {expr: 记录}（**按 expr 去重合并**）。

    每条记录：
      expr / srcs [pool...] / gens {pool: gen} / _no {pool: F编号} / _tag_doc {pool: 写入时标签} /
      allA 指标（取各路中 Calmar 最大的那份，附 from_pool/gen）/ 池内 {pool: (ann_ex, calmar)} /
      in_bank {pool: bool}
    """
    merged = {}
    for pool in pools:
        entries = parse_library(pool)
        bank = _state_bank(pool)
        ar = _archive(pool)
        ob = _poolobs(pool)
        strip = load_strip(pool)
        for en in entries:
            expr = en['expr']
            rec = merged.setdefault(expr, dict(expr=expr, srcs=[], gens={}, _no={},
                                               _tag_doc={}, allA=None, pool_met={},
                                               in_bank={}, cat=None, leaf=None, strip={},
                                               sign=None))
            # ★ 同一式子在各池应当 sign 一致（同表达式 ⇒ 同方向）；不一致则标出来（下面会用）
            if en.get('sign') is not None:
                if rec['sign'] is None:
                    rec['sign'] = en['sign']
                elif rec['sign'] != en['sign']:
                    rec['sign_conflict'] = True
            # ---- 剥风格（同一 (gen,expr) 优先；退回该池任意代）----
            sr = strip.get((en['gen'], expr))
            if sr is None:
                cands = [v for (g, e), v in strip.items() if e == expr]
                sr = cands[0] if cands else None
            if sr is not None:
                rec['strip'][pool] = sr
            if pool not in rec['srcs']:
                rec['srcs'].append(pool)
            rec['gens'][pool] = en['gen']
            rec['_no'][pool] = en['no']
            rec['_tag_doc'][pool] = en['tag']
            rec['in_bank'][pool] = bool(bank and expr in bank)
            # ---- 全A 指标：从该池 archive 的该代表达式行里取（props 结构化，避免解析 md） ----
            if len(ar) and 'expr' in ar.columns:
                q = ar[ar['expr'].astype(str) == expr]
                if len(q):
                    if 'gen' in q.columns and en['gen'] is not None:
                        q2 = q[q['gen'] == en['gen']]
                        q = q2 if len(q2) else q
                    r0 = q.iloc[-1]
                    cand = dict(ic=r0.get('ic'), ann_ex=r0.get('ann_ex'),
                                calmar=r0.get('calmar'), sharpe=r0.get('sharpe'),
                                turn=r0.get('turn'), neg_yr=r0.get('neg_yr'),
                                dd=r0.get('dd'), cat=r0.get('cat'), leaf=r0.get('leaf'),
                                gen=int(r0['gen']) if 'gen' in r0 else en['gen'],
                                from_pool=pool)
                    if rec['cat'] is None:
                        rec['cat'], rec['leaf'] = cand.get('cat'), cand.get('leaf')
                    if rec['allA'] is None or _num(cand.get('calmar')) > _num(rec['allA'].get('calmar')):
                        rec['allA'] = cand
            # ---- 池内指标（key = 被评测的池，用于并集重算标签） ----
            #  ⚠⚠ **必须按「入库那一代」过滤**（2026-09-14 实测踩到）：
            #    同一个表达式在**别的代**也会作为**候选**出现在 `loop_pool_obs` 里，
            #    而那些代可能测了更多池 ⇒ 不过滤就会把"当时没测/只是候选"的池算进并集，
            #    把标签**错误升级**（实测 `ts_mean150(mul(barra_residual_volatility,...))`
            #    在 500 库 gen3 写入时是 `csi300_500_all`，却被误重算成 `all3`）。
            #  `en['gen']` 缺失(极少数) 时才退回全表（并视为低置信）。
            if len(ob) and 'expr' in ob.columns:
                q2 = ob[ob['expr'].astype(str) == expr]
                if len(q2) and 'gen' in q2.columns and en['gen'] is not None:
                    q3 = q2[q2['gen'] == en['gen']]
                    q2 = q3 if len(q3) else q2
                for _, rr in q2.iterrows():
                    pt = str(rr.get('pool'))
                    met = (rr.get('ann_ex'), rr.get('calmar'))
                    if pt not in rec['pool_met'] or _num(met[1]) > _num(rec['pool_met'][pt][1]):
                        rec['pool_met'][pt] = met
    return merged


def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else -1e9
    except Exception:
        return -1e9


def recount_tag(rec, pools):
    """用**各来源池观测到的并集**重算标签（`loop_pools.derive_tag` = 单一事实源）。

    ★★ 分母是**配置的池全集** `pools`（= 引擎 `--pools` 的值，本轨道恒为 `300,500,1000`），
       **不是**"这一代实际算出来的池"。理由（2026-09-14 实测踩到）：
       引擎里是 `derive_tag(_oka, _okp, _pools)`，而 `_pools` **始终是配置的三个池**
       （`run_tracks.py` 恒传 `--pools=300,500,1000`），只有**算出来的**池才进 `_okp`
       ⇒ **没测的池在 `okp.get(p)` 上是 falsy** ⇒ `all3` 天然要求**三个池都通过**。
       我第一版把分母写成"实际算过的池"，于是"只测 300/500 且都通过"被判成 `all3`
       （实测把 `ts_mean150(mul(barra_residual_volatility,...))` 从 `csi300_500_all` 误升为 `all3`）。

    ★ "并集"体现在：同一表达式可能在**多个池、多代**分别被评测过，
      每个来源各自贡献"它测到的那些池"的结果 ⇒ 合并后 `okp` 覆盖得更全（这正是本视图的价值）。
    """
    a = rec.get('allA') or {}
    # ★ 2026-09-14（§1.19 ③）：Calmar **优先日频**，缺失回退期频（旧数据不炸）
    _ac = a.get('calmar_d')
    _ac = _ac if (_ac is not None and np.isfinite(_san(_ac))) else a.get('calmar')
    ok_all = (a.get('ann_ex') is not None and np.isfinite(_san(a.get('ann_ex')))
              and float(a['ann_ex']) > 0
              and np.isfinite(_san(_ac))
              and float(_ac) >= LP.TAG_CAL_MIN)
    okp = {}
    for p, met in rec['pool_met'].items():
        # met = (calmar, ann_ex, ...) —— ★ 池内也要卡 Calmar（§1.18 B；原来只要超额>0）
        _pc = met[2] if len(met) > 2 else met[0]        # 日频 calmar（若视图里有）
        if _pc is None or not np.isfinite(_san(_pc)):
            _pc = met[0]
        okp[p] = (met[0] is not None and np.isfinite(_san(met[0]))
                  and float(met[0]) > LP.TAG_POOL_FLOOR
                  and np.isfinite(_san(_pc))
                  and float(_pc) >= LP.TAG_POOL_FLOOR_CAL)
    tested = [p for p in pools if p in rec['pool_met']]
    if not tested:
        return ('none' if not ok_all else 'csi_all_only'), ok_all, tested, okp
    return LP.derive_tag(ok_all, okp, pools), ok_all, tested, okp


def _order(k):
    """判定档位排序（取"最好"的那份时用：A > B > C > D）。"""
    return {'A': 3, 'B': 2, 'C': 1, 'D': 0}.get(k, 0)


def _san(v):
    try:
        return float(v)
    except Exception:
        return float('nan')


def _pct(v):
    v = _san(v)
    return '{:+.1f}%'.format(100 * v) if np.isfinite(v) else '-'


def _f(v, n=3):
    v = _san(v)
    return ('{:.' + str(n) + 'f}').format(v) if np.isfinite(v) else '-'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='300,500,1000')
    ap.add_argument('--out', default=os.path.join(DOCS, 'factor_library_crosspool.md'))
    ap.add_argument('--print', dest='do_print', action='store_true')
    a = ap.parse_args()
    pools = [x.strip() for x in a.pools.split(',') if x.strip()]

    merged = collect(pools)
    if not merged:
        print('没有可汇总的池库（先跑池轨道 / 修好 state）')
        return 1

    # 全A 库里的表达式（用于回答"放进来会不会重复"）
    all_lib = _state_bank('all')
    if not all_lib:
        t = os.path.join(DOCS, 'factor_library.md')
        if os.path.exists(t):
            import re
            all_lib = set(re.findall(r'^([a-z_][A-Za-z0-9_]*\([^\n]*)$',
                                     io.open(t, encoding='utf-8').read(), re.M))

    rows = []
    for expr, rec in merged.items():
        tag_new, ok_all, tested, okp = recount_tag(rec, pools)
        rows.append(dict(rec=rec, expr=expr, tag=tag_new, ok_all=ok_all,
                         tested=tested, okp=okp, old=rec['_tag_doc'],
                         in_all_lib=(expr in all_lib),
                         still_bank=any(rec['in_bank'].values())))
        # ★ 剥风格判定：取各来源池里**最好**的那份（口径同 check_strip_style_pool.py）
        _sv, _sr = 'D', None
        for _p, _r in (rec.get('strip') or {}).items():
            _k, _txt = strip_verdict(_r)
            if _sr is None or _order(_k) > _order(_sv):
                _sv, _sr = _k, _r
        r_ = rows[-1]
        r_['strip_k'], r_['strip_r'] = _sv, _sr
    # ★ 排序（2026-09-14 改）：**先按"剥风格判定"降序**（独立有效 → 弱独立 → 纯风格），
    #   再按全A Calmar。理由：只看未剥风格 Calmar 会把**纯风格因子排在最前**（实测
    #   `corr100(mf_s_bqty, mf_x_sell)` 全A Calmar 1.193 但剥完 -0.075）⇒ **排序本身就是误导**。
    rows.sort(key=lambda r: (not r['ok_all'], -_order(r.get('strip_k', 'D')),
                             -_num((r['rec']['allA'] or {}).get('calmar'))))

    n_all_eff = sum(1 for r in rows if r['ok_all'])
    n_dup = sum(1 for r in rows if r['in_all_lib'])
    multi = [r for r in rows if len(r['rec']['srcs']) > 1]
    n_entries = sum(len(r['rec']['srcs']) for r in rows)

    L = []
    L += ['# 跨池因子视图（全A 有效因子汇总）', '']
    L += ['> **派生视图**，由 `python tools/build_crosspool_view.py` 生成 —— '
          '**可随时重建**，不占编号、不被引擎改写。', '']
    L += ['> 为什么需要：`docs/factor_library.md`（全A 轨道）是 **append-only 且编号连续**，'
          '其计数由 `_lib_sync` 按 `len(bank)` 重写 ⇒ **手工插入会让文档 ≠ state**；'
          '且**同一式子会在多个池被独立发现**（各池 bank/decorr 独立）⇒ 直接合并会重复入场。',
          '']
    L += ['> 本视图按 **表达式去重**，把「在哪些池被发现」「在哪些池有效」合并成一行，'
          '并用 `loop_pools.derive_tag`（**单一事实源**）重算标签 ——'
          ' **各来源池测到的结果取并集**（同一个式子在 A 池的轨迹里测了 300/500、'
          '在 B 池的轨迹里测了三个池 ⇒ 合并后信息最全），'
          '而 `all3` 的分母仍是**引擎配置的池全集**（`--pools` 恒为 `300,500,1000`）'
          '—— 即"**三个池都通过**"才算真 alpha。'
          '⇒ 解决池库文件自己警告的「不同代标签不能直接比」问题。', '']
    L += ['## 摘要', '', '| 项 | 值 |', '|---|---|']
    L += ['| 参与的池 | {} |'.format(', '.join(pools))]
    L += ['| 池入库**条目**合计 | {} 条 |'.format(n_entries)]
    L += ['| **去重后唯一因子** | **{} 个** |'.format(len(rows))]
    L += ['| ★ **其中「全A 有效」** | **{} 个** |'.format(n_all_eff)]
    L += ['| 其中已存在于全A 库(`factor_library.md`) | **{} 个** |'.format(n_dup)]
    L += ['| 跨池重复（>1 个池入库） | **{} 个** |'.format(len(multi))]
    L += ['| 其中「仍在 state.bank」（非仅存于文档） | **{} 个** |'.format(
        sum(1 for r in rows if r['still_bank']), )]
    # ★★ 剥风格体检摘要（2026-09-14）：这是**比"全A 有效"更关键的**质量维度
    _sc = {}
    for r in rows:
        _sc[r.get('strip_k', 'D')] = _sc.get(r.get('strip_k', 'D'), 0) + 1
    L += ['| ★ **剥风格判定**：A 独立有效 | **{} 个** |'.format(_sc.get('A', 0))]
    L += ['| ★ 剥风格判定：B 弱独立 | **{} 个** |'.format(_sc.get('B', 0))]
    L += ['| ★★ **剥风格判定：C 纯风格（应拒）** | **{} 个** |'.format(_sc.get('C', 0))]
    if _sc.get('D'):
        L += ['| 剥风格判定：D 无记录 | {} 个 |'.format(_sc.get('D'))]
    L += ['']
    if _sc.get('C'):
        L += ['⇒ ⚠⚠ **{} / {} 个池因子是「纯风格」**（剥掉 lncap+lnamt 后超额转负）—— '
              '**根因是入库判定漏了一道关**：`tools/run_tracks.py` 传了 `--strip_style`（记录）'
              '但**没传** `--min_strip_calmar`（默认 `-1` = **只记录不拦**）⇒ 剥风格结果'
              '**从未参与入库判定**；而 `derive_tag` 的 `ok_all` 也是**未剥风格**口径 ⇒ '
              '`all3` 号称的"真 alpha"**含风格水分**。'.format(_sc.get('C'), len(rows)), '']
    if n_dup == 0:
        L += ['⇒ ★ **{} 个「全A 有效」的池因子，一个都不在 `factor_library.md` 里**'
              ' ⇒ 全A 库确实缺了它们（**用户的判断成立**）。'.format(n_all_eff), '']
        L += ['> ⚠ 但**不要直接 append 进 `factor_library.md`**：它是 append-only + 编号连续，'
              '计数由 `_lib_sync` 按 `len(bank)` 重写 ⇒ 手插行会造成**文档 ≠ state**，'
              '且下次全A 轨道一跑计数就被覆盖、编号错位。⇒ 用**本视图**提供全A 视角。', '']
    else:
        L += ['⇒ 有 **{} 个**已与全A 库重叠 ⇒ **"放进来"会产生重复**，'
              '这正是本视图用「去重 + 来源标注」而不是直接合并的原因。'.format(n_dup), '']

    # ---- 表 A：全A 有效 ----
    L += ['## 表A · 全A 有效（**先按"剥风格判定"降序**，再按全A Calmar）', '']
    L += ['`all3` = 全A **且 300/500/1000 三个池全部通过**；'
          '`csi*_all` = 全A + 列出的那些池通过；`csi_all_only` = 仅全A（**须三池都测过才可信**）。'
          '「来源池(编号)」= 在哪些池的库里入库 + 各池库里的 F 编号；'
          '「仍在bank?」中的 `⚠仅文档` = **曾入库但 state 丢了**（详见 §8.44）。', '']
    L += ['> ★★ **「风格判定」列是本表最重要的列**（2026-09-14 加）：'
          '`A 独立有效`(`剥Calmar≥0.30`) / `B 弱独立`(0~0.30) / '
          '**`C 纯风格`**（**剥掉 lncap+lnamt 后超额转负** ⇒ 信息基本全是市值/成交额风格暴露）/ '
          '`D 无记录`。', '']
    L += ['> ★★ **「`sign`」列（2026-09-14 加, §1.23）**：引擎求值时对 `sign<0` 的候选**取负**'
          '（让"值越大越好"）。',
          '> 下游拿到 `facs/` 的因子值 h5 **直接排序选股、不乘 `sign`** ⇒ '
          '**方向反了、组合反向选股** ✗（精选池实测 7 个里 **6 个 `sign=-1`** ⇒ 中招概率很高）。',
          '> ⚠ 「未记录」= 该因子**没在 `facs/` 落地**，`sign` 无从取得 —— **不臆造**'
          '（roadmap §8.45 铁律）。', '']
    L += ['> ⚠ **为什么必须看这一列**：池轨道的**入库判定没有经过剥风格这道关** —— '
          '`tools/run_tracks.py` 传了 `--strip_style`（记录）但**没传** `--min_strip_calmar`'
          '（默认 `-1` = **只记录不拦**）⇒ 池库里混进了纯风格因子（实测 **7/14**）。'
          '⇒ **只看"全A Calmar"排序会被误导**（实测最高的两个剥完都是负的）。', '']
    L += ['| # | 表达式 | **`sign`** | 风格判定 | 全A超额 | Calmar | **剥风格超额** | **剥风格Calmar** | 池标签(重算) | 来源池(编号) | 换手 | 负年 | 仍在bank? |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for i, r in enumerate([x for x in rows if x['ok_all']], 1):
        A = r['rec']['allA'] or {}
        sr = r.get('strip_r')
        k = r.get('strip_k', 'D')
        _mark = {'A': '**A 独立有效**', 'B': 'B 弱独立',
                 'C': '❌ **C 纯风格**', 'D': 'D 无记录'}[k]
        L.append('| {} | {} | {} | {} | **{}** | **{}** | {} | {} | **{}** | {} | {} | {} | {} |'.format(
            i, '{}{}{}'.format(BT, r['expr'], BT), _sign_cell(r['rec'].get('sign')),
            _mark,
            _pct(A.get('ann_ex')), _f(A.get('calmar')),
            _pct(sr.get('strip_ann_ex')) if sr else '-',
            ('**%s**' % _f(sr.get('strip_calmar'))) if sr else '-',
            r['tag'],
            ' · '.join('{}({})'.format(p, r['rec']['_no'].get(p, '?')) for p in r['rec']['srcs']),
            _pct(A.get('turn')), A.get('neg_yr', '-'),
            '✓' if r['still_bank'] else '⚠仅文档'))
    L += ['']

    # ---- 表 B：仅池内有效 ----
    rest = [x for x in rows if not x['ok_all']]
    if rest:
        L += ['## 表B · 仅池内有效（全A 口径不过）', '']
        L += ['| # | 表达式 | **`sign`** | 池标签(重算) | 来源池 | 全A超额 | Calmar | 池内有效池 |',
              '|---|---|---|---|---|---|---|---|']
        for i, r in enumerate(rest, 1):
            A = r['rec']['allA'] or {}
            okp = [p for p, v in r['okp'].items() if v]
            L.append('| {} | {} | {} | **{}** | {} | {} | {} | {} |'.format(
                i, '{}{}{}'.format(BT, r['expr'], BT), _sign_cell(r['rec'].get('sign')),
                r['tag'],
                '/'.join(r['rec']['srcs']), _pct(A.get('ann_ex')), _f(A.get('calmar')),
                ', '.join(okp) or '—'))
        L += ['']

    # ---- 跨池重复 ----
    if multi:
        L += ['## 跨池重复（同一式子被多个池独立入库）', '',
              '⚠ 各池 bank / decorr 相互独立 ⇒ 池轨道**不会跨池去重**。'
              '这些因子在多池入库，说明信号**跨域稳健**；但也提示**合成时不要重复计入**。', '',
              '| 表达式 | 来源池 | 各池写入时标签 | **重算标签** |', '|---|---|---|---|']
        for r in multi:
            L += ['| {}{}{} | {} | {} | **{}** |'.format(
                BT, r['expr'], BT, '/'.join(r['rec']['srcs']),
                ' · '.join('{}={}'.format(p, r['old'].get(p, '?')) for p in r['rec']['srcs']),
                r['tag'])]
        L += ['']

    # ---- 标签修正对照 ----
    fixed = [r for r in rows if any(r['old'].get(p) != r['tag'] for p in r['rec']['srcs'])]
    if fixed:
        L += ['## 池标签修正对照（并集重算）', '',
              '池库文件自带警告：**不同代测的池不同 ⇒ 标签不能直接比**。'
              '典型陷阱：只测 300/500 时被标 `csi_all_only`（"小盘溢价嫌疑"），'
              '**其实只是没测 1000**。', '',
              '| 表达式 | 来源池 | 写入时标签（测哪些池就写哪个） | **重算标签** | 含义 |',
              '|---|---|---|---|---|']
        for r in fixed:
            L += ['| {}{}{} | {} | {} | **{}** | {} |'.format(
                BT, r['expr'], BT, '/'.join(r['rec']['srcs']),
                ' · '.join('{}={}'.format(p, r['old'].get(p, '?')) for p in r['rec']['srcs']),
                r['tag'], _desc(r['tag'], r['tested']))]
        L += ['']

    L += ['---', '', '## 相关文件导航', '', '| 文件 | 内容 |', '|---|---|']
    L += ['| `docs/factor_library_crosspool.md`（本文件） | **跨池派生视图**（去重 + 并集重算标签） |']
    L += ['| `docs/factor_library.md` | 全A 轨道的入库因子（append-only，编号连续） |']
    for p in pools:
        L += ['| `docs/factor_library_{}.md` | 池 **{}** 的入库因子（append-only，池隔离） |'.format(p, p)]
    L += ['| `docs/loop_pool_obs_{pool}.csv` | 各池候选的**池内指标**（本视图的数据源） |']
    L += ['| `docs/loop_archive_{pool}.csv` | 各池每代 L2 流水（全A 口径指标来源） |']

    outp = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    io.open(outp, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('[DONE] -> {}'.format(outp))
    print('  唯一因子 {} 个; **全A 有效 {} 个**; 已在全A库 {} 个; 跨池重复 {} 个'.format(
        len(rows), n_all_eff, n_dup, len(multi)))
    if a.do_print:
        for r in rows:
            A = r['rec']['allA'] or {}
            print('  [{}] {:<16s} {:<26s} 全A超额={:>7s} Calmar={:>6s} 来源={}'.format(
                '全A' if r['ok_all'] else '池内', r['tag'], r['expr'][:26],
                _pct(A.get('ann_ex')), _f(A.get('calmar')), '/'.join(r['rec']['srcs'])))
    return 0


def _desc(tag, tested):
    if tag == 'all3':
        return '真 alpha（全A + 被测池全通过）'
    if tag == 'csi_all_only':
        return '仅全A 通过（**注意**：仅当所有池都测过时才可信）'
    if tag.endswith('_all'):
        return '全A + ' + tag[3:-4] + ' 池通过'
    return '仅池内有效'


def _old_tag(pool, expr):
    """从池库 md 里取该表达式的**原始**（写入时的）标签。"""
    f = os.path.join(DOCS, 'factor_library_{}.md'.format(pool))
    if not os.path.exists(f):
        return None
    import re
    t = io.open(f, encoding='utf-8').read()
    for blk in re.split(r'\n### F\d+ · ', t)[1:]:
        m = re.search(r'```\n([^\n]+)', blk)
        if m and m.group(1).strip() == expr:
            mt = re.search(r'池标签：\*\*' + BT + r'?([^' + BT + r'\*\n]+)', blk)
            if mt:
                return mt.group(1).strip()
    return None


if __name__ == '__main__':
    sys.exit(main())
