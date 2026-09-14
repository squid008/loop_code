# -*- coding: utf-8 -*-
"""probe_models.py — 实测 DeepSeek 当前**可用模型名**（防"名字改了但代码没改 -> 400 被拒"）

背景：2026-09-09 曾因模型名写错（deepseek-flash-v4）被 400 拒；2026-09-12 用户告知
      `deepseek-v4-flash` 已更名为 `deepseek-flash`。**不照猜改代码**，先问 API。
做法：
  1. GET /models（OpenAI 兼容的列表端点）—— 直接拿权威名单
  2. 对候选名各发一次最小 chat 请求，报告 通/不通 + 报错原文
用法：python tools/probe_models.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_llm                                   # noqa: E402

BASE = 'https://api.deepseek.com'
KEY = loop_llm.api_key()
print(f"key: {'found' if KEY else 'MISSING'}  当前代码里的 DEFAULT_MODEL = {loop_llm.DEFAULT_MODEL}\n")

CANDIDATES = ['deepseek-flash', 'deepseek-v4-flash', 'deepseek-pro', 'deepseek-v4-pro',
              'deepseek-chat', 'deepseek-reasoner']


def http(method, path, payload=None, timeout=30):
    req = urllib.request.Request(
        BASE + path,
        data=(json.dumps(payload).encode('utf-8') if payload is not None else None),
        method=method,
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + (KEY or '')})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return -1, f'{type(e).__name__}: {e}'


print("=" * 62)
print("【1】GET /models —— 权威可用名单")
print("=" * 62)
st, body = http('GET', '/models')
print(f"HTTP {st}")
listed = []
try:
    d = json.loads(body)
    for m in d.get('data', []):
        listed.append(m.get('id'))
    print("  可用模型:", listed if listed else '(空)')
except Exception:
    print("  (非 JSON):", body[:400])

print()
print("=" * 62)
print("【2】逐个最小 chat 请求实测")
print("=" * 62)
ok_names = []
for name in CANDIDATES:
    st, body = http('POST', '/chat/completions', {
        'model': name,
        'messages': [{'role': 'user', 'content': 'hi'}],
        'max_tokens': 600,                 # v4-flash 是推理模型，给足以免 content 空
        'reasoning_effort': 'none',        # 与引擎一致（否则推理吃光 token）
    }, timeout=60)
    verdict = 'OK' if st == 200 else f'HTTP {st}'
    snippet = ''
    if st == 200:
        ok_names.append(name)
        try:
            j = json.loads(body)
            msg = j['choices'][0]['message']
            snippet = (f"content={(msg.get('content') or '')[:20]!r} "
                       f"reasoning={(msg.get('reasoning_content') or '')[:12]!r} "
                       f"finish={j['choices'][0].get('finish_reason')}")
        except Exception:
            snippet = body[:120]
    else:
        try:
            snippet = json.loads(body)['error']['message'][:150]
        except Exception:
            snippet = body[:150]
    print(f"  {name:22s} {verdict:9s} {snippet}")

print()
print("=" * 62)
print(f"实测可用: {ok_names}")
print(f"代码现值: {loop_llm.DEFAULT_MODEL}")
if listed:
    print(f"名单一致? {'是' if set(ok_names) <= set(listed) else '否(名单外也可用)'}")
