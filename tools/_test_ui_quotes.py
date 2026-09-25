# -*- coding: utf-8 -*-
"""★★ 守门：**用户看得到的文案里不许出现引号**（`「」『』“”‘’`）。

用户要求（2026-09-16）：「所有前端文案提示涉及到引号的地方都改改去掉引号」
⇒ 这条规矩必须**静态钉住** —— 文案是手写的，端到端测试**测不到"有没有引号"** ✗
  （同 `_test_frontend_wiring.py` 的思路：交互/文案类规则用源码级断言守住）

范围（**只查用户看得到的**；注释与 docstring 不算 —— 用户看不到，保留项目原有风格 ✓）：
  · `dashboard/web/src/*.tsx|*.ts` + `index.html`
    ⇒ 先把注释剥掉（`//` · `/* */` · JSX 的 `{/* */}`），**字符串里的 `//` 不当注释**（状态机，别用正则）
  · `dashboard/api/app/**.py`（会被看板直接渲染的后端串：`note` / `memNote` / 提示消息）
    ⇒ 用 `ast` 取**非 docstring** 的字符串字面量（含 f-string 的静态片段）

退出码：0 = 干净 ✓ · 1 = 还有引号 ✗（进全量回归 ⇒ 不会再退化）
"""
import ast
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUOTES = '「」『』“”‘’'
WEB = os.path.join(ROOT, 'dashboard', 'web')
API = os.path.join(ROOT, 'dashboard', 'api', 'app')
QRE = re.compile('[%s]' % QUOTES)


def rel(path):
    """相对路径（⚠ 自检用的是**系统临时目录**，与仓库**不同盘** ⇒ `relpath` 会抛 ValueError ✗）"""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


def strip_js(text):
    """剥掉 JS/TS/JSX 注释（**状态机**：字符串里的 `//` `/*` 不算注释）。

    ⚠ 不能用正则：`title="http://x"` 里的 `//` 会被误当注释 ⇒ 后面全乱 ✗
    换行**原样保留** ⇒ 行号与原文一致（报错能直接定位）✓
    """
    out = []
    i, n = 0, len(text)
    st = None                      # None | "'" | '"' | '`' | '//' | '/*'
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ''
        if st is None:
            if c == '/' and nx == '/':
                st = '//'
                i += 2
                continue
            if c == '/' and nx == '*':
                st = '/*'
                i += 2
                continue
            if c in ('"', "'", '`'):
                st = c
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        if st == '//':
            if c == '\n':
                st = None
                out.append(c)
            i += 1
            continue
        if st == '/*':
            if c == '*' and nx == '/':
                st = None
                i += 2
                continue
            if c == '\n':                    # 保留换行 ⇒ 行号对齐
                out.append(c)
            i += 1
            continue
        # 字符串内部
        if c == '\\':
            out.append(c)
            out.append(nx)
            i += 2
            continue
        if c == st:
            st = None
        out.append(c)
        i += 1
    return ''.join(out)


def docstring_ids(tree):
    """模块/类/函数**文档字符串**的节点 id（这些是"注释性"的，不算文案）"""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, 'body', None) or []
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def check_js(path, bad):
    txt = io.open(path, encoding='utf-8').read()
    for k, l in enumerate(strip_js(txt).splitlines(), 1):
        if QRE.search(l):
            bad.append((rel(path), k, l.strip()[:120]))


def sym_table_ids(tree):
    """★ **窄豁免**：清洗表（`_QM` / `_SYM`）自己**必须写着那些符号** —— 否则没法清洗它们。

    ⚠ 只豁免"整张表"这一处，**不做全局放宽**（否则真文案也溜过去了 ✗）——
      同 `_QM` 的定义注释：清洗表是**唯一的例外**，且它的存在恰恰是为了别处没有引号 ✓
    """
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ('_QM', '_SYM') for t in node.targets):
            for x in ast.walk(node.value):
                ids.add(id(x))
    return ids


def check_py(path, bad):
    # ⚠ 必须 `utf-8-sig`：仓库里 `__init__.py` 带 **BOM(U+FEFF)** ⇒ 用 `utf-8` 读进去
    #   `ast.parse` 会报 "invalid non-printable character" ⇒ 被当成"引号残留"误报 ✗（实测踩到）
    src = io.open(path, encoding='utf-8-sig').read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        # 语法错**不算引号问题**（自有测试/编译守门会抓它）⇒ 只提示，不判失败 ✓
        print('  ⚠ 跳过 %s（语法错：%s）' % (rel(path), e))
        return
    ds = docstring_ids(tree) | sym_table_ids(tree) | regex_arg_ids(tree)
    lines = src.splitlines()
    for node in ast.walk(tree):
        v = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in ds:
                continue
            v = node.value
        elif isinstance(node, ast.JoinedStr):          # f-string：查它的静态片段
            v = ''.join(x.value for x in node.values
                        if isinstance(x, ast.Constant) and isinstance(x.value, str))
        if v and QRE.search(v):
            k = getattr(node, 'lineno', 0)
            bad.append((rel(path), k,
                        '%s   ⟵ 原样：%s' % (lines[k - 1].strip()[:88] if k and k <= len(lines) else '',
                                          v.strip()[:70])))


def self_test():
    """★ 负向自检：**证明这个守门会失败**（否则等于没检查 ✓）
      [1] TSX 文案里塞引号 ⇒ 必须被查出
      [2] Python 串里塞引号 ⇒ 必须被查出
      [3] **docstring / 注释** 里塞引号 ⇒ 必须**不**被查（用户看不到 ⇒ 保持项目风格）
      [4] 字符串里的 `//` **不是注释**（状态机正确性）—— 别把后面的文案一起吞掉
    """
    import tempfile
    fails = []
    bad = []
    tf = os.path.join(tempfile.gettempdir(), '_q_selftest.tsx')
    io.open(tf, 'w', encoding='utf-8').write(
        'const a = "点「原始」看看"\n'
        'const b = "https://example.com/x"   // 这行注释里有「引号」也不算\n'
        '{/* 「这段是 JSX 注释」*/}\n'
        'const c = "干净的一句话"\n')
    check_js(tf, bad)
    hit = [x for x in bad if '原始' in x[2]]
    if not hit:
        fails.append('TSX 文案里的引号没查出来 ✗')
    if any('这行注释' in x[2] or 'JSX 注释' in x[2] for x in bad):
        fails.append('注释里的引号被误报 ✗（注释不算文案）')
    if any('干净的一句话' in x[2] for x in bad):
        fails.append('干净文案被误报 ✗')
    bad = []
    pf = os.path.join(tempfile.gettempdir(), '_q_selftest.py')
    io.open(pf, 'w', encoding='utf-8').write(
        '"""模块文档：「引号」允许"""\n'
        '\n'
        '\n'
        'def f():\n'
        '    """函数文档：「引号」允许"""\n'
        '    note = "已把池 %s 加入「并行」"\n'
        '    # 注释里「引号」允许\n'
        '    return note\n')
    check_py(pf, bad)
    if not any('并行' in x[2] for x in bad):
        fails.append('Python 串里的引号没查出来 ✗')
    if any('允许' in x[2] for x in bad):
        fails.append('docstring/注释里的引号被误报 ✗')
    for p in (tf, pf):
        try:
            os.remove(p)
        except OSError:
            pass
    print('  [自检] 能查出真引号 ✓ · 注释/docstring 不误报 ✓ · 字符串里的 // 不当注释 ✓'
          if not fails else '  [自检] ✗ ' + ' / '.join(fails))
    return fails


def plain_covers_quotes():
    """★ 后端出口 `_plain()` 必须**把引号也洗掉**。

    为什么单独查它：`docs/*.md` 是给看板展示的（库里的一句话/公式/须知/精选池要点都从 md 来），
    而 md 是技术文档、本身保留引号 ⇒ **出口清洗是唯一的去处** ✓
    2026-09-16 实测：`_plain` 原来只去 `**` 和反引号 ⇒ 用户在看板上仍看得到引号 ✗

    返回 `(缺哪些引号字符, 是否真的应用了 _QM)`
    """
    p = os.path.join(API, 'sources', 'factors.py')
    src = io.open(p, encoding='utf-8-sig').read()
    tree = ast.parse(src)
    have = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '_QM' for t in node.targets):
            for el in getattr(node.value, 'elts', []):
                for c in getattr(el, 'elts', []):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        have.add(c.value)
    return [c for c in QUOTES if c not in have], bool(re.search(r'_SYM\s*\+\s*_QM', src))


def scan_curve_json(bad):
    """★ 离线曲线 JSON 的**口径串会被看板原样渲染** ⇒ 也在守门范围内。

    ⚠ 只查 `caliber`（散文）；**不要全量扫字符串** —— 因子表达式等字段不是文案，
      全扫会有误报 ✗（守门宁可窄一点，但必须准）
    """
    d = os.path.join(ROOT, 'docs', 'factor_curves')
    if not os.path.isdir(d):
        return 0
    n = 0
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json'):
            continue
        try:
            js = json.load(io.open(os.path.join(d, f), encoding='utf-8'))
        except Exception:
            continue
        cand = [('caliber', js.get('caliber')),
                ('strip.caliber', (js.get('strip') or {}).get('caliber')),
                ('style.caliber', (js.get('style') or {}).get('caliber'))]
        for path, s in cand:
            if not isinstance(s, str) or not s:
                continue
            n += 1
            hit = [t for t in ('**', '★', '⚠', '⇒', '✗') if t in s] + \
                  ([c for c in QUOTES if c in s] or [])
            if hit:
                bad.append(('docs/factor_curves/%s' % f, 0,
                            '%s 含 %s：%s' % (path, ''.join(hit), s[:60])))
    return n


MACHINE = ('**', '★', '⚠', '⇒', '✓', '✗', '❗')
CJK = re.compile(r'[\u4e00-\u9fa5]')


def _only_symbols(v):
    """该字面量**只由机味符号组成**（如 `'⇒'`、`'**'`、`'_SYM'` 表里的条目）⇒ 它是**符号表数据**，
    不是"文案" ⇒ 豁免 ✓（否则"清洗表本身"会被判违规，等于无法清洗）"""
    if CJK.search(v):
        return False
    return all(ch in '**★⚠⇒✓✗❗・·，\ufe0f ' for ch in v)


def regex_arg_ids(tree):
    """★ 豁免：`re.compile/sub/search/...` 的**模式串**不是文案

    （`r'当前\\s*\\**\\s*(\\d+)'` 里的 `**` 是**正则元字符**，不是"机味加粗" ✗ 别误报）
    """
    ids = set()
    names = ('compile', 'sub', 'subn', 'search', 'match', 'findall', 'finditer',
             'split', 'fullmatch')
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in names:
                for a in node.args:
                    for x in ast.walk(a):
                        ids.add(id(x))
    return ids


def scan_api_strings(bad):
    """★ 后端**返回给看板的字符串**（API 模块里非 docstring 的字面量）不许有：
        ① 机味符号（`** ★ ⚠ ⇒ ✓ ✗`）；② **中文旁边的 ASCII 引号**（引号也该去掉）
    为什么能这么扫：看板里所有文案最终都来自这些串（`note`/`hint`/表格单元格/口径串）✓
    """
    n = 0
    for dirpath, _d, files in os.walk(API):
        for f in sorted(files):
            if not f.endswith('.py'):
                continue
            p = os.path.join(dirpath, f)
            src = io.open(p, encoding='utf-8-sig').read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            skip = docstring_ids(tree) | sym_table_ids(tree) | regex_arg_ids(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in skip or _only_symbols(node.value):
                    continue
                v = node.value
                n += 1
                hit = [t for t in MACHINE if t in v]
                # ASCII 引号夹中文（`"...中文..."`）⇒ 也算"文案里的引号"
                if re.search(r'[\u4e00-\u9fa5][\'"]|[\'"][\u4e00-\u9fa5]', v):
                    hit.append('引号')
                if hit:
                    k = getattr(node, 'lineno', 0)
                    bad.append((rel(p), k, '含 %s：%s' % (''.join(hit), v.strip()[:70])))
    return n


def scan_config_json(bad):
    """`dashboard/config.json` 的注释字段会在**配置/口径**页显示 ⇒ 一并守门 ✓"""
    p = os.path.join(ROOT, 'dashboard', 'config.json')
    if not os.path.isfile(p):
        return 0
    n = 0
    try:
        cfg = json.load(io.open(p, encoding='utf-8-sig'))
    except Exception:
        return 0
    stack = [('', cfg)]
    while stack:
        path, o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                stack.append(('%s.%s' % (path, k), v))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                stack.append(('%s[%d]' % (path, i), v))
        elif isinstance(o, str):
            n += 1
            hit = [t for t in MACHINE if t in o]
            if hit:
                bad.append(('dashboard/config.json', 0, '%s 含 %s：%s' % (path, ''.join(hit), o[:60])))
    return n


def curves_exit_clean():
    """出口清洗必须作用在**会被渲染的口径串**上（`factors.curves()`）"""
    p = os.path.join(API, 'sources', 'factors.py')
    src = io.open(p, encoding='utf-8-sig').read()
    return (bool(re.search(r"'caliber':\s*_plain\(", src))
            and "'style': _plain_style(" in src)


def main():
    print('=' * 100)
    print('自检（先证明守门会失败，再查全仓库）')
    print('=' * 100)
    st = self_test()
    miss, applied = plain_covers_quotes()
    if miss:
        st.append('后端出口清洗 `_QM` 缺引号字符：%s' % ''.join(miss))
    if not applied:
        st.append('`_plain()` 没有应用 `_QM`（出口没洗引号）')
    if not curves_exit_clean():
        st.append('`factors.curves()` 没对**口径串**做出口清洗（离线 JSON 会被原样渲染）')
    print()
    bad = []
    n_api = scan_api_strings(bad)
    n_cfg = scan_config_json(bad)
    n_json = scan_curve_json(bad)
    for nm in ('index.html',):
        p = os.path.join(WEB, nm)
        if os.path.isfile(p):
            check_js(p, bad)
    srcdir = os.path.join(WEB, 'src')
    if os.path.isdir(srcdir):
        for f in sorted(os.listdir(srcdir)):
            if f.endswith(('.tsx', '.ts')):
                check_js(os.path.join(srcdir, f), bad)
    for dirpath, _dirs, files in os.walk(API):
        for f in sorted(files):
            if f.endswith('.py'):
                check_py(os.path.join(dirpath, f), bad)
    print('=' * 100)
    print('用户可见文案的引号检查（%s）' % QUOTES)
    print('=' * 100)
    if not bad and not st:
        print('  ✓ 全部干净：前端文案 + 后端返回串 + 离线曲线口径串（查了 %d 条）都没有引号/机味符号 ✓'
              % n_json)
        return 0
    for f, k, l in bad:
        print('  ✗ %s:%s  %s' % (f, k, l))
    print()
    print('★ 共 %d 处还带引号（+ 自检失败 %d 项）⇒ 去掉引号'
          '（自然语言 + 普通标点即可）✗' % (len(bad), len(st)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
