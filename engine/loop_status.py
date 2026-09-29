# -*- coding: utf-8 -*-
"""Loop 挖掘进度查询：进程存活 + 当前阶段 + 最近日志/档案尾行。
用法:  D:\\miniconda3\\envs\\rqdata\\python.exe D:\\loop_code\\engine\\loop_status.py
"""
import glob, io, os, re, datetime      # ★ 2026-09-29：json/subprocess 随 PS 查询一起下岗（死码 ✗）

try:
    import os_compat as OC          # ★ 2026-09-29：操作系统专有件（单一实现 ✓，见 §1.40.3）
except Exception:                   # noqa: BLE001
    OC = None                       # 取不到就按"查询失败"如实回传，不静默当成"没在跑" ✗

HERE = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(os.path.dirname(HERE), 'docs', 'loop_journal.md')


def read_tail(path, n=10):
    """自动探测编码(utf-8/gbk)并返回尾部 n 行文本。"""
    with open(path, 'rb') as f:
        raw = f.read()
    txt = None
    for enc in ('utf-8', 'gbk'):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    if txt is None:
        txt = raw.decode('utf-8', 'replace')
    return txt.splitlines()[-n:]


def running_engine():
    """在跑的引擎 ⇒ `[{pid, run(已跑分钟), mem(MB)}, …]`；查失败 ⇒ `[{'err': …}]` ✓（旧契约 ✓）。

    ★ 2026-09-29（`loop_todo §1.40.3` 可移植性平台化）：原实现是 PowerShell
      `Get-CimInstance Win32_Process` ✗（Win32 专有）⇒ 改走 `os_compat.list_procs()` ✓
      （Windows 分支仍是**同一句** PS ✓，POSIX 换成 `ps` ✓）。
    ⚠ 两处口径微差，都无害，据实记明 ✓：
      ① 进程名过滤由 `Name='python.exe'` 放宽为 `Name like 'python%'` ✓
         （与看板/其它工具**统一** ✓；多出来的 `pythonw.exe` 不影响"跑没跑引擎"的判断 ✓）；
      ② `run` 改在 Python 里按 `start` 算 ✓ —— 与 PS 的 `(Get-Date)-CreationDate` **语义等价** ✓，
         但不是同一条算式（本函数只供**人肉看进度** ✓，不参与任何判定 ✓）；算不出时返回 `-1`
         ⇒ `main()` 会显示 `?` ✓（**不**编造一个假的分钟数 ✗）。
    """
    if OC is None:
        return [{'err': '取不到 engine/os_compat.py（sys.path 里没有 engine/ ?）'}]
    try:
        now = datetime.datetime.now()
        rows = []
        for p in OC.list_procs():
            cmd = p.get('cmd') or ''
            if 'loop_engine' not in cmd:
                continue                        # 只认引擎（口径与旧 PS 的 -match 'loop_engine' 一致 ✓）
            run = -1
            try:
                _t0 = datetime.datetime.strptime(p.get('start') or '', '%Y-%m-%d %H:%M:%S')
                run = int((now - _t0).total_seconds() // 60)
            except Exception:                   # noqa: BLE001
                run = -1                        # 时间戳解析不了 ⇒ 如实标"未知" ✓
            rows.append({'pid': p.get('pid'), 'run': run, 'mem': p.get('mem_mb')})
        return rows
    except Exception as e:                      # noqa: BLE001
        return [{'err': str(e)}]


def main():
    print('=' * 60)
    procs = running_engine()
    if procs and 'err' not in procs[0]:
        for p in procs:
            # ★ 2026-09-29：`run` 为 -1 = 拿不到开工时刻 ⇒ 显示 `?` ✓（不编造假分钟数 ✗）
            print(f"[引擎] PID {p['pid']}  已运行 {'?' if p['run'] < 0 else p['run']} 分钟  "
                  f"内存 {p['mem']} MB  -> 运行中")
    elif procs and 'err' in procs[0]:
        print(f"[引擎] 进程查询失败: {procs[0]['err']}")
    else:
        print('[引擎] 无 loop_engine 进程 -> 未在运行(可能已完成或中断)')

    logs = sorted(glob.glob(os.path.join(HERE, 'loop*C.log')),
                  key=os.path.getmtime, reverse=True)
    if logs:
        lg = logs[0]
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(lg))
        tail = read_tail(lg, 10)
        body = '\n'.join(tail)
        if '诊断已写入' in body:
            stage = '本代已完成(B角诊断已落档)'
        elif 'L1 求值完成' in body:
            stage = 'L2 费后验证阶段(接近完成)'
        elif '生成候选' in body or 'L1' in body:
            stage = 'L1 批量 IC 筛选阶段(耗时长, 耐心等)'
        else:
            stage = '启动/载入阶段'
        print(f"\n[日志] {os.path.basename(lg)}  更新于 {mtime:%m-%d %H:%M}  阶段: {stage}")
        print('-' * 60)
        for ln in tail:
            print(' ', ln)
    else:
        print('\n[日志] 未找到 loop*C.log')

    if os.path.exists(JOURNAL):
        try:
            with io.open(JOURNAL, 'r', encoding='utf-8') as f:
                jt = f.read()
            gens = re.findall(r'第 (\d+) 代', jt)
            if gens:
                print(f"\n[档案] loop_journal.md 最近落档: 第 {gens[-1]} 代 诊断")
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(JOURNAL))
                print(f'        档案文件更新于 {mtime:%m-%d %H:%M}'
                      '(若晚于本代日志=本代刚跑完)')
        except Exception as e:
            print(f'\n[档案] 读取失败: {e}')
    print('=' * 60)


if __name__ == '__main__':
    main()
