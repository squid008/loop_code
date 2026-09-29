# -*- coding: utf-8 -*-
"""tools/feishu.py — 飞书通道：**发**通知（群机器人 webhook）+ **收**手机回复（应用接口轮询）。

★ 来源：`E:\\quant\\trader_code\\backend\\app\\services\\feishu.py`（2026-09-28 那套 ✓ 逐条搬来，适配本仓库 ✓）。
  为什么照搬：那边的两个坑是真金白银踩出来的 ——
  ① 飞书 `im/v1/messages` 的 `start_time` 是**秒级**（而 `create_time` 回的是毫秒 ✗，
     按毫秒传会被拒：`code=230001 The end_time is earlier than the start_time`）；
  ② 判断发送成功必须要求字段**存在**且为 0（`code` / 老接口 `StatusCode`）——
     写成 `int(d.get("code") or 0) == 0` 的话，**缺字段会被当成成功** ⇒ 每次都误报"发出去了" ✗。

## ⚠⚠ 别串台（用户 2026-09-29 明确交代 ✓）
| | 事实 | 本工具的规矩 |
|---|---|---|
| **发** | 两个群**各有自己的**自定义机器人 webhook（trader 群 `967ecde3-…` ✗ / 本仓库 loop_code 群 `45300305-…` ✓）| 只许用 `config.local.json` 里配的那个 ✓；配成 trader 那个会被 `_guard_not_trader()` **硬拦** ✗ |
| **收** | `app_id=cli_aa30f2e87c389bda` 是**两个群共用**的同一个应用 ✓ | 只按**本仓库配置的 `chat_id`** 取消息 ✓；`chat_id` 若等于 trader 那个 ⇒ **硬拦** ✗ |

## 四条纪律（与 trader 一致，改动前先读 ✓）
1. **绝不因为发通知而影响主流程**：对外函数把异常全吞 ✓，只记日志、返回 False/空。
2. **收消息只进收件箱，绝不执行命令** ✗：`--poll/--wait` 只把消息落进 `inbox.jsonl` ✓；
   "要不要据此干活、干什么"由**上层（人或调用方）**决定 ✓ —— 聊天文本永远不等于可执行命令 ✓。
3. **默认关**：`enabled=false` 或没配齐 ⇒ 一切照旧，**连网络请求都不发** ✓（静默降级 ✓）。
4. **不猜、不吞**：取消息要显式给 `since_ms`；解析不了的字段留空串，不编造 ✓。

## 用法
    python tools/feishu.py --find-chat                  # 列出机器人所在的群（用来取 chat_id ✓）
    python tools/feishu.py --send "正文" [--title 标题]   # 发到**本仓库的那个群** ✓
    python tools/feishu.py --poll --since-min 30         # 取最近 30 分钟**人发的**消息（打印 ✓）
    python tools/feishu.py --wait --timeout 3600         # 轮询等待：新消息**追加**进收件箱 ✓

配置（仓库根 `config.local.json`，**已 gitignore** ✓ —— 别写进 `change_log`/文档/提交 ✗）：
    {"notify": {"feishu": {"enabled": true,
                           "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/<本群>",
                           "app_id": "cli_...", "app_secret": "...", "chat_id": "oc_...",
                           "proxy": ""}}}
产物：`ai_test/notify/inbox.jsonl`（gitignore 区 ✓；一行一条 {"ts_ms","message_id","text",...} ✓）
"""
import argparse
import io
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG_LOCAL = os.path.join(ROOT, 'config.local.json')
INBOX = os.path.join(ROOT, 'ai_test', 'notify', 'inbox.jsonl')
FEISHU_BASE = 'https://open.feishu.cn/open-apis'
_TIMEOUT = 12
_TOKEN_CACHE: Dict[str, Any] = {'token': '', 'expire_at': 0.0}

# ★ 别串台的硬拦（用户 2026-09-29 交代 ✓）：只拦"明显配成了别的项目"的情况 ✓，不做别的脑补 ✗
#   ★★ 实测（`--find-chat` 2026-09-29）：**同一个 app 在三个群里** ✗ ——
#      trader_code 群 · data_wash 群 · 本仓库 loop_code 群 ⇒ 后两个都要拦 ✗（本仓库只能用第三个 ✓）
_FOREIGN_WEBHOOK_TAILS = {
    '967ecde3-6236-4612-857c-4fed9f7cad9b': 'trader_code',       # trader 群的自定义机器人 ✗
}
_FOREIGN_CHAT_IDS = {
    'oc_c412ecb7a1c5b11e5452be24588adcce': 'trader_code',        # trader 群 ✗
    'oc_47d11dc9f2e158da0ed30b3112ada28d': 'data_wash',         # data_wash 群 ✗
}


def _cfg() -> Dict[str, Any]:
    """读 `config.local.json` 的 `notify.feishu` 段（缺文件/坏 JSON ⇒ 空字典，**不抛** ✓）。"""
    try:
        with io.open(CFG_LOCAL, encoding='utf-8') as f:
            d = json.load(f) or {}
        return dict(((d.get('notify') or {}).get('feishu')) or {})
    except Exception:                                                    # noqa: BLE001
        return {}


def _err(msg: str) -> str:
    print('[feishu] [!] %s' % msg, file=sys.stderr)
    return ''


def _guard_foreign(c: Dict[str, Any]) -> Optional[str]:
    """串台检查：配成**别的项目**的群（webhook / chat_id ⇒ 见 `_FOREIGN_*`）⇒ 返回错误说明 ✓。

    调用方拿到非空 ⇒ **拒绝执行** ✗（发不出去 / 收不进来，而不是"悄悄发到别人的群" ✗✗）。
    """
    wh = str(c.get('webhook') or '')
    cid = str(c.get('chat_id') or '')
    for tail, proj in _FOREIGN_WEBHOOK_TAILS.items():
        if tail and tail in wh:
            return ('webhook 指向的是 **%s 群** ✗（%s…）—— 本仓库必须用 loop_code 群的 webhook ✓'
                    % (proj, tail[:8]))
    if cid in _FOREIGN_CHAT_IDS:
        return ('chat_id 是 **%s 群** ✗（%s）—— 收消息会串台 ✓；'
                '请用 `--find-chat` 取本群（**Loop_code机器人** ✓）'
                % (_FOREIGN_CHAT_IDS[cid], cid))
    return None


def enabled() -> bool:
    """要不要发（没配或显式关掉 ⇒ False ✓）。"""
    c = _cfg()
    if not bool(c.get('enabled')):
        return False
    return bool(str(c.get('webhook') or '').strip()
                or (str(c.get('app_id') or '').strip() and str(c.get('app_secret') or '').strip()))


def can_receive() -> bool:
    """能不能收（需要应用三件套 app_id/app_secret/chat_id ✓）。"""
    c = _cfg()
    return bool(str(c.get('app_id') or '').strip() and str(c.get('app_secret') or '').strip()
                and str(c.get('chat_id') or '').strip())


def _proxies() -> Optional[Dict[str, str]]:
    """飞书是国内服务 ⇒ 默认**直连** ✓（想走代理就配 `"proxy": "http://…"` ✓）。"""
    p = str(_cfg().get('proxy') or '').strip()
    return {'http': p, 'https': p} if p else None


def _post(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    import requests
    r = requests.post(url, json=payload, headers=headers or {}, timeout=_TIMEOUT, proxies=_proxies())
    try:
        return r.json()
    except Exception:                                                    # noqa: BLE001
        return {'_status': r.status_code, '_text': (r.text or '')[:300]}


def _get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    import requests
    r = requests.get(url, headers=headers or {}, timeout=_TIMEOUT, proxies=_proxies())
    try:
        return r.json()
    except Exception:                                                    # noqa: BLE001
        return {'_status': r.status_code, '_text': (r.text or '')[:300]}


def tenant_token() -> str:
    """取应用凭证（进程内缓存，过期前 5 分钟续 ✓）。失败返回空串 ✓。"""
    c = _cfg()
    if not (str(c.get('app_id') or '').strip() and str(c.get('app_secret') or '').strip()):
        return ''
    if _TOKEN_CACHE['token'] and time.time() < float(_TOKEN_CACHE['expire_at']):
        return str(_TOKEN_CACHE['token'])
    try:
        d = _post('%s/auth/v3/tenant_access_token/internal' % FEISHU_BASE,
                  {'app_id': str(c['app_id']), 'app_secret': str(c['app_secret'])})
        tok = str(d.get('tenant_access_token') or '')
        if tok:
            _TOKEN_CACHE['token'] = tok
            _TOKEN_CACHE['expire_at'] = time.time() + max(60, int(d.get('expire') or 7200) - 300)
        else:
            _err('取 token 失败：%s' % str(d)[:200])
        return tok
    except Exception as e:                                               # noqa: BLE001
        _err('取 token 异常：%s' % str(e)[:200])
        return ''


#: 出站文案的"去 Markdown"（★ 与 trader 同款护栏 ✓）：飞书这条路发的是**纯文本**，
#: `**粗体**`/反引号会**原样显示成符号** ✗（用户实测问过"怎么飞书收到的跟 IDE 里不一样" ✗）。
_MD_PLAIN = re.compile(r'\*\*|__|`')


def to_plain(text: str) -> str:
    """去掉外发文案里的 Markdown 强调符号（**保留文字本身** ✓，纯文本通道专用 ✓）。"""
    return _MD_PLAIN.sub('', str(text or ''))


def send(text: str, *, title: str = '') -> bool:
    """发一条文本消息。**永不抛异常** ✓（失败只记日志 + 返回 False ✓）。

    优先 Webhook（最小配置 ✓）；没有 webhook 但有应用三件套时走应用接口 ✓。
    ⚠ 正文先过 `to_plain()` ✓；⚠ 配成 trader 群 ⇒ **直接拒绝** ✗（别串台 ✓）。
    """
    body = ('%s\n%s' % (title, text)) if str(title or '').strip() else str(text or '')
    body = to_plain(body)
    if not str(body).strip():
        return False
    c = _cfg()
    bad = _guard_foreign(c)
    if bad:
        _err(bad)
        return False
    if not enabled():
        return False
    wh = str(c.get('webhook') or '').strip()
    try:
        if wh:
            d = _post(wh, {'msg_type': 'text', 'content': {'text': body}})
            # ⚠ 必须要求字段**存在**且为 0（见文件头坑 ② ✓）
            code, sc = d.get('code'), d.get('StatusCode')
            ok = (code is not None and int(code) == 0) or (sc is not None and int(sc) == 0)
            if not ok:
                _err('webhook 返回异常：%s' % str(d)[:200])
            return bool(ok)
        tok = tenant_token()
        if not tok or not can_receive():
            return False
        d = _post('%s/im/v1/messages?receive_id_type=chat_id' % FEISHU_BASE,
                  {'receive_id': str(c.get('chat_id')), 'msg_type': 'text',
                   'content': json.dumps({'text': body}, ensure_ascii=False)},
                  headers={'Authorization': 'Bearer %s' % tok})
        ok = int(d.get('code') or 0) == 0
        if not ok:
            _err('应用发消息失败：%s' % str(d)[:200])
        return bool(ok)
    except Exception as e:                                               # noqa: BLE001
        _err('发消息异常（不影响主流程）：%s' % str(e)[:200])
        return False


def _text_of(msg_type: str, content: str) -> str:
    """从 `body.content`（JSON 字符串）里取人话：`text` ✓ / `post`（富文本 ✓）；其它类型返回空串 ✓。"""
    try:
        d = json.loads(content or '{}') or {}
    except Exception:                                                    # noqa: BLE001
        return ''
    if not isinstance(d, dict):
        return ''
    if str(msg_type) == 'text':
        return str(d.get('text') or '')
    if str(msg_type) == 'post':
        parts: List[str] = [str(d.get('title') or '')]
        for line in (d.get('content') or []):
            for seg in (line or []):
                if isinstance(seg, dict) and seg.get('tag') == 'text':
                    parts.append(str(seg.get('text') or ''))
        return ''.join(p for p in parts if p).strip()
    return ''


def _parse_message(item: Dict[str, Any]) -> Dict[str, Any]:
    """把飞书一条消息拍平成我们自己的形状（缺的字段留空串 ✓，不编造 ✓）。"""
    sender = item.get('sender') or {}
    body = item.get('body') or {}
    msg_type = str(item.get('msg_type') or '')
    return {'message_id': str(item.get('message_id') or ''),
            'create_time': int(item.get('create_time') or 0),
            'sender_id': str((sender.get('id') or '') if isinstance(sender, dict) else ''),
            'sender_type': str(sender.get('sender_type') or '') if isinstance(sender, dict) else '',
            'msg_type': msg_type,
            'text': _text_of(msg_type, str(body.get('content') or ''))}


def list_chats(*, limit: int = 50) -> List[Dict[str, Any]]:
    """机器人**所在的群**列表（取 `chat_id` 用 ✓）。没权限时把 `_err` 原样带回来 ✓。"""
    c = _cfg()
    if not (str(c.get('app_id') or '').strip() and str(c.get('app_secret') or '').strip()):
        return [{'_err': '还没配 app_id / app_secret'}]
    tok = tenant_token()
    if not tok:
        return [{'_err': '取 tenant_access_token 失败（app_id/app_secret 是否正确？）'}]
    try:
        d = _get('%s/im/v1/chats?page_size=%d' % (FEISHU_BASE, max(1, min(100, limit))),
                 headers={'Authorization': 'Bearer %s' % tok})
        if int(d.get('code') or 0) != 0:
            return [{'_err': 'code=%s msg=%s（大概率缺 im:chat:readonly 权限）'
                             % (d.get('code'), d.get('msg'))}]
        return [{'chat_id': str(it.get('chat_id') or ''), 'name': str(it.get('name') or ''),
                 'chat_mode': str(it.get('chat_mode') or '')}
                for it in ((d.get('data') or {}).get('items') or []) if isinstance(it, dict)]
    except Exception as e:                                               # noqa: BLE001
        return [{'_err': '请求异常：%s' % str(e)[:160]}]


def fetch_replies(since_ms: int, *, limit: int = 20) -> List[Dict[str, Any]]:
    """取 `since_ms`（毫秒 ✓）**之后**的消息（升序 ✓）。失败返回空列表 ✓。

    ⚠ 只取**人发的文本/富文本** ✓：机器人自己发的（`sender_type=app`）不回灌（免得自我循环 ✗）；
      `system`（入群/改名）是噪音 ⇒ 过滤掉 ✓（不过滤的话收件箱全是"XX 邀请 XX 加入群聊" ✗）。
    ⚠ `start_time` 必须换成**秒**（见文件头坑 ① ✓）。
    """
    c = _cfg()
    bad = _guard_foreign(c)
    if bad:
        _err(bad)
        return []
    if not (enabled() and can_receive()):
        return []
    tok = tenant_token()
    if not tok:
        return []
    try:
        url = ('%s/im/v1/messages?container_id_type=chat&container_id=%s&start_time=%d'
               '&sort_type=ByCreateTimeAsc&page_size=%d'
               % (FEISHU_BASE, str(c.get('chat_id')), max(0, int(since_ms) // 1000),
                  max(1, min(50, limit))))
        d = _get(url, headers={'Authorization': 'Bearer %s' % tok})
        if int(d.get('code') or 0) != 0:
            _err('取消息失败：%s' % str(d)[:200])
            return []
        items = ((d.get('data') or {}).get('items') or [])
        out = [_parse_message(it) for it in items if isinstance(it, dict)]
        return [m for m in out if m['sender_type'] in ('', 'user')
                and m['msg_type'] in ('text', 'post')]
    except Exception as e:                                               # noqa: BLE001
        _err('取消息异常：%s' % str(e)[:200])
        return []


def append_inbox(msgs: List[Dict[str, Any]]) -> int:
    """把消息**追加**进收件箱（JSONL ✓，带收到时刻 ✓）。返回写入条数 ✓。"""
    if not msgs:
        return 0
    os.makedirs(os.path.dirname(INBOX), exist_ok=True)
    seen = set()
    if os.path.exists(INBOX):
        try:
            with io.open(INBOX, encoding='utf-8') as f:
                for ln in f:
                    try:
                        seen.add(str((json.loads(ln) or {}).get('message_id') or ''))
                    except Exception:                                    # noqa: BLE001
                        pass
        except Exception:                                                # noqa: BLE001
            pass
    n = 0
    with io.open(INBOX, 'a', encoding='utf-8') as f:
        for m in msgs:
            if str(m.get('message_id') or '') in seen:
                continue                                                 # 幂等：同一条不重复落 ✓
            rec = dict(m)
            rec['ts_ms'] = m.get('create_time') or 0
            rec['got_ms'] = int(time.time() * 1000)
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            n += 1
    return n


def latest_inbox_ms() -> int:
    """收件箱里最大 `create_time`（没有则 0 ✓）—— 供 `--poll/--wait` 续接 ✓。"""
    if not os.path.exists(INBOX):
        return 0
    mx = 0
    try:
        with io.open(INBOX, encoding='utf-8') as f:
            for ln in f:
                try:
                    mx = max(mx, int((json.loads(ln) or {}).get('create_time') or 0))
                except Exception:                                        # noqa: BLE001
                    pass
    except Exception:                                                    # noqa: BLE001
        pass
    return mx


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description='飞书通道（发通知 / 收手机回复 ✓）')
    ap.add_argument('--send', metavar='TEXT', help='发一条文本到本仓库配置的群 ✓')
    ap.add_argument('--send-file', metavar='PATH',
                    help='从文件读正文再发 ✓ —— ★ 多行文本**必须**用它 ✗：'
                         '命令行里的换行会被 shell 拆成多个参数（实测 `unrecognized arguments` ✗✗）')
    ap.add_argument('--title', default='', help='与 --send/--send-file 搭配的标题行 ✓')
    ap.add_argument('--find-chat', action='store_true', help='列出机器人所在的群（取 chat_id ✓）')
    ap.add_argument('--poll', action='store_true', help='取新消息并打印（不落收件箱 ✓）')
    ap.add_argument('--wait', action='store_true', help='轮询等待新消息并**追加进收件箱** ✓')
    ap.add_argument('--since-min', type=float, default=5.0, help='--poll 的回看分钟数（默认 5 ✓）')
    ap.add_argument('--since-ms', type=int, default=0, help='显式起始毫秒（优先于 --since-min ✓）')
    ap.add_argument('--timeout', type=float, default=1800.0, help='--wait 的总等待秒数（默认 1800 ✓）')
    ap.add_argument('--interval', type=float, default=5.0, help='--wait 的轮询间隔秒（默认 5 ✓）')
    ap.add_argument('--status', action='store_true', help='打印配置状态（不碰网络 ✓）')
    a = ap.parse_args()
    c = _cfg()

    if a.send_file is not None:
        try:
            with io.open(a.send_file, encoding='utf-8') as f:
                _txt = f.read()
        except Exception as e:                                           # noqa: BLE001
            print('[feishu] 读文件失败：%r' % (e,))
            return 2
        ok = send(_txt, title=a.title)
        print('[feishu] 发送 %s' % ('成功 ✓' if ok else '失败/未启用 ✗（看上面的 [!] 行 ✓）'))
        return 0 if ok else 1

    if a.status or not any([a.send, a.send_file, a.find_chat, a.poll, a.wait]):
        bad = _guard_foreign(c)
        print('[feishu] 配置文件: %s（%s）' % (CFG_LOCAL, '存在' if os.path.exists(CFG_LOCAL) else '不存在'))
        print('         enabled=%s · 有 webhook=%s · 可收(三件套齐)=%s · chat_id=%s'
              % (enabled(), bool(str(c.get('webhook') or '').strip()), can_receive(),
                 (str(c.get('chat_id') or '')[:12] + '…') if c.get('chat_id') else '(未配)'))
        if bad:
            print('         ✗ %s' % bad)
            return 2
        print('         收件箱: %s' % INBOX)
        return 0

    if a.send is not None:
        ok = send(a.send, title=a.title)
        print('[feishu] 发送 %s' % ('成功 ✓' if ok else '失败/未启用 ✗（看上面的 [!] 行 ✓）'))
        return 0 if ok else 1

    if a.find_chat:
        rows = list_chats()
        for r in rows:
            if '_err' in r:
                print('  ✗ %s' % r['_err'])
            else:
                _proj = _FOREIGN_CHAT_IDS.get(r['chat_id'])
                mark = ('  ← ★ 这是 **%s 群**（别人的群，别选 ✗）' % _proj) if _proj else ''
                print('  %-34s %-24s %s%s' % (r['chat_id'], r['name'], r['chat_mode'], mark))
        return 0

    since = a.since_ms or int((time.time() - max(0.0, a.since_min) * 60.0) * 1000)
    if a.poll:
        msgs = fetch_replies(since)
        print('[feishu] %s 之后 %d 条（人发的文本/富文本 ✓）' % (since, len(msgs)))
        for m in msgs:
            print('  [%s] %s' % (time.strftime('%m-%d %H:%M:%S',
                                               time.localtime((m['create_time'] or 0) / 1000.0)),
                                 m['text'][:200]))
        return 0

    # --wait：轮询并**追加进收件箱**（纪律 2：只进收件箱，绝不执行 ✗）
    t0 = time.time()
    last = max(since, latest_inbox_ms())
    print('[feishu] --wait：从 %s 起轮询 %s 秒（间隔 %ss）⇒ 新消息进 %s'
          % (last, a.timeout, a.interval, INBOX), flush=True)
    total = 0
    while time.time() - t0 < a.timeout:
        msgs = fetch_replies(last)
        if msgs:
            n = append_inbox(msgs)
            total += n
            for m in msgs:
                print('  + %s' % m['text'][:200], flush=True)
            last = max([last] + [int(m['create_time'] or 0) for m in msgs])
        time.sleep(max(1.0, a.interval))
    print('[feishu] 结束：新增 %d 条 ✓' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
