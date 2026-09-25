# -*- coding: utf-8 -*-
"""【只读】端到端验证前端看板：
① 前端页面可访问 ② **通过前端端口访问 API**（验证 Vite proxy 生效）
③ 前端业务代码**零硬编码端口**（用户要求"只改一个地方"）
④ 后端所有 API 正常
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(io.open(os.path.join(R, 'dashboard', 'config.json'), encoding='utf-8'))
BH, BP = CFG['backend']['host'], CFG['backend']['port']
FH, FP = CFG['frontend']['host'], CFG['frontend']['port']


def http(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')


print('=' * 98)
print('【0】端口（全部来自 dashboard/config.json）')
print('=' * 98)
print('  后端 http://%s:%d   前端 http://%s:%d' % (BH, BP, FH, FP))
print('  保留端口(需避让): %s' % CFG.get('reservedPorts'))
clash = [k for k, v in (CFG.get('reservedPorts') or {}).items() if int(v) in (BP, FP)]
print('  冲突检查: %s' % ('✗ 与保留端口冲突: %s' % clash if clash else '✓ 无冲突'))

print()
print('=' * 98)
print('【1】前端页面')
print('=' * 98)
try:
    st, body = http('http://%s:%d/' % (FH, FP), 12)
    print('  HTTP %d (%d B)' % (st, len(body)))
    print('  %s 含 <title>' % ('✓' if '<title>' in body else '✗'))
except Exception as e:
    print('  ✗ %r' % (e,))

print()
print('=' * 98)
print('【2】★ 通过【前端端口】访问 API —— 验证 Vite proxy（前端只请求相对路径）')
print('=' * 98)
for ep in ('/api/status', '/api/meta', '/api/library', '/api/selected'):
    try:
        st, body = http('http://%s:%d%s' % (FH, FP, ep), 40)
        j = json.loads(body)
        extra = ''
        if ep == '/api/status':
            extra = 'anyRunning=%s 池=%s 总库=%s 进程=%s' % (
                j['anyRunning'], j['summary']['poolCount'],
                j['summary']['totalLibrary'], len(j['processes']))
        elif ep == '/api/meta':
            extra = 'v%s 后端:%s 前端:%s' % (j['version'], j['settings']['backend']['port'],
                                            j['settings']['frontend']['port'])
        elif ep == '/api/library':
            extra = ' '.join('%s:%s' % (l['pool'], l.get('stateBank')) for l in j['libraries'])
        elif ep == '/api/selected':
            extra = 'count=%s' % j.get('count')
        print('  ✓ %-16s HTTP %d  %s' % (ep, st, extra))
    except Exception as e:
        print('  ✗ %-16s %r' % (ep, e))

print()
print('=' * 98)
print('【3】★ 前端业务代码零硬编码端口（用户要求：只改一个地方）')
print('=' * 98)
bad = 0
for d, ds, fs in os.walk(os.path.join(R, 'dashboard', 'web', 'src')):
    ds[:] = [x for x in ds if x != 'node_modules']
    for f in fs:
        if not f.endswith(('.ts', '.tsx', '.css')):
            continue
        p = os.path.join(d, f)
        for n, l in enumerate(io.open(p, encoding='utf-8', errors='replace').read().splitlines(), 1):
            if re.search(r'\b(8101|5273|8001|5173|27017)\b|localhost:\d|127\.0\.0\.1:\d', l):
                print('  ⚠ %s:%d %s' % (os.path.relpath(p, R), n, l.strip()[:80]))
                bad += 1
print('  ⇒ %s' % ('✓ 零硬编码端口（只请求相对路径 /api/*）' if bad == 0 else '✗ 发现 %d 处' % bad))

print()
print('=' * 98)
print('【4】端口配置的"单一来源"检查')
print('=' * 98)
for f in ('dashboard/config.json', 'dashboard/api/app/settings.py', 'dashboard/api/run.py',
          'dashboard/web/vite.config.ts'):
    p = os.path.join(R, f)
    t = io.open(p, encoding='utf-8', errors='replace').read()
    literals = sorted(set(re.findall(r'\b(8101|5273)\b', t)))
    kind = '★ 定义处（应有字面量）' if 'config.json' in f else (
        '读配置（可含默认值兜底）' if 'settings.py' in f or 'run.py' in f or 'vite' in f else '')
    print('  %-42s 出现 %-18s %s' % (f, literals or '(无)', kind))
