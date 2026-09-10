# -*- coding: utf-8 -*-
"""Loop 引擎无人值守接力 watcher（不依赖 automation 调度）。

每 ~5 分钟一个循环：
1. 若 loop_engine 进程在跑 -> 等待。
2. 若空闲 -> 读 docs/loop_journal.md 找最近已完成代数 N（标题 "## 第 N 代"）。
   - 该代 err log 非空 -> 记日志并退出（报错停止，等待人工）。
   - N >= TARGET_GEN -> 达成目标退出（TARGET_GEN 默认 70，可用环境变量 LOOP_TARGET_GEN 覆盖）。
   - 否则启动 gen N+1（防重复：对应 loop{N+1}C.log 不存在才启）。
3. 每代启动后 sleep 20s 确认进程存活 + 日志头正常。

运行: D:\\miniconda3\\envs\\rqdata\\python.exe D:\\loop_code\\engine\\loop_watch.py
日志:  D:\\loop_code\\engine\\loop_watcher.log
"""
import os
import re
import subprocess
import time
from datetime import datetime

ENGINE_DIR = r"D:\loop_code\engine"
DOCS_DIR = r"D:\loop_code\docs"
PY = r"D:\miniconda3\envs\rqdata\python.exe"
WATCH_LOG = os.path.join(ENGINE_DIR, "loop_watcher.log")
POLL_S = 300          # 主轮询间隔
LIFTOFF_S = 20        # 启动后确认存活间隔
TARGET_GEN = int(os.environ.get("LOOP_TARGET_GEN", "70"))   # 目标代数(达此代即停)

_LOG_FD = open(WATCH_LOG, "a", encoding="utf-8", buffering=1)


def log(msg: str) -> None:
    line = f"{datetime.now():%m-%d %H:%M:%S} {msg}"
    _LOG_FD.write(line + "\n")
    try:
        print(line, flush=True)
    except UnicodeEncodeError:  # 控制台 gbk 编码遇日志头乱码字符
        try:
            print(line.encode("utf-8", errors="replace").decode("gbk", errors="replace"), flush=True)
        except Exception:
            pass


def now_s() -> int:
    return int(time.time())


def is_engine_running() -> bool:
    """WMI 查 loop_engine 进程。查不到时保守返回 True（宁可不启也不重复启）。"""
    ps = (
        'powershell -NoProfile -Command "Get-CimInstance Win32_Process '
        "-Filter \\\"Name like 'python%'\\\" "
        "| Where-Object { $_.CommandLine -match 'loop_engine' } "
        '| Measure-Object | Select-Object -ExpandProperty Count"'
    )
    try:
        out = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=60)
        n = int((out.stdout or "").strip())
        return n > 0
    except Exception as e:
        log(f"[WARN] is_engine_running 异常({e})，保守视为运行中")
        return True


def latest_done_gen():
    """读 journal 找已完成代数 N（标题行 '## 第 N 代'），返回最大 N；无则 None。"""
    jp = os.path.join(DOCS_DIR, "loop_journal.md")
    if not os.path.exists(jp):
        return None
    text = open(jp, encoding="utf-8", errors="ignore").read()
    gens = [int(m) for m in re.findall(r"^##\s*第\s*(\d+)\s*代", text, re.M)]
    return max(gens) if gens else None


def err_nonempty(gen: int) -> bool:
    p = os.path.join(ENGINE_DIR, f"loop{gen}C_err.log")
    return os.path.exists(p) and os.path.getsize(p) > 0


def start_next_gen(g: int) -> bool:
    log_p = os.path.join(ENGINE_DIR, f"loop{g}C.log")
    err_p = os.path.join(ENGINE_DIR, f"loop{g}C_err.log")
    if os.path.exists(log_p):
        log(f"[SKIP] loop{g}C.log 已存在，疑似重复代，不启动")
        return False
    seed = g * 10 + 7
    cmd = [PY, "-u", "loop_engine.py", f"--gen={g}", "--n=800", "--l2=30", f"--seed={seed}"]
    log(f"[START] gen{g} seed={seed}")
    out = open(log_p, "w", encoding="utf-8")
    err = open(err_p, "w", encoding="utf-8")
    subprocess.Popen(cmd, cwd=ENGINE_DIR, stdout=out, stderr=err)
    return True


def liftoff_check(g: int) -> bool:
    """启动 LIFTOFF_S 秒后确认进程存活 + err 日志为空 + log 头正常。"""
    time.sleep(LIFTOFF_S)
    if not is_engine_running():
        log(f"[FAIL] gen{g} 进程未存活")
        return False
    err_p = os.path.join(ENGINE_DIR, f"loop{g}C_err.log")
    if os.path.exists(err_p) and os.path.getsize(err_p) > 0:
        log(f"[FAIL] gen{g} err 日志非空")
        return False
    log_p = os.path.join(ENGINE_DIR, f"loop{g}C.log")
    head = open(log_p, encoding="utf-8", errors="ignore").read(300).replace("\n", " | ")
    log(f"[OK] gen{g} 已启动，日志头: {head[:220]}")
    return True


def already_running() -> bool:
    """防多实例：已有一个 loop_watch 进程则本实例退出。"""
    ps = (
        'powershell -NoProfile -Command "Get-CimInstance Win32_Process '
        "-Filter \\\"Name like 'python%'\\\" "
        "| Where-Object { $_.CommandLine -match 'loop_watch' } "
        '| Measure-Object | Select-Object -ExpandProperty Count"'
    )
    try:
        out = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=60)
        n = int((out.stdout or "").strip())
        return n > 1   # 含本进程自身
    except Exception:
        return False   # 查不到不阻塞（宁可多轮询也不停摆）


def main():
    if already_running():
        # 本进程刚启动可能还没被 WMI 统计到，退让一次
        time.sleep(10)
        if already_running():
            log("检测到已有 watcher 实例，本实例退出")
            return
    log("==== watcher 启动 ====")
    quiet_skips = 0
    while True:
        if is_engine_running():
            quiet_skips += 1
            if quiet_skips % 12 == 1:   # 约每小时报一次
                log(f"[RUN] 引擎运行中，继续等待 (第{quiet_skips}次轮询)")
            time.sleep(POLL_S)
            continue
        quiet_skips = 0
        N = latest_done_gen()
        if N is None:
            log("[WAIT] journal 未找到已完成代数，等待")
            time.sleep(POLL_S)
            continue
        if err_nonempty(N):
            log(f"[STOP] gen{N} err 日志非空，按铁律停止等人工")
            break
        if N >= TARGET_GEN:
            log(f"[DONE] 已达成 gen{N} >= {TARGET_GEN}，目标完成")
            break
        g = N + 1
        if start_next_gen(g):
            if not liftoff_check(g):
                log(f"[STOP] gen{g} 升空检查失败，停止等人工")
                break
        # 启动成功后回到循环顶部确认进程在跑
    log("==== watcher 退出 ====")


if __name__ == "__main__":
    main()
