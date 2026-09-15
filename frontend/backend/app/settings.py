# -*- coding: utf-8 -*-
"""配置加载 —— **端口/主机的唯一来源** `frontend/config.json`。

★ 设计要点（用户 2026-09-15 明确要求）：
  「端口注意万一将来项目多了，要可以改哈，抽象出来，**只改一个地方**就好，
    别多个文件都把端口号写死进去了」
  ⇒ 本模块是**唯一**读取端口的地方；`run.py` / 前端 `vite.config.ts` 都问它（或问同一个 json）✓
  ⇒ 前端代码**只请求相对路径 `/api/*`** ⇒ 它甚至不知道端口 ✓
"""
import io
import json
import os
import sys

# ★ 统一兜住 Windows 控制台 GBK 编码问题（打印 `⚠`/中文会 UnicodeEncodeError 崩掉）
for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))          # frontend/backend/app
BACKEND_DIR = os.path.dirname(HERE)                        # frontend/backend
FRONTEND_DIR = os.path.dirname(BACKEND_DIR)                # frontend
CONFIG_PATH = os.path.join(FRONTEND_DIR, 'config.json')


def _load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError('缺少配置文件: %s' % CONFIG_PATH)
    with io.open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


CFG = _load_config()


def _locate_project_root():
    """定位仓库根：优先取 config 的 `project.root`，否则**自动向上找**含 engine/ 与 docs/ 的目录。"""
    raw = ((CFG.get('project') or {}).get('root') or '').strip()
    if raw:
        p = os.path.abspath(os.path.join(FRONTEND_DIR, raw))
        if os.path.isdir(p):
            return p
    cand = FRONTEND_DIR
    for _ in range(6):
        if os.path.isdir(os.path.join(cand, 'engine')) and os.path.isdir(os.path.join(cand, 'docs')):
            return cand
        parent = os.path.dirname(cand)
        if parent == cand:
            break
        cand = parent
    return os.path.dirname(FRONTEND_DIR)


PROJECT_ROOT = _locate_project_root()
DOCS = os.path.join(PROJECT_ROOT, 'docs')
ENGINE = os.path.join(PROJECT_ROOT, 'engine')

BACKEND_CFG = CFG.get('backend') or {}
FRONTEND_CFG = CFG.get('frontend') or {}

BACKEND_HOST = BACKEND_CFG.get('host', '127.0.0.1')
BACKEND_PORT = int(BACKEND_CFG.get('port', 8101))
BACKEND_RELOAD = bool(BACKEND_CFG.get('reload', False))

FRONTEND_HOST = FRONTEND_CFG.get('host', '127.0.0.1')
FRONTEND_PORT = int(FRONTEND_CFG.get('port', 5273))

RESERVED_PORTS = CFG.get('reservedPorts') or {}

# 允许的前端来源（CORS）—— 由上面的端口推导，**不再出现硬编码端口**
CORS_ORIGINS = [
    'http://%s:%d' % (FRONTEND_HOST, FRONTEND_PORT),
    'http://localhost:%d' % FRONTEND_PORT,
    'http://127.0.0.1:%d' % FRONTEND_PORT,
]

API_PREFIX = '/api'


def describe():
    """给 `/api/meta` 用：把"配置从哪来"透明化（便于排查端口冲突）。"""
    return {
        'configPath': CONFIG_PATH,
        'projectRoot': PROJECT_ROOT,
        'docsDir': DOCS,
        'engineDir': ENGINE,
        'backend': {'host': BACKEND_HOST, 'port': BACKEND_PORT},
        'frontend': {'host': FRONTEND_HOST, 'port': FRONTEND_PORT},
        'reservedPorts': RESERVED_PORTS,
        'corsOrigins': CORS_ORIGINS,
        'database': CFG.get('database') or {},
    }
