# -*- coding: utf-8 -*-
"""pool_tags.py — 把引擎的池内指标（`docs/loop_pool_obs.csv` 长表）派生为**入库池标签**

用户需求（2026-09-12）："300、500、全市场都能选，入库时打标签 —— 这个因子是 300 好用 /
300+500 好用 / 全部都好用 / 只有全A好用。将来做因子库 PG 时按这个标签筛选。"

本工具做三件事：
  1. 把长表 `loop_pool_obs.csv`(每候选 x 每池一行) 与 `loop_archive.csv`(全A口径) 按 (gen,expr) 合并
  2. 按**显式阈值**判定每个池是否"好用"，派生 `pool_tag`
  3. 导出**宽表** `docs/pool_tags.csv`（每个池一列指标 + 一列标签）—— 直接喂 PG

★ 设计要点（roadmap §8.9-④）：**以逐池指标为主、`pool_tag` 为派生列**。
  阈值改了只要重跑本脚本即可重算标签，不必回头改引擎。

口径（与 §8.13 的 bank 诊断保持一致，可用参数覆盖）：
    通过 = 该池**费后超额 > 0**（`--pool-floor`，默认 0）
    全A   = 费后超额 > 0 **且** Calmar >= `--cal-min`（默认 0.30）

用法：
  python standard/pool_tags.py                          # 用 docs/ 下的默认文件
  python standard/pool_tags.py --cal-min=0.5 --pool-floor=0.01
"""
import io
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POOL_OBS = os.path.join(ROOT, 'docs', 'loop_pool_obs.csv')
ARCHIVE = os.path.join(ROOT, 'docs', 'loop_archive.csv')
OUT_CSV = os.path.join(ROOT, 'docs', 'pool_tags.csv')
OUT_MD = os.path.join(HERE, 'pool_tags_report.md')

def _ensure_engine_on_path():
    """把 engine/ 加进 sys.path（`loop_pools` 在那边）。幂等。"""
    eng = os.path.join(ROOT, 'engine')
    if eng not in sys.path:
        sys.path.insert(0, eng)


# ★ 阈值**取自单一事实源** `engine/loop_pools.py`（2026-09-13）：引擎入库时也要用同一套规则，
#   两份各自写死必然漂移。仍可用 --cal-min/--pool-floor 覆盖（覆盖后的标签只影响本脚本输出）。
_ensure_engine_on_path()
import loop_pools as LP                                   # noqa: E402
CAL_MIN, POOL_FLOOR = LP.TAG_CAL_MIN, LP.TAG_POOL_FLOOR
# ★ 2026-09-14（§1.18 用户拍板 B + §1.19 ③）：**池内也要卡 Calmar**（原来只要超额>0 ⇒
#   `all3` 名不副实），且**一律用日频**（日频缺失回退期频）。
POOL_FLOOR_CAL = LP.TAG_POOL_FLOOR_CAL


def _cal_d(row):
    """取**日频** Calmar；缺列/NaN 时**回退期频**（旧 CSV 无 `calmar_d` 列时不炸）。

    ★ 为什么一律优先日频（2026-09-14, §1.19 ③）：期频 `nav=(1+ex).cumprod()` 只在每换仓期末
      打点 ⇒ 漏掉持有期内回撤 ⇒ 回撤被系统性低估（实测折比中位 0.928）⇒ 判据偏松。
    """
    try:
        v = row.get('calmar_d', None)
        if v is not None and np.isfinite(float(v)):
            return float(v)
    except (TypeError, ValueError):
        pass
    try:
        v = row.get('calmar', None)
        return float(v) if (v is not None and np.isfinite(float(v))) else np.nan
    except (TypeError, ValueError):
        return np.nan
for a in sys.argv[1:]:
    if a.startswith('--cal-min='):
        CAL_MIN = float(a[10:])
    elif a.startswith('--pool-floor='):
        POOL_FLOOR = float(a[13:])
    elif a.startswith('--pool-obs='):
        POOL_OBS = a[11:]
    elif a.startswith('--archive='):
        ARCHIVE = a[10:]


def tag_of(ok_all, ok_by_pool, pools):
    """由"哪些池通过"派生标签。

    ★ 2026-09-13 改为**转发到单一事实源** `engine/loop_pools.derive_tag`
      （原先这里有一份独立实现，而引擎入库时也要写标签 ⇒ 两份必然漂移）。
      保留本函数名只是兼容旧调用；新代码请直接用 `loop_pools.derive_tag`。
    """
    _ensure_engine_on_path()
    import loop_pools as LP
    return LP.derive_tag(ok_all, ok_by_pool, pools)


def main():
    if not os.path.exists(POOL_OBS):
        print(f"找不到 {POOL_OBS}\n=> 先用引擎跑一代带 --pool_obs 的实验, 例如:\n"
              f"   python engine\\loop_engine.py --gen=74 --n=800 --pool_obs")
        return 1
    obs = pd.read_csv(POOL_OBS)
    # ★ 必须把 pool 键统一成**字符串**: 引擎写入的池标签是 '300'/'500', 但 CSV 往返后
    #  pandas 会把它读成 int64 -> 用字符串 '300' 查表全部落空 -> 标签会**静默全错**
    #  (由 ai_test/qa_pool_tags.py 抓到, 2026-09-12)。
    obs['pool'] = obs['pool'].astype(str)
    pools = sorted(obs['pool'].unique())
    print(f"载入 {POOL_OBS}: {len(obs)} 行, 池={pools}")

    # ---- 全A 口径: 从 archive 取同 (gen, expr) 的行 ----
    allm = {}
    if os.path.exists(ARCHIVE):
        ar = pd.read_csv(ARCHIVE)
        for _, r in ar.iterrows():
            allm[(int(r['gen']), str(r['expr']))] = (r.get('ann_ex', np.nan),
                                                     _cal_d(r))
    else:
        print(f"[!] 无 {ARCHIVE} -> 无法判 全A 口径(全A 视为不通过)")

    # ---- 逐池透视 ----
    #  ★ 2026-09-14：pivot 带上 `calmar_d`（日频）。旧 CSV 没这列 ⇒ 下面的 `_cal_d` 回退期频 ✓
    _vals = ['ann_ex', 'calmar', 'ic'] + (['calmar_d'] if 'calmar_d' in obs.columns else [])
    piv = obs.pivot_table(index=['gen', 'expr'], columns='pool',
                          values=_vals, aggfunc='last')

    L = [f"# 入库池标签（`pool_tag`）报告", "",
         f"来源 `{os.path.relpath(POOL_OBS, ROOT)}`（{len(obs)} 行, 池={pools}）", "",
         "判定口径（**改阈值只需重跑本脚本**，标签会重算）：",
         f"- 池内通过 = 费后超额 > **{POOL_FLOOR:g}** **且 Calmar ≥ {POOL_FLOOR_CAL:g}**"
         f"（★ 2026-09-14 新增后半个条件：原来只要超额>0 ⇒ `all3` 名不副实，见 §1.18）",
         f"- 全A通过 = 费后超额 > 0 **且 Calmar ≥ {CAL_MIN:g}**",
         f"- ⚠ **Calmar 一律取「日频」口径**（缺列时回退期频）—— 期频漏掉持有期内回撤", "",
         "| 标签 | 含义 |", "|---|---|",
         "| `all3` | 全A + **所有**池都通过（真 alpha） |",
         "| `csi_all_only` | **只有全A通过** -> 小盘/流动性溢价嫌疑 |",
         "| `csi<p>_all` | 全A + 部分池通过 |",
         "| `csi<p>_only` | 仅单池通过 |",
         "| `csi<p>_<q>` | 多池通过但全A不通过 |",
         "| `none` | 全不通过 |", ""]

    export, rows = [], []
    for (g, e), _ in piv.iterrows():
        ok_pool, rec = {}, dict(gen=g, expr=e)
        for p in pools:
            ex = piv.loc[(g, e), ('ann_ex', p)] if ('ann_ex', p) in piv.columns else np.nan
            cal = piv.loc[(g, e), ('calmar', p)] if ('calmar', p) in piv.columns else np.nan
            ic = piv.loc[(g, e), ('ic', p)] if ('ic', p) in piv.columns else np.nan
            _cd = (piv.loc[(g, e), ('calmar_d', p)]
                   if ('calmar_d', p) in piv.columns else None)
            cal = _cd if (_cd is not None and np.isfinite(_cd)) else cal   # ★ 日频优先
            rec[f'ic_{p}'], rec[f'ann_ex_{p}'], rec[f'calmar_{p}'] = ic, ex, cal
            # ★ 池内也要卡 Calmar（§1.18 B）：原来只要 `ex > POOL_FLOOR` ⇒ 误标 `all3`
            ok_pool[p] = bool(np.isfinite(ex) and ex > POOL_FLOOR
                              and np.isfinite(cal) and cal >= POOL_FLOOR_CAL)
        ae, ac = allm.get((int(g), str(e)), (np.nan, np.nan))
        rec['all_ann_ex'], rec['all_calmar'] = ae, ac
        ok_all = bool(np.isfinite(ae) and ae > 0 and np.isfinite(ac) and ac >= CAL_MIN)
        rec['n_pool_pass'] = sum(ok_pool.values())
        rec['pool_tag'] = tag_of(ok_all, ok_pool, pools)
        rec['expr'] = str(e)[:200]
        export.append(rec)

    ex_df = pd.DataFrame(export).sort_values(['n_pool_pass', 'pool_tag'],
                                             ascending=[False, True])
    ex_df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    print(f"已写 {OUT_CSV}（{len(ex_df)} 行, 可直接喂 PG）")

    # 明细表
    L += ["## 明细（按通过池数降序）", "",
          "| gen | 全A超额 | 全ACalmar | "
          + " | ".join(f"**{p}**超额" for p in pools)
          + " | " + " | ".join(f"{p}Calmar" for p in pools)
          + " | **pool_tag** |", "|---" * (3 + 2 * len(pools) + 1) + "|"]
    for _, r in ex_df.iterrows():
        L.append(f"| {r['gen']} | {r['all_ann_ex']*100:+.2f}% | {r['all_calmar']:.3f} | "
                 + " | ".join(f"{r.get(f'ann_ex_{p}', np.nan)*100:+.2f}%" for p in pools)
                 + " | " + " | ".join(f"{r.get(f'calmar_{p}', np.nan):.3f}" for p in pools)
                 + f" | **{r['pool_tag']}** |")

    vc = ex_df['pool_tag'].value_counts().to_dict()
    L += ["", "## 分布", "", "```",
          f"pool_tag: {vc}",
          f"全A通过: {int((ex_df['all_ann_ex'] > 0).sum() if len(ex_df) else 0)}/{len(ex_df)}",
          "```", ""]
    io.open(OUT_MD, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print(f"已写 {OUT_MD}")
    print(f"pool_tag 分布: {vc}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
