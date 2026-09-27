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
    ② 规模压到最小（`--n=12 --l2=2`）⇒ 全链路 **~3 分钟**（不是 50~80 分钟 ✓）
    ③ **备份 + 还原**池的轨迹（隔离逻辑见 `tools/_pool_traj.py` ✓）
    ④ 断言：里程碑齐全 · 无 `Traceback`/`NameError` · state/archive/journal **真的被更新** ·
       **别的池的文件分毫未动**（防"写错池"）✓

★ 安全前提：**挖掘在跑时禁止执行** —— 检测到就直接失败退出（不静默跳过，否则发版可能不经它 ✓）。

★ 与 `tools/ab_generation.py` 的分工：
  本守门答"**链条有没有断**"（里程碑 + 产物存在 ✓）；A/B 工具答"**行为有没有变**"（逐字节对照 ✓）。
  两者共用 `tools/_pool_traj.py` 的备份/还原/起引擎（单一实现 ✓）。
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pool_traj as T                                                 # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = T.ROOT
POOL = '50'                       # ★ 最小池（50 只成分股）⇒ 最便宜
GEN = 9999                        # ★ 远离真实进度（避免和真实轨迹的代号混淆 ✓）
BAK = os.path.join(ROOT, 'ai_test', '_e2ebak_e2e')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def main():
    print('=' * 96)
    print('端到端守门：真跑一代的完整 L1 + L2（池 %s · gen %d）' % (POOL, GEN))
    print('=' * 96)

    print('\n【0】安全前提：挖掘必须已停止（本守门会真写该池轨迹）')
    busy = T.mining_busy()
    chk('挖掘未在跑', not busy,
        '在跑：%s ⇒ 先全部停止再跑本守门（否则会与真实挖掘互相覆盖 ✗）' % '; '.join(busy))
    if busy:
        print('\n✗ 拒绝执行（没有动任何文件）')
        return 1

    mine_files = T.pool_files('_' + POOL)
    other_files = [p for p in (T.pool_files('_300') + T.pool_files('_500') + T.pool_files('_1000'))
                   if os.path.basename(p) != 'library_entries.jsonl']       # 台账是**全池共用** ✓

    print('\n【1】备份池 %s 的轨迹文件' % POOL)
    print('  备份 %d 个文件 -> %s' % (T.backup(mine_files, BAK), os.path.relpath(BAK, ROOT)))
    before = T.snap(mine_files)
    before_other = T.snap(other_files)
    print('  跑前 state 摘要: %s' % str(before.get(mine_files[0]))[:16])

    try:
        print('\n【2】真跑一代（生产同款 flag + 极小规模）')
        rc, out, err, dt = T.run_generation(POOL, GEN, n=12, l2=2)
        print('  用时 %.0fs · 退出码=%d' % (dt, rc))
        with open(os.path.join(ROOT, 'ai_test', '_e2e_last.log'), 'w',
                  encoding='utf-8') as f:
            f.write(out + '\n' + err)

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
        after = T.snap(mine_files)
        st, ar, jn = mine_files[0], mine_files[3], mine_files[1]
        chk('★ state 被更新（gen %d 已落盘）' % GEN, before[st] != after[st],
            'state 没变 ⇒ 一代白跑 ✗')
        chk('★ archive 被更新（每个过 L1 的候选一行）', before[ar] != after[ar])
        chk('★ journal 被更新（诊断已写入）', before[jn] != after[jn])

        rows = []
        try:
            with open(ar, encoding='utf-8') as f:
                rows = [l for l in f.read().splitlines() if l.strip()]
        except Exception as e:
            FAIL.append('archive 读不了: %r' % (e,))
        chk('★ archive 新行都标着 gen=%d' % GEN,
            any(l.split(',')[0].strip() == str(GEN) for l in rows),
            '行数 %d；前 3 行 = %r' % (len(rows), rows[:3]))

        print('\n【5】隔离断言：别的池不许被碰（防"写错池" ✗）')
        after_other = T.snap(other_files)
        bad = [os.path.basename(p) for p in other_files if before_other[p] != after_other[p]]
        chk('300/500/1000 的轨迹文件分毫未动', not bad, '被改了: %r' % (bad,))
    finally:
        print('\n【6】还原池 %s 的轨迹（无论如何都要还原 ✓）' % POOL)
        bad = T.restore(mine_files, BAK)
        if bad:
            print('  [!] 还原有失败项: %r' % (bad,))
        now = T.snap(mine_files)
        diff = [os.path.basename(p) for p in mine_files if before.get(p) != now.get(p)]
        chk('★ 还原后与跑前逐字节一致', not diff and not bad, '仍不一致: %r' % (diff,))
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
