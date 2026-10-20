# -*- coding: utf-8 -*-
"""参数页：生产挖掘参数的**读 / 写 / 恢复默认**（唯一事实源 `engine/loop_params.py`）。

★ 数据流（2026-10-21，用户：前端要能看/改全部参数）：
  · 默认值 / 分组 / 范围 / 危险等级 全部来自 `engine/loop_params.py`（代码）
  · 页面改的只存**覆盖项** → `docs/loop_params.json`
  · `tools/run_tracks.py` 启动时 `merge_extra(load_overrides(), base=_LEGACY_EXTRA)`
    ⇒ 改完**下次启动**生效；正在跑的代不受影响 ✓

⚠ 为什么用 `importlib` 按路径加载而不是 `sys.path.insert`：
  后端进程里塞 engine/ 到 sys.path 会与 `loop_paths` 之类模块名冲突的风险（同名文件多），
  按文件加载只取这一个模块，副作用最小。
"""
import importlib.util
import os

from . import core

_LP_CACHE = {'mtime': None, 'mod': None}


def _lp():
    """加载 `engine/loop_params.py`（按 mtime 缓存）。"""
    p = os.path.join(core.ROOT, 'engine', 'loop_params.py')
    mt = os.path.getmtime(p)
    if _LP_CACHE['mtime'] == mt and _LP_CACHE['mod'] is not None:
        return _LP_CACHE['mod']
    spec = importlib.util.spec_from_file_location('_loop_params_view', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _LP_CACHE.update(mtime=mt, mod=mod)
    return mod


def params_view():
    """GET `/api/params` —— 分组 + 每项（当前值 / 默认值 / 范围 / 危险等级 / 说明）。"""
    lp = _lp()
    ov = lp.load_overrides()
    items, groups = [], []
    for s in lp.PARAM_SPECS:
        g = s['group']
        if g not in groups:
            groups.append(g)
        items.append(dict(
            key=s['key'], flag=s['flag'], label=s['label'], group=g,
            type=s['type'], default=s['default'],
            value=ov.get(s['key'], s['default']),
            overridden=(s['key'] in ov),
            lo=s.get('lo'), hi=s.get('hi'), choices=s.get('choices'),
            danger=s.get('danger', 0), desc=s.get('desc', '')))
    p = lp.DEFAULT_PATH
    exists = os.path.exists(p)
    return dict(groups=groups, items=items,
                path=os.path.relpath(p, core.ROOT),
                exists=exists, mtime=core.mtime_iso(p) if exists else None,
                n_overrides=len(ov),
                note='保存后下次启动挖掘才生效（正在跑的代不变）。'
                     '恢复默认 = 删除覆盖文件，回到代码里的生产默认值。')


def params_save(values):
    """POST `/api/params` —— 校验 + 原子写；返回 `(ok, warnings, saved)`。"""
    lp = _lp()
    clean, errors = lp.validate(values or {})
    if not clean and errors:
        return False, errors, 0
    n = lp.save_overrides(clean)
    return True, errors, n


def params_reset():
    """POST `/api/params/reset` —— 删除覆盖文件（恢复默认）。"""
    lp = _lp()
    p = lp.DEFAULT_PATH
    if os.path.exists(p):
        os.remove(p)
    return True
