# -*- coding: utf-8 -*-
"""★★★★★ 曲线 JSON ↔ 接口 DTO 的**契约守门**（2026-09-21 新增 · 真事故驱动）

★ 为什么需要（用户："图出来了，但是风格暴露的时序图怎么没有呢？"）：
  我给曲线 JSON 加了新键 `expo`（动态风格暴露 ✓），前端也把图画好了 ✓
  但 `dashboard/api/app/sources/factors.py::curves()` 是**固定白名单** ✗
  ⇒ 新键**没被透传** ⇒ 前端 `c.expo` 恒为 undefined ⇒ **数据在、图不在** ✗✗
  （排查绕了"文件层→前端层→接口层"三层才发现是接口这层过滤 ✓）

⇒ 本守门两件事：
  ① **静态对账**：`docs/factor_curves/*.json` 里出现过的所有键（含嵌套段）
     与"接口已处理的键"逐一对照 ⇒ 出现**新键而接口没同步** ⇒ 直接红 ✗
     （报错里会写明"该去哪登记 / 去哪透传" ✓）
  ② **动态实测**：真调一次 `factors.curves(<真实因子名>)` ⇒ 断言 DTO 里
     `daily / period / strip / style / expo / caliber …` 都在 ✓，
     且 `expo` 的嵌套键（dates/styles/series/neutral/caliber ✓）齐全 ✓
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
CURVE_DIR = os.path.join(ROOT, 'docs', 'factor_curves')
APP_TSX = os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


# ---------------------------------------------------------------- ① 静态对账表
# JSON 顶层键 → 它被送到 DTO 的哪里 ✓（**新键必须在这里登记 + 在 factors.curves() 里透传**）
JSON2DTO = {
    'name': 'name', 'pool': 'pool', 'expr': 'expr', 'sign': 'sign', 'gen': 'gen',
    'start': 'start', 'end': 'end', 'n_rebal': 'n_rebal', 'cost': 'cost',
    'window': 'window', 'caliber': 'caliber',
    'd_dates': 'daily.dates', 'nav_t': 'daily.navT', 'nav_m': 'daily.navM',
    'nav_e': 'daily.navE', 'dd_e': 'daily.ddE', 'dd_t': 'daily.ddT',
    'r_dates': 'period.dates', 'ic': 'period.ic', 'rank_ic': 'period.rankIc',
    'decile': 'period.decile', 'ls': 'period.ls', 'turn_series': 'period.turn',
    'strip': 'strip', 'expo': 'expo', 'style': 'style',
}
# 刻意不透传的键（**内部增量标记**之类 ✓ 不是漏 ✗）—— 登记在这里才允许出现 ✓
JSON_DROP_OK = {'styCal'}
# 嵌套段：允许出现的键 ✓（None = 该段键多且**整段原样透传** ⇒ 不逐个对账 ✓）
NESTED_OK = {
    'strip': {'dates', 'navs', 'calmars', 'caliber'},
    'expo': {'dates', 'styles', 'series', 'neutral', 'caliber'},
    'style': None,
}
NESTED_DROP_OK = {'styCal'}


print('【1】静态对账：曲线 JSON 的键 ⊆ 接口已处理的键')
files = sorted(glob.glob(os.path.join(CURVE_DIR, '*.json')))
chk('曲线目录里有 JSON（%d 个）' % len(files), bool(files),
    '没有曲线文件 ⇒ 跑 python tools/factor_curves.py --stage=core 先生成 ✓')
top_keys, nested_keys = set(), {}
bad_top, bad_nest = set(), {}
n_loaded = 0
for p in files:
    try:
        d = json.load(io.open(p, encoding='utf-8'))
    except Exception:                                       # 坏文件由别的守门负责 ✓
        continue
    n_loaded += 1
    top_keys |= set(d.keys())
    for sec in ('strip', 'expo', 'style'):
        blk = d.get(sec)
        if isinstance(blk, dict):
            nested_keys.setdefault(sec, set()).update(blk.keys())
bad_top = sorted(top_keys - set(JSON2DTO) - JSON_DROP_OK)
chk('顶层键全部有着落（对账 %d 个文件 · %d 个键）' % (n_loaded, len(top_keys)),
    not bad_top,
    '新键 %s 未登记 ⇒ 大概率**接口没透传**（去 factors.py::curves() 加，再登记到本脚本 JSON2DTO ✓）'
    % bad_top)
for sec, keys in nested_keys.items():
    ok = NESTED_OK.get(sec)
    if ok is None:
        continue
    miss = sorted(keys - ok - NESTED_DROP_OK)
    if miss:
        bad_nest[sec] = miss
chk('嵌套段（strip/expo）的键全部有着落', not bad_nest,
    '未登记：%s ⇒ 去 factors.py::curves() 对应的段落里透传 ✓' % bad_nest)


# ---------------------------------------------------------------- ② 动态实测
print('\n【2】动态实测：真调一次接口函数（不是读文件 ✓）')
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
DTO = None
try:
    from app.sources import factors as F                       # noqa: N812
    sample = None
    sample_expo = None
    for p in files:
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:                                       # noqa: BLE001
            continue
        nm = os.path.basename(p)[:-5]
        if sample is None:
            sample = (nm, d)
        if d.get('expo') and sample_expo is None:
            sample_expo = (nm, d)
    chk('找到可用样本', sample is not None)
    if sample is not None:
        DTO = F.curves(sample[0])
        chk('接口 found=True（样本 %s）' % sample[0], bool(DTO.get('found')),
            str(DTO.get('hint') or DTO.get('err') or '')[:80])
except Exception as e:                                          # noqa: BLE001
    chk('能 import 接口模块并调用 curves()', False, '%s: %s' % (type(e).__name__, str(e)[:100]))

# ★ 前端**真的在读**的字段（跟着 App.tsx 走 ✓）—— 少一个就是"数据在、图不在"✗
MUST_IN_DTO = ('found', 'name', 'pool', 'expr', 'sign', 'daily', 'period',
               'strip', 'style', 'expo', 'caliber', 'mtime', 'path')
if DTO:
    miss = [k for k in MUST_IN_DTO if k not in DTO]
    chk('DTO 含前端要用的全部字段', not miss, '缺 %s ⇒ 前端读不到 ✗' % miss)
    chk('expo 是 None 也算"有键"（无数据时不报错 ✓）', 'expo' in DTO)

    # ★ 真事故的靶心：带 expo 的样本 ⇒ 接口必须**吐出来** ✓
    if sample_expo is not None:
        dt = F.curves(sample_expo[0])
        ex = dt.get('expo')
        chk('带 expo 的样本（%s）接口确实透传了' % sample_expo[0], ex is not None,
            '出了这个红就是"数据在、图不在"的老毛病 ✗')
        if ex:
            need = ('dates', 'styles', 'series', 'neutral', 'caliber')
            miss2 = [k for k in need if k not in ex]
            chk('expo 的嵌套键齐全', not miss2, '缺 %s' % miss2)
            chk('expo.series 是"风格→序列"的字典',
                isinstance(ex.get('series'), dict) and bool(ex.get('series')))
            chk('expo 与 dates 等长（抽一个风格核 ✓）',
                (not ex.get('series')) or
                len(next(iter(ex['series'].values()))) == len(ex.get('dates') or []))
    else:
        chk('样本里有带 expo 的曲线（跳过 expo 深检）', True)

# ---------------------------------------------------------------- ③ 前端接线（靶向）
print('\n【3】前端"真在渲染"的字段必须有后端支撑（静态靶向 ✓）')
try:
    src = io.open(APP_TSX, encoding='utf-8').read()
    for field, why in (('c?.expo', '动态风格暴露图'), ('c?.strip', '剥风格图'),
                       ('c.style', '风格相关性画像')):
        if field in src:
            key = field.split('.')[-1]
            chk('App.tsx 用了 `%s`（%s）⇒ DTO 必须给' % (field, why),
                (DTO is not None) and (key in (DTO or {})),
                'DTO 少了 `%s` ⇒ 图上不来 ✗' % key)
except Exception as e:                                          # noqa: BLE001
    chk('能读 App.tsx', False, '%s: %s' % (type(e).__name__, str(e)[:80]))

print('\n' + ('★ 全过 ✓ 曲线 JSON 与接口 DTO 对得上' if not FAIL
             else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL))))
sys.exit(1 if FAIL else 0)
