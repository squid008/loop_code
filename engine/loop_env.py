# -*- coding: utf-8 -*-
"""loop_env.py — 机器相关「外部路径」的单一事实源（读 `config.local.json` 的 `paths` 段）

★ 为什么要有这个文件（2026-10-27）：
  项目在两台机器之间搬（公司 E 盘 / 家里 D 盘），而**数据根**（米筐 bundle 那套）
  与项目根**不在同一处** ⇒ 任何 `.py` 里写死 `D:\\rq` 或 `E:\\rq`，换机器就必错
  （错法还很隐蔽：要么报"文件不存在"，要么读到另一份旧数据 ⇒ **静默算错** ✗）。

★ 唯一事实源 = `config.local.json`（已在 `.gitignore`，含密钥 ⇒ 绝不入库）：
  {
    "paths": {
      "active": "auto",
      "profiles": {
        "company": {"data_root": "E:/rq", "project_root": "E:/quant/loop_code"},
        "home":    {"data_root": "D:/rq", "project_root": "D:/quant/loop_code"}
      }
    }
  }

★ 选择顺序（先命中者生效）：
  ① 环境变量 `LOOP_DATA_ROOT`（直接给数据根，排错/临时用）
  ② 环境变量 `LOOP_PROFILE`（= profiles 里的名字，如 company / home）
  ③ `paths.active`（**不是** `auto` 时照它走，且**不再探测** —— 配错要立刻炸，绝不静默换机器）
  ④ `auto`：按 profiles 顺序，取第一个 `<data_root>/bundle` 真实存在者
  ⑤ 都不成立 ⇒ **抛 SystemExit 并打印怎么修**（绝不静默回退到某个盘符）

★ 仓库根**不配置**：一律由本文件位置派生（整仓可搬移）；profile 里的 `project_root`
  只用于自检/打印，与实际不符时给一行告警，不参与任何读写。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))          # engine/
ROOT = os.path.dirname(HERE)                               # 仓库根（派生）
CFG_PATH = os.path.join(ROOT, 'config.local.json')

# 数据根成立的最小判据（bundle 是每台机器都必须有的那套）
_SENTINEL = 'bundle'
# 最后兜底（只在 config 里**完全没有**可用 profiles 时才用，且会打印一行告警）
_DEFAULT_ROOTS = ('D:/rq', 'E:/rq')

_CFG = None
_PROFILES = {}
_PROFILE = None
_DATA_ROOT = None


def _load():
    global _CFG
    if _CFG is None:
        if os.path.isfile(CFG_PATH):
            try:
                with open(CFG_PATH, encoding='utf-8') as f:
                    _CFG = json.load(f)
            except Exception as e:                          # noqa: BLE001
                raise SystemExit('[loop_env] 读 %s 失败(%s: %s) —— 修好这个 JSON 再跑'
                                 % (CFG_PATH, type(e).__name__, e))
        else:
            _CFG = {}
    return _CFG


def profiles():
    """返回 {名字: {'data_root':..., 'project_root':...}}（保持 config 里的顺序）。"""
    global _PROFILES
    if not _PROFILES:
        raw = ((_load().get('paths') or {}).get('profiles') or {})
        out = {}
        for name, p in raw.items():
            p = dict(p or {})
            dr = (p.get('data_root') or '').strip() if isinstance(p.get('data_root'), str) else ''
            if not dr:
                continue
            p['data_root'] = os.path.normpath(dr)
            p['project_root'] = (p.get('project_root') or '').strip()
            out[name] = p          # ★ 保留 profile 里的其它可选键（如 moneyflow_csv_root）
        _PROFILES = out
    return _PROFILES


def _ok(dr):
    return bool(dr) and os.path.isdir(os.path.join(dr, _SENTINEL))


def _fail(msg):
    raise SystemExit(
        '[loop_env] %s\n'
        '  ⇒ 请在 %s 里配好 paths 段（模板见 config.example.json），例如：\n'
        '     "paths": {"active": "auto", "profiles": {\n'
        '        "company": {"data_root": "E:/rq", "project_root": "E:/quant/loop_code"},\n'
        '        "home":    {"data_root": "D:/rq", "project_root": "D:/quant/loop_code"}}}'
        % (msg, CFG_PATH))


def resolve():
    """解析出生效的 (profile 名, data_root)。规则见模块 docstring。"""
    global _PROFILE, _DATA_ROOT
    if _DATA_ROOT:
        return _PROFILE, _DATA_ROOT
    prof = profiles()

    env_root = (os.environ.get('LOOP_DATA_ROOT') or '').strip()
    if env_root:
        dr = os.path.normpath(env_root)
        if not _ok(dr):
            _fail('环境变量 LOOP_DATA_ROOT=%s 下没有 %s\\（不像是数据根）' % (dr, _SENTINEL))
        _PROFILE, _DATA_ROOT = '<env:LOOP_DATA_ROOT>', dr
        return _PROFILE, _DATA_ROOT

    env_name = (os.environ.get('LOOP_PROFILE') or '').strip()
    if env_name:
        if env_name not in prof:
            _fail('环境变量 LOOP_PROFILE=%s 不在 config 的 paths.profiles 里（现有: %s）'
                  % (env_name, ', '.join(prof) or '无'))
        dr = prof[env_name]['data_root']
        if not _ok(dr):
            _fail('profile %s 的 data_root=%s 下没有 %s\\' % (env_name, dr, _SENTINEL))
        _PROFILE, _DATA_ROOT = env_name, dr
        return _PROFILE, _DATA_ROOT

    active = ((_load().get('paths') or {}).get('active') or 'auto').strip()
    if active and active.lower() != 'auto':
        if active not in prof:
            _fail('paths.active=%s 不在 paths.profiles 里（现有: %s）' % (active, ', '.join(prof) or '无'))
        dr = prof[active]['data_root']
        if not _ok(dr):
            _fail('paths.active=%s 指到 %s，但那里没有 %s\\（配错了就直说，不会偷偷换机器）'
                  % (active, dr, _SENTINEL))
        _PROFILE, _DATA_ROOT = active, dr
        return _PROFILE, _DATA_ROOT

    for name, p in prof.items():
        if _ok(p['data_root']):
            _PROFILE, _DATA_ROOT = name, p['data_root']
            return _PROFILE, _DATA_ROOT

    if prof:
        _fail('没探到可用的数据根（候选: %s）；每个候选下都要有 %s\\'
              % ('; '.join('%s=%s' % (k, v['data_root']) for k, v in prof.items()), _SENTINEL))

    # 兜底：config 里根本没有 paths 段（例：刚 pull 下来、本机 config.local.json 还是旧的）
    for dr in _DEFAULT_ROOTS:
        if _ok(dr):
            print('[loop_env] 注意：%s 里没有可用的 paths.profiles ⇒ 兜底探到数据根 %s\n'
                  '          建议写进 config 的 paths 段（模板见 config.example.json），免得下次靠猜'
                  % (CFG_PATH, os.path.normpath(dr)))
            _PROFILE, _DATA_ROOT = '<默认探测>', os.path.normpath(dr)
            return _PROFILE, _DATA_ROOT

    _fail('config 里没有 paths.profiles，默认候选 %s 下也没有 %s\\（本项目的外部数据根靠它定位）'
          % ('/'.join(_DEFAULT_ROOTS), _SENTINEL))


def data(*parts):
    """拼数据根下的路径：`data('bundle', 'stocks.h5')`。"""
    _, dr = resolve()
    return os.path.join(dr, *parts)


def opt(key, default=None):
    """取当前 profile 里的**可选**键（如 `moneyflow_csv_root`）；没有就给 default。"""
    name, _ = resolve()
    v = (profiles().get(name) or {}).get(key)
    if isinstance(v, str):
        v = v.strip()
        return os.path.normpath(v) if v else default
    return v if v else default


def describe():
    """给看板/自检打印用的一行说明（不抛错，探不到就如实说）。"""
    prof = profiles()
    try:
        name, dr = resolve()
    except SystemExit:
        return ('数据根: 未配置/未探到（config.local.json 的 paths 段；仓库根 %s；'
                '候选 %s）' % (ROOT, ', '.join('%s=%s' % (k, v['data_root']) for k, v in prof.items()) or '无'))
    p = prof.get(name) or {}
    pr = p.get('project_root') or ''
    warn = ''
    if pr and os.path.normpath(pr).lower() != ROOT.lower():
        warn = ' ⚠ profile %s 写的 project_root=%s 与实际仓库根 %s 不一致（实际以仓库根为准）' % (name, pr, ROOT)
    return '数据根: %s（profile=%s）· 仓库根: %s%s' % (dr, name, ROOT, warn)


# ★ 惰性取值（PEP 562）：**import 本模块不做任何解析** ⇒ 配错/没配的机器上，
#   `import loop_env` 本身不会崩（只有真正用到路径时才炸，且炸得清楚）。
#   ⇒ 使用方推荐 `loop_env.data('bundle', 'stocks.h5')`，而不是 `from loop_env import DATA_ROOT`（那是 import 时取值拷贝）。
_LAZY = ('DATA_ROOT', 'PROFILE', 'BUNDLE', 'POOLS_DIR')


def __getattr__(name):
    if name in _LAZY:
        prof, dr = resolve()
        val = {'DATA_ROOT': dr, 'PROFILE': prof,
               'BUNDLE': os.path.join(dr, 'bundle'),
               'POOLS_DIR': os.path.join(dr, 'constituents', 'index')}[name]
        globals()[name] = val
        return val
    raise AttributeError('module %r has no attribute %r' % (__name__, name))
