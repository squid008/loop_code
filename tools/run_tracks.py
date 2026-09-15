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


def main():
    pools = ['300', '500', '1000']
    rounds = 3
    n, l2 = 800, 30
    dry = False
    inject_spec = ''       # ★ §1.8：外部池库对照集注入（默认自动：只给 all 轨道）
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
    extra = ['--pool_obs', '--pools=300,500,1000', '--strip_style', '--dup_ex_corr=0.90',
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

    for p, g0, done in plan:
        sfx = '' if p == 'all' else '_' + p
        for i in range(rounds):
            gen = g0 + i
            seed = gen * 10 + 7
            logf = os.path.join(LOGD, 'pool{}_gen{}.log'.format(sfx, gen))
            errf = os.path.join(LOGD, 'pool{}_gen{}_err.log'.format(sfx, gen))
            cmd = [PY, '-u', 'engine/loop_engine.py', '--gen={}'.format(gen),
                   '--n={}'.format(n), '--l2={}'.format(l2), '--seed={}'.format(seed)] + extra
            # ★ 2026-09-14（loop_todo §1.8）：给 `all` 轨道注入池库作对照集（避免重挖）。
            _inj = inject_for(p, pools, inject_spec)
            if _inj:
                cmd.append('--inject_pools={}'.format(','.join(_inj)))
            if p != 'all':
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
                pr = subprocess.run(cmd, cwd=ROOT, stdout=o, stderr=e, env=_env)
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
                log('[!] 本池非正常结束 -> **停止本池**（继续下一池）。'
                    '人工看 {}'.format(os.path.basename(errf)))
                break
    log('===== 全部轨道结束 =====')
    # ★★★ 收尾：**跨池审查 + 精选池**（2026-09-14 用户批准；见 `tools/cross_pool_review.py`）
    #   为什么必须放在这里：**跨池去重无法放进引擎** —— 三个池是独立进程、互不知道；
    #   若让后跑的池读先跑的池的 bank ⇒ **跑序一变结果就变、不可复现**。
    #   ⇒ 正确地做成"**一轮轨道跑完后的一次性审查**"。
    #   ⚠ 前置：先把新入库因子的值落地到 `facs/`（否则审查看不到新因子）。
    if not dry:
        log('')
        log('=' * 76)
        log('[收尾 ①] 因子值落地到 facs/（新入库的必须落，否则审查看不到）')
        log('=' * 76)
        try:
            # ★ `--only-new`（2026-09-14 优化）：**增量落地** —— 已落地的跳过、只缺
            #   `values_q.h5` 的只补副本、都不缺时**连面板都不载**。
            #   实测：52 个全就绪 ⇒ **4.0s**（全量要 ~21min）；缺 3 个副本 ⇒ 5.9s。
            #   ⚠ 增量模式下 CSV 走「读-合并-写」（`_merge_csv`）⇒ 不会清空已有的
            #     52 条剥风格记录（那是精选池 L3 的闸门依据）。回归测试：
            #     `python tools/_test_build_facs_merge.py`（11 项）。
            r = subprocess.run([PY, '-u', 'tools/build_facs.py', '--only-new'],
                               cwd=ROOT, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=7200)
            for ln in (r.stdout or '').splitlines()[-6:]:
                log('    ' + ln[:150])
            if r.returncode != 0:
                log('    [!] 落地非零退出={} -> 仍继续审查（用已有 facs/）'.format(r.returncode))
        except Exception as e:
            log('    [!] 落地失败({}) -> 仍继续审查'.format(type(e).__name__))
        log('')
        log('=' * 76)
        log('[收尾 ②] L2 跨池审查 + L3 精选池')
        log('=' * 76)
        try:
            r = subprocess.run([PY, '-u', 'tools/cross_pool_review.py'],
                               cwd=ROOT, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=3600)
            for ln in (r.stdout or '').splitlines():
                log('    ' + ln[:150])
            if r.stderr and r.stderr.strip():
                log('    [stderr] ' + r.stderr.strip()[:300])
        except Exception as e:
            log('    [!] 审查失败({}: {})'.format(type(e).__name__, e))
        log('')
        log('⇒ 精选池见 docs/factor_pool_selected.md（比"入库数"更接近"能用几个"）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
