# -*- coding: utf-8 -*-
"""配置加载 —— **端口/主机的唯一来源** `dashboard/config.json`。

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

HERE = os.path.dirname(os.path.abspath(__file__))          # dashboard/api/app
API_DIR = os.path.dirname(HERE)                            # dashboard/api
DASHBOARD_DIR = os.path.dirname(API_DIR)                   # dashboard
CONFIG_PATH = os.path.join(DASHBOARD_DIR, 'config.json')


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
        p = os.path.abspath(os.path.join(DASHBOARD_DIR, raw))
        if os.path.isdir(p):
            return p
    cand = DASHBOARD_DIR
    for _ in range(6):
        if os.path.isdir(os.path.join(cand, 'engine')) and os.path.isdir(os.path.join(cand, 'docs')):
            return cand
        parent = os.path.dirname(cand)
        if parent == cand:
            break
        cand = parent
    return os.path.dirname(DASHBOARD_DIR)


PROJECT_ROOT = _locate_project_root()
DOCS = os.path.join(PROJECT_ROOT, 'docs')
ENGINE = os.path.join(PROJECT_ROOT, 'engine')


def _read_version():
    """★ 项目版本**单一来源** = 仓库根的 `VERSION` 文件（与端口同思路：只改一处）。

    ⚠ 2026-09-15 加：此前版本号散落在 `README.md` / `change_log.md` / 看板代码里，
      实测**三处打架**（tag=v0.21.1 · change_log=0.20.2 · README=v0.20.0）✗
      ⇒ 改为 `VERSION` 一处，并由 `tools/_test_version_sync.py` 守门 ✓
    """
    p = os.path.join(PROJECT_ROOT, 'VERSION')
    if os.path.exists(p):
        # ⚠ 用 `utf-8-sig` 容忍 BOM（Windows 编辑器常加 BOM ⇒ 否则版本会变成 '\ufeff1.0.0' ✗）
        v = io.open(p, encoding='utf-8-sig').read().strip().splitlines()
        if v and v[0].strip():
            return v[0].strip().lstrip('v').lstrip('\ufeff')
    return '0.0.0'


VERSION = _read_version()


def current_version():
    """★ 2026-09-19（用户之问："页面我刷新怎么还是 1.19.3 版本？"）—— **每次调用都重新读 `VERSION`** ✓

    真因：`VERSION` 是**模块级常量**（导入时读一次）✗ ⇒ 服务进程启动后版本就**冻结在内存里**，
      改 `VERSION` 之后**刷新页面没用**，非得重启 API 才变 ✗
      （实测：API 进程 09-17 12:22 启动 ⇒ 页面一直显示 `1.19.3`，而当时 `VERSION` 已是 `1.21.x` ✗）
    ⇒ `/api/meta` 与 `describe()` 改用**本函数** ⇒ **刷新即可看到最新版本** ✓
      （省掉"改一次版本就要重启一次服务"的隐性坑 ✗）
    ⚠ `VERSION` 常量仍保留：FastAPI 的 `title/version` 在**启动时**定 ✓ 那是元信息，冻结无妨 ✓
    """
    return _read_version()

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
        # ★ 动态读（不是启动时那个常量）⇒ 改 VERSION 后**刷新即生效** ✓
        'version': current_version(),
        'versionSource': os.path.join(PROJECT_ROOT, 'VERSION'),
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
