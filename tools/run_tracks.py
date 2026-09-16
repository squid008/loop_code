# -*- coding: utf-8 -*-
"""run_tracks.py -- 多池轨道的**串行**驱动器（Python 版，替代 run_3pools.ps1；roadmap §8.41）

为什么换成 Python（2026-09-13）：
  `run_3pools.ps1` 有两个问题：
   ① **代数不读 journal** —— 代码是 `$gen = $StartGen + $i`（注释却写着"从本池 journal 读"）
      ⇒ 池已有 gen1-5 时会**重跑 gen1**（浪费整代，journal 里代数还混在一起）。
   ② .ps1 里写中文有编码风险（PS 5.1 按 GBK 读无 BOM 文件），且内联引号易错。
  ⇒ 改 Python：**自动续代数**（读本池 journal 取 max+1）+ 无编码/引号问题 + 可断点续跑。

⚠ 成本提示（2026-09-13 实测推算）：每轮 = L1 + L2；其中 L2 因 `--pool_obs --pools=300,500,1000`
   + `--strip_style` ⇒ **每候选 5 次回测**（主口径/剥风格/300/500/1000）⇒ L2 约占 50min/轮。
   L1 随池并集列数走：300≈925 列、500≈1776、**1000≈2818**（最贵）。
   ⇒ 单池单轮 ≈ 60~80min；**3 池 × 3 轮 ≈ 10 小时**。默认**不含 all**
   （all 已有 41 个入库、且不是瓶颈；要跑就把它加进 --pools）。

用法:
  python tools/run_tracks.py                      # 默认 300,500,1000 × 3 轮
  python tools/run_tracks.py --pools=300,500,1000,all --rounds=1
  python tools/run_tracks.py --dry                # 只打印"将跑哪些代"，不执行
  python tools/run_tracks.py --pools=all --inject_pools=300,500,1000   # 显式指定注入
  python tools/run_tracks.py --pools=all --inject_pools=none           # 关掉注入

 ★★ `--no_global`（2026-09-16 新增）：**跳过一轮结束后的"全局收尾"**。
    收尾两项（`build_facs.py --only-new` + `cross_pool_review.py`）是**全局动作** ——
    尤其跨池审查必须"看全所有池"才能去重（见下方 L332 注释）⇒
    **池驱动一律加 `--no_global`**（看板「每池独立启停」就是这么调的）✓
    全局收尾由**单独一次**调用完成：`python tools/run_tracks.py --pools=300 --rounds=0`
    （`--rounds=0` ⇒ 一轮都不跑、直接进收尾；看板上的「收尾审查」按钮即调它）✓
    ⚠ 不加它的后果：5 个池各跑一次收尾 ⇒ **重复 5 倍 + 并发写同一份
      `factor_library_crosspool.md` / `factor_pool_selected.md` ⇒ 互相覆盖** ✗✗

★★ `--inject_pools`（2026-09-14, loop_todo §1.8）：给 `all` 轨道**注入池库作对照集**。
   默认（不传）= **自动给 `all` 注入本次要跑的其它池**；池轨道**不注入**（理由见 `inject_for`）。
   为什么：`--decorr`/`--dup_ex_corr` 的对照集原本只是本轨道自己的 bank ⇒ 跑全A 时不知道
   池库挖到了什么 ⇒ 重挖（实测池因子 vs 全A 库 收益流最大 |相关| **中位 0.767**、>0.7 占 82%，
   而 `--dup_ex_corr=0.90` 只挡得住 18%）。
   ⚠ 外部池库只作**对照** —— **不会**写回本轨道的 state / `docs/factor_library*.md`。

   ★ 亲本选择策略（2026-09-14, loop_todo §1.3-C）也走 `--extra=` 透传，**无需本文件加参数**：
    python tools/run_tracks.py --pools=1000 --rounds=3 \
           --extra=--parent_sel=top_percent_plus_random
    # 引擎侧：--parent_sel {uniform|best|top_percent_plus_random}（默认 uniform = 行为不变）
    #        --parent_top_pct（默认 0.30）
    # ⚠ 换策略 = **换搜索行为** ⇒ A/B 对比时同池同轮数、只有这一个参数不同。
   """
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(ROOT, 'engine')
DOCS = os.path.join(ROOT, 'docs')
LOGD = os.path.join(ROOT, 'ai_test', '_tracks')
PY = sys.executable

# ★★★ 2026-09-16：**所有子进程都不许弹黑窗**（用户要求「启动不要开 python 窗口，审查之类的都后台静默」）。
#
# 为什么会弹窗（Windows 经典陷阱）：
#   看板后端用 `DETACHED_PROCESS` 起本调度器 ⇒ **本进程没有控制台**；
#   此时若再用 `subprocess.run(...)` **不指定** `CREATE_NO_WINDOW` 起子进程，
#   Windows 会给这个 **控制台程序新建一个控制台窗口** ✗✗
#   ⇒ 表现：点「一键启动全部」弹一个黑窗、每代再弹一个、收尾审查还弹 ✗
# ⇒ 修法：**所有** `subprocess` 调用统一带 `NO_WIN` ✓
#   （已核实：`build_facs.py` / `cross_pool_review.py` / `engine/loop_engine.py`
#     **都不再 spawn 子进程** ⇒ 只需这一层，不会漏孙子进程 ✓）
NO_WIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if os.name == 'nt' else 0

MY_LOG = os.path.join(LOGD, '_driver.log')


def log(m):
    line = "{} {}".format(datetime.now().strftime('%m-%d %H:%M:%S'), m)
    print(line, flush=True)
    os.makedirs(LOGD, exist_ok=True)
    with io.open(MY_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def journal_of(pool):
    sfx = '' if pool == 'all' else '_' + pool
    return os.path.join(DOCS, 'loop_journal{}.md'.format(sfx))


def read_log(path):
    """宽容读日志（utf-8 -> gbk 逐个试）。

    ⚠ 2026-09-13 实录：`subprocess.run(stdout=<文本文件对象>)` 只把**底层 fd** 传给子进程，
      子进程按**自己的**编码写（Windows 下 cp936/GBK）⇒ 父进程按 utf-8 解读会得到**乱码**，
      连 `L1 批 x/y` 都解析不出来。修法：给子进程设 `PYTHONIOENCODING=utf-8`（本文件已设），
      读取端再用本函数兜底（历史日志仍是 GBK）。
    """
    if not os.path.exists(path):
        return ''
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


def next_gen(pool):
    """从**本池** journal 读已完成的最大代数 -> 下一个代数（无 journal 则从 1 开始）。"""
    jf = journal_of(pool)
    if not os.path.exists(jf):
        return 1, 0
    txt = io.open(jf, encoding='utf-8', errors='replace').read()
    gens = [int(m) for m in re.findall(r'^##\s*第\s*(\d+)\s*代', txt, re.M)]
    return ((max(gens) + 1) if gens else 1), (max(gens) if gens else 0)


def inject_for(pool, pools, spec):
    """该轨道要注入哪些**其它池**的库作对照集（2026-09-14, `loop_todo §1.8`）。

    :param spec: `--inject_pools=` 的值
        · `''`（默认）⇒ **自动**：只给 `all` 轨道注入"本次要跑的其它池"；池轨道不注入
        · `'none'`     ⇒ 全关（行为回到注入功能之前）
        · `'300,500'`  ⇒ 显式指定（对所有轨道都用这套，自动去掉自己）

    ★★ 为什么**默认只给 `all` 轨道注入**（不对称是刻意的）：
      - `all` 轨道的痛点是"**重挖池库**"（实测收益流 |相关| 中位 0.767、>0.7 占 82%）⇒ 必须注入；
      - **池轨道的产出不是"新因子"，而是"有效域标签"** —— 同一个式子（或已被全A 库
        高相关因子覆盖的式子）全A 库可能早就有了，池轨道真正的新增信息是
        「它在 300/500/1000 上分别有没有效」。
      ⇒ 若给池轨道也注入全A 库，那些"已存在但没打过池标签"的式子会被**对照集挡在门外**
        ⇒ **池轨道就没产出了** ✗（把它的唯一价值掐掉）
      ⇒ 所以：**只给 all 注入**。
    """
    if spec.strip().lower() == 'none':
        return []
    if spec.strip():
        return [x.strip() for x in spec.split(',') if x.strip() and x.strip() != pool]
    if pool != 'all':
        return []
    return [x for x in pools if x != 'all']


def _ltime():
    return datetime.now().strftime('%m-%d %H:%M:%S')


# ============================================================================================
# ★★★★★ 2026-09-16 v1.3.0：**单调度器 + 池轮转**（用户拍板）
#
# 用户决策（原话）：「1、走 2；2、立即停不影响其他池挖掘审查吧？ 3、每轮结束自动收尾。
#   4、有个问题，如果一轮中间我停了一个池子，它是不是就不能收尾了？我觉得应该也要能收尾。
#   启停任意池子都不能影响收尾这个不冲突吧？然后一键全部停掉后，它就自动进入收尾阶段」
#
# ## 为什么改（**内存**，用户质疑"四个池四份内存不科学"—— 实测他是对的）
#   · 只读大对象 `B`（49 个 float32 字段，3309×5384）≈ **3.25 GB** ⇒ 每个池进程**各一份** ✗
#   · 单引擎峰值 ≈ 6 GB ⇒ 5 个池 = **30 GB** > 可用 **27 GB** ⇒ **根本跑不起来** ✗
#   · ★★ 但**每个池只是它列子集**（`set_mine_pool` 原话「L1 子面板列 = 该池并集」）
#     ⇒ **同一时刻只跑 1 个引擎** ⇒ 内存 **~6 GB**（省 5 倍）✓
#   · CPU 只有 6 核/12 线程而单引擎已吃满多核 ⇒ **并行本来就会被互相拖慢 ⇒ 损失≈0** ✓
#
# ## 新调度（**交换两层循环** —— 原来是"每池连跑 N 代"，现在是"每轮每池各 1 代"）
#     for r in 1..N:                     # ← 外：轮次
#         for pool in 启用池:            # ← 内：池轮转（★ 可单独跳过/停止）
#             跑该池 1 代                 #     spawn 引擎，跑完退出（一代一进程，原本如此）
#         ★ 一轮结束 ⇒ **自动收尾**       # ← 用户要求 3
#     ★ 收到"全部停" ⇒ 跳出 ⇒ **自动收尾** # ← 用户要求 4
#
# ## 为什么"停一个池"不会让收尾落空（用户问的第 4 点）
#   收尾的触发条件是「**没有任何池在跑**」+「**本轮有过真实进展**」，
#   而**不是**「所有池都跑完 N 轮」✗ ⇒ 被停的池只是"不参与轮转"，**绝不会阻塞收尾** ✓
#
# ## "立即停"为什么安全（已核实，不是想当然）
#   · 池间**文件隔离**（`set_mine_pool` 把 7 个路径全按池派生）⇒ **不会影响别的池** ✓
#   · 引擎落盘是「**原子写 + 代末**」——
#     `loop_engine.py:1709` 注释明写：`open(STATE,'wb')` 被改成了 `.tmp` + `os.replace`，
#     「一旦 dump 中途异常（**或进程被杀**）就得到 0 字节坏状态」⇒ 已加固 ✓
#     ⇒ 所以杀掉"当前那一代"= 该代整体作废、旧状态完好、下次重跑 ✓
# ============================================================================================
CTL_FILE = os.path.join(LOGD, '_control.json')

CTL_DEFAULT = {'running': False, 'enabled': [], 'stopped': [], 'stopAll': False,
               'rounds': 0, 'round': 0, 'curPool': None, 'curGen': None,
               'phase': 'idle', 'tailAt': None, 'updated': None}


def read_ctl():
    """读控制文件。缺失/损坏 ⇒ 返回安全默认（**全启用、不停止**）。"""
    d = dict(CTL_DEFAULT)
    try:
        with io.open(CTL_FILE, encoding='utf-8') as f:
            d.update(json.load(f) or {})
    except Exception:
        pass
    return d


def write_ctl(**kw):
    """★ 合并式更新控制文件（其他键保持不动）—— 前端/调度器**并发读写**时更安全。"""
    d = read_ctl()
    d.update(kw)
    d['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        os.makedirs(LOGD, exist_ok=True)
        tmp = CTL_FILE + '.tmp'
        with io.open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CTL_FILE)          # ★ 原子替换：前端读到的永远是完整 JSON ✓
    except Exception as e:
        log('[CTL] 写控制文件失败: {!r}'.format(e))
    return d


def do_global_tail(tag=''):
    """★ **全局收尾**：facs 落地 + 跨池审查 + 精选池。

    ⚠ 为什么必须"单独一次、无人并行"：跨池审查要做**跨池去重**，必须"看全所有池"才能做
      （见 `main()` 里原有注释）⇒ 5 个池各跑一次会重复 5 倍且并发写同一份产出 ✗
      ⇒ 在**轮转调度器**下天然满足（同一时刻只有 1 个引擎在跑）✓
    """
    log('')
    log('=' * 76)
    log('[收尾] ★ {}（facs 落地 → 跨池审查 → 精选池）'.format(tag or '全局收尾'))
    log('=' * 76)
    write_ctl(phase='tail', tailAt=_ltime())
    log('  [收尾 ①] 因子值落地到 facs/（新入库的必须落，否则审查看不到）')
    try:
        # ★ `--only-new`（增量落地）：52 个全就绪 ⇒ **4.0s**（全量 ~21min）✓
        r = subprocess.run([PY, '-u', 'tools/build_facs.py', '--only-new'],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=7200,
                           creationflags=NO_WIN)
        for ln in (r.stdout or '').splitlines()[-4:]:
            log('      ' + ln[:150])
        if r.returncode != 0:
            log('      [!] 落地非零退出={} -> 仍继续审查（用已有 facs/）'.format(r.returncode))
    except Exception as e:
        log('      [!] 落地失败({}) -> 仍继续审查'.format(type(e).__name__))
    log('  [收尾 ②] L2 跨池审查 + L3 精选池')
    try:
        r = subprocess.run([PY, '-u', 'tools/cross_pool_review.py'],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=3600,
                           creationflags=NO_WIN)
        for ln in (r.stdout or '').splitlines()[-10:]:
            log('      ' + ln[:150])
        if r.stderr and r.stderr.strip():
            log('      [stderr] ' + r.stderr.strip()[:300])
    except Exception as e:
        log('      [!] 审查失败({}: {})'.format(type(e).__name__, e))
    log('  ⇒ 精选池见 docs/factor_pool_selected.md（比"入库数"更接近"能用几个"）')
    log('=' * 76)
    # ★★ 2026-09-16 修 BUG E：收尾结束后**必须自己复位 phase** ——
    #   调用方（`main()`）的复位写在 `do_global_tail()` **之前** ⇒ 这里若不复位，
    #   控制文件就**永久停在 `phase='tail'`**（实测：收尾早已结束，看板仍显示"收尾审查中"）✗
    #   ⇒ 由**本函数**负责状态一致性更稳妥（谁设谁清）✓
    write_ctl(phase='idle', tailAt=None)


def main():
    pools = ['300', '500', '1000']
    rounds = 3
    n, l2 = 800, 30
    dry = False
    inject_spec = ''       # ★ §1.8：外部池库对照集注入（默认自动：只给 all 轨道）
    # ★★★ 2026-09-16 新增 `--no_global`：**跳过一轮结束后的「全局收尾」**。
    #   为什么需要（"看板每池独立启停"改造的前提）：
    #     · 收尾两项（`build_facs.py --only-new` / `cross_pool_review.py`）是**全局动作** ——
    #       尤其 `cross_pool_review` 要做**跨池去重**，它必须"看全所有池"才能做（见 L332-335 注释）
    #     · 一旦改成"**每池一个独立驱动进程**"（可单独启停），5 个池就会**各跑一次收尾**
    #       ⇒ ①**重复 5 倍**（`cross_pool_review` 单次要 ~5min）②**并发写同一份
    #          `factor_library_crosspool.md` / `factor_pool_selected.md` ⇒ 互相覆盖** ✗✗
    #     ⇒ 所以：**池驱动一律加 `--no_global`**；全局收尾由**单独一次**调用完成
    #       （看板「收尾审查」按钮 / 或 `run_tracks.py --pools=... --rounds=0`）✓
    no_global = False
    # ★★ 池内挖掘的**必要参数组**（2026-09-13 实测；不传 = 白跑一整夜）
    #   300/500 gen6~8 六代全部 `fail_calmar = 1.000`（**100%** 因全A Calmar 不足被砍），
    #   B角原话:「L2中100%因Calmar不足(信号弱)」。根因：我只传了 `--pool_obs`，
    #   引擎仍用**默认的全A 严格门槛**(`--min_calmar` 默认 0.5 量级) ⇒ 池内因子在池内
    #   再有效也**先被全A 门槛砍掉** ⇒ **池门槛(--min_pool_calmar)根本轮不到生效**。
    #   ⇒ 必须**解开全A 门槛**、把判定权交给**池门槛**(与 §8.26 验收轮同参数)。
    # ★★★ 剥风格门槛（2026-09-14 用户采纳；roadmap §8.45 / loop_todo §1.9）
    #   此前只传了 `--strip_style`（**开记录**）却**没传** `--min_strip_calmar`
    #   ⇒ 后者默认 `-1.0` ⇒ 引擎里 `if args.min_strip_calmar > 0 ...` 不成立
    #   ⇒ **只记录不拦** ⇒ 剥风格结果**从未参与入库判定**。
    #   实测后果（`python tools/check_strip_style_pool.py`）：**池库 7/14 = 50% 是"纯风格因子"**
    #   （剥掉 lncap+lnamt 后超额**转负**）—— 包括我先前误标为"质量最高"的
    #   `corr100(mf_s_bqty, mf_x_sell)`（原 Calmar 1.193 → 剥后 **−0.075**）。
    #   档位取 0.15 = 与 `--min_pool_calmar` 同档（口径一致）；实测**不会误伤**两个真独立有效的
    #   （剥后 0.349 / 0.667 都远高于 0.15），但会挡掉那个 `all3`（剥后仅 0.064）与 7 个纯风格。
    # ★★★ 十档单调性门槛（2026-09-15，用户拍板；`loop_todo §1.3-B` / roadmap §8.50）----
    #   为什么现在才开：这道门**早就建好、也标定过**（引擎 L1959），但 `--min_mono` 默认 `0.0`
    #   ⇒ **一直没生效**。本次用独立数据复核后确认可信：
    #     引擎注释（标定 **1150** 条）：「L2 通过者 mono 中位 0.964 / 最小 0.770；判死者中位 0.867
    #       ⇒ `mono >= 0.75` 可拦下 ~27% 判死候选且对 19 个入库因子**零误杀**」
    #     我复核（**独立 124 条**，`python tools/calib_gate.py --target=l1_l2 --eval "mono>=0.75"`）：
    #       **误杀正样本 0/6 = 0.0%** ✓ · **拦掉负样本 42/118 = 35.6%** ✓
    #   ⇒ **两次独立标定互相印证** ✓ 收益：**L2（全量面板费后回测，最贵的一环）成本降 ~27~36%**
    #     —— 实测 `n_l1=28 → n_l2=28 → n_pass=2`，L2 命中率仅 **4.8%** ⇒ 这里最值得省。
    #   ⚠ 阈值是**样本内**标定（正样本仅 6 个）⇒ 若发现"入库数骤降/连续多代 0 入库"，
    #     第一件事就是**回退这一项**（`--extra=...` 覆盖，见文件头用法）✓
    #   ⚠ 注意：`_min_mono` 是**L1 后、L2 前**的门 —— 引擎里 `if _min_mono > 0` 才生效，
    #     所以传 `0.75` 才真正开启（与"生成后 L1 前"无关，那个位置实测无判据可用）。
    # ══════════════════════════════════════════════════════════════════════════════════
    # ★★★ 2026-09-15 **已回退**（跑完 3 轮 9 代后实测，**用户拍板选 A**）----
    #   结论：`--min_mono=0.75` **既不省成本，也无证据改善选人** ⇒ 关掉，回基线。
    #
    #   【为什么不省成本 —— 而且是我标定时口径错了】
    #   实测（`ai_test/_check_run.py`）：L1 全量上确实拦掉 **72.3%**
    #     （如 `[形状门槛] 原 664 -> 剩 193`），**但「进 L2 的数」几乎没变**：
    #       300 池 gen12/13/14: 进L2 = 30, 30, 30   ← 仍顶格
    #       500 池 gen13/14:    进L2 = 21, 17
    #       1000 池 gen10/11:   进L2 = 25, 23
    #   ★ 根因：这道门在 **`head(TOPN)` 之前**，而 **L1 候选有 600~700 个（≫ `TOPN=30`）**
    #     ⇒ 筛掉 mono 低的之后**剩下的仍 ≥30 个** ⇒ **top-N 照样填满** ⇒ **L2 数量不变** ✗
    #   ⚠ **我的错**：标定时我是在「**已进 top-N 的 30 个**」上算拦获（27~36%），
    #     而实际门作用在「**L1 全量 ~700 个**」上 ⇒ **口径不同，高估了省成本的效果** ✗
    #   ★ 正确说法：这道门的作用是「**换人**」（改变谁进 L2），**不是「省成本」**。
    #
    #   【选人是否变好 —— 无证据，信号偏负面】
    #   全局（`ai_test/_ab_mono.py`）：无 mono 21 代入库 **0.67 个/代** ->
    #                                 有 mono  9 代入库 **0.11 个/代**（约 1/6）
    #   分池：300: 1/6代 -> 0/3代 · 500: 3/6代 -> 0/3代 · 1000: 10/9代 -> 1/3代
    #   ⚠ 但**不能定因果**：① 样本仅 9 代 ② **最公平的对照是 1000 池** ——
    #     无 mono 的 gen7/8/9 = 1/0/0（**已降到 0.33 个/代**）vs 有 mono 的 gen10/11 = 0/1
    #     （**0.50 个/代**）⇒ **其实没降** ⇒ 300/500 池的"下降"更可能是**自然边际递减**
    #     （它们都已 11 代）✓
    #
    #   ⇒ **决策原则：没有可证实的收益 + 有风险信号 ⇒ 不该开** ✓
    #   ⇒ 关掉后接下来的 47 轮 = **A/B 的后半段**（有 mono 9 代 vs 无 mono 47 代），趋势可比 ✓
    #   ⇒ 若将来要重开，**必须先修标定口径**（在"L1 全量"上算，而不是"top-N 30 个"上）⚠
    # ══════════════════════════════════════════════════════════════════════════════════
    # ★★★ 2026-09-15（v0.20.2）补上 `--style_obs` —— 这是**长期遗漏，不是有意权衡** ✓
    #   ① **成本≈0（代码级证据）**：`loop_engine.py:2051-2063`
    #        `style_features(B)` 是**一代只算一次**的贵函数，而 `--strip_style`（**早已在生产开**）
    #        已经触发了它 ⇒ `if _style_obs or _shape_neutral or _strip_style: _sf = style_features(B)`
    #        ⇒ 加 `--style_obs` 的**增量**只是：一代一次的 4 个 `rank_rows` + 一次 `neutralize_rows`
    #          + 每候选几个廉价相关 —— **无任何额外回测** ✓
    #      ⚠ 别被 `docs/log/2026-09.md:1246` 的"每候选 +1 次回测"误导 —— 那是 **`--strip_style`** 的
    #        开销（§8.14 那张表），同一行只说 `style_features` 与 `--style_obs` **共用（一代一次）** ✗
    #   ② **用途仍必需**：生产参数含 `--score_mode=new`（下一行）⇒ 而 `--style_obs` 是**唯一**
    #        能验证"new 排序分是否让因子更往低换手/低成交额挤"的观测手段 ✓
    #   ③ ★★ **它补的是一个已知盲区**（`loop_todo` §1.24-①）：
    #        我们"剥风格"**只剥 2 个**（`lncap`+`lnamt`），而 `--style_obs` 记录 **4 个**
    #        （+`lntr` 换手率 / `lnpx` 价格）⇒ **`lntr`/`lnpx` 一直看不见** ✗
    #        实证代价：`F07` 号称"最独立"（剥两风格后 Cal 1.209 > 原 0.812），
    #        但它 **`lntr` 暴露 −0.51（很强）** ⇒ "独立有效"的准确含义只是"剥掉市值+成交额后仍有效"️
    #   ④ 状态污染**不构成问题**：它跑的是真实一代、会改 `loop_state.pkl`，但生产轨道本来就在真跑
    #        （`--strip_style` 同样改），且多池已各自有独立 state 文件 ✓
    #   ⇒ 结论：**开着它 = 几乎零成本地补上一个已知盲区** ✓
    extra = ['--pool_obs', '--pools=300,500,1000', '--strip_style', '--style_obs',
             '--dup_ex_corr=0.90',
             '--min_calmar=0.0', '--min_ic=-1', '--score_mode=new',
             '--min_pool_calmar=0.15', '--pool_gate_or_all',
             '--min_strip_calmar=0.15']
    for a in sys.argv[1:]:
        if a.startswith('--pools='):
            pools = [x.strip() for x in a.split('=', 1)[1].split(',') if x.strip()]
        elif a.startswith('--rounds='):
            rounds = int(a.split('=', 1)[1])
        elif a.startswith('--n='):
            n = int(a.split('=', 1)[1])
        elif a.startswith('--l2='):
            l2 = int(a.split('=', 1)[1])
        elif a.startswith('--inject_pools='):
            inject_spec = a.split('=', 1)[1].strip()
        elif a == '--dry':
            dry = True
        elif a == '--no_global':
            no_global = True
        elif a.startswith('--extra='):
            extra = [x for x in a.split('=', 1)[1].split() if x]

    log('=' * 76)
    log('多池轨道驱动: 池={}  每池 {} 轮  n={} l2={}  dry={}'.format(pools, rounds, n, l2, dry))
    log('透传引擎参数: {}'.format(' '.join(extra)))
    plan = []
    for p in pools:
        g0, done = next_gen(p)
        plan.append((p, g0, done))
        _inj = inject_for(p, pools, inject_spec)
        log('  [PLAN] pool={:<5s} 既有 {} 代 -> 从第 {} 代起跑 {} 轮{}'.format(
            p, done, g0, rounds,
            ('   [注入对照集] {}'.format(','.join(_inj)) if _inj else '')))
    _n_all = sum(1 for p, _, _ in plan if inject_for(p, pools, inject_spec))
    if _n_all:
        log('  ★ 注入外部池库对照集（loop_todo §1.8）：为什么 —— `--decorr`/`--dup_ex_corr` '
            '的对照集原本只是本轨道自己的 bank')
        log('     ⇒ 跑全A 时**不知道池库挖到了什么** ⇒ 重挖。实测池因子 vs 全A 库 的收益流最大 |相关| '
            '**中位 0.767**、>0.7 占 82%，而 --dup_ex_corr=0.90 只挡得住 18%')
        log('     ⇒ 不注入 ≈ **把 82% 的算力花在重挖上**。语义：外部池库只作**对照**，'
            '**不会**写回本轨道的 state/因子库。')
        log('     ⚠ 只给 `all` 轨道注入（池轨道的价值是"给式子打池内标签"，注入全A 库会让它无产出）；'
            '`--inject_pools=none` 可关。')
    log('=' * 76)
    if dry:
        log('（--dry：只列计划，不执行）')
        return 0

    # ★★★ v1.3.0：改为**池轮转**（外循环轮次、内循环池）。原来"每池连跑 N 代"会让
    #   先跑的池吃掉全部时间（实测 9.3 小时里 300 独占、500/1000/50 一代没跑 ✗）。
    #   ★ 代数**每代现取**（`next_gen(p)` 读 journal）—— journal 是**唯一事实源**，
    #     比维护内存字典更健壮（进程重启/被杀后自动续上）✓
    write_ctl(running=True, round=0, rounds=rounds, phase='mine',
              enabled=[p for p, _, _ in plan] or pools, curPool=None, curGen=None)
    dirty = False                # ★ 有没有“未被收尾覆盖过的新进展”
    stopped_by_user = False
    for rnd in range(1, rounds + 1):
        ctl = read_ctl()
        if ctl.get('stopAll'):
            log('[CTL] ★ 收到「全部停止」⇒ 结束轮转（随后自动收尾）')
            stopped_by_user = True
            break
        en = set(ctl.get('enabled') or [p for p, _, _ in plan])
        st = set(ctl.get('stopped') or [])
        if not en:
            log('[CTL] 启用池为空 ⇒ 无池可跑，结束轮转')
            break
        log('')
        log('#' * 76)
        log('## 第 {} / {} 轮   启用池={}   本轮停={}'.format(rnd, rounds, sorted(en), sorted(st) or '无'))
        log('#' * 76)
        ran_round = False
        for p, g0, done in plan:
            ctl2 = read_ctl()
            if ctl2.get('stopAll'):
                log('[CTL] ★ 收到「全部停止」⇒ 中断本轮（随后自动收尾）')
                stopped_by_user = True
                break
            if p not in en:
                log('[SKIP] pool={:<5s} 不在启用集合 ⇒ 本轮跳过'.format(p))
                continue
            if p in set(ctl2.get('stopped') or []):
                log('[SKIP] pool={:<5s} 已被单独停止 ⇒ 本轮跳过（不影响其他池）'.format(p))
                continue
            g0, done = next_gen(p)             # ★ 每代现取（journal 为唯一事实源）
            gen = g0
            sfx = '' if p == 'all' else '_' + p
            seed = gen * 10 + 7
            logf = os.path.join(LOGD, 'pool{}_gen{}.log'.format(sfx, gen))
            errf = os.path.join(LOGD, 'pool{}_gen{}_err.log'.format(sfx, gen))
            write_ctl(round=rnd, curPool=p, curGen=gen, phase='mine')
            cmd = [PY, '-u', 'engine/loop_engine.py', '--gen={}'.format(gen),
                   '--n={}'.format(n), '--l2={}'.format(l2), '--seed={}'.format(seed)] + extra
            # ★ 2026-09-14（loop_todo §1.8）：给 `all` 轨道注入池库作对照集（避免重挖）。
            _inj = inject_for(p, pools, inject_spec)
            if _inj:
                cmd.append('--inject_pools={}'.format(','.join(_inj)))
            # ★★★ 2026-09-16 修 BUG G：**所有池都显式传 `--mine_pool`（含 `all`）**。
            #   ⚠ 原来 `if p != 'all'` 才传 ⇒ **`all` 的引擎命令行里没有 `--mine_pool`** ✗
            #     ⇒ 看板**无法把该进程归属到 `all`**（`classify_proc` 解析不到）
            #     ⇒ 后果（用户实测）：
            #       ① 点「停止本池(all)」⇒ `engine_of('all')` 返回空 ⇒ **杀不掉它的引擎** ✗
            #       ② 该引擎当时还带着 `--inject_pools=300,500,1000,50`
            #          ⇒ 被旧正则**误认成"在跑 4 个池"**（BUG H，已在 `pools.py` 修）
            #   ⇒ 修：统一传参。`set_mine_pool('all')` 是**幂等**的（等于不动）⇒ 行为不变 ✓
            cmd.append('--mine_pool={}'.format(p))
            log('[START] pool={} gen={} seed={} -> {}'.format(
                p, gen, seed, os.path.basename(logf)))
            t0 = time.time()
            # ⚠ 必须给子进程设 PYTHONIOENCODING=utf-8（2026-09-13 实录）：
            #   `subprocess.run(stdout=<文本文件对象>)` 只把**底层 fd** 传给子进程，
            #   子进程按**自己的**编码写（Windows 下 cp936/GBK），而这里按 utf-8 解读
            #   ⇒ **日志里中文全成乱码**，连 `L1 批 x/y` 都解析不出来（进度/ETA 全失效）。
            _env = dict(os.environ)
            _env['PYTHONIOENCODING'] = 'utf-8'
            with io.open(logf, 'w', encoding='utf-8') as o, \
                    io.open(errf, 'w', encoding='utf-8') as e:
                pr = subprocess.run(cmd, cwd=ROOT, stdout=o, stderr=e, env=_env,
                                    creationflags=NO_WIN)
            mins = (time.time() - t0) / 60.0
            errsz = os.path.getsize(errf) if os.path.exists(errf) else 0
            log('[END]   pool={} gen={} 退出码={} 耗时={:.1f}min err={}B'.format(
                p, gen, pr.returncode, mins, errsz))
            # 摘结果 + ★ 守卫：若"全部因同一个门被砍"，这是**配置问题**的强信号，必须吼出来
            try:
                txt = read_log(logf)
                for pat in (r'入库 \d+ 个新因子[^\n]*', r'L2 通过 \d+/\d+ 个[^\n]*',
                            r'保存状态: [^\n]*'):
                    mm = re.findall(pat, txt)
                    if mm:
                        log('        ' + mm[-1][:150])
                # 守卫 ①：**直接核验驱动器真正传了"池内判定"那组参数**（2026-09-14 重写）
                #   ⚠ 原判据是「`fail_calmar` > 0.9 且 L2 通过 0/x」—— 但 `fail_calmar`
                #     当时**恒为 1.000**（硬编码 0.5 + 全A 口径的传感器失真，已在 §1.1 修好）
                #     ⇒ 轨道跑完时**必然误报**：实测 09-14 03:32 那条 GUARD，
                #       而当时参数其实**传全了**（`--min_calmar=0.0 --pool_gate_or_all` 都在）。
                #   ★★ 教训：**用不可靠的量当报警判据 ⇒ 必然误报**，
                #     "狼来了"会让真警报被忽略（比不报警更糟）。
                #   ⇒ 改为检查**命令里有没有那组 flag** —— 这是可信、可证伪的事实。
                fc = re.findall(r'fail_calmar\s+([\d.]+)', txt)
                pass0 = re.findall(r'L2 通过 0/(\d+)', txt)
                _need = ['--pool_obs', '--min_pool_calmar', '--pool_gate_or_all']
                _miss = [f for f in _need if not any(x.startswith(f) for x in cmd)]
                if _miss:
                    log('        [!][GUARD] 本池**漏传**池内判定的必要参数: {} ⇒ '
                        '池门槛不会生效（池内因子会先被全A 门槛砍掉）'.format(', '.join(_miss)))
                # 守卫 ②（辅助信号，**已修好对账后才可信**）：全A 与池口径**都** >90% 失败
                #   ⇒ 更可能是"这批候选真的弱"，而不是配置问题（给人工判读一个提示）
                _fpc = re.findall(r'fail_pool_calmar\s+([\d.]+)', txt)
                if pass0 and fc and _fpc and float(fc[-1]) > 0.9 and float(_fpc[-1]) > 0.9:
                    log('        [note] L2 通过 0/{}，且**对账后**的全A({})与池口径({})失败率均 >90% '
                        '⇒ 更像"候选真的弱"，而非配置问题'.format(pass0[-1], fc[-1], _fpc[-1]))
                # 守卫 ②：真的一个都没入库，连代次数都数出来，便于判断"是配置还是候选真的不行"
                if re.search(r'入库 0 个新因子', txt):
                    log('        [note] 本代入库 0（若连续多代如此，先看 fail_* 分布再下结论）')
            except Exception:
                pass
            if pr.returncode != 0 or errsz > 0:
                _c3 = read_ctl()
                _killed = bool(_c3.get('stopAll')) or (p in set(_c3.get('stopped') or []))
                log('[!] pool={} 本代非正常结束{} -> **只跳过本池本轮**（不影响其他池）。人工看 {}'.format(
                    p, '（★ 被用户停止，该代作废下次重跑）' if _killed else '（疑似崩溃）',
                    os.path.basename(errf)))
                continue                      # ★★ 原为 `break`（会中断整个池循环）⇒ 改 `continue` ✓
            ran_round = True
            dirty = True
        # ★★ 一轮结束 ⇒ **自动收尾**（用户要求 3：「每轮结束自动收尾」）
        if stopped_by_user:
            break
        if ran_round and not dry and not no_global:
            do_global_tail('第 {} / {} 轮结束'.format(rnd, rounds))
            dirty = False
    log('===== 全部轨道结束 =====')
    # ★★ 因"全部停"退出、且还有未被收尾覆盖的进展 ⇒ **自动收尾**
    #    （用户要求 4：「一键全部停掉后，它就自动进入收尾阶段」）
    if stopped_by_user and dirty and not dry and not no_global:
        do_global_tail('★ 全部停止后')
        dirty = False
    # ★★ 退出前**清掉 `stopAll`**（2026-09-16 修 BUG C）：
    #   残留的 `stopAll=true` 会让**下一次启动立刻又退出**（读到"全部停"）✗
    #   ⇒ 必须由"读到它的人"（本调度器）负责清掉 ✓
    write_ctl(running=False, phase='idle', curPool=None, curGen=None,
              stopAll=False, stopped=[], tailAt=None)
    log('  [CTL] 调度器退出（已复位控制文件）✓')
    # ★★★ 收尾：**跨池审查 + 精选池**（2026-09-14 用户批准；见 `tools/cross_pool_review.py`）
    #   为什么必须放在这里：**跨池去重无法放进引擎** —— 三个池是独立进程、互不知道；
    #   若让后跑的池读先跑的池的 bank ⇒ **跑序一变结果就变、不可复现**。
    #   ⇒ 正确地做成"**一轮轨道跑完后的一次性审查**"。
    #   ⚠ 前置：先把新入库因子的值落地到 `facs/`（否则审查看不到新因子）。
    # ==================== 收尾（v1.3.0 起由 `do_global_tail()` 统一承担）====================
    # ★ 为什么原实现必须放在这里（2026-09-14 的注释，仍然成立）：
    #   **跨池去重无法放进引擎** —— 各池是独立轨迹、互不知道；若让后跑的池读先跑的池的 bank
    #   ⇒ **跑序一变结果就变、不可复现** ⇒ 正确地做成"**一轮跑完后的一次性审查**" ✓
    #   ⚠ 前置：先把新入库因子的值落地到 `facs/`（否则审查看不到新因子）。
    #
    # ★★ v1.3.0 变化：
    #   · **每轮结束** ⇒ 自动收尾（在轮转循环里，见上）
    #   · **收到「全部停」** ⇒ 自动收尾（见上）
    #   · 这里**只兜住 `--rounds=0`**（= "纯收尾"调用，看板旧接口/CLI 仍可用）✓
    #   · `--no_global` 仍保留：**给"每池一进程"的旧并行模式**兜底（默认已不需要）✓
    if rounds == 0 and not dry and not no_global:
        do_global_tail('--rounds=0（仅收尾）')
    if no_global and not dry:
        log('')
        log('=' * 76)
        log('[收尾] ⏭ **已跳过**（`--no_global`）')
        log('       ⇒ 用 `run_tracks.py --rounds=0` 单独收尾，或直接跑轮转调度器 ✓')
        log('=' * 76)
    return 0


if __name__ == '__main__':
    sys.exit(main())
