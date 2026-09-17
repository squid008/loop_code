# -*- coding: utf-8 -*-
"""build_facs.py — 把**已入库因子**的因子值落地到 `facs/`（2026-09-14）

## 用途（用户之问：「facs 文件夹可以加，然后因子值是用 h5 存吧？」）
`docs/software_framework.md` §4.3 早已定稿"每因子一 h5"的落地格式，但标注 **M6 未落地**。
本脚本把它落地，**顺带做两件事**（都要载面板，一次做完最省）：

  1. **因子值 → `facs/{hash前2位}/{名字}/values.h5`**（格式见 `engine/factor_store.py`）
  2. **补测剥风格**（§1.9 待办③）：对**没有剥风格记录**的已入库因子，重跑「原 + 剥风格」回测
     ⇒ 结果写 `docs/loop_strip_style_bank.csv`（**新文件**，不污染已有的 per-pool 表）

## ★ 为什么要补测剥风格
实测（`python tools/check_strip_style_pool.py`）：**约一半入库因子是"纯风格"**
（全A 口径 Calmar 漂亮，剥掉 lncap+lnamt 后转负）。而 `docs/loop_strip_style.csv`（全A 轨道）
**只有 11/41** —— 因为 `--strip_style` 是 09-12 才加的 ⇒ **另 30 个从未测过**（已知盲区）。

## ★ 内置自检（很重要）
每个因子算完后，把**算出的 IC** 与 `factor_library*.md` 里记录的 IC 对比；
偏差 > `--ic_tol`（默认 0.002）就**打印警告**。
⇒ 否则口径没对齐（轴序/符号/子面板/停牌处理）时，落地的是**错的因子值**而不会有人发现
   （本项目 §8.44 的教训：**失败必须吼出来，不能静默**）。

## 用法
    python tools/build_facs.py --limit=2          # 冒烟：只做 2 个（含自检）
    python tools/build_facs.py --no-strip         # 只落地因子值，跳过剥风格补测（快）
    python tools/build_facs.py                    # 全量（41 全A + 11 池，含剥风格补测）
"""
import argparse
import csv
import io
import json
import os
import pickle
import re
import sys
import time

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)


def parse_library(pool):
    """读 `factor_library{_pool}.md` → [{no, gen, expr, ic, calmar, ann_ex, turn}]（文档=主口径）。"""
    sfx = '' if pool == 'all' else '_' + pool
    f = os.path.join(DOCS, 'factor_library{}.md'.format(sfx))
    if not os.path.exists(f):
        return []
    t = io.open(f, encoding='utf-8').read()
    parts = re.split(r'\n### (F\d+) · ', t)
    out = []
    for k in range(1, len(parts) - 1, 2):
        no, body = parts[k], parts[k + 1]
        m_e = re.search(r'```\n([^\n]+)', body)
        m_m = re.search(r'费后指标[^：]*：IC ([\d.]+) / IC_IR [\d.]+ / 年化超额 ([+\-\d.]+)% / '
                        r'回撤 [+\-\d.]+% / Calmar ([\d.]+) / Sharpe [\d.]+ / 最近年 [+\-\d.]+% / '
                        r'单期换手 ([\d.]+)%', body)
        m_g = re.search(r'gen(\d+) 入库', body)
        if not m_e:
            continue
        # ★ 宽容回退（2026-09-14）：全A 库**早期条目**用的是另一套行文
        #   （如 F01「（全A 超额 +3.37% / Calmar +0.302；300 -7.76%；…）」+「本档建立前未归档」）
        #   ⇒ 标准正则匹配不到 ⇒ 退而抓**第一个"超额 X%"**（那正是 全A 口径）。
        #   ⚠ 只用它判**符号**（"入库时有没有取负号"），不当精确指标用。
        _ae = None
        if m_m:
            _ae = float(m_m.group(2)) / 100
        else:
            m_ae = re.search(r'全A 超额\s*([+\-][\d.]+)%', body)
            if m_ae:
                _ae = float(m_ae.group(1)) / 100
        out.append(dict(
            pool=pool, no=no, gen=int(m_g.group(1)) if m_g else None,
            expr=m_e.group(1).strip(),
            ic=float(m_m.group(1)) if m_m else None,
            ann_ex=_ae,
            calmar=float(m_m.group(3)) if m_m else None,
            turn=float(m_m.group(4)) / 100 if m_m else None))
    return out


def _prep_main():
    """pkl 是引擎以 `__main__` 身份存的 ⇒ 注入引擎的类，否则 `Can't get attribute 'Node'`。"""
    import loop_engine as LE
    for n in dir(LE):
        if n[:1].isupper() and isinstance(getattr(LE, n), type):
            setattr(sys.modules['__main__'], n, getattr(LE, n))
    return LE


def load_bank_nodes(pool):
    """从 `loop_state{_pool}.pkl` + `docs/factor_registry.json` 读 **入库 Node 列表**。

    ★★ 为什么不 `parse_expr(库里的表达式文本)`（2026-09-14 实测踩到）：
      `parse_expr` 有一道 **`nd.size() > LLM_MAX_SIZE` 的尺寸上限**，超限时
      **静默返回 `None`**（docstring 原话："任一不合规返回 None, **由调用方静默丢弃**"）。
      实测：全A 库 **F01** 的式子合法（5 层嵌套）却因超限返回 `None` ⇒ 下游
      `eval_expr(None)` 才炸出 `'NoneType' object has no attribute 'key'`（**报错点离病根很远**）。
      ⇒ 入库因子**已经在 state 里存着 Node**，直接用它最准（无解析歧义、不受 LLM 生成限制）。

    ★★★★ 2026-09-17（用户之问："我家里 pull 项目，库是空的，能不能自动把因子重跑一遍
      生成 facs/各种曲线？"）：**这条路径原先在"家里"是断的** ✗ ——
      `.gitignore` 忽略 `*.pkl` ⇒ 家里没有 `loop_state*.pkl` ⇒ 本函数返回空 ⇒
      `build_facs` / `factor_metrics` / `factor_curves` **全部无从下手**（一个因子都建不出来）✗✗
      ⇒ 现在**优先并合并 `docs/factor_registry.json`**（**进 git**，见 `tools/export_factor_registry.py`）：
        · 家里：pkl 缺失 ⇒ 直接用 JSON 里的 **node 结构**精确重建 ✓
        · 本机：两边都有 ⇒ **取并集**（JSON 可能比 pkl 旧 ⇒ 新入库的因子仍从 pkl 拿到 ✓）
    """
    out = {}
    # ---- ① registry（进 git；换机器时是**唯一**来源 ✓）----
    rp = os.path.join(DOCS, 'factor_registry.json')
    if os.path.exists(rp):
        try:
            js = json.load(io.open(rp, encoding='utf-8'))
            for f in (js.get('factors') or []):
                if f.get('pool') != pool or not f.get('node') or not f.get('expr'):
                    continue
                try:
                    out[str(f['expr'])] = _LE().node_from_dict(f['node'])
                except Exception:
                    continue
        except Exception as e:
            print('  [!] 读 {} 失败: {}: {}'.format(os.path.basename(rp), type(e).__name__, e))
    n_reg = len(out)
    # ---- ② pkl（本机才有；补上 registry 里还没有的新因子 ✓）----
    sfx = '' if pool == 'all' else '_' + pool
    sf = os.path.join(ENG, 'loop_state{}.pkl'.format(sfx))
    if not os.path.exists(sf):
        print('  [{}] 无 state pkl ⇒ 用 registry 里的 {} 个入库因子（换机器场景 ✓）'.format(pool, n_reg))
        return out
    try:
        st = pickle.load(open(sf, 'rb'))
    except Exception as e:
        print('  [!] 读 {} 失败: {}: {}'.format(sf, type(e).__name__, e))
        return out
    n0 = len(out)
    for x in (st.get('bank', []) or []):
        out.setdefault(str(x), x)
    if len(out) > n0:
        print('  [{}] registry {} 个 + state 新增 {} 个 ⇒ 共 {} 个入库因子'
              .format(pool, n_reg, len(out) - n0, len(out)))
    return out


def _LE():
    """拿 `loop_engine`（**延迟 import**：本模块在 `_prep_main()` 之前就要用它建 Node ✓）"""
    import loop_engine
    return loop_engine


def load_archive_ic(pool):
    """`docs/loop_archive{_pool}.csv`（**+ gen16 前的历史快照**）→ {expr: ic}（**带符号的** IC）。

    ⚠ 必须连 **`history/loop_archive.legacy_pre_gen16.csv`** 一起读（2026-09-14 实测）：
      全A 库的 F01~F04 来自 **gen8~11**，而 `loop_archive.csv` 是 gen16 起的新表
      ⇒ 只读新表会找不到它们、误报"库无记录"。
      实测覆盖：新表命中 **32/41** + 历史表命中 **1/41** ⇒ **8 个仍无记录**
      （那 8 个的指标在文档里也写着"本档建立前未归档"）⇒ **只能靠库里的分池超额推符号**。
    """
    sfx = '' if pool == 'all' else '_' + pool
    cands = [os.path.join(DOCS, 'loop_archive{}.csv'.format(sfx))]
    if pool == 'all':
        # ★ 2026-09-15：归档区 `docs/history/` 已整体移到**仓库根 `history/`**
        #   ⚠ 注意这里**不能**用 `DOCS` —— 它拼出来是 `docs/history/...`（已不存在）✗
        cands.append(os.path.join(ROOT, 'history', 'loop_archive.legacy_pre_gen16.csv'))
    out = {}
    for p in cands:
        if not os.path.exists(p):
            continue
        try:
            for r in csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')):
                e, ic = r.get('expr'), r.get('ic')
                if e and ic not in (None, ''):
                    try:
                        out.setdefault(e, float(ic))
                    except ValueError:
                        pass
        except Exception as e:
            print('  [!] 读 {} 失败: {}: {}'.format(os.path.basename(p), type(e).__name__, e))
    return out


def plan(items, root, only_new, force):
    """把待处理条目分成三档（**必须在载面板之前做**，见 docstring 的「增量模式」一节）。

    :return: (full, quant_only, skipped)
        full       —— 需要\"求值 + 回测 + 剥风格\"的（值文件缺失）
        quant_only —— 值已落地、只缺 `values_q.h5` 快查副本（**不用载面板/不用回测**）
        skipped    —— 两个文件都在（`--only-new` 且非 `--force`）

    ★★ 为什么要在载面板**之前**分流：`build_facs.py` 全量跑 52 个要 **~21 分钟**，
      而其中真正的成本是\"每因子 求值 + 1~2 次全期回测\"；面板载入本身只 ~11s。
      轨道收尾时**通常只有 0~3 个新因子** ⇒ 若仍全量重跑，等于为 3 个新因子付 52 个的代价。
      ⇒ 分流后：无新因子时**连面板都不载**（~0s 退出）；有几个新的就只算几个（~20s/个）。
    """
    import factor_store as FS
    full, quant_only, skipped = [], [], []
    for it in items:
        p, _ = FS.FactorStore(root=root).path_of(_name_of(it), it['expr'])
        pq = os.path.join(os.path.dirname(p), 'values_q.h5')
        has_f, has_q = os.path.exists(p), os.path.exists(pq)
        if force or not has_f:
            full.append(it)
        elif not has_q:
            quant_only.append(it)
        else:
            skipped.append(it)
    return full, quant_only, skipped


def _name_of(it):
    return it['no'] if it['pool'] == 'all' else '{}_{}'.format(it['no'], it['pool'])


def _merge_csv(path, new_rows, cols):
    """把新行**合并**进已有 CSV（按 `name` 去重，新行覆盖旧行）。

    ★★ 为什么增量模式**必须合并而不是覆盖**（2026-09-14）：
      `docs/loop_strip_style_bank.csv` 是 **52 个因子的剥风格实测**（精选池 L3 的闸门依据）。
      旧代码每次 `open(...,'w')` **只写本次处理的行** ⇒ 配合 `--only-new` 会**把已有的 52 行清空**,
      只剩那几个新因子 ⇒ **下游 `cross_pool_review.py` 会误判成\"库里只有 3 个因子\"**,
      而且**静默**（文件还在、格式也对）。⇒ 增量模式一律\"读-合并-写\"。
    """
    old = []
    if os.path.exists(path):
        try:
            old = [r for r in csv.DictReader(io.open(path, encoding='utf-8-sig', newline=''))]
        except Exception:
            old = []
    new_names = {r['name'] for r in new_rows}
    out = [r for r in old if r.get('name') not in new_names] + list(new_rows)
    for r in out:
        for c in cols:
            r.setdefault(c, '')
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    return len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='all,300,500,1000')
    ap.add_argument('--limit', type=int, default=0, help='只做前 N 个（冒烟用）')
    ap.add_argument('--no-strip', action='store_true', help='跳过剥风格补测')
    ap.add_argument('--ic_tol', type=float, default=0.002, help='IC 自检容差')
    ap.add_argument('--facs_root', default=None)
    ap.add_argument('--only-new', action='store_true',
                    help='★ 增量模式：跳过已落地的因子（值+快查副本都在）；'
                         '缺 values_q.h5 的只补副本、不重跑回测。**轨道收尾推荐开这个**')
    ap.add_argument('--force', action='store_true', help='配合 --only-new：忽略已有、强制重算')
    a = ap.parse_args()

    import pandas as pd
    LE = _prep_main()
    import factor_store as FS
    from factor_miner import evaluate_real, cs_rank
    from loop_metrics import neutral_rank
    import loop_engine as LE2

    root = a.facs_root or os.path.join(ROOT, 'facs')

    # ---- 收集条目：**以 state.bank 的 Node 为权威**；库文档提供 F 编号 ----
    items = []
    for p in [x.strip() for x in a.pools.split(',') if x.strip()]:
        nodes = load_bank_nodes(p)
        if not nodes:
            print('  [{}] state 不存在或无 bank -> 跳过'.format(p))
            continue
        ics = load_archive_ic(p)
        lib = {r['expr']: r for r in parse_library(p)}
        for expr, nd in nodes.items():
            L = lib.get(expr) or {}
            items.append(dict(pool=p, no=L.get('no') or _fallback_name(expr), expr=expr,
                              node=nd, ic_lib=L.get('ic'),
                              ic_arc=ics.get(expr), ae_lib=L.get('ann_ex'), also=[]))
    _ic = lambda it: it['ic_arc'] if it['ic_arc'] is not None else it['ic_lib']
    # 去重（跨池重复的式子只落一份值，记下来源）
    seen, uniq = {}, []
    for it in items:
        if it['expr'] in seen:
            seen[it['expr']]['also'].append(it['pool'])
            continue
        seen[it['expr']] = it
        uniq.append(it)
    for it in uniq:
        it['ic_ref'] = _ic(it)
    if a.limit:
        uniq = uniq[:a.limit]
    print('=' * 96)
    print('落地因子值到 {} —— bank 内共 {} 个（去重后）{}'.format(
        root, len(uniq), '  [增量模式 --only-new]' if a.only_new else ''))
    print('=' * 96)

    # ---- ★ 先分流（增量模式），再决定要不要载面板 ----
    full, quant_only, skipped = ((plan(uniq, root, True, a.force) if a.only_new
                                  else (uniq, [], [])))
    if a.only_new:
        print('  分流: 需重算 **{}** · 仅缺快查副本 **{}** · 已就绪跳过 **{}**'.format(
            len(full), len(quant_only), len(skipped)))
    st = FS.FactorStore(root=root)

    t0 = time.time()
    # ---- 仅缺 `values_q.h5` 的：**不用载面板、不用回测**（读 h5→量化→写 h5）----
    for it in quant_only:
        nm = _name_of(it)
        try:
            st.write_quant_copy(nm, it['expr'], overwrite=True)
            print('  [{:<10s}] 仅补 values_q.h5 ✓'.format(nm))
        except Exception as e:
            print('  [{:<10s}] **补副本失败** {}: {}'.format(nm, type(e).__name__, e))
    if not full:
        print('\n⇒ 无需重算的因子（增量模式）—— **不载面板**，完成，用时 {:.0f}s'.format(
            time.time() - t0))
        _report(a, [], [], 0, len(quant_only), len(skipped))
        return 0

    # ---- 载面板（只在确实要重算时才载）----
    bf = LE2.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('面板载入完成: {} 日 x {} 股, 用时 {:.0f}s'.format(len(dates), len(cols), time.time() - t0))

    STYLE = {}
    if not a.no_strip:
        t1 = time.time()
        sf = LE2.style_features(B)
        for k in ('lncap', 'lnamt'):
            STYLE[k] = sf[k]
        del sf
        print('风格特征(lncap/lnamt) 完成, 用时 {:.0f}s'.format(time.time() - t1))

    rows_out, warn, nosign, strip_rows = [], [], [], []
    uniq = full        # ★ 循环只处理\"需要重算\"的那批
    for i, it in enumerate(uniq, 1):
        expr = it['expr']
        nm = it['no'] if it['pool'] == 'all' else '{}_{}'.format(it['no'], it['pool'])
        nd = it['node']
        try:
            v = LE.eval_expr(nd, B, {})
            fac = pd.DataFrame(v, index=dates, columns=cols)
            f = cs_rank(fac.astype('float64'))
            # ★ 一次调用同时拿**期频**(dd/calmar/sharpe)与**日频**(dd_d/calmar_d/sharpe_d)口径
            #   （2026-09-14, loop_todo §1.19：期频=期末打点 ⇒ 回撤系统性低估 ~3.6pp）
            #   ⚠ 只多算一条净值序列（**不重新选股**），实测每因子 +4s 左右 ✓
            rr = evaluate_real(f, close, expr, cost=0.004, window=5, with_daily=True)
        except Exception as e:
            print('  [{}] **求值/回测失败** {}: {}'.format(nm, type(e).__name__, e))
            continue
        if rr is None:
            print('  [{}] 回测返回 None -> 跳过'.format(nm))
            continue
        ic_got = float(rr['ic'])
        # ---- ★ 符号对齐：库里记录的是**带符号**的 IC；node 是**不带符号**的 ----
        #   引擎 L2 里是 `if r['sign'] < 0: v = -v` ⇒ 入库因子可能取过负号。
        #   判据 = 与库记录同号；库无记录（老条目）⇒ **不猜**，标 '?' 并告警。
        sign = 1
        ic_ref = it.get('ic_ref')
        _ref = ic_ref if (ic_ref not in (None, 0)) else it.get('ae_lib')
        _src = 'IC' if ic_ref not in (None, 0) else '分池超额'
        if _ref not in (None, 0) and np.sign(ic_got) != np.sign(_ref):
            sign = -1
            f = -f
            fac = -fac
            rr = evaluate_real(f, close, expr, cost=0.004, window=5, with_daily=True) or rr
            ic_got = float(rr['ic'])
        elif _ref in (None, 0):
            nosign.append(nm)
        # ---- 落地 ----
        p, ah = st.write(nm, expr, fac.values, dates, cols, freq=5, unit='raw',
                         source='lib:{}:gen{}'.format(it['pool'], it.get('gen')),
                         sign=sign, leaf_set=None, cat=None)
        # ★ 双写（2026-09-14 用户批准）：同时生成 `values_q.h5`（uint8 截面分位快查副本）。
        #   实测（`tools/bench_quant_read.py`）：省 3.99x 空间，且**秩类用法快 14.4x**
        #   （IC/分层/多空/正交诊断 只需秩 ⇒ 免去 `rank_rows` 的 O(N logN)）。
        #   ⚠ 需要原值（中性化/回归/剥风格/合成）必须读 `values.h5`。
        try:
            st.write_quant_copy(nm, expr, overwrite=True)
        except Exception as e:
            print('      [双写] values_q.h5 生成失败(不影响主流程): {}: {}'.format(
                type(e).__name__, e))
        # ---- 自检：IC 对账（**必须吼出来**，否则落地了错的因子值也没人发现）----
        flag = ''
        if ic_ref is not None and abs(ic_got - ic_ref) > a.ic_tol:
            flag = ' ⚠ **IC 不符**(库 {:.4f} vs 算 {:.4f})'.format(ic_ref, ic_got)
            warn.append((nm, ic_ref, ic_got))
        elif ic_ref is None:
            # 没有 IC 可对账：符号是**从库里的分池超额方向**推的（`_src`），指标本身未对账。
            flag = (' [符号取自{}，指标未对账]'.format(_src) if _ref not in (None, 0)
                    else ' **无任何记录 -> 未对账/未定符号**')
        sgn = ' [sign=-1]' if sign < 0 else ''
        print('  [{:<10s}] {:>7s} IC={:+.4f}{}{}  {}'.format(nm, str(tuple(fac.shape)), ic_got, sgn, flag, expr[:38]))
        rows_out.append(dict(name=nm, pool=it['pool'], no=it['no'], expr=expr, sign=sign,
                             ic=ic_got, calmar=rr['calmar'], ann_ex=rr['ann_ex'],
                             # ★ 日频口径（§1.19）：跨频率/跨因子比风险必须看这几列
                             dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'),
                             sharpe_d=rr.get('sharpe_d'),
                             path=os.path.relpath(p, ROOT)))
        # ---- 剥风格补测 ----
        if not a.no_strip:
            try:
                fn = neutral_rank(f.values.astype('float64'), [STYLE['lncap'], STYLE['lnamt']])
                rr_s = evaluate_real(pd.DataFrame(fn, index=dates, columns=cols), close,
                                     expr + '#strip', cost=0.004, window=5, with_daily=True)
                if rr_s is not None:
                    # ★ 档位吃**日频**（§1.19 ③）；日频缺失回退期频
                    k, t = LE_pools_grade(rr_s.get('calmar_d'), rr_s['ann_ex'],
                                          rr_s.get('dd_d'), rr_s['calmar'])
                    strip_rows.append(dict(name=nm, pool=it['pool'], expr=expr,
                                           ic=rr['ic'], calmar=rr['calmar'], ann_ex=rr['ann_ex'],
                                           dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'),
                                           strip_ic=rr_s['ic'], strip_calmar=rr_s['calmar'],
                                           strip_ann_ex=rr_s['ann_ex'],
                                           strip_sharpe=rr_s['sharpe'],
                                           # ★ 剥风格后的**日频**口径（§1.19）：标定新档位阈值用它
                                           strip_dd_d=rr_s.get('dd_d'),
                                           strip_calmar_d=rr_s.get('calmar_d'),
                                           strip_sharpe_d=rr_s.get('sharpe_d'),
                                           grade=k))
            except Exception as e:
                print('      [剥风格] 失败(不影响落地): {}: {}'.format(type(e).__name__, e))

    # ---- 汇总（★ 增量模式：**读-合并-写**，不覆盖 —— 见 `_merge_csv` 的告警）----
    if rows_out:
        bp = os.path.join(ROOT, 'ai_test', '_facs_built.csv')
        if a.only_new:
            n = _merge_csv(bp, rows_out, list(rows_out[0].keys()))
            print('\n清单 -> ai_test/_facs_built.csv （合并后 {} 条）'.format(n))
        else:
            with open(bp, 'w', newline='', encoding='utf-8-sig') as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
                w.writeheader()
                w.writerows(rows_out)
            print('\n清单 -> ai_test/_facs_built.csv （{} 个）'.format(len(rows_out)))
    strip_n = 0
    if strip_rows:
        # ★ 2026-09-14（§1.19）：新增**日频**列 —— 期频=期末打点，回撤系统性低估，
        #   跨频率/跨因子比风险必须看日频。`_merge_csv` 用 DictWriter（按 key 写）⇒
        #   加列**不会**让历史行错位（§8.30 那个坑只发生在"裸行写入"的场景）；
        #   缺列的旧行由 `_merge_csv` 的 `setdefault(c,'')` 补空 ✓
        cols_o = ['name', 'pool', 'expr', 'ic', 'calmar', 'ann_ex',
                  'dd_d', 'calmar_d',
                  'strip_ic', 'strip_calmar', 'strip_ann_ex', 'strip_sharpe',
                  'strip_dd_d', 'strip_calmar_d', 'strip_sharpe_d', 'grade']
        outp = os.path.join(DOCS, 'loop_strip_style_bank.csv')
        strip_n = (_merge_csv(outp, strip_rows, cols_o) if a.only_new
                   else _write_csv(outp, strip_rows, cols_o))
        cnt = {}
        for r in strip_rows:
            cnt[r['grade']] = cnt.get(r['grade'], 0) + 1
        print('剥风格补测 -> docs/loop_strip_style_bank.csv （本次 {} 个，共 {} 条）'.format(
            len(strip_rows), strip_n))
        print('  本次档位: ' + ', '.join('{}x{}'.format(k, v) for k, v in sorted(cnt.items())))
        if cnt.get('C'):
            print('  [!] **{} 个是「纯风格」**（剥掉 lncap+lnamt 后转负）⇒ 指数增强不可用'
                  '（详见 loop_todo §1.9）'.format(cnt['C']))
    _report(a, nosign, warn, len(full), len(quant_only), len(skipped))
    print('\n完成，用时 {:.0f}s'.format(time.time() - t0))
    return 0


def _write_csv(path, rows, cols):
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def _report(a, nosign, warn, n_full, n_quant, n_skip):
    """统一尾报（**无论走「全量」还是「增量且无新因子」的分支都要打** —— 避免静默）。"""
    if a.only_new:
        print('\n增量小结: 本次**重算 {}** 个 · 仅补快查副本 {} 个 · 已就绪跳过 {} 个'.format(
            n_full, n_quant, n_skip))
    if nosign:
        print('\n⚠ **{} 个因子的 IC 无库记录**（全A 库早期条目，标注「指标未归档」）'
              '⇒ 无法判符号/对账，已按 node 原样落地并记 `sign=1`，**可信度较低**：'.format(len(nosign)))
        print('   ' + ', '.join(nosign[:14]) + (' ...' if len(nosign) > 14 else ''))
    if warn:
        print('\n⚠ **{} 个因子的 IC 与库记录不符**（口径可能没对齐，先查再信落地值）：'.format(len(warn)))
        for nm, e, g in warn:
            print('   {}  库 {:.4f} vs 算 {:.4f}  (差 {:+.4f})'.format(nm, e, g, g - e))


def _fallback_name(expr):
    """库里没有 F 编号时（理论上不该发生）用表达式短哈希当名字。"""
    import hashlib
    return 'X' + hashlib.md5(expr.encode()).hexdigest()[:6]


def LE_pools_grade(calmar_d, strip_ann_ex, dd_d=None, calmar_p=None):
    """分档（调用 `loop_pools.strip_grade` = **单一事实源**）。

    ★ 2026-09-14（`loop_todo §1.19 ③`，用户拍板）：**优先用「日频」口径**；
      日频缺失时**回退期频**（旧数据 / 未开 `with_daily` 时不炸、不误杀）。

    :param calmar_d: 剥风格后**日频** Calmar（首选）
    :param calmar_p: 剥风格后**期频** Calmar（日频缺失时的回退）
    :param dd_d:     剥风格后**日频**回撤（`TAG_STRIP_DD_MIN` 判据用）
    """
    import loop_pools as LP
    _c = calmar_d if (calmar_d is not None and np.isfinite(calmar_d)) else calmar_p
    return LP.strip_grade(_c, strip_ann_ex, dd_d)


if __name__ == '__main__':
    sys.exit(main())
