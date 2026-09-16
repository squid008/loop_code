# -*- coding: utf-8 -*-
"""构建 / 校验「面板只读缓存」（`engine/_panel_cache/`）—— 2026-09-16 新增。

用法:
    python tools/build_panel_cache.py           # 构建（覆盖旧缓存；约 1~2 分钟）
    python tools/build_panel_cache.py --check   # 只**校验**现有缓存是否有效、是否最新

★ 为什么要单独一个工具（而不是让引擎"偷偷"构建）：
  缓存过期会**静默改变结果** ⇒ 构建必须是**显式**动作；
  引擎侧 `--panel_cache=use` 只负责"用"，缺失/过期**直接报错** ✓

★ 缓存内容**与池无关**（只存全量面板 `B` + `close` + dates/cols）
  ⇒ **构建一次、所有池共用** ✓
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_engine as LE          # noqa: E402
import panel_cache as PC          # noqa: E402


def main():
    check = '--check' in sys.argv[1:]
    sha = PC.code_sha1(LE._build_panel_fresh)
    print('=' * 80)
    print('面板只读缓存  %s' % PC.CACHE_DIR)
    print('  构造代码 SHA1 : %s   （`_build_panel_fresh` 源码；改了它 ⇒ 缓存自动失效）' % sha)
    print('  来源文件      : %s' % ', '.join(PC.SRC_FILES))
    print('  长度指纹      : (size, mtime_ns) —— 数据一变 ⇒ 缓存自动失效')
    print('=' * 80)
    ok, msg = PC.status(sha)
    print('  当前缓存: %s' % msg)

    if check:
        print('  %s' % ('[OK] 缓存可用' if ok else '[FAIL] 需要重建（python tools/build_panel_cache.py）'))
        return 0 if ok else 1

    t0 = time.time()
    B, dates, cols, close = LE._build_panel_fresh()
    t1 = time.time()
    print('  现场构造完成: %d 字段 / %.2f GB / %.1fs'
          % (len(B), PC.size_gb(B), t1 - t0))
    PC.save(B, dates, cols, close.values, sha)
    ok, msg = PC.status(sha)
    print('  校验: %s' % msg)
    print('  ⇒ 引擎用 `--panel_cache=use` 即可只读映射（多进程共享同一份物理页）✓')
    print('  ⚠ 缓存目录不入 git（`.gitignore` 已含 *.npy），可随时删掉重建 ✓')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
