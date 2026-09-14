# -*- coding: utf-8 -*-
"""backfill_bank_ex.py -- 给已有 state 补齐 `bank_ex`（收益流库），让收益流去重立刻全量生效。

背景（roadmap §8.34）：新增 `--dup_ex_corr` 需要 state 里的 `bank_ex`（{表达式: 每期费后超额}）。
旧 state 没有这个字段 ⇒ 首代只能与"本次运行新入库的"比（效果打折）。
本脚本把**历史入库因子**逐条重算收益流填进去 —— 一次性成本，之后就自动随入库增长。

⚠ 关于方向：bank 里只存 `Node`（不存 `sign`），而本脚本按 **|Spearman 相关|** 判重
   ⇒ **方向完全不影响判重结果**，所以不必还原符号，直接 `cs_rank(eval_expr(node))` 即可。

用法:
  python tools/backfill_bank_ex.py --pool=all      (或 300 / 500)
  python tools/backfill_bank_ex.py --pool=300 --dry   (只看要算什么, 不写盘)
"""
import io
import os
import pickle
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

import loop_engine as LE           # noqa: E402
import factor_miner as FM          # noqa: E402

# ⚠ 状态 pkl 是引擎以 `__main__` 身份运行时 pickle 的 ⇒ 需把同名类注入 __main__ 才能读
for _n in dir(LE):
    if _n[:1].isupper() and isinstance(getattr(LE, _n), type):
        setattr(sys.modules['__main__'], _n, getattr(LE, _n))


def main():
    pool = 'all'
    dry = False
    reset = False
    for a in sys.argv[1:]:
        if a.startswith('--pool='):
            pool = a.split('=', 1)[1].strip() or 'all'
        elif a == '--dry':
            dry = True
        elif a == '--reset':
            reset = True
    LE.set_mine_pool(pool)
    print('=' * 78)
    print('池 =', pool, '  状态文件 =', LE.STATE, '  dry =', dry)
    if not os.path.exists(LE.STATE):
        print('状态文件不存在，无需补齐')
        return 0
    st = pickle.load(open(LE.STATE, 'rb'))
    bank = st.get('bank', []) or []
    old = st.get('bank_ex', {}) or {}
    if reset:
        # ⚠ 只在"上一轮补到一半被杀、且那批是**未定向**的"时用（2026-09-13 实录：
        #   首版没定向 ⇒ 存了 −28%/−22% 这种反向序列 ⇒ 签名相关会算错 ⇒ 必须清掉重补）。
        #   未定向序列对 |corr| 判重无害，但对 `library_kpi` 的**签名**相关有害。
        print('[--reset] 清空已有 {} 条收益流，全部重补'.format(len(old)))
        old = {}
    print('入库因子 {} 个; 已有收益流 {} 条'.format(len(bank), len(old)))
    todo = [nd for nd in bank if str(nd) not in old]
    print('待补 {} 条'.format(len(todo)))
    if not todo:
        print('已完整，无需补齐')
        return 0
    if dry:
        for nd in todo[:10]:
            print('   ', str(nd)[:140])
        return 0

    base = LE.base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    print('面板 {} 日 x {} 股'.format(len(dates), len(cols)), flush=True)
    from scipy.stats import spearmanr
    U = FM.get_universe().reindex(index=dates, columns=cols).fillna(False).values
    fwd_ret = (close.shift(-(1 + FM.FWD)) / close.shift(-1) - 1).values
    new = dict(old)
    t0 = time.time()
    for k, nd in enumerate(todo, 1):
        key = str(nd)
        try:
            v = LE.eval_expr(nd, B, {})
            f = FM.cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
            del v
            # ★★ 按样本 IC **定向**（与 standard_test / 引擎 同约定）。
            #   为什么必须做（2026-09-13 实录）：`bank` 里只存**未定向**的 Node，而引擎入库时
            #   是"按 IC 符号定向后交易"的 ⇒ 直接跑 raw node 会得到 **−28%/−22%** 这种反向结果。
            #   · 对 `ex_max_corr`（用 |corr|）**不影响判重**；
            #   · 但对 `library_kpi` 的**签名**相关是致命的（A 存正、B 存负 ⇒ 真相关会显示为负）
            #   ⇒ 必须让所有收益流**同向**存储，签名相关才有意义。
            fv = f.values
            _ics = []
            for _i in range(0, len(dates), 5):
                _u = U[_i]
                _a, _b = fv[_i][_u], fwd_ret[_i][_u]
                _m = np.isfinite(_a) & np.isfinite(_b)
                if _m.sum() >= 50:
                    _ics.append(spearmanr(_a[_m], _b[_m])[0])
            _mu = float(np.nanmean(_ics)) if _ics else np.nan
            if np.isfinite(_mu) and _mu < 0:
                f = -f
            r = FM.evaluate_real(f, close, key[:40], with_ex=True)
            del f
            if r is None or 'ex' not in r:
                print('  [{}/{}] 样本不足，跳过 {}'.format(k, len(todo), key[:70]), flush=True)
                continue
            new[key] = r['ex']
            print('  [{}/{}] OK 费后超额 {:+.2f}% 期数 {}  {}s   {}'.format(
                k, len(todo), r['ann_ex'] * 100, len(r['ex']),
                int(time.time() - t0), key[:60]), flush=True)
        except Exception as e:
            print('  [{}/{}] 失败 {}: {}'.format(k, len(todo), type(e).__name__,
                                                str(e)[:70]), flush=True)
        if k % 10 == 0:                       # 分段落盘，防中途被杀全丢
            st['bank_ex'] = new
            _tmp = LE.STATE + '.tmp'
            with open(_tmp, 'wb') as fh:
                pickle.dump(st, fh)
            os.replace(_tmp, LE.STATE)
            print('     （已落盘，累计 {} 条）'.format(len(new)), flush=True)

    st['bank_ex'] = new
    _tmp = LE.STATE + '.tmp'
    with open(_tmp, 'wb') as fh:
        pickle.dump(st, fh)
    os.replace(_tmp, LE.STATE)
    print()
    print('补齐完成: {} -> {} 条, 用时 {:.0f}s'.format(len(old), len(new), time.time() - t0))
    import subprocess
    print()
    print('—— 现在算 KPI ——')
    subprocess.run([sys.executable, os.path.join(HERE, 'library_kpi.py'), '--pool=' + pool],
                   cwd=ROOT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
