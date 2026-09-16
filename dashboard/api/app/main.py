# -*- coding: utf-8 -*-
"""Loop 挖掘看板 —— 后端 API（FastAPI）。

★ 端口**不在此文件**（也不在任何路由里）—— 全部来自 `dashboard/config.json`（见 `settings.py`）✓
★ 前端只请求**相对路径** `/api/*`（Vite proxy 转发）⇒ 前端代码完全不知道端口 ✓

启动:  python dashboard/api/run.py        （推荐，自动读 config.json）
       uvicorn app.main:app --port <n>       （手动，n 要与 config.json 一致）
文档:  http://<host>:<port>/docs
"""
import os
import sys
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

if __package__ in (None, ''):                      # 允许 `python app/main.py` 直接跑
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import settings
    from app import mine
    from app.sources import core, factors, pools
else:
    from . import settings
    from . import mine
    from .sources import core, factors, pools

T0 = time.time()

app = FastAPI(
    title='Loop 挖掘看板 API',
    description='引擎运行状态 + 各池因子库 + 精选池（逐步向聚宽因子看板 / PostgreSQL 靠）',
    version=settings.VERSION,          # ★ 来自仓库根 `VERSION`（项目版本单一来源）
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,           # ★ 由 config.json 的端口推导，无硬编码
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/api/health')
def health():
    return {'ok': True, 'uptimeSec': round(time.time() - T0, 1)}


@app.get('/api/meta', summary='配置透明化（端口从哪来 / 项目路径 / 版本）')
def meta():
    return {
        'app': 'loop-code-dashboard',
        'version': settings.VERSION,       # ★ 项目版本（来自根 `VERSION` 文件）
        'settings': settings.describe(),
        'pools': core.POOLS,
        'factorFields': factors.FACTOR_FIELDS,
        'endpoints': [
            '/api/health', '/api/meta', '/api/status', '/api/pools',
            '/api/library', '/api/library/{pool}', '/api/selected',
            '/api/strip-bank', '/api/pool-obs/{pool}', '/api/factors/flat',
            '/api/mine/state', '/api/mine/start', '/api/mine/stop',
            '/api/mine/start_pool', '/api/mine/global',
        ],
    }


@app.get('/api/status', summary='池运行状态快照（是否在跑 / 跑多少轮 / 库规模）')
def status(fresh: bool = Query(False, description='true=跳过缓存强制重查进程')):
    if fresh:
        core._CACHE.pop('procs', None)
    return pools.snapshot()


@app.get('/api/pools', summary='池定义（键/名称/指数代码/配色）')
def pool_defs():
    return {'pools': core.POOLS}


@app.get('/api/library', summary='全部池的因子库清单')
def library_all():
    libs = factors.all_libraries()
    return {'libraries': libs,
            'totalFactors': sum(l.get('count') or 0 for l in libs)}


@app.get('/api/library/{pool}', summary='单池因子库清单')
def library_one(pool: str):
    if pool not in core.POOL_KEYS:
        raise HTTPException(404, '未知池: %s（可选 %s）' % (pool, core.POOL_KEYS))
    return factors.library(pool)


@app.get('/api/curves/{pool}/{name}', summary='因子曲线（离线预算，详情页图表用）')
def factor_curves(pool: str, name: str, max_pts: int = Query(700, ge=50, le=3000)):
    if '/' in name or '..' in name:
        raise HTTPException(400, '非法因子名')
    return factors.curves(name, max_pts=max_pts)


@app.get('/api/selected', summary='精选池（L3 双闸门）')
def selected():
    return factors.selected()


@app.get('/api/strip-bank', summary='剥风格评估档（全库）')
def strip_bank():
    return factors.strip_bank()


@app.get('/api/pool-obs/{pool}', summary='池内观测（最近 N 条）')
def pool_obs(pool: str, limit: int = Query(300, ge=1, le=5000)):
    if pool not in core.POOL_KEYS:
        raise HTTPException(404, '未知池: %s' % pool)
    return factors.pool_obs(pool, limit=limit)


@app.get('/api/factors/flat', summary='扁平化因子记录（面向 PG / 看板导入）')
def flat():
    recs = factors.flatten_for_db()
    return {'count': len(recs), 'fields': factors.FACTOR_FIELDS, 'rows': recs}


# ================================================================ 挖掘控制
class StartBody(BaseModel):
    pools: list[str] = []
    rounds: int = 50
    # ★★★ 2026-09-16：把「调度模式 + 面板共享」暴露到看板（能力早在 `run_tracks.py` v1.4.0 里）
    #   ⚠ 全部**可选**；都不传 ⇒ 沿用上次设置；再没有 ⇒ 历史默认（rotate / off）⇒ **默认行为一行不改** ✓
    execMode: str | None = None        # rotate | parallel
    maxParallel: int | None = None     # 仅 parallel
    memPerEngine: float | None = None  # 仅 parallel（GB）
    panelCache: str | None = None      # off | use | build（rotate 也建议 use：载入 28.6s→1.8s）


class StopBody(BaseModel):
    scope: str = 'all'          # all | pool
    pool: str | None = None


@app.get('/api/mine/state', summary='挖掘状态（调度器 / 当前池·代数 / 阶段 / 各池启停）')
def mine_state():
    return mine.state()


@app.post('/api/mine/start', summary='启动调度器（轮转/并行；已在跑则就地更新启用集合与轮数）')
def mine_start(body: StartBody):
    try:
        return mine.start(body.pools, body.rounds, exec_mode=body.execMode,
                          max_parallel=body.maxParallel, mem_per_engine=body.memPerEngine,
                          panel_cache=body.panelCache)
    except mine.MineError as e:
        raise HTTPException(e.code, e.msg)


@app.post('/api/mine/stop', summary='停止。指定池则只停该池；不指定则全部停（随后自动收尾）')
def mine_stop(body: StopBody):
    try:
        pool = body.pool if (body.scope == 'pool' and body.pool) else None
        return mine.stop(pool=pool)
    except mine.MineError as e:
        raise HTTPException(e.code, e.msg)


class PoolBody(BaseModel):
    pool: str


@app.post('/api/mine/start_pool', summary='单独恢复某池（从停止集合移除，下一轮即轮到它）')
def mine_start_pool(body: PoolBody):
    try:
        return mine.start_pool(body.pool)
    except mine.MineError as e:
        raise HTTPException(e.code, e.msg)


@app.post('/api/mine/global', summary='（兼容保留）一次性全局收尾 —— 正常已由调度器每轮自动执行')
def mine_global():
    try:
        return mine.run_global()
    except mine.MineError as e:
        raise HTTPException(e.code, e.msg)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host=settings.BACKEND_HOST,
                port=settings.BACKEND_PORT, reload=settings.BACKEND_RELOAD)
