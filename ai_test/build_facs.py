# -*- coding: utf-8 -*-
"""⚠ **兼容垫片（shim）** —— 真身在 `tools/build_facs.py`。

存在的唯一原因：**v0.5.2 迁移时轨道驱动 `run_tracks.py` 正在跑**，
它收尾①用**硬编码路径** `subprocess.run(['ai_test/build_facs.py', '--only-new'])` 调本脚本
⇒ 直接把文件搬走会让那次轨道**在收尾时报「文件不存在」**。

**轨道结束后可安全删除本文件**（`git rm ai_test/build_facs.py`），此后一律用 `tools/build_facs.py`。

⚠ 提示写 **stdout**（不写 stderr）：PowerShell 会把子进程的 stderr 当 `NativeCommandError`，
   且 `run_tracks.py` 收尾段会检查子进程 stderr 非空并记 `[stderr]` —— 兼容垫片不该制造这种噪声。
"""
import os
import runpy
import sys

_REAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'tools', 'build_facs.py')
if not os.path.exists(_REAL):
    sys.stdout.write('[shim] 真身不存在: {}\n'.format(_REAL))
    sys.exit(2)
# 让真身所在目录成为 sys.path[0]（等价于"直接跑 tools/build_facs.py"）
sys.path.insert(0, os.path.dirname(_REAL))
sys.stdout.write('[shim] ai_test/build_facs.py -> tools/build_facs.py（兼容垫片，轨道结束后可删）\n')
sys.stdout.flush()
# runpy 会正确设置 __file__；真身的 sys.exit(main()) 会以 SystemExit 穿透本层 ✓
runpy.run_path(_REAL, run_name='__main__')
