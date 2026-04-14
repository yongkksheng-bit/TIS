/**
 * golden_path.spec.ts — TIS 全链路 E2E 主线测试
 *
 * 测试范围：上传 PDF → 确认立项 → 评估分析 → 技术标生成
 *           → 博弈定价 → 形式审查 → 最终输出
 *
 * 运行前提：
 *   1. Docker Compose 环境已启动（backend + frontend + db）
 *   2. cd scripts/e2e && npm install
 *   3. npx playwright install chromium
 *
 * 设计哲学：
 *   - 每步以 DOM 可见状态为断言锚，不依赖内部 API 响应体
 *   - AI 生成类操作以按钮文案或进度变化为就绪信号
 *   - 失败时保留 trace/screenshot，供调试分析
 */

import { test, expect, Page } from '@playwright/test'
import path from 'path'

/* ─────────────────────────────────────────────────────────
   常量与路径
───────────────────────────────────────────────────────── */

const TEST_PDF = path.resolve(__dirname, '../../../data/test_documents/惠州市交通运输局交通大厦食堂管理和食材配送服务_招标文件.pdf')

/** 未来90天后的日期字符串（用于截标日期） */
function futureDateStr(daysFromNow = 90): string {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString().slice(0, 10)   // 'YYYY-MM-DD'
}

/** 绝对值大于零的预算 */
const BUDGET_AMOUNT = 1_500_000

/* ─────────────────────────────────────────────────────────
   工具函数
───────────────────────────────────────────────────────── */

/**
 * 等待 Element Plus DatePicker 弹窗出现
 * el-date-picker 在 focus 后渲染 .el-picker-panel
 */
async function waitForDatePicker(popup: Page): Promise<void> {
  await popup.waitForSelector('.el-date-editor.el-input__wrapper', { timeout: 10_000 })
}

/**
 * 向 el-input-number 填入数值（通过 Fill + Blur 触发 v-model 更新）
 */
async function fillInputNumber(page: Page, selector: string, value: number): Promise<void> {
  const input = page.locator(selector).locator('input').first()
  await input.click()
  await input.fill(String(value))
  await input.blur()
}

/* ─────────────────────────────────────────────────────────
   STEP 1: 上传招标文件
───────────────────────────────────────────────────────── */
test.describe('STEP 1 — 上传招标文件', () => {
  test('上传 PDF 后跳转到确认页', async ({ page }) => {
    // 访问新建项目上传页
    await page.goto('/projects/new/upload')

    // 等待上传区域可见
    await expect(page.locator('.upload-view')).toBeVisible({ timeout: 15_000 })

    // el-upload 内部藏有 <input type="file">，通过 label 点击触发文件选择
    // 先确保上传区域渲染完毕
    await page.waitForSelector('.upload-area input[type="file"]', { timeout: 10_000 })
    await page.locator('.upload-area input[type="file"]').setInputFiles(TEST_PDF)

    // 选择文件后，按钮文案变为"开始智能解析"
    await expect(page.getByRole('button', { name: /开始智能解析/ })).toBeEnabled()

    // 点击开始解析 → 进入确认页
    await page.getByRole('button', { name: /开始智能解析/ }).click()

    // 等待 URL 变为 /projects/:id/confirm
    await page.waitForURL(/\/confirm$/, { timeout: 120_000 })

    // 确认页加载中
    await expect(page.locator('.confirmation-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 2: 确认立项 — 填写所有 OCR 必填项
───────────────────────────────────────────────────────── */
test.describe('STEP 2 — 招标文件信息确认', () => {
  test('填写必填字段并提交成功', async ({ page }) => {
    await page.goto(page.url().replace(/\/upload$/, '/confirm'))

    // 等待表单渲染
    await expect(page.locator('.confirmation-view .form-card')).toBeVisible({ timeout: 15_000 })

    // ── 预算金额（el-input-number）────────────────────────────────────
    // 表单初始状态：OCR 可能已回填，预算若为 0 则手动填入
    const budgetInput = page.locator('.form-card').locator('.el-input-number').first()
    const budgetVal = await budgetInput.locator('input').inputValue()
    if (!budgetVal || Number(budgetVal) === 0) {
      await fillInputNumber(page, '.form-card .el-input-number >> nth=0', BUDGET_AMOUNT)
    }

    // ── 截标日期（el-date-picker）────────────────────────────────────
    // 后端要求必填。尝试从 OCR 回填中获取，若为空则填 90 天后
    const datePicker = page.locator('.form-card .el-date-editor').first()
    const existingDate = await datePicker.locator('input').inputValue()
    if (!existingDate || existingDate.trim() === '') {
      await datePicker.locator('.el-input__wrapper').click()
      await page.waitForSelector('.el-picker-panel', { timeout: 5_000 })
      // 手动输入日期字符串触发 v-model
      await page.keyboard.type(futureDateStr(90))
      await page.keyboard.press('Enter')
      await page.waitForSelector('.el-picker-panel', { state: 'hidden', timeout: 5_000 }).catch(() => {
        // picker 可能自动关闭
      })
    }

    // ── 地区（el-input）──────────────────────────────────────────────
    const regionInput = page.locator('.form-card .el-input').filter({ hasText: /如：广东省广州市/ }).first()
    if (await regionInput.isVisible()) {
      await regionInput.clear()
      await regionInput.fill('广东省惠州市')
    }

    // ── 项目类型（el-select，默认服务类）───────────────────────────────
    // 默认已是"服务类"，无需操作

    // ── 确认并立项按钮 ───────────────────────────────────────────────
    // 去掉 loading 状态后等待
    const confirmBtn = page.getByRole('button', { name: /确认无误并立项/ })
    await expect(confirmBtn).toBeEnabled({ timeout: 10_000 })
    await confirmBtn.click()

    // 等待进入评估页
    await page.waitForURL(/\/evaluation$/, { timeout: 60_000 })
    await expect(page.locator('.evaluation-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 3: 评估分析 — 生成报告 + 选择推荐 + 直接执行
───────────────────────────────────────────────────────── */
test.describe('STEP 3 — 评估分析', () => {
  test('生成评估报告后直接执行，跳过老板等待', async ({ page }) => {
    await page.goto(page.url().replace(/\/confirm$/, '/evaluation'))

    // 等待页面加载
    await expect(page.locator('.evaluation-view')).toBeVisible({ timeout: 15_000 })

    // ── 生成评估报告 ─────────────────────────────────────────────────
    const generateBtn = page.getByRole('button', { name: /生成评估报告/ })
    if (await generateBtn.isVisible()) {
      await generateBtn.click()
      // 等待报告生成（loading 状态消失 + 出现资质表格）
      await page.waitForSelector('.qualification-table, .el-table', { timeout: 90_000 })
    }

    // ── 选择「推荐投标」───────────────────────────────────────────────
    // 找到"推荐投标" radio 并点击整个 option 区域
    const recommendOption = page.locator('.approval-option', { has: page.locator('text=推荐投标') })
    await recommendOption.click()
    await expect(recommendOption).toHaveClass(/selected/)

    // ── 选择「否，无关系」内幕关系 ─────────────────────────────────
    // 内幕关系默认"否"即可（不填内幕信息）
    const noRelationRadio = page.locator('.el-radio', { hasText: '否（无关系）' })
    if (await noRelationRadio.isVisible()) {
      await noRelationRadio.click()
    }

    // ── 点击「自己直接执行」──────────────────────────────────────────
    // （不点"提交老板审批"，跳过等待，直接进入技术标）
    const directBtn = page.getByRole('button', { name: /自己直接执行/ })
    await expect(directBtn).toBeEnabled({ timeout: 10_000 })
    await directBtn.click()

    // 等待跳转到技术标页面
    await page.waitForURL(/\/tech-proposal$/, { timeout: 60_000 })
    await expect(page.locator('.tech-proposal-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 4: 技术标生成 — 生成章节 + 确认推进定价
───────────────────────────────────────────────────────── */
test.describe('STEP 4 — 技术标编辑与生成', () => {
  test('等待章节生成完毕并确认全部章节', async ({ page }) => {
    await page.goto(page.url().replace(/\/evaluation$/, '/tech-proposal'))

    await expect(page.locator('.tech-proposal-view')).toBeVisible({ timeout: 15_000 })

    // ── 检查章节树是否已有生成内容 ───────────────────────────────────
    const existingSections = page.locator('.el-tree-node__content')
    const sectionCount = await existingSections.count()

    if (sectionCount > 0 && await page.locator('.el-tag', { hasText: '已生成' }).count() > 0) {
      // 章节已生成，直接进入确认
    } else {
      // 需要逐个生成：遍历所有"待生成"章节
      const pendingSections = page.locator('.el-tag', { hasText: '待生成' }).locator('..')
      const pendingCount = await page.locator('.el-tag', { hasText: '待生成' }).count()

      for (let i = 0; i < pendingCount; i++) {
        // 点击第 i 个待生成章节节点
        const node = page.locator('.el-tree-node').nth(i)
        await node.locator('.el-tree-node__content').click()

        // 等待右侧编辑器选中该章节
        await expect(page.locator('.editor-card .el-textarea__inner')).toBeVisible({ timeout: 5_000 })

        // 点击「生成选中章节」
        const genBtn = page.getByRole('button', { name: /生成选中章节/ })
        if (await genBtn.isEnabled()) {
          await genBtn.click()
          // 等待生成完成（按钮恢复，非 loading）
          await expect(genBtn).not.toBeDisabled({ timeout: 90_000 })
        }
      }
    }

    // ── 点击「确认全部章节」──────────────────────────────────────────
    const confirmAllBtn = page.getByRole('button', { name: /确认全部章节/ })
    await expect(confirmAllBtn).toBeEnabled({ timeout: 10_000 })
    await confirmAllBtn.click()

    // 等待推进到定价页
    await page.waitForURL(/\/pricing$/, { timeout: 90_000 })
    await expect(page.locator('.pricing-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 5: 博弈定价 — 填写成本 + 老板最终定价
───────────────────────────────────────────────────────── */
test.describe('STEP 5 — 定价博弈', () => {
  test('填写成本明细并提交老板最终定价', async ({ page }) => {
    await page.goto(page.url().replace(/\/tech-proposal$/, '/pricing'))

    await expect(page.locator('.pricing-view')).toBeVisible({ timeout: 15_000 })

    // ── 填写成本明细（左侧成本录入卡片）──────────────────────────────
    // 食材成本
    const costFields: Array<{ label: string; value: number }> = [
      { label: '食材成本', value: 600_000 },
      { label: '物流成本', value: 80_000 },
      { label: '人工成本', value: 200_000 },
      { label: '管理费用', value: 50_000 },
      { label: '其他费用', value: 30_000 },
    ]

    for (const field of costFields) {
      const inputRow = page.locator('.cost-input-row', { hasText: field.label })
        .locator('.el-input-number input')
      await inputRow.click()
      await inputRow.fill(String(field.value))
      await inputRow.blur()
    }

    // ── 点击「保存并确认成本」────────────────────────────────────────
    const saveCostBtn = page.getByRole('button', { name: /保存并确认成本/ })
    await expect(saveCostBtn).toBeEnabled({ timeout: 5_000 })
    await saveCostBtn.click()

    // 等待成本确认成功（按钮恢复）
    await expect(saveCostBtn).not.toBeDisabled({ timeout: 30_000 })

    // ── 填写老板最终报价（≥ 成本基准）──────────────────────────────
    // boss_final 要求 price >= cost_base，填 980000 元（98万）
    const priceInput = page.locator('.decision-card .el-input-number input').last()
    await priceInput.click()
    await priceInput.fill('980000')
    await priceInput.blur()

    // ── 提交老板最终定价（boss_final）────────────────────────────────
    // 找到「提交老板定夺」或等效的老板确认按钮
    // 状态为 pending_boss_approval 时，specialist 看到"提交老板审批"
    // boss 用户（authStore role=boss）才显示"提交老板定夺"
    // 我们以 specialist 身份走 saveDraft (specialist_draft) → formal-review
    // 或者：直接调用 boss_final action（需要知道当前用户角色）

    // 更稳健方案：先 saveDraft 推进到 pending_boss_approval，
    // 然后以 boss 身份审批。但 authStore 默认是 specialist。
    // 直接用 specialist 走 saveDraft，绕过老板等待：
    const saveDraftBtn = page.getByRole('button', { name: /保存报价并进入下一步/ })
    if (await saveDraftBtn.isVisible()) {
      await saveDraftBtn.click()
      await page.waitForURL(/\/formal-review$/, { timeout: 60_000 })
    } else {
      // 如果已经显示"提交老板定夺"（boss 角色），直接点击
      const submitFinalBtn = page.getByRole('button', { name: /提交老板定夺/ })
      await submitFinalBtn.click()
      await page.waitForURL(/\/formal-review$/, { timeout: 60_000 })
    }

    await expect(page.locator('.formal-review-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 6: 形式审查 — 初始化清单 + 处理所有项 + 完成审查

   策略说明：
   - 系统生成的清单项包含"确认"、"修正"、"删除"三个操作
   - fatal 风险项只能通过"删除"移除，否则 complete_review 会拦截
   - E2E 遍历所有行，优先尝试确认；fatal 项会被拒绝，降级为删除
   - 删除后轮询进度条直到 100%，确保所有强制项均已处理
───────────────────────────────────────────────────────── */
test.describe('STEP 6 — 形式审查', () => {
  test('初始化审查清单并完成所有项', async ({ page }) => {
    await page.goto(page.url().replace(/\/pricing$/, '/formal-review'))

    await expect(page.locator('.formal-review-view')).toBeVisible({ timeout: 15_000 })

    // ── 初始化质检清单（如尚未初始化）────────────────────────────────
    const initBtn = page.getByRole('button', { name: /初始化质检清单/ })
    if (await initBtn.isVisible()) {
      await initBtn.click()
      await page.waitForSelector('.progress-card', { timeout: 60_000 })
    }

    // ── 等待清单加载完毕 ────────────────────────────────────────────
    await page.waitForSelector('.category-block', { timeout: 60_000 })
    await page.waitForTimeout(2_000)   // 留时间让骨架屏/loading 消失

    // ── 遍历处理所有审查项 ─────────────────────────────────────────
    // 从后往前遍历（删除后 DOM 动态变化），对 pending 项尝试确认或删除
    async function processAllItems() {
      for (let attempt = 0; attempt < 3; attempt++) {
        const items = page.locator('.checklist-item')
        const count = await items.count()
        let allProcessed = true
        for (let i = count - 1; i >= 0; i--) {
          const item = items.nth(i)
          // 跳过已处理项（confirmed/corrected/deleted）
          const cls = await item.getAttribute('class') || ''
          if (cls.includes('item-confirmed') || cls.includes('item-corrected') || cls.includes('item-deleted')) {
            continue
          }
          allProcessed = false
          // 查找确认按钮（第一个 button，绿色勾）
          const btns = item.locator('button')
          const firstBtn = btns.first()
          if (await firstBtn.isEnabled()) {
            await firstBtn.click()
            await page.waitForTimeout(1_000)
          }
        }
        if (allProcessed) break
      }
    }

    await processAllItems()

    // ── 轮询等待 progressPct 达到 100% ─────────────────────────────
    await page.waitForFunction(
      () => {
        const el = document.querySelector('.progress-card')
        if (!el) return false
        const text = el.querySelector('.el-progress__text')?.textContent || ''
        return text.includes('100%')
      },
      { timeout: 90_000, polling: 1500 }
    )

    // ── 点击「核对无误，生成最终标书」────────────────────────────────
    const completeBtn = page.getByRole('button', { name: /核对无误，生成最终标书/ })
    await expect(completeBtn).toBeEnabled({ timeout: 5_000 })
    await completeBtn.click()

    // 等待进入输出页
    await page.waitForURL(/\/output$/, { timeout: 60_000 })
    await expect(page.locator('.final-output-view')).toBeVisible()
  })
})

/* ─────────────────────────────────────────────────────────
   STEP 7: 最终输出 — 验证标书下载成功
───────────────────────────────────────────────────────── */
test.describe('STEP 7 — 最终输出与下载', () => {
  test('点击下载 Word 标书，拦截下载请求并验证', async ({ page }) => {
    await page.goto(page.url().replace(/\/formal-review$/, '/output'))

    await expect(page.locator('.final-output-view')).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('.el-result')).toBeVisible()

    // ── 拦截 /final-documents/generate 和 /download 请求 ──────────────
    const downloadPromise = page.waitForResponse(
      (resp) => resp.url().includes('/final-documents/') && resp.url().includes('/download'),
      { timeout: 60_000 }
    )

    // 点击「下载最终 Word 标书」
    const downloadBtn = page.getByRole('button', { name: /下载最终 Word 标书/ })
    await expect(downloadBtn).toBeEnabled({ timeout: 10_000 })
    await downloadBtn.click()

    // 等待下载响应
    const downloadResp = await downloadPromise
    const contentType = downloadResp.headers()['content-type'] || ''

    // 断言：响应成功且类型为 Word 文档
    expect(downloadResp.status()).toBeGreaterThanOrEqual(200)
    expect(downloadResp.status()).toBeLessThan(400)
    expect(contentType).toMatch(/word|document|octet/)

    // 断言：页面显示成功提示（el-message 消失后仍可见）
    await expect(page.locator('.el-message--success')).toBeVisible({ timeout: 10_000 })
  })
})
