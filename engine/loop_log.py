# -*- coding: utf-8 -*-
"""日志的**时间 / 耗时**单一实现（2026-09-28 v1.26.0 ✓）。

★ 为什么单独一个模块：
  ① **R5 单一实现**：人类可读耗时（`1h59m2s` ✓）与"时间戳行"同时被两处需要 ——
     `loop_persist.py`（stdout 的 `保存状态` 段 ✓）与 `loop_critic.py`（journal 代标题 ✓）；
     各写一份就是两份实现 ✗。
  ② **R2 文件长度**：`loop_persist.py` 那时已 792 行 ✓，把这俩塞进去会顶过 800 行 ✗
     ⇒ 抽出后两个调用点各只剩 1~2 行 ✓，两边都回到线内 ✓。
★ 为什么不塞进 `loop_paths.py`：那个模块**唯一职责是路径常量** ✓（见其文件头 ✓）——
   让它兼任"时间格式化"正是本项目反对的混合职责 ✗。
★ 本模块被 `loop_persist.py` 与 `loop_critic.py` 同时 import ✓ ⇒ 不是孤儿模块 ✓。
"""
import time


def fmt_dur(secs):
    """秒 → 人类可读耗时（`1h59m2s` ✓ / `58m42s` ✓ / `42s` ✓）。★ 唯一实现 ✓

    ⚠ 不补零：用户给的样例就是 `1h58m42s` ✓（`1h09m07s` 不好读 ✗）。
    """
    _s = int(secs)
    if _s >= 3600:
        return '%dh%dm%ds' % (_s // 3600, _s % 3600 // 60, _s % 60)
    if _s >= 60:
        return '%dm%ds' % (_s // 60, _s % 60)
    return '%ds' % _s


def stamp(t0=None, tail=''):
    """一行时间戳：`时间: … · 开工 … · 完工 … · 耗时 …`（★ 唯一实现 ✓）。

    · 给了 `t0`：开工 = `t0`、完工 = 调用时刻 ✓ ⇒ 与 `耗时` **同源**（恒等 ✓，不会两个时钟打架 ✗）
    · 没给 `t0`（如 journal 的"诊断落档" ✓）：**只写当下**，**不编造** 开工/完工 ✗ ——
      那一刻"整代是否完工"还不可知（AI 审查在其**后**才跑 ✓）⇒ 宁缺勿假 ✓
    · 时区用 `%z` **实测** ✓（不硬编码 `+08:00` ✗ —— 本机在北京时即 `+0800` ✓，换机器也不撒谎 ✓）
    · `tail` 附一句语义（如 `（诊断落档时刻 · 本机时区）` ✓）
    """
    _now = time.strftime('%Y-%m-%d %H:%M:%S')
    _tz = time.strftime('%z')
    if t0 is None:
        return '时间: %s %s%s' % (_now, _tz, tail)
    return ('时间: %s %s · 开工 %s · 完工 %s · 耗时 %s%s'
            % (_now, _tz, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0)),
               _now, fmt_dur(time.time() - t0), tail))
