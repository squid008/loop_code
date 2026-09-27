# -*- coding: utf-8 -*-
"""_pool_traj.py —— 池轨迹的**快照 / 还原 / 真跑一代**（供守门与 A/B 工具共用 · 单一实现 R5 ✓）

## 为什么需要它

引擎的产物路径全部由 `engine/loop_paths.py` 从 `__file__` 派生、**没有任何参数或环境变量出口** ✗
（`loop_paths.set_mine_pool` 还只接受**真实池名** ⇒ 连"用个假池名隔离"都做不到 ✗）。
所以"真跑一代但又不想污染真实轨迹"只有一个办法：**备份 → 跑 → 还原** ✓

本模块把这套动作收成**一份**实现，给两处共用：
· `tools/_test_e2e_l1l2.py` —— 端到端守门（断言里程碑 / 产物 / 隔离 ✓）
· `tools/ab_generation.py`   —— 同 seed A/B 工具（改前改后产物**逐字对照** ✓，见 R7 铁律）

## 安全前提

**挖掘在跑时不许调用** ✗ —— 它会真写池的轨迹（`mining_busy()` 就是给调用方做这道闸的 ✓）。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def pool_files(tag):
    """该池（+ 全池共用的入库台账）的轨迹文件清单 —— 全部由 `engine/loop_paths.py` 决定 ✓"""
    eng, docs = os.path.join(ROOT, 'engine'), os.path.join(ROOT, 'docs')
    return [os.path.join(eng, 'loop_state%s.pkl' % tag),
            os.path.join(docs, 'loop_journal%s.md' % tag),
            os.path.join(docs, 'factor_library%s.md' % tag),
            os.path.join(docs, 'loop_archive%s.csv' % tag),
            os.path.join(docs, 'loop_style_obs%s.csv' % tag),
            os.path.join(docs, 'loop_strip_style%s.csv' % tag),
            os.path.join(docs, 'loop_pool_obs%s.csv' % tag),
            os.path.join(docs, 'library_entries.jsonl')]      # ★ 全池共用（入库台账）


def sha(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def snap(paths):
    return {p: sha(p) for p in paths}


def mining_busy():
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


def wait_gone(paths, timeout=25.0):
    """等文件不再被占用（引擎刚退出时 Windows 还可能持有句柄）—— 能改名即视为可写 ✓"""
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


def backup(paths, bakdir):
    """把 paths 全部复制进 bakdir（文件名扁平化）✓"""
    shutil.rmtree(bakdir, ignore_errors=True)
    os.makedirs(bakdir, exist_ok=True)
    n = 0
    for p in paths:
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bakdir, os.path.basename(p)))
            n += 1
    return n


def restore(paths, bakdir, timeout=25.0):
    """从 bakdir 还原；**跑前不存在的文件要删掉**（否则跑出来的会留下）✓ 返回失败的清单。"""
    if not wait_gone(paths, timeout):
        pass                                    # 等不到也照样尽力还原（调用方自行判定 ✓）
    bad = []
    for p in paths:
        b = os.path.join(bakdir, os.path.basename(p))
        try:
            if os.path.exists(b):
                shutil.copy2(b, p)
            elif os.path.exists(p):
                os.unlink(p)
        except OSError as e:
            bad.append('%s: %r' % (os.path.basename(p), e))
    return bad


def gen_cmd(pool, gen, n=12, l2=2, batch=None, seed=777, extra=None, prod_flags=True):
    """跑一代的命令（★ 与端到端守门共用同一份口径 ✓）。

    prod_flags=True ⇒ 加上**生产同款**的那组 flag（`--strip_style --style_obs --pool_obs
    --dual_fwd=20 …`）—— v1.23.0 崩掉的 4 个 `NameError` 就住在这几条路上 ✓
    """
    cmd = [PY, '-u', 'engine/loop_engine.py',
           '--mine_pool=%s' % pool, '--gen=%d' % gen,
           '--n=%d' % n, '--l2=%d' % l2, '--batch=%d' % (batch or n),
           '--seed=%d' % seed, '--panel_cache=use',
           '--llm_guide=off', '--ai_critic=off', '--ai_jury=off']
    if prod_flags:
        cmd += ['--strip_style', '--style_obs', '--pool_obs',
                '--min_strip_calmar=0.15', '--min_pool_calmar=0.15', '--pool_gate_or_all',
                '--dual_fwd=20', '--min_calmar2=0.701']
    return cmd + list(extra or [])


def run_generation(pool, gen, n=12, l2=2, seed=777, extra=None, prod_flags=True, timeout=900):
    """真跑一代（不动任何文件管理）—— 返回 (rc, out, err, dt_sec) ✓"""
    cmd = gen_cmd(pool, gen, n=n, l2=l2, seed=seed, extra=extra, prod_flags=prod_flags)
    # ★ `PYTHONHASHSEED=0`：把"字符串哈希随机化"固定下来 ✓
    #   不固定的话，`Counter`/`set` 的迭代顺序每次不同 ⇒ 诊断行里 `leaf_hist {...}` 的键序会变 ✗
    #   （**内容相同、只是顺序不同** —— 对数值无影响，但会让 A/B 出现假差异 ✗）
    #   ⚠ 生产**没有**设它 ⇒ 那条诊断行的键序在生产里本就随进程变（无害 ✓，本工具只是把它固定成可控实验 ✓）
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONHASHSEED='0')
    t0 = time.time()
    try:
        pr = subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env, timeout=timeout)
        out = (pr.stdout or b'').decode('utf-8', 'replace')
        err = (pr.stderr or b'').decode('utf-8', 'replace')
        rc = pr.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = '', 'TIMEOUT(%ds)' % timeout, -9
    return rc, out, err, time.time() - t0
