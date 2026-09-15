# -*- coding: utf-8 -*-
"""后端启动器 —— **唯一入口**，自动从 `dashboard/config.json` 读端口。

用法:
    python dashboard/api/run.py
    python dashboard/api/run.py --check      # 只做端口冲突自检，不启动

★ 为什么要有它：让"改端口"只发生在一个地方（`config.json`）——
  本文件**不写任何端口字面量**，全部从配置读 ✓
"""
import argparse
import io
import json
import os
import socket
import sys

# ★ 2026-09-15 修：Windows 控制台默认 **GBK**，而本文件打印 `⚠` 等符号
#   ⇒ `UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0'` ⇒ **直接崩** ✗
#   ⇒ 强制 stdout/stderr 走 utf-8（本项目其它脚本也常踩，统一在这里兜住）✓
for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))          # dashboard/api
DASHBOARD = os.path.dirname(HERE)                          # dashboard
CONFIG = os.path.join(DASHBOARD, 'config.json')


def load_cfg():
    if not os.path.exists(CONFIG):
        print('✗ 缺少配置文件: %s' % CONFIG)
        sys.exit(1)
    with io.open(CONFIG, encoding='utf-8') as f:
        return json.load(f)


def port_free(host, port):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect((host, port))
        return False        # 连得上 ⇒ 已被占用
    except OSError:
        return True
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只做端口自检')
    a = ap.parse_args()

    cfg = load_cfg()
    b = cfg.get('backend') or {}
    f = cfg.get('frontend') or {}
    host, port = b.get('host', '127.0.0.1'), int(b.get('port', 8101))
    fport = int(f.get('port', 5273))
    reserved = cfg.get('reservedPorts') or {}

    print('=' * 62)
    print('Loop 挖掘看板 — 后端')
    print('=' * 62)
    print('  配置来源 : %s' % CONFIG)
    print('  后端     : http://%s:%d' % (host, port))
    print('  前端     : http://%s:%d' % (f.get('host', '127.0.0.1'), fport))
    if reserved:
        print('  ⚠ 需避让的保留端口 : %s' % ', '.join('%s=%s' % kv for kv in reserved.items()))

    # 冲突自检
    clash = [('%s(%s)' % (k, v)) for k, v in reserved.items() if int(v) in (port, fport)]
    if clash:
        print('  ✗ 端口与保留端口冲突: %s ⇒ 请改 config.json' % ', '.join(clash))
        sys.exit(2)
    for tag, p, is_front in (('后端', port, False), ('前端', fport, True)):
        if not port_free(host if not is_front else f.get('host', '127.0.0.1'), p):
            print('  ⚠ %s端口 %d 已被占用（可能是本服务已在跑，或别的程序）' % (tag, p))
    print('=' * 62)

    if a.check:
        print('  ✓ 自检完成（未启动）')
        return

    sys.path.insert(0, HERE)
    try:
        import uvicorn
    except ImportError:
        print('✗ 缺 uvicorn ⇒ 先执行: pip install -r %s'
              % os.path.join(HERE, 'requirements.txt'))
        sys.exit(1)
    os.chdir(HERE)
    uvicorn.run('app.main:app', host=host, port=port,
                reload=bool(b.get('reload', False)))


if __name__ == '__main__':
    main()
