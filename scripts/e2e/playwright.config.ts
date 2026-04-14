import { defineConfig, devices } from '@playwright/test'
import path from 'path'

/**
 * Playwright 配置 — TIS 招投标系统 E2E 测试基线
 *
 * 目标 URL: http://localhost:3000 （Docker port mapping: 3000:80）
 * 后端 API:  http://localhost:8000 （直连，用于 debug）
 *
 * 测试哲学：
 * - 每步操作后等待 networkidle，避免竞态导致的"愚蠢失败"
 * - AI 生成类操作（评估/技术标）给予 90s 超时宽限
 * - 所有断言基于 DOM 可观测状态，不依赖内部 API 响应体
 */
export default defineConfig({
  testDir: path.join(__dirname, 'tests'),

  /* ── 全局超时策略 ───────────────────────────────────────── */
  timeout: 90_000,        // 每个 test case 90s（覆盖 AI 生成等待）
  expect: {
    timeout: 30_000,      // 断言等待（表单项出现/消失）
  },

  /* ── 全局报告与录像 ──────────────────────────────────── */
  reporter: [
    ['html', { outputFolder: 'test-results/report' }],
    ['list'],              // CI 友好输出
  ],

  use: {
    baseURL: 'http://localhost:3000',

    // 截图/录像：仅失败时保留（减少磁盘占用）
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',

    // Trace Viewer：本地 debug 用
    trace: 'on-first-retry',

    // 跳过自动等待，让测试显式控制节奏
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  /* ── 全局 teardown ────────────────────────────────────── */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // 如需 Firefox 多浏览器兼容，取消下方注释：
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
  ],
})
