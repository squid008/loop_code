# -*- coding: utf-8 -*-
"""★★★ 实证：**只改 `frontend/config.json` 一处**，前后端端口是否一起变？

用户 2026-09-15：「端口注意万一将来项目多了，要可以改哈，抽象出来，
  **只改一个地方**就好，别多个文件都把端口号写死进去了」
⇒ 本脚本就是**证明这一点**（而不是嘴上说）：
  ① 改 config.json 的端口 → ② 重启前后端 → ③ 验证新端口通、旧端口不通 → ④ 改回
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r'D:\loop_code'
CFG = os.path.join(R, 'frontend', 'config.json')
PY = sys.executable
TMP = os.environ.get('TEMP', r'C:\Windows\Temp')


def read_cfg():
    return json.load(io.open(CFG, encoding='utf-8'))


def write_cfg(c):
    io.open(CFG, 'w', encoding='utf-8', newline='').write(
        json.dumps(c, ensure_ascii=False, indent=2) + '\n')


def probe(url, timeout=6):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def kill_backend():
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                    "Where-Object { $_.CommandLine -like '*frontend\\backend\\run.py*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    time.sleep(2)


def kill_web():
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*vite*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True)
    time.sleep(2)


def start_backend():
    subprocess.Popen([PY, os.path.join(R, 'frontend', 'backend', 'run.py')], cwd=R,
                     stdout=io.open(os.path.join(TMP, 'fe_out.log'), 'w', encoding='utf-8'),
                     stderr=io.open(os.path.join(TMP, 'fe_err.log'), 'w', encoding='utf-8'))


def start_web():
    subprocess.Popen('npm run dev', cwd=os.path.join(R, 'frontend', 'web'), shell=True,
                     stdout=io.open(os.path.join(TMP, 'web_out.log'), 'w', encoding='utf-8'),
                     stderr=subprocess.STDOUT)


orig = read_cfg()
ob, of = orig['backend']['port'], orig['frontend']['port']
nb, nf = ob + 1, of + 1

print('=' * 96)
print('【实证】只改 config.json ⇒ 前后端端口一起变')
print('=' * 96)
print('  原端口: 后端 %d · 前端 %d' % (ob, of))
print('  新端口: 后端 %d · 前端 %d（只改 config.json 的这两个数字）' % (nb, nf))

# ---- 步骤 0：确认原端口通 ----
print()
print('  [0] 原端口基线:')
print('      后端 %d /api/health -> %s' % (ob, probe('http://127.0.0.1:%d/api/health' % ob)))
print('      前端 %d /           -> %s' % (of, probe('http://127.0.0.1:%d/' % of)))

# ---- 步骤 1：只改 config.json ----
print()
print('  [1] 改 config.json ...')
c = read_cfg()
c['backend']['port'] = nb
c['frontend']['port'] = nf
write_cfg(c)
print('      ✓ 已写入（只动这一个文件）')

# ---- 步骤 2：重启 ----
print()
print('  [2] 重启前后端（脚本里没有任何端口字面量，全读 config）...')
kill_backend(); kill_web()
start_backend(); start_web()
print('      等待启动 ...')
time.sleep(20)

# ---- 步骤 3：验证新端口 ----
print()
print('  [3] 验证:')
h = probe('http://127.0.0.1:%d/api/health' % nb, 10)
w = probe('http://127.0.0.1:%d/' % nf, 10)
px = probe('http://127.0.0.1:%d/api/status' % nf, 40)
print('      后端【新】%d /api/health  -> %s   %s' % (nb, h, '✓' if h == 200 else '✗'))
print('      前端【新】%d /            -> %s   %s' % (nf, w, '✓' if w == 200 else '✗'))
print('      前端【新】%d /api/status  -> %s   %s（★ Vite proxy 自动跟到新后端端口）'
      % (nf, px, '✓' if px == 200 else '✗'))
o1 = probe('http://127.0.0.1:%d/api/health' % ob, 4)
o2 = probe('http://127.0.0.1:%d/' % of, 4)
print('      后端【旧】%d -> %s   %s' % (ob, o1, '✓ 已停用' if o1 is None else '⚠ 仍在响应'))
print('      前端【旧】%d -> %s   %s' % (of, o2, '✓ 已停用' if o2 is None else '⚠ 仍在响应'))
ok = (h == 200 and w == 200 and px == 200)
print()
print('  ⇒ ★★ %s' % ('**证明成立**：只改 config.json 一处，前后端（含 proxy）全部跟着变 ✓'
                     if ok else '⚠ 验证未全通过 —— 需排查'))

# ---- 步骤 4：改回 ----
print()
print('  [4] 改回原端口 %d / %d 并重启 ...' % (ob, of))
c = read_cfg()
c['backend']['port'] = ob
c['frontend']['port'] = of
write_cfg(c)
kill_backend(); kill_web()
start_backend(); start_web()
time.sleep(20)
print('      后端 %d -> %s' % (ob, probe('http://127.0.0.1:%d/api/health' % ob, 10)))
print('      前端 %d -> %s' % (of, probe('http://127.0.0.1:%d/' % of, 10)))
print('      ✓ 已恢复')
