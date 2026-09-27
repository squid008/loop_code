# -*- coding: utf-8 -*-
"""守门：**真跑一代的完整 L1 + L2 全链路**（2026-09-27 新增 · 补上最大的测试空白）。

★ 为什么需要（v1.23.0 真事故）：
  这个项目此前**没有任何测试跑过 L1/L2** ✗ —— 现存的"真起引擎"测试
  （`smoke_gen_only.py` / `_test_parallel_runner.py` / `_test_dynamic_add.py`）
  **一律用 `--gen_only`，而它恰好跳过 L1+L2** ✗✗（`_test_ghost_args.py` 自己都承认这点）。
  ⇒ v1.23.0 文件级拆分后，`loop_stage.py` 少了 4 个 import（`HERE` / `trim_cache_mb` /
  `ts_mean` / `_P.LIB_ENTRIES`），**所有测试照样全绿**，而真实挖掘**每代秒崩** ✗✗
  ⇒ 用户白等一整晚（看板徽标一直"启动即崩"）。

  本守门把"真跑一代"变成**可断言、可回归、零污染**的一件事：
    ① 用**生产同款 flag**（`--strip_style --style_obs --pool_obs --dual_fwd=20`）
       —— 那 4 个 `NameError` 就住在这几条路上 ✓
    ② 规模压到最小（`--n` / `--l2` 极小）⇒ 全链路 **~2 分钟**（不是 50~80 分钟）✓
    ③ **备份 + 还原**池的轨迹文件（引擎路径是 `__file__` 派生的、**没有**参数/环境变量出口 ✗，
       所以只能备份还原）✓
    ④ 断言：里程碑齐全 · 无 `Traceback`/`NameError` · state/archive/journal **真的被更新** ·
       **别的池的文件分毫未动**（防"写错池"）✓

★ 安全前提：**挖掘在跑时禁止执行**（它会真写池的轨迹）—— 与既有规矩同源
  （`_test_dynamic_add` / `_probe_dynamic_add` 会写控制文件 ⇒ "挖掘运行时禁跑全量回归" ✓）。
  本守门把这条**变成硬检查**：检测到在跑就**直接失败退出**（不静默跳过，否则发版可能不经它 ✓）。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
POOL = '50'                       # ★ 最小池（50 只成分股）⇒ 最便宜
GEN = 9999                        # ★ 远离真实进度（避免和真实轨迹的代号混淆 ✓）
BAK = os.path.join(ROOT, 'ai_test', '_e2ebak_e2e')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def _pool_files(tag):
    """该池（+ 全池共用）的轨迹文件清单 —— 全部由 `engine/loop_paths.py` 决定 ✓"""
    eng, docs = os.path.join(ROOT, 'engine'), os.path.join(ROOT, 'docs')
    return [os.path.join(eng, 'loop_state%s.pkl' % tag),
            os.path.join(docs, 'loop_journal%s.md' % tag),
            os.path.join(docs, 'factor_library%s.md' % tag),
            os.path.join(docs, 'loop_archive%s.csv' % tag),
            os.path.join(docs, 'loop_style_obs%s.csv' % tag),
            os.path.join(docs, 'loop_strip_style%s.csv' % tag),
            os.path.join(docs, 'loop_pool_obs%s.csv' % tag),
            os.path.join(docs, 'library_entries.jsonl')]      # ★ 全池共用（入库台账）


def _sha(p):
    try:
        with open(p, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _snap(paths):
    return {p: _sha(p) for p in paths}


def _mining_busy():
    """挖掘是否在跑。两路来源（控制文件 + 真进程），任一命中即算"在跑" ✓"""
    why = []
    try:
        with io.open(os.path.join(ROOT, 'ai_test', '_tracks', '_control.json'),
                     encoding='utf-8') as f:
            c = json.load(f) or {}
        if c.get('running'):
            why.append('控制文件 running=true')
        if c.get('active'):
            why.append('控制文件 active=%r' % (c.get('active'),))
    except Exception:
        pass
    try:
        sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
        from app import mine as _M                                     # noqa: N812
        _e = _M.engines()
        if _e:
            why.append('真进程里有 %d 个引擎' % len(_e))
    except Exception:
        pass
    return why


def _wait_gone(paths, timeout=25.0):
    """等文件不再被占用（引擎刚退出时 Windows 还可能持有句柄 ✓）—— 能改名即视为可写 ✓"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for p in paths:
                if os.path.exists(p):
                    tmp = p + '.wtest'
                    os.replace(p, tmp)
                    os.replace(tmp, p)
            return True
        except OSError:
            time.sleep(0.4)
    return False


def main():
    print('=' * 96)
    print('端到端守门：真跑一代的完整 L1 + L2（池 %s · gen %d）' % (POOL, GEN))
    print('=' * 96)
    print('  命令: engine/loop_engine.py --mine_pool=%s --gen=%d --n=12 --l2=2 ...'
          % (POOL, GEN))

    print('\n【0】安全前提：挖掘必须已停止（本守门会真写该池轨迹）')
    busy = _mining_busy()
    chk('挖掘未在跑', not busy,
        '在跑：%s ⇒ 先全部停止再跑本守门（否则会与真实挖掘互相覆盖 ✗）' % '; '.join(busy))
    if busy:
        print('\n✗ 拒绝执行（没有动任何文件）')
        return 1

    mine_files = _pool_files('_' + POOL)
    other_files = _pool_files('_300') + _pool_files('_500') + _pool_files('_1000')
    empty_le = os.path.join(ROOT, 'docs', 'library_entries.jsonl')
    other_files = [p for p in other_files if p != empty_le]

    print('\n【1】备份池 %s 的轨迹文件' % POOL)
    shutil.rmtree(BAK, ignore_errors=True)
    os.makedirs(BAK, exist_ok=True)
    for p in mine_files:
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(BAK, os.path.basename(p)))
    before = _snap(mine_files)
    before_other = _snap(other_files)
    print('  备份 %d 个文件 -> %s' % (len(before), os.path.relpath(BAK, ROOT)))
    print('  跑前 state 摘要: %s' % (str(before.get(mine_files[0]))[:16]))

    out = err = ''
    rc = -1
    t0 = time.time()
    try:
        print('\n【2】真跑一代（生产同款 flag + 极小规模）')
        cmd = [PY, '-u', 'engine/loop_engine.py',
               '--mine_pool=%s' % POOL, '--gen=%d' % GEN,
               '--n=12', '--l2=2', '--batch=12', '--seed=777',
               '--panel_cache=use',                      # 生产同款（面板共享）
               '--strip_style', '--style_obs', '--pool_obs',
               '--min_strip_calmar=0.15', '--min_pool_calmar=0.15', '--pool_gate_or_all',
               '--dual_fwd=20', '--min_calmar2=0.701',
               '--llm_guide=off', '--ai_critic=off', '--ai_jury=off']
        print('  ' + ' '.join(cmd[1:]))
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        try:
            pr = subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env, timeout=900)
            out = (pr.stdout or b'').decode('utf-8', 'replace')
            err = (pr.stderr or b'').decode('utf-8', 'replace')
            rc = pr.returncode
        except subprocess.TimeoutExpired:
            rc = -9
            err = 'TIMEOUT(900s)'
        dt = time.time() - t0
        print('  用时 %.0fs · 退出码=%d' % (dt, rc))
        io.open(os.path.join(ROOT, 'ai_test', '_e2e_last.log'), 'w',
                encoding='utf-8').write(out + '\n' + err)

        print('\n【3】全链路里程碑（缺任何一个都说明链条断了 ✗）')
        chk('退出码 0（实得 %d）' % rc, rc == 0)
        chk('无 Traceback', 'Traceback' not in out and 'Traceback' not in err)
        chk('★ 无 NameError（v1.23.0 的崩法就是这个）',
            'NameError' not in out and 'NameError' not in err)
        for desc, pat in (('候选生成完成', '生成候选 '),
                          ('L1 分批开跑', 'L1 批 '),
                          ('L1 出结果', 'L1 通过 '),
                          ('L2 费后精筛开跑', 'L2 费后精筛 '),
                          ('L2 出结论', 'L2 通过 '),
                          ('诊断写 journal', '诊断已写入'),
                          ('状态落盘（代末原子写）', '保存状态:')):
            chk(desc + '（输出含 %r）' % pat, pat in out,
                '链条断在这里 ⇒ 真实挖掘会每代崩 ✗（日志 ai_test/_e2e_last.log ✓）')
        chk('★ 剥风格路径真的走了（--strip_style）', '[剥风格]' in out)
        chk('★ 风格观测路径真的走了（--style_obs）', '[风格观测]' in out)

        print('\n【4】产物断言（不是"跑完就算"，要真有东西落盘 ✓）')
        after = _snap(mine_files)
        st, ar, jn = mine_files[0], mine_files[3], mine_files[1]
        chk('★ state 被更新（gen %d 已落盘）' % GEN, before[st] != after[st],
            'state 没变 ⇒ 一代白跑 ✗')
        chk('★ archive 被更新（每个过 L1 的候选一行）', before[ar] != after[ar])
        chk('★ journal 被更新（诊断已写入）', before[jn] != after[jn])

        _rows = []
        try:
            with io.open(ar, encoding='utf-8') as f:
                _rows = [l for l in f.read().splitlines() if l.strip()]
        except Exception as e:
            FAIL.append('archive 读不了: %r' % (e,))
        chk('★ archive 新行都标着 gen=%d' % GEN,
            any(l.split(',')[0].strip() == str(GEN) for l in _rows),
            '行数 %d；前 3 行 = %r' % (len(_rows), _rows[:3]))

        print('\n【5】隔离断言：别的池不许被碰（防"写错池" ✗）')
        after_other = _snap(other_files)
        _bad = [os.path.basename(p) for p in other_files if before_other[p] != after_other[p]]
        chk('300/500/1000 的轨迹文件分毫未动', not _bad, '被改了: %r' % (_bad,))
    finally:
        print('\n【6】还原池 %s 的轨迹（无论如何都要还原 ✓）' % POOL)
        if not _wait_gone(mine_files):
            print('  [!] 文件仍被占用，等超时了 —— 还原可能不完整（请人工核对）')
        ok_restore = []
        for p in mine_files:
            b = os.path.join(BAK, os.path.basename(p))
            try:
                if os.path.exists(b):
                    shutil.copy2(b, p)
                    ok_restore.append(os.path.basename(p))
                elif os.path.exists(p):
                    os.unlink(p)        # 跑前不存在 ⇒ 跑出来的要删掉 ✓
                    ok_restore.append(os.path.basename(p) + '(删)')
            except OSError as e:
                FAIL.append('还原 %s 失败: %r' % (os.path.basename(p), e))
        now = _snap(mine_files)
        _diff = [os.path.basename(p) for p in mine_files if before.get(p) != now.get(p)]
        chk('★ 还原后与跑前逐字节一致', not _diff, '仍不一致: %r' % (_diff,))
        shutil.rmtree(BAK, ignore_errors=True)

    print('\n' + '=' * 96)
    if FAIL:
        print('✗ 失败 %d 项：' % len(FAIL))
        for x in FAIL:
            print('   - ' + x)
        return 1
    print('★ 全过 ✓ 完整 L1+L2 全链路真跑通：' 
          '里程碑齐全 · 产物真落盘 · 别的池未被碰 · 轨迹已还原 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
