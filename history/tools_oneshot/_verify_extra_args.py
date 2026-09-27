# -*- coding: utf-8 -*-
"""【只读】静态解析 `run_tracks.py` 的 `extra` 参数列表（**不执行**，避免误触发挖掘）。"""
import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools', 'run_tracks.py')
tree = ast.parse(io.open(P, encoding='utf-8').read())
found = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'extra':
        if isinstance(node.value, (ast.List, ast.Tuple)):
            found = [e.value for e in node.value.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            break
print('=' * 96)
print('`run_tracks.py` 的 extra（透传给引擎的生产参数）')
print('=' * 96)
if not found:
    print('  ✗ 未解析到 extra 列表')
    sys.exit(1)
for a in found:
    print('  %s' % a)
print()
print('  ★ `--style_obs` 在列表里吗: %s' % ('✓ 在' if '--style_obs' in found else '✗ 不在'))
print('  ★ `--strip_style` 在列表里吗: %s' % ('✓ 在' if '--strip_style' in found else '✗ 不在'))
print('  ★ `--score_mode=new`（它要验证的对象）: %s'
      % ('✓ 在' if '--score_mode=new' in found else '✗ 不在'))
print()
print('  ⇒ 与 `--strip_style` 共存 = 断言 `style_features` 会被复用（成本≈0）= %s'
      % ('✓ 成立' if ('--style_obs' in found and '--strip_style' in found) else '✗ 不成立'))
