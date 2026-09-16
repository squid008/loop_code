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

★ 三池并行挖掘(2026-09-12, roadmap §8.19): 加 `--pool=300|500` 即驱动对应池的**独立轨迹**
  (journal/日志名加 `_<池>` 后缀、启动引擎时透传 `--mine_pool`、进程探测按池区分)。
  三条轨迹**完全独立**, 可同时开三个 watcher(注意内存), 也可串行跑(见 ai_test/run_3pools.ps1)。
  例: D:\\miniconda3\\envs\\rqdata\\python.exe D:\\loop_code\\engine\\loop_watch.py --pool=300
  不带 --pool 时 = 'all'(全A轨迹, **完全向后兼容**原行为)。
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# ★ 2026-09-15：原为硬编码仓库路径 + 写死的解释器路径 ⇒ 换机器即崩 ✗
#   ① 本文件就在 `engine/` 里 ⇒ `HERE` 即 engine 目录 ✓
#   ② `PY` 改用 `sys.executable` = **当前正在跑的解释器**（比写死路径更正确）✓
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = HERE
DOCS_DIR = os.path.join(os.path.dirname(HERE), "docs")
PY = sys.executable
WATCH_LOG = os.path.join(ENGINE_DIR, "loop_watcher.log")
POLL_S = 300          # 主轮询间隔
LIFTOFF_S = 20        # 启动后确认存活间隔
TARGET_GEN = int(os.environ.get("LOOP_TARGET_GEN", "70"))   # 目标代数(达此代即停)

# ---- 三池并行挖掘(2026-09-12, roadmap §8.19) -----------------------------------
# 非 all 时: ①journal / 日志文件名全部加 `_<池>` 后缀(否则三条轨迹**同名碰撞**, 互相覆盖);
#            ②启动引擎时透传 --mine_pool; ③进程探测按池区分(否则三条 watch 互相误判)。
_POOL = "all"
for _a in sys.argv[1:]:
    if _a.startswith("--pool="):
        _POOL = _a.split("=", 1)[1].strip() or "all"
    elif not _a.startswith("-"):
        _POOL = _a.strip() or "all"
_POOL = os.environ.get("LOOP_MINE_POOL", _POOL).strip() or "all"
SFX = "" if _POOL == "all" else "_" + _POOL
POOL_ARG = [] if _POOL == "all" else [f"--mine_pool={_POOL}"]

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
    """WMI 查 loop_engine 进程。查不到时保守返回 True（宁可不启也不重复启）。

    池轨迹下只认**本池**的引擎(命令含 `--mine_pool=<池>`); all 轨迹只认**不带**该参数的引擎
    —— 否则三条轨迹会互相误判(一个在跑就都不启动 / 或不带池的会撞进池轨迹)。
    """
    if _POOL == "all":
        cond = ("($_.CommandLine -match 'loop_engine') "
                "-and ($_.CommandLine -notmatch '--mine_pool=(?!all)')")
    else:
        cond = (f"($_.CommandLine -match 'loop_engine') "
                f"-and ($_.CommandLine -match '--mine_pool={_POOL}')")
    ps = (
        'powershell -NoProfile -Command "Get-CimInstance Win32_Process '
        "-Filter \\\"Name like 'python%'\\\" "
        f"| Where-Object {{ {cond} }} "
        '| Measure-Object | Select-Object -ExpandProperty Count"'
    )
    try:
        out = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=60,
                             creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                                            if os.name == 'nt' else 0))
        n = int((out.stdout or "").strip())
        return n > 0
    except Exception as e:
        log(f"[WARN] is_engine_running 异常({e})，保守视为运行中")
        return True


def log_paths(g: int):
    """本池轨迹的 (log, err) 路径。加 SFX 防三条轨迹同名互相覆盖(§8.19)。"""
    return (os.path.join(ENGINE_DIR, f"loop{g}C{SFX}.log"),
            os.path.join(ENGINE_DIR, f"loop{g}C{SFX}_err.log"))


def latest_done_gen():
    """读**本池** journal 找已完成代数 N（标题行 '## 第 N 代'），返回最大 N；无则 None。"""
    jp = os.path.join(DOCS_DIR, f"loop_journal{SFX}.md")
    if not os.path.exists(jp):
        return None
    text = open(jp, encoding="utf-8", errors="ignore").read()
    gens = [int(m) for m in re.findall(r"^##\s*第\s*(\d+)\s*代", text, re.M)]
    return max(gens) if gens else None


def err_nonempty(gen: int) -> bool:
    _, p = log_paths(gen)
    return os.path.exists(p) and os.path.getsize(p) > 0


def start_next_gen(g: int) -> bool:
    log_p, err_p = log_paths(g)
    if os.path.exists(log_p):
        log(f"[SKIP] {os.path.basename(log_p)} 已存在，疑似重复代，不启动")
        return False
    seed = g * 10 + 7
    # 附加参数透传(2026-09-11): 便于无人值守时启用批1 新开关而不改代码
    #   例: set LOOP_EXTRA_ARGS=--min_mono=0.75 --score_mode=new
    extra = (os.environ.get('LOOP_EXTRA_ARGS') or '').split()
    cmd = [PY, "-u", "loop_engine.py", f"--gen={g}", "--n=800", "--l2=30",
           f"--seed={seed}"] + POOL_ARG + extra
    if _POOL != "all":
        log(f"[POOL] 本 watcher 只驱动 **{_POOL}** 池轨迹(--mine_pool={_POOL})")
    if extra:
        log(f"[ARGS] 附加参数: {' '.join(extra)}")
    log(f"[START] gen{g} seed={seed}")
    out = open(log_p, "w", encoding="utf-8")
    err = open(err_p, "w", encoding="utf-8")
    # ★ 2026-09-16：隐藏控制台（否则会被 Windows 新建一个黑窗；用户要求"后台静默启动"）
    subprocess.Popen(cmd, cwd=ENGINE_DIR, stdout=out, stderr=err,
                     creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                                    if os.name == 'nt' else 0))
    return True


def liftoff_check(g: int) -> bool:
    """启动 LIFTOFF_S 秒后确认进程存活 + err 日志为空 + log 头正常。"""
    time.sleep(LIFTOFF_S)
    if not is_engine_running():
        log(f"[FAIL] gen{g} 进程未存活")
        return False
    log_p, err_p = log_paths(g)
    if os.path.exists(err_p) and os.path.getsize(err_p) > 0:
        log(f"[FAIL] gen{g} err 日志非空")
        return False
    head = open(log_p, encoding="utf-8", errors="ignore").read(300).replace("\n", " | ")
    log(f"[OK] gen{g} 已启动，日志头: {head[:220]}")
    return True


def already_running() -> bool:
    """防多实例：**同一个池**已有一个 loop_watch 进程则本实例退出。

    ★ 必须按池区分 —— 否则 300 轨迹的 watcher 会把 500 轨迹的当成自己、直接退出(静默停摆)。
    """
    if _POOL == "all":
        cond = ("($_.CommandLine -match 'loop_watch') "
                "-and ($_.CommandLine -notmatch '--pool=(?!all)')")
    else:
        cond = (f"($_.CommandLine -match 'loop_watch') "
                f"-and ($_.CommandLine -match '--pool={_POOL}')")
    ps = (
        'powershell -NoProfile -Command "Get-CimInstance Win32_Process '
        "-Filter \\\"Name like 'python%'\\\" "
        f"| Where-Object {{ {cond} }} "
        '| Measure-Object | Select-Object -ExpandProperty Count"'
    )
    try:
        out = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=60,
                             creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                                            if os.name == 'nt' else 0))
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
    log(f"==== watcher 启动 (池={_POOL}{' / 后缀=' + SFX if SFX else ''}) ====")
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
