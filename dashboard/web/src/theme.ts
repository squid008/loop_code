import { useCallback, useEffect, useState } from 'react'

/**
 * 皮肤（深色 / 浅色）切换 —— 纯前端，不改后端。
 *
 * ★ 2026-10-23（用户：把 DataCausal 的浅色皮肤搞过来，我们也要两种皮肤）——
 *   移植自 `E:\datacausal\dashboard\web\src\theme.ts`（同一套设计）。
 *
 * 设计要点：
 *   ① **唯一落点 = `<html data-theme="...">`** ⇒ 所有配色都写在 `styles.css` 的变量里，
 *      换皮肤只换变量、不动组件 ✓（组件里不许出现写死颜色，否则浅色下必然花 ✗）
 *   ② **记在 localStorage**（键 `lc-theme`）⇒ 刷新/重开浏览器保持上次选择 ✓
 *   ③ `color-scheme` 一并设 ⇒ 原生控件（滚动条、下拉框、复选框）跟着变 ✓
 *   ④ **首屏不闪**：`main.tsx` 在渲染前调用一次 `applyTheme(readTheme())` ✓
 */
export type ThemeMode = 'dark' | 'light'

const KEY = 'lc-theme'

export function readTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* 隐私模式/禁用存储时忽略，回落到默认 */
  }
  return 'dark' // 默认仍是原来的深色（用户已习惯）
}

export function applyTheme(mode: ThemeMode) {
  const el = document.documentElement
  el.dataset.theme = mode
  el.style.colorScheme = mode
}

export function useTheme(): [ThemeMode, () => void] {
  const [mode, setMode] = useState<ThemeMode>(readTheme)

  // 首次挂载时同步一次（main.tsx 已设过，这里兜底，防止热更新丢了属性）
  useEffect(() => { applyTheme(mode) }, [mode])

  const toggle = useCallback(() => {
    setMode(prev => {
      const next: ThemeMode = prev === 'dark' ? 'light' : 'dark'
      applyTheme(next)
      try { localStorage.setItem(KEY, next) } catch { /* 存不了就算了 */ }
      return next
    })
  }, [])

  return [mode, toggle]
}
