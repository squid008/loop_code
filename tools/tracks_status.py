# -*- coding: utf-8 -*-
"""tracks_status.py -- 三/四池轨道的实时状态（roadmap §8.41）

为什么单独写：`status_all.py` 是给夜间流水线用的；轨道驱动器是 `run_tracks.py`，
它的进度/计划/各池 journal 是否已创建，需要一处看清。
用法: python tools/tracks_status.py
"""
import io
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
LOGD = os.path.join(HERE, '_tracks')
sys.path.insert(0, os.path.join(ROOT, 'engine'))


def bank_counts():
    """各池 bank 入库数 —— ⚠ 读 state pkl 必须先把 engine 的类注入 `__main__`：
    pkl 是引擎**以 `__main__` 身份运行**时 pickle 的，里面的 `Node` 记的是 `__main__.Node`，
    在别的脚本里 unpickle 会报 `Can't get attribute 'Node' on <module '__main__'>`。
    """
    import pickle
    out = {}
    try:
        import loop_engine as LE
        for n in dir(LE):
            if n[:1].isupper() and isinstance(getattr(LE, n), type):
                setattr(sys.modules['__main__'], n, getattr(LE, n))
    except Exception as e:
        return {'(import 失败)': '{}: {}'.format(type(e).__name__, e)}
    for tag in ('all', '300', '500', '1000'):
        sfx = '' if tag == 'all' else '_' + tag
        sf = os.path.join(ROOT, 'engine', 'loop_state{}.pkl'.format(sfx))
        if not os.path.exists(sf):
            out[tag] = None
            continue
        try:
            st = pickle.load(open(sf, 'rb'))
            out[tag] = (len(st.get('bank', []) or []), len(st.get('bank_ex', {}) or {}))
        except Exception as e:
            out[tag] = '{}: {}'.format(type(e).__name__, e)
    return out


def read_log(path):
    """宽容读日志 —— ⚠ 2026-09-13 实录：`run_tracks.py` 用 `subprocess.run(stdout=<文本文件>)`
    时，Python 只把**底层 fd** 交给子进程 ⇒ 子进程按**自己的编码**(Windows 下 cp936/GBK)写字节，
    而父进程的文件对象按 utf-8 解读 ⇒ **日志里中文全是乱码**、解析必然失败。
    ⇒ 这里逐编码试；`run_tracks.py` 侧也已加 `PYTHONIOENCODING=utf-8`（新起的进程才生效）。
    """
    if not os.path.exists(path):
        return ''
    raw = None
    try:
        raw = open(path, 'rb').read()
    except Exception:
        return ''
    for enc in ('utf-8', 'gbk', 'cp936'):
        try:
            s = raw.decode(enc)
            if s.count('\ufffd') == 0:
                return s
        except Exception:
            continue
    return raw.decode('utf-8', errors='replace')


def gen_progress(logf):
    """从引擎日志里摘当前阶段（L1 批 x/y / L2 / 完成），用于给 ETA。"""
    t = read_log(logf)
    if not t:
        return ''
    l1 = re.findall(r'L1 批 (\d+)/(\d+) 开始 \(耗时 (\d+)s\)', t)
    if l1:
        k, n, sec = l1[-1]
        try:
            eta = float(sec) / max(int(k), 1) * int(n) - float(sec)
            return 'L1 {}/{} 已 {:.0f}min（L1 预计还需 ~{:.0f}min）'.format(
                k, n, float(sec) / 60, eta / 60)
        except Exception:
            return 'L1 {}/{}'.format(k, n)
    for pat in ('L2 费后精筛', 'L2 通过', '保存状态', '入库 '):
        m = re.findall(pat + r'[^\n]*', t)
        if m:
            return m[-1][:70]
    return '(早段：载面板/生成候选)'


def main():
    print('=' * 78)
    print('现在', time.strftime('%H:%M:%S'))
    # 1) 驱动日志
    p = os.path.join(LOGD, '_driver.log')
    print('\n[1] 驱动器日志（尾 12 行）')
    if os.path.exists(p):
        for l in io.open(p, encoding='utf-8', errors='replace').read().splitlines()[-12:]:
            print('   ', l[:126])
    else:
        print('    (不存在)')

    # 2) 各池 journal / state
    print('\n[2] 各池 journal / state / 入库数')
    for tag in ('all', '300', '500', '1000'):
        sfx = '' if tag == 'all' else '_' + tag
        jf = os.path.join(DOCS, 'loop_journal{}.md'.format(sfx))
        sf = os.path.join(ROOT, 'engine', 'loop_state{}.pkl'.format(sfx))
        jok = os.path.exists(jf)
        n_gen = 0
        if jok:
            import re
            gs = [int(x) for x in re.findall(r'^##\s*第\s*(\d+)\s*代',
                                             io.open(jf, encoding='utf-8',
                                                     errors='replace').read(), re.M)]
            n_gen = max(gs) if gs else 0
        print('    {:<6s} journal={:<26s} 已完成 {} 代   state={}'.format(
            tag, os.path.basename(jf) + ('✓' if jok else '**尚未创建**'),
            n_gen, '有' if os.path.exists(sf) else '无'))

    # 3) 正在跑的池
    print('\n[3] 正在跑的引擎（看 mine_pool 参数）')
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
          "($_.CommandLine -match 'loop_engine|run_tracks') } | "
          "ForEach-Object { $_.ProcessId.ToString() + '  ' + $_.CommandLine }")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace').stdout.strip()
        print('\n'.join('    ' + x[:150] for x in out.splitlines()) if out
              else '    (无)')
    except Exception as e:
        print('    查询失败:', type(e).__name__, e)

    # 4) 最近写的池日志
    print('\n[4] _tracks 下最近写的日志')
    if os.path.isdir(LOGD):
        fs = sorted(((os.path.getmtime(os.path.join(LOGD, f)), f)
                     for f in os.listdir(LOGD) if f.endswith('.log')
                     and '_err' not in f))
        for mt, f in fs[-4:]:
            print('    {:36s} {:7.0f}s 前'.format(f, time.time() - mt))

    # 5) 各池 bank 入库数
    print('\n[5] 各池 bank（入库数 / 收益流库）')
    bc = bank_counts()
    for tag, v in bc.items():
        if v is None:
            print('    {:<6s} (state 不存在)'.format(tag))
        elif isinstance(v, tuple):
            print('    {:<6s} 入库 {:3d} 个   收益流库 {:3d} 条'.format(tag, v[0], v[1]))
        else:
            print('    {:<6s} 读取失败: {}'.format(tag, v))

    # 6) 当前正在跑的那一代的进度（给 ETA）
    print('\n[6] 在跑的代 进度')
    if os.path.isdir(LOGD):
        fs = sorted(((os.path.getmtime(os.path.join(LOGD, f)), f)
                     for f in os.listdir(LOGD) if f.endswith('.log')
                     and '_err' not in f and f != '_driver.log'))
        if fs:
            mt, f = fs[-1]
            print('    {}  ({:.0f}s 前写入)'.format(f, time.time() - mt))
            print('    ' + gen_progress(os.path.join(LOGD, f)))

    # 7) 内存
    try:
        o = subprocess.run(['powershell', '-NoProfile', '-Command',
                            'Get-CimInstance Win32_OperatingSystem | '
                            'Select-Object -ExpandProperty FreePhysicalMemory'],
                           capture_output=True, text=True).stdout.strip()
        if o.isdigit():
            print('\n[7] 可用内存 {:.1f} GB'.format(float(o) / 1e6))
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
