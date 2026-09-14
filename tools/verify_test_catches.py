# -*- coding: utf-8 -*-
"""verify_test_catches.py — **负向验证**：证明某个回归测试**真的抓得到**它要防的 bug。

## 为什么需要它

**一个"永远通过"的测试没有价值** —— 它可能：
  · 断言写得太松（永远为真）
  · 扫错了文件 / 匹配错了模式
  · 被测的代码路径根本没走到
⇒ 唯一可靠的检验方式：**把 bug 人为放回去，看测试会不会 FAIL**。

本工具自动化这个过程（4 步，全程 try/finally 保证**一定还原**）：
  ① 在源码里把 `--from` 改成 `--to`（= 把 bug 放回去）
  ② 跑 `--regen`（重新生成被测产物）
  ③ 跑 `--test`  ⇒ **期望退出码非 0（FAIL = 抓到了）**
  ④ 还原源码 + 重跑 `--regen` + 再跑 `--test` ⇒ **期望退出码 0（PASS）**

## 用法（以"精选池表达式截断"那次为例）

    python tools/verify_test_catches.py \
        --file=tools/cross_pool_review.py \
        --from="BT, _cell(meta[n]['expr']), BT))" \
        --to="BT, _cell(meta[n]['expr'][:58]), BT))" \
        --regen="tools/cross_pool_review.py" \
        --test="tools/_test_reports_expr.py"

⚠ **只用于验证测试本身**，不是 CI 的一环（它会**故意破坏源码再还原**）。
   还原由 `try/finally` 保证；若中途被强杀，源码可能停在"已破坏"状态 ⇒
   本工具会在开始时**把原文件内容也写到 `<file>.verifybak`**，便于手工恢复。
"""
import argparse
import io
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def run(rel):
    return subprocess.run([PY, '-u', rel.replace('/', os.sep)], cwd=ROOT,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace',
                          env=dict(os.environ, PYTHONIOENCODING='utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='要临时破坏的源文件（仓库相对路径）')
    ap.add_argument('--from', dest='frm', required=True, help='原始片段（正确的）')
    ap.add_argument('--to', dest='to', required=True, help='替换成（= bug）')
    ap.add_argument('--regen', default='', help='重新生成被测产物的脚本（可空）')
    ap.add_argument('--test', required=True, help='回归测试脚本')
    a = ap.parse_args()

    path = os.path.join(ROOT, a.file)
    print('=' * 96)
    print('负向验证：证明 {} 真的抓得到 bug'.format(a.test))
    print('=' * 96)
    src = io.open(path, encoding='utf-8').read()
    if a.frm not in src:
        print('  [!] 在 {} 里找不到 --from 片段 ⇒ 无法验证'.format(a.file))
        return 2
    io.open(path + '.verifybak', 'w', encoding='utf-8').write(src)
    caught = False
    try:
        io.open(path, 'w', encoding='utf-8').write(src.replace(a.frm, a.to))
        print('  ① 已把 bug 放回 {}（{} -> {}）'.format(
            a.file, a.frm[:40], a.to[:40]))
        if a.regen:
            r = run(a.regen)
            print('  ② 重新生成 {} -> 退出码 {}'.format(a.regen, r.returncode))
        r = run(a.test)
        caught = (r.returncode != 0)
        print('  ③ 跑 {} -> 退出码 {} ⇒ {}'.format(
            a.test, r.returncode, '**抓到 bug** ✓' if caught else '**没抓到 ⇒ 测试无效** ✗'))
        for l in (r.stdout or '').splitlines():
            if 'FAIL' in l:
                print('       ' + l.strip()[:134])
    finally:
        io.open(path, 'w', encoding='utf-8').write(src)
        if a.regen:
            run(a.regen)
        print('  ④ 已还原 {} 并重新生成'.format(a.file))
    r = run(a.test)
    restored = (r.returncode == 0)
    print('  ⑤ 再跑 {} -> 退出码 {} ⇒ {}'.format(
        a.test, r.returncode, '还原成功、测试通过 ✓' if restored else '**还原后仍 FAIL** ✗'))
    # 还原成功 ⇒ 删掉应急备份（留着会让工作区多一个无意义文件）
    if restored:
        try:
            os.remove(path + '.verifybak')
            print('  ⑥ 已删除应急备份 {}.verifybak'.format(a.file))
        except OSError:
            pass
    print()
    ok = caught and restored
    print('=' * 96)
    print('结论: {}'.format(
        '✓ 负向验证成立（bug 放回去会 FAIL、还原后 PASS）—— 这个测试是有价值的'
        if ok else '✗ 负向验证失败：测试可能无效，或还原不干净'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
