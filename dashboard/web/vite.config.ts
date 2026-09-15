import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

/**
 * ★★★ 端口抽象的关键：本文件从 `dashboard/config.json` **读**端口，不写死。
 *
 * 用户要求（2026-09-15）：「端口注意万一将来项目多了，要可以改哈，抽象出来，
 *   **只改一个地方**就好，别多个文件都把端口号写死进去了」
 *
 * 三层解耦：
 *   ① `dashboard/config.json`  —— **唯一**端口来源
 *   ② 后端 `api/app/settings.py` 读它；本文件也读它（设 proxy）
 *   ③ 前端业务代码**只请求相对路径 `/api/*`** ⇒ 它甚至不知道端口 ✓
 *
 * ⇒ 要改端口，**只改 `config.json` 一处**，前后端一起变 ✓
 */
const cfgPath = path.resolve(__dirname, '..', 'config.json')
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'))
const backend = cfg.backend ?? {}
const frontend = cfg.frontend ?? {}
const API_TARGET = `http://${backend.host ?? '127.0.0.1'}:${backend.port ?? 8101}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: frontend.host ?? '127.0.0.1',
    port: frontend.port ?? 5273,
    strictPort: true, // 端口被占就直接报错（别静默换端口，否则与 config.json 不一致）
    open: frontend.open ?? false,
    proxy: {
      // ★ 前端只认这个前缀，永远不知道后端真实端口
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
