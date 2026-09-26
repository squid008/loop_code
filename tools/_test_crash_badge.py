# -*- coding: utf-8 -*-
"""守门：**「启动即崩」徽标的生命周期**（2026-09-26 新增 · 用户实测驱动）。

★ 为什么需要（用户实测："我全部停止了，然后看到俩池子现在都是启动即崩的状态，
  这跟以前好像不一样？以前应该是回到已停止的状态才对吧"）：
  徽标语义 = 「**此刻**启动即崩」，但它**只有一个撤销触发点：跑通一代（rc=0）** ✗ ——
  而「**被用户停掉**」是 rc=1 ⇒ 走 `if rc != 0` 分支、`killed=True` ⇒ **既不写也不撤** ✗✗
  ⇒ v1.23.0 的一次真崩（`NameError`）留下的徽标，在用户停止后**一直挂着** ✗
  ⇒ 卡片写着"已停止"却顶着红字「启动即崩 ×1」，自相矛盾 ✓
  实测时间线（`ai_test/_tracks/_engine_exits.log`）：
    22:22 `all`/`300` 真崩 ⇒ 写徽标；23:42 两池各跑 24.9 分钟、err=0、被用户停 ⇒ 徽标残留 ✗

本守门钉住两件事：
  ① **停止（单池 / 全部）会撤掉对应的过期徽标** —— 行为实测（临时控制文件，不碰真状态 ✓）；
  ② **保护不减弱** —— 「非被停的异常退出」仍然会写徽标（`parallel_runner` 的 `if not killed` ✓）。
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


MINE_SRC = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'),
                   encoding='utf-8').read()
PARR_SRC = io.open(os.path.join(ROOT, 'tools', 'parallel_runner.py'),
                   encoding='utf-8').read()


def _strip_comments(t):
    """去掉注释与字符串字面量，避免"注释里提到某写法"造成误判 ✓"""
    out, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if c == '#':
            j = t.find('\n', i)
            i = n if j < 0 else j
        elif c in '"\'':
            q, i = c, i + 1
            while i < n and t[i] != q:
                i += 2 if t[i] == '\\' else 1
            i += 1
            out.append('""')
        else:
            out.append(c)
            i += 1
    return ''.join(out)


MINE_CODE = _strip_comments(MINE_SRC)
PARR_CODE = _strip_comments(PARR_SRC)

print('【1】静态：位置与接线')
chk('`mine.py` 定义了 `clear_crashes(`',
    re.search(r'^def clear_crashes\(', MINE_CODE, re.M) is not None)
chk('单池停止分支调用了 `clear_crashes([pool])`',
    re.search(r'_write_ctl\(stopped=st\)\s*\n\s*clear_crashes\(\[pool\]\)', MINE_CODE) is not None,
    '不撤 ⇒ 用户停止后徽标残留 ✗（本次用户实测的本体 ✓）')
chk('全部停止分支调用了 `clear_crashes()`',
    re.search(r'_write_ctl\(stopAll=True\)\s*\n\s*clear_crashes\(\)', MINE_CODE) is not None)
chk('★ 保护不减弱：非"被停"的异常退出**仍然**写徽标',
    re.search(r'if not killed:', PARR_CODE) is not None
    and '_g[-3:]' in PARR_CODE and 'crashes=' in PARR_CODE,
    '撤过期证据 ≠ 关掉报警：真·必崩的池下次启动还会崩 ⇒ 一分钟内徽标自动回来 ✓')

print()
print('【2】行为实测：真调 `clear_crashes`（临时控制文件，不碰真状态 ✓）')
TMP = tempfile.mkdtemp(prefix='_test_crashbadge_')
try:
    from app import mine as M                                          # noqa: N812
    M.LOGD = TMP
    M.CTL_FILE = os.path.join(TMP, '_control.json')
    M.CTL_LOCK = M.CTL_FILE + '.lock'
    # 造一份"真崩残留"的控制文件：all/300 有徽标，500 也有、1000 没有
    with io.open(M.CTL_FILE, 'w', encoding='utf-8') as f:
        json.dump({'running': False, 'enabled': ['all', '300'], 'stopped': ['all', '300'],
                   'crashes': {'all': [81], '300': [191], '500': [99]},
                   'exits': {'all': {'gen': 81, 'rc': 1, 'killed': True}}}, f)

    def _crashes():
        return (M.ctl().get('crashes') or {})

    chk('前置：徽标已就位（all/300/500）',
        sorted(_crashes()) == ['300', '500', 'all'], '实得 %r' % (_crashes(),))

    _hit = M.clear_crashes(['all', '300'])
    chk('单池停止 ⇒ 只撤该池的徽标（返回被撤的池名 ✓）',
        sorted(_hit) == ['300', 'all'] and sorted(_crashes()) == ['500'],
        '实得 hit=%r cr=%r' % (_hit, _crashes()))
    chk('★ 别的池的徽标**不许**被误撤',
        '500' in _crashes(),
        '撤错池会把真正在崩的池藏起来 ✗')

    chk('对没有徽标的池调用 ⇒ 无事发生、也不报错（幂等 ✓）',
        M.clear_crashes(['1000']) == [] and sorted(_crashes()) == ['500'])

    _hit2 = M.clear_crashes()
    chk('全部停止 ⇒ 撤掉所有徽标（`pools=None` ✓）',
        sorted(_hit2) == ['500'] and _crashes() == {},
        '实得 hit=%r cr=%r' % (_hit2, _crashes()))

    _ex = M.ctl().get('exits') or {}
    chk('★ 撤徽标**不碰**其它字段（`exits` 等原样保留 ✓）',
        'all' in _ex and _ex['all'].get('rc') == 1,
        '误清 exits 会让"为什么退出"的记录丢掉 ✗')
    chk('★ 撤徽标**不碰**启用/剔除集合（`enabled`/`stopped` 原样 ✓）',
        M.ctl().get('enabled') == ['all', '300'] and M.ctl().get('stopped') == ['all', '300'])
    chk('写盘是原子的（`.tmp` + `os.replace` ✓）',
        os.path.isfile(M.CTL_FILE) and not os.path.exists(M.CTL_FILE + '.tmp'))
except ImportError as e:
    chk('可导入 `app.mine`（后端依赖齐全）', False, repr(e))
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   - ' + x)
    sys.exit(1)
print('★ 全过 ✓ 「停止 ⇒ 撤过期徽标」已接线，且"真崩仍会重新打标"的保护未减弱 ✓')
