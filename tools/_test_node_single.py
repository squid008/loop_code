# -*- coding: utf-8 -*-
"""★★★★★ 守门：**一份代码里只许有一个 `Node` 类**（2026-09-25 用户实测："这 F47 为啥会显示未分类"）。

## 病根（本次修的真 bug）
引擎直跑时模块名是 `__main__`（类全名 `__main__.Node`）；而 `loop_critic` 的**惰性**
`import loop_engine as LE` 会把 `loop_engine.py` **再执行一遍**（这次叫 `loop_engine` 模块）
⇒ 同一进程里出现**两个 `Node` 类** ✗

实测（读 `loop_state.pkl` 按 pickle 记录的类路径统计）：`bank` 439 个 Node 里
**438 个是第二份**；`seeds` / `last_l1` 也混着 24 个 ✗

## 为什么必须守（后果远超"显示"）
`isinstance(x, Node)` 是**类身份**判定 ⇒ 对第二份实例恒 False ✗ 牵连：
  · `collect()` → `leaf_parts()` ⇒ 因子库"家族"全落「未分类」（archive 的 cat/leaf 空，392 行）
  · **`skeleton()` ⇒ 骨架去重 / FSA 冻结失效**（同族重复因子拦不住）
  · `key()` / `size()`（FSA 结构哈希）· `crossover`/`mutate`（子树操作退化成只动顶层）
  · `dim_of()`（跨量纲审查）· `clone`

## 两条修复（本守门各钉一处）
① **文件末尾**那句：`sys.modules.setdefault('loop_engine', sys.modules['__main__'])`
   ⇒ 之后任何 `import loop_engine` 都拿到**本模块** ⇒ 结构上不可能再有第二份 ✓
   ⚠ 它只能放在**末尾那个 `__main__` 块**里、**不能放文件顶部** ✗ —— 引擎里从此**只许有
     1 个** `if __name__ == '__main__':`：`tools/_test_fwd_wiring.py` 用 AST 取**第一个**块，
     并在其中断言 `set_panel_cache` / `set_mem_budget` / `run(_args)` 是**直接语句**；
     顶部另起一块会把它的"目标块"抢走（实测该守门当场失败 ✗）
② 读 state：`_StateUnpickler` 把**历史上误存的** `loop_engine.Node` 也还原成本模块的类 ✓
   （旧 state 里已经混了 486 个，不归一它们就一直是"判不出身份"的异类 ✗）

⚠⚠⚠ 三条**血泪注意**（验证这类问题时别踩）：
  1. **绝不许用 `importlib` 以 `__name__='__main__'` exec `loop_engine.py` 来"模拟直跑"** ✗✗
     —— 那会执行 `if __name__ == '__main__':` 块 ⇒ **真跑一代引擎**！（2026-09-25 亲历，
     所幸进程在写盘前因 stdout 管道断裂退出，state/库 mtime 未变 ✓）
  2. 本测试只**静态断言** + **`import`**（`import` 不会执行 `__main__` 块 ✓）⇒ 安全 ✓
  3. 真机验证交给"下一代挖掘"或 `smoke_gen_only.py`（`--gen_only` 不写状态 ✓）✓
"""
import csv
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)
import loop_engine as LE                                     # noqa: E402  ← 安全：不打 __main__ 块

SRC = io.open(os.path.join(ENG, 'loop_engine.py'), encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：从源头杜绝"第二份 Node 类"')
_REG = "sys.modules.setdefault('loop_engine', sys.modules['__main__'])"
chk("有 `sys.modules.setdefault('loop_engine', sys.modules['__main__'])`",
    _REG in SRC,
    '否则 loop_critic 的惰性 import 会再 exec 一遍本模块 ⇒ 两个 Node 类 ✗')
_i_reg = SRC.index(_REG)
# ⚠ 必须按**行首**匹配（`^`）：注释里也会提到这个字符串（用来解释"它为何放在末尾" ✗）
_MAIN_RE = r"^if __name__ == '__main__':"
_main_starts = [m.start() for m in re.finditer(_MAIN_RE, SRC, re.M)]
chk("注册在**末尾那个** `__main__` 块里（不是在文件顶部另起一块 ✗）",
    _i_reg > max(_main_starts),
    '⚠ 顶部另起 `__main__` 块会抢走 `_test_fwd_wiring.py` 的目标块（它取**第一个**块 '
    '并断言 set_panel_cache/set_mem_budget/run(_args) 是直接语句）')
chk("引擎里**只有 1 个** `__main__` 块（护住上一条假设 ✓），实 %d 个" % len(_main_starts),
    len(_main_starts) == 1)
chk('注册在 `run(_args)` **之前**（`loop_critic` 是惰性 import ⇒ 足够早 ✓）',
    _i_reg < SRC.index('    run(_args)'),
    '晚于 run(_args) ⇒ loop_critic 的 import 已经跑过 ⇒ 第二份照旧产生 ✗')

print()
print('[2] 静态：读 state 时归一旧数据')
PERSIST_SRC = io.open(os.path.join(ENG, 'loop_persist.py'), encoding='utf-8').read()  # _StateUnpickler 已迁 loop_persist
STAGE_SRC = io.open(os.path.join(ENG, 'loop_stage.py'), encoding='utf-8').read()  # 读取调用在 loop_stage
chk('定义了 `_StateUnpickler`（`find_class` 把类名 Node 一律映射成本模块的）',
    'class _StateUnpickler(pickle.Unpickler)' in PERSIST_SRC
    and re.search(r"def find_class\(self, module, name\):\s*\n\s+if name == 'Node':\s*\n\s+return Node",
                  PERSIST_SRC) is not None)
_n_call = len(re.findall(r'(st|_stp) = _StateUnpickler\(', STAGE_SRC))
chk('state 的**两处**读取都走了它（主 state + 外部池注入），实 %d 处' % _n_call, _n_call == 2)
chk('没有残留的裸 `pickle.load` 读 state ✗',
    re.search(r'\b(st|_stp) = pickle\.load\(', SRC) is None)

print()
print('[3] 功能：`_StateUnpickler` 把**两种**类名都归一（旧 state 里的 486 个异类）')
stp = os.path.join(ENG, 'loop_state.pkl')
if not os.path.exists(stp):
    print('  ⚠ 无 loop_state.pkl ⇒ 跳过功能检查（不影响结论 ✓）')
else:
    with open(stp, 'rb') as f:
        st = LE._StateUnpickler(f).load()

    def walk(n, out):
        if isinstance(n, LE.Node):
            out.append(n)
            for a in n.args:
                walk(a, out)

    alln = []
    for k in ('bank', 'seeds'):
        for n in (st.get(k) or []):
            walk(n, alln)
    bad = [n for n in alln if type(n) is not LE.Node]
    chk('`bank`+`seeds` 里 %d 个 Node **全部**是本模块类（异类 %d 个）' % (len(alln), len(bad)),
        not bad, '仍有异类：%r' % sorted({type(x).__module__ for x in bad})[:3])

    l1 = st.get('last_l1')
    if l1 is not None and 'node' in getattr(l1, 'columns', []):
        empty = [r for r in l1['node'] if isinstance(r, LE.Node) and not LE.leaf_parts(r)[0]]
        chk('`last_l1` 里"取不到叶子"（会落「未分类」）的候选 = 0，实 %d' % len(empty), not empty)

print()
print('[4] 数据：archive 的 cat/leaf 不许再为空（已回填 ✓ 防再次出现）')
_bad_files = []
for _p in sorted(os.path.join(ROOT, 'docs', 'loop_archive%s.csv' % s)
                 for s in ('', '_300', '_500', '_1000', '_50')):
    if not os.path.exists(_p):
        continue
    with io.open(_p, encoding='utf-8-sig', newline='') as f:
        rr = list(csv.DictReader(f))
    _e = sum(1 for r in rr if not (r.get('cat') or '').strip())
    if _e:
        _bad_files.append('%s: %d 行' % (os.path.basename(_p), _e))
chk('各池 `loop_archive*.csv` 里 `cat` 为空的行 = 0',
    not _bad_files, '仍有：%s' % ', '.join(_bad_files))

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：一份 Node 类 + state 已归一 + archive 标注齐（骨架去重 / FSA / 家族分类不再失效 ✓）')
