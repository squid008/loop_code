# -*- coding: utf-8 -*-
"""loop_params.py — 生产挖掘参数**单一事实源**（2026-10-21，用户：前端要能看/改全部参数）

★ 为什么单独一个文件（而不是散在 `run_tracks.extra` 的 list + 前端各存一份）：
  · 参数**默认值 / 分组 / 类型 / 范围 / 危险等级**只有这一处 ⇒
    前端 `GET /api/params`、后端保存、`run_tracks` 拼命令行**都 import 它**
    ⇒ 不会出现"页面显示 0.15、代码里却是 0.20"的漂移 ✗
  · 用户在页面改的只存**覆盖项**（`docs/loop_params.json`），默认值仍来自本文件
    ⇒ 删掉 JSON（或点"恢复默认"）即完全回到生产默认 ✓

★ 危险等级（页面据此标色）：
  `2` = **会直接改变入库严格度**（调松 = 往库里塞坏因子）；`1` = 改前想清楚；
  `0` = 安全（观测/展示类）

对外接口：
  `PARAM_SPECS`      参数元数据（列表顺序 = 页面分组顺序）
  `DEFAULT_EXTRA`    生产默认 extra（与 v1.42.0 的生产命令行**逐字一致**）
  `load_overrides(path=None)`  读 JSON 覆盖项 -> {key: value}
  `save_overrides(d, path=None)` 原子写
  `merge_extra(overrides=None)` 默认 + 覆盖 -> 引擎参数 list
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_PATH = os.path.join(ROOT, 'docs', 'loop_params.json')

# ---------------------------------------------------------------- 参数元数据
# 字段：key（= flag 去掉 --）/ flag / label / group / type / default /
#       lo / hi（数值校验，None=不限）/ choices（枚举）/ danger / desc
PARAM_SPECS = [
    # ---- 生成 ----
    dict(key='n', flag='--n', label='每代候选数', group='生成', type='int',
         default=800, lo=50, hi=3000, danger=1,
         desc='每代生成并求值的候选数。调大更慢、内存更高'),
    dict(key='score_mode', flag='--score_mode', label='L1 排序', group='生成', type='enum',
         default='mono_n', choices=['old', 'new', 'ic_n', 'mono_n'], danger=2,
         desc='mono_n=风格中性十档单调性（实测与剥风格结果相关 +0.764，最强）；new=旧 stab 主导（已证失效）'),
    dict(key='dup_ex_corr', flag='--dup_ex_corr', label='收益流去重阈值', group='生成', type='float',
         default=0.90, lo=0.0, hi=0.99, danger=1,
         desc='与库内因子收益流相关的上限；调低更严（更难入库）'),
    dict(key='style_gate', flag='--style_gate', label='生成端拦纯风格组合', group='生成', type='int',
         default=0, lo=0, hi=1, danger=1,
         desc='1=丢弃 barra 占比≥0.5 或 div 分子含 barra 的候选。实测 2026-10-21 开启后 10 代 0 入库（方向反），故默认关'),
    # ---- 成本 / 口径 ----
    dict(key='cost', flag='--cost', label='往返成本', group='成本口径', type='float',
         default=0.004, lo=0.0, hi=0.02, danger=1,
         desc='双边合计单期成本（0.004 = 0.4%）'),
    dict(key='window', flag='--window', label='回测窗口', group='成本口径', type='enum',
         default='full', choices=['full', 'recent600'], danger=1,
         desc='full=全样本；recent600=最近 600 日'),
    dict(key='dual_fwd', flag='--dual_fwd', label='副口径天数', group='成本口径', type='int',
         default=20, lo=0, hi=60, danger=0,
         desc='0=关双口径；20=同时用 20 日口径评估，任一通过即入库'),
    # ---- L2 门槛 ----
    dict(key='l2', flag='--l2', label='L2 名额', group='L2 门槛', type='int',
         default=30, lo=5, hi=120, danger=1,
         desc='每代最多回测多少个候选。调大更慢（每个约 56 秒）'),
    dict(key='min_ic', flag='--min_ic', label='IC 准入门槛', group='L2 门槛', type='float',
         default=-1.0, lo=-1.0, hi=0.2, danger=2,
         desc='-1=关闭（现状）。调正值会把 IC 变成准入条件'),
    dict(key='min_calmar', flag='--min_calmar', label='超额 Calmar 门槛', group='L2 门槛', type='float',
         default=0.0, lo=-1.0, hi=1.0, danger=2,
         desc='5 日费后超额 Calmar 下限'),
    dict(key='min_calmar2', flag='--min_calmar2', label='20 日 Calmar 门槛', group='L2 门槛', type='float',
         default=0.701, lo=0.0, hi=2.0, danger=2,
         desc='20 日副口径卡玛门槛（0.701 = 全库 20 日口径中位）'),
    dict(key='min_pool_calmar', flag='--min_pool_calmar', label='池内 Calmar 门槛', group='L2 门槛', type='float',
         default=0.15, lo=0.0, hi=1.0, danger=2,
         desc='300/500/1000 池内卡玛下限（配合"池内 OR 全A"）'),
    dict(key='pool_gate_or_all', flag='--pool_gate_or_all', label='池内 OR 全A', group='L2 门槛', type='bool',
         default=True, danger=1,
         desc='开=全A 或池内任一达标即可；关=必须全A 达标'),
    # ---- 剥风格 ----
    dict(key='min_strip_calmar', flag='--min_strip_calmar', label='剥风格 Calmar 门槛', group='剥风格', type='float',
         default=0.15, lo=0.0, hi=2.0, danger=2,
         desc='剥掉 lncap+lnamt 后的 Calmar 下限。**调到 0 = 允许纯风格因子入库**'),
    # ---- 通道 B（剥风格独立通道）----
    dict(key='strip_channel_b', flag='--strip_channel_b', label='启用通道 B', group='通道B', type='bool',
         default=True, danger=2,
         desc='纯 alpha 型因子的第二条入库路（不要求原始 calmar/年超额）'),
    dict(key='min_strip_calmar_b', flag='--min_strip_calmar_b', label='通道B Calmar 下限', group='通道B', type='float',
         default=0.5, lo=0.0, hi=3.0, danger=2,
         desc='标定：1496 条候选里仅 1 条达标 ⇒ 极严档'),
    dict(key='min_strip_ann_b', flag='--min_strip_ann_b', label='通道B 剥后年化下限', group='通道B', type='float',
         default=0.03, lo=0.0, hi=0.3, danger=2,
         desc='剥风格后的费后年化下限（0.03 = 3%）'),
    dict(key='min_strip_sharpe_b', flag='--min_strip_sharpe_b', label='通道B 剥后夏普下限', group='通道B', type='float',
         default=0.8, lo=0.0, hi=3.0, danger=2,
         desc='剥风格后的夏普下限'),
    dict(key='min_ic_b', flag='--min_ic_b', label='通道B IC 下限', group='通道B', type='float',
         default=0.02, lo=0.0, hi=0.2, danger=2,
         desc='通道 B 要求的最小 |IC|'),
    # ---- 观测开关 ----
    dict(key='pool_obs', flag='--pool_obs', label='池内观测', group='观测', type='bool',
         default=True, danger=0, desc='记录 300/500/1000 池内指标（池标签依据）'),
    dict(key='pools', flag='--pools', label='对照池集合', group='观测', type='str',
         default='300,500,1000', danger=0, desc='池内指标与池门槛使用的池'),
    dict(key='strip_style', flag='--strip_style', label='剥风格评估', group='观测', type='bool',
         default=True, danger=1, desc='关闭后无法判定"是否纯风格"，不建议关'),
    dict(key='style_obs', flag='--style_obs', label='风格观测', group='观测', type='bool',
         default=True, danger=1, desc='关闭后 mono_n/ic_n 会缺值并回退到 new 排序'),
]

# 生产默认 extra（**与 v1.42.0 生产命令行逐字一致**；顺序即命令行顺序）
DEFAULT_EXTRA = [
    '--pool_obs', '--pools=300,500,1000', '--strip_style', '--style_obs',
    '--dup_ex_corr=0.90', '--min_calmar=0.0', '--min_ic=-1',
    '--score_mode=mono_n', '--min_pool_calmar=0.15', '--pool_gate_or_all',
    '--min_strip_calmar=0.15', '--dual_fwd=20', '--min_calmar2=0.701',
    '--strip_channel_b', '--min_strip_calmar_b=0.5', '--min_strip_ann_b=0.03',
    '--min_strip_sharpe_b=0.8', '--min_ic_b=0.02',
]

_SPEC_BY_KEY = {s['key']: s for s in PARAM_SPECS}


def spec_of(key):
    return _SPEC_BY_KEY.get(key)


def _fmt(flag, val, typ):
    """把一个参数格式化成命令行片段；bool 为 False 时返回 None（不出现）。"""
    if typ == 'bool':
        return flag if val else None
    if typ == 'int':
        return '%s=%d' % (flag, int(val))
    if typ == 'float':
        return '%s=%g' % (flag, float(val))
    return '%s=%s' % (flag, val)


def load_overrides(path=None):
    """读覆盖项（只含用户改过的键）；文件不存在/损坏 -> {}（绝不抛）。"""
    p = path or DEFAULT_PATH
    try:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            return {}
        d = json.loads(io.open(p, encoding='utf-8').read())
        return d if isinstance(d, dict) else {}
    except Exception:                                        # noqa: BLE001
        return {}


def save_overrides(d, path=None):
    """原子写覆盖项（先 .tmp 再 replace）；返回写入的键数。"""
    p = path or DEFAULT_PATH
    d = dict(d or {})
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
    os.replace(tmp, p)
    return len(d)


def validate(overrides):
    """按 `PARAM_SPECS` 校验覆盖项 -> (clean, errors)。

    只保留**认识的键**（未知键直接丢弃并在 errors 里说明，避免"静默生效不了的配置"）。
    """
    clean, errors = {}, []
    for k, v in (overrides or {}).items():
        s = _SPEC_BY_KEY.get(k)
        if s is None:
            errors.append('%s: 未知参数（已忽略）' % k)
            continue
        t = s['type']
        try:
            if t == 'bool':
                if not isinstance(v, bool):
                    raise ValueError('必须是 true/false')
                clean[k] = v
            elif t == 'int':
                iv = int(v)
                if s.get('lo') is not None and iv < s['lo']:
                    raise ValueError('不得小于 %s' % s['lo'])
                if s.get('hi') is not None and iv > s['hi']:
                    raise ValueError('不得大于 %s' % s['hi'])
                clean[k] = iv
            elif t == 'float':
                fv = float(v)
                if s.get('lo') is not None and fv < s['lo']:
                    raise ValueError('不得小于 %s' % s['lo'])
                if s.get('hi') is not None and fv > s['hi']:
                    raise ValueError('不得大于 %s' % s['hi'])
                clean[k] = fv
            elif t == 'enum':
                if v not in (s.get('choices') or []):
                    raise ValueError('只能是 %s' % '/'.join(s.get('choices') or []))
                clean[k] = v
            else:
                clean[k] = str(v)
        except (TypeError, ValueError) as e:
            errors.append('%s(%s): %s' % (k, s.get('label') or k, e))
    return clean, errors


def merge_extra(overrides=None, base=None):
    """默认 extra（或调用方给的 `base`）+ 覆盖项 -> 引擎参数 list。

    `base` 让 `run_tracks` 用它自己那份 `_LEGACY_EXTRA` 当默认值（保持"生产默认只有一处"），
    本函数只负责**按 flag 替换**，不重复追加 ✓
    """
    ov = dict(overrides or {})
    out, done = [], set()
    for item in (base if base is not None else DEFAULT_EXTRA):
        flag = item.split('=', 1)[0]
        key = flag.lstrip('-').replace('-', '_')
        if key in ov:
            s = _SPEC_BY_KEY.get(key)
            x = _fmt(flag, ov[key], (s or {}).get('type', 'str'))
            if x:
                out.append(x)
            done.add(key)
        else:
            out.append(item)
    # 默认 extra 里没有、但用户显式设了的键（如 n / l2 / cost / window / style_gate）
    for k, v in ov.items():
        if k in done:
            continue
        s = _SPEC_BY_KEY.get(k)
        if s is None:
            continue
        x = _fmt(s['flag'], v, s['type'])
        if x:
            out.append(x)
    return out
