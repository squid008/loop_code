# -*- coding: utf-8 -*-
"""Loop 挖掘进度查询：进程存活 + 当前阶段 + 最近日志/档案尾行。
用法:  D:\\miniconda3\\envs\\rqdata\\python.exe D:\\loop_code\\engine\\loop_status.py
"""
import glob, io, json, os, re, subprocess, datetime

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
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          "Where-Object { $_.CommandLine -match 'loop_engine' } | "
          "ForEach-Object { [PSCustomObject]@{ pid=$_.ProcessId; "
          "run=[int](((Get-Date)-$_.CreationDate).TotalMinutes); "
          "mem=[math]::Round($_.WorkingSetSize/1MB,0) } } | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                             capture_output=True, timeout=30)
        s = out.stdout.decode('utf-8', 'replace').strip()
        if not s:
            return []
        rows = json.loads(s)
        return rows if isinstance(rows, list) else [rows]
    except Exception as e:
        return [{'err': str(e)}]


def main():
    print('=' * 60)
    procs = running_engine()
    if procs and 'err' not in procs[0]:
        for p in procs:
            print(f"[引擎] PID {p['pid']}  已运行 {p['run']} 分钟  "
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
