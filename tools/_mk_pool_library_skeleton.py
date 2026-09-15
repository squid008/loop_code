# -*- coding: utf-8 -*-
"""为指定池预建 `docs/factor_library_{pool}.md` 骨架 —— **模板直接取自引擎源码**。

## 为什么要它
- 上证50（`pool=50`）的 4 个数据文件已从归档恢复，但 `factor_library_50.md` **从未存在**
  （50 池 `bank=0`，引擎的 `_lib_sync` 在 `if not added_exprs: return` 处直接返回 ⇒ 不触发建骨架）
- 看板「因子库」页签会让用户看到 50 池**空着** ⇒ 需要骨架文件

## ⚠ 为什么不直接调 `engine.loop_engine._mk_library_skeleton`
它写到**模块级 `LIBRARY`**（由 `set_mine_pool` 派生，默认是**全A 的 `docs/factor_library.md`**）
⇒ 直接调用会**覆盖全A 库文件** ✗✗
⇒ 所以：**从引擎源码里用 `ast` 提取那个模板字符串**，再按目标池生成 ⇒ **格式与引擎 100% 一致** ✓
   （若提取失败则回退到内置副本，并校验 3 个锚点）

## 骨架必须含的 3 个锚点（引擎 `_lib_sync` 依赖）
① `> 当前 **N 个入库**`（供 `re.sub` 更新计数）② `## 因子明细` ③ `## 相关文件导航`
"""
import ast
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r'D:\loop_code'
ENGINE_SRC = os.path.join(R, 'engine', 'loop_engine.py')
POOL = sys.argv[1] if len(sys.argv) > 1 else '50'
TAG = POOL
SFX = '' if POOL == 'all' else '_' + POOL
OUT = os.path.join(R, 'docs', 'factor_library%s.md' % SFX)


def extract_template():
    """从 `_mk_library_skeleton` 里取那个被 `(...)` 拼接后 `.format(t=..., s=...)` 的字符串。

    ⚠ 2026-09-15 修：初版写 `and sub.args`（要求**位置参数**）⇒ 而引擎那句是
      `('...' '...').format(t=tag, s=sfx)` —— **只有关键字参数**，`sub.args` 为空
      ⇒ ast 提取**总是失败**（回退到内置副本，等于白写）✗
      ⇒ 正确取法是 `sub.func.value`（`.format` 的**接收者**，即那个拼接出来的字符串）✓
    """
    src = io.open(ENGINE_SRC, encoding='utf-8').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_mk_library_skeleton':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == 'format':
                    for cand in (sub.func.value,) + tuple(sub.args):
                        try:
                            val = ast.literal_eval(cand)
                        except Exception:
                            continue
                        if isinstance(val, str) and '{t}' in val and '因子总览' in val:
                            return val
    return None


FALLBACK = (
    '# 因子库（池 = {t}）\n\n'
    '> 当前 **0 个入库**\n'
    '> 本文件由引擎在**每代末尾自动同步**（`--mine_pool={t}` 时生效；实现见 `_lib_sync`）。\n'
    '> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。\n\n'
    '---\n\n'
    '## 因子总览\n\n'
    '| 编号 | 入库代数 | 家族 | 一句话 | 状态 |\n'
    '|---|---|---|---|---|\n\n'
    '## 因子明细\n\n'
    '## 相关文件导航\n\n'
    '| 文件 | 内容 |\n|---|---|\n'
    '| `docs/factor_library{s}.md`（本文件） | 池 **{t}** 的入库因子（只增不改） |\n'
    '| `docs/factor_library.md` | 全A 轨道的入库因子 |\n'
    '| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图** |\n'
    '| `docs/loop_journal{s}.md` | 池 **{t}** 的每代诊断 + B角下一代参数 |\n'
    '| `docs/loop_pool_obs{s}.csv` | 池 **{t}** 候选的**三池池内指标**宽表 |\n'
    '| `docs/loop_archive{s}.csv` | 池 **{t}** 每代 L2 全量候选流水 |\n'
)

if os.path.exists(OUT):
    print('  ⚠ 已存在，不覆盖: %s' % os.path.relpath(OUT, R))
    sys.exit(0)

tpl = extract_template()
src = '引擎源码 `_mk_library_skeleton`（ast 提取）' if tpl else '**内置副本**（提取失败，已回退）'
if not tpl:
    tpl = FALLBACK
print('  模板来源: %s' % src)

txt = tpl.format(t=TAG, s=SFX)

# ★ 加一句"尚未开采"说明（放在锚点之外，不破坏 ③ 个锚点）
NOTE = ('> ★ 2026-09-15：**本池尚未开采**（`bank=0`；数据文件 `loop_journal_50.md` / '
        '`loop_archive_50.csv` / `loop_pool_obs_50.csv` / `loop_strip_style_50.csv` 已就位）。\n'
        '> 首个因子入库时，引擎会**自动**把条目同步进本表 ✓\n')
txt = txt.replace('> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。\n',
                  '> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。\n' + NOTE)

# 校验 3 个锚点
anchors = ['> 当前 **', '## 因子明细', '## 相关文件导航']
missing = [a for a in anchors if a not in txt]
if missing:
    print('  ✗ 缺锚点 %s ⇒ 中止（引擎 `_lib_sync` 会静默出错）' % missing)
    sys.exit(1)

io.open(OUT, 'w', encoding='utf-8', newline='').write(txt)
print('  ✓ 已生成 %s（%d 行）· 锚点 3/3 ✓' % (os.path.relpath(OUT, R), len(txt.splitlines())))
