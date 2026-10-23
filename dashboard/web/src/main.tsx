import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { applyTheme, readTheme } from './theme'
import './styles.css'

// ★ 2026-10-23：渲染前先把皮肤写到 <html data-theme>，否则浅色用户会先闪一帧深色 ✓
applyTheme(readTheme())

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
