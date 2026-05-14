<template>
  <div class="pricing-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">定价博弈沙盘</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <p class="text-sm text-gray-500 mt-1">项目预算：¥{{ formatMoney(budgetLimit || 0) }}</p>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <el-icon class="is-loading text-4xl text-blue-500"><Loading /></el-icon>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <!-- ═══════════════ 左列：系统只读（成本+博弈论） ═══════════════ -->
        <div class="flex flex-col gap-4">
          <!-- 成本明细 — 永远只读，系统预估展示 -->
          <el-card class="cost-card">
            <template #header>
              <span class="font-medium">成本明细分析</span>
              <el-tag type="info" size="small" class="ml-2">系统预估</el-tag>
            </template>
            <div class="flex flex-col gap-3">
              <div v-for="item in costItems" :key="item.label" class="cost-item">
                <span class="text-sm text-gray-600">{{ item.label }}</span>
                <span class="font-medium">{{ item.value > 0 ? '¥' + formatMoney(item.value) : '--' }}</span>
              </div>
              <el-divider class="my-2" />
              <div class="cost-item font-bold text-lg">
                <span>总成本</span>
                <span class="text-blue-600">{{ aiTotalCost > 0 ? '¥' + formatMoney(aiTotalCost) : '--' }}</span>
              </div>
            </div>
          </el-card>

          <!-- 博弈论建议报价 -->
          <el-card class="scenario-card">
            <template #header>
              <span class="font-medium">博弈论建议报价</span>
            </template>
            <div class="flex flex-col gap-3">
              <div
                v-for="s in scenarios"
                :key="s.scenario"
                class="scenario-item border rounded-lg p-3 cursor-pointer transition-all hover:shadow-md"
                :class="[scenarioClass(s), selectedScenario === s.scenario ? 'ring-2 ring-offset-1' : '']"
                @click="selectScenario(s)"
              >
                <div class="flex justify-between items-center">
                  <div>
                    <span class="text-sm font-medium" :class="scenarioTextClass(s)">{{ s.label }}</span>
                    <el-tag v-if="s.is_recommended" type="success" size="small" class="ml-2">推荐</el-tag>
                    <el-tag v-if="selectedScenario === s.scenario" type="primary" size="small" class="ml-2">已选择</el-tag>
                  </div>
                  <span class="font-bold" :class="scenarioTextClass(s)">¥{{ formatMoney(Number(s.price)) }}</span>
                </div>
                <p class="text-xs mt-1" :class="scenarioSubClass(s)">
                  利润率 {{ costBase > 0 ? ((s.profit / costBase) * 100).toFixed(2) : '—' }}% ·
                  中标概率 {{ isNaN(s.win_prob) ? '--' : Number(s.win_prob * 100).toFixed(0) }}% ·
                  期望收益 {{ isNaN(s.expected_value) ? '--' : '¥' + formatMoney(Number(s.expected_value)) }}
                </p>
              </div>
            </div>
          </el-card>
        </div>

        <!-- ═══════════════ 右列：人工录入（成本+定价） ═══════════════ -->
        <div class="flex flex-col gap-4">
          <!-- 成本录入卡片 — 始终可编辑 -->
          <el-card class="cost-entry-card">
            <template #header>
              <span class="font-medium">成本明细录入</span>
              <el-tag type="warning" size="small" class="ml-2">可随时修改</el-tag>
            </template>

            <div class="flex flex-col gap-3">
              <div class="flex justify-between items-center cost-input-row">
                <span class="cost-input-label">食材成本</span>
                <el-input-number v-model="foodCost" :min="0" :step="1000" :precision="0" :controls="false" placeholder="0" class="cost-input-number" />
              </div>
              <div class="flex justify-between items-center cost-input-row">
                <span class="cost-input-label">物流成本</span>
                <el-input-number v-model="logisticsCost" :min="0" :step="1000" :precision="0" :controls="false" placeholder="0" class="cost-input-number" />
              </div>
              <div class="flex justify-between items-center cost-input-row">
                <span class="cost-input-label">人工成本</span>
                <el-input-number v-model="laborCost" :min="0" :step="1000" :precision="0" :controls="false" placeholder="0" class="cost-input-number" />
              </div>
              <div class="flex justify-between items-center cost-input-row">
                <span class="cost-input-label">管理费用</span>
                <el-input-number v-model="managementCost" :min="0" :step="1000" :precision="0" :controls="false" placeholder="0" class="cost-input-number" />
              </div>
              <div class="flex justify-between items-center cost-input-row">
                <span class="cost-input-label">其他费用</span>
                <el-input-number v-model="otherCost" :min="0" :step="1000" :precision="0" :controls="false" placeholder="0" class="cost-input-number" />
              </div>
              <el-divider class="my-2" />
              <div class="cost-item font-bold text-lg">
                <span>总成本（预览）</span>
                <span class="text-blue-600">¥{{ formatMoney(totalCostPreview) }}</span>
              </div>
              <div class="flex justify-end gap-2 mt-2">
                <el-button type="primary" :disabled="!canSaveCost" @click="saveAndConfirmCost">
                  <el-icon class="mr-1"><Check /></el-icon>
                  保存并确认成本
                </el-button>
              </div>
            </div>
          </el-card>

          <!-- 定价操作卡片 -->
          <el-card class="decision-card">
            <template #header>
              <span class="font-medium">
                {{ isBoss ? '老板最终报价' : '我的报价方案' }}
              </span>
            </template>

            <el-form label-position="top">
              <el-form-item label="报价金额（元）">
                <el-input-number
                  v-model="inputPrice"
                  :min="0"
                  :step="100"
                  :precision="2"
                  :controls="false"
                  size="large"
                  placeholder="0"
                  class="price-input"
                  :class="{ 'price-warning': priceWarning, 'price-danger': (inputPrice ?? 0) < costBase }"
                />
                <div v-if="priceWarning" class="mt-2">
                  <el-alert :type="priceWarningType" :closable="false" show-icon>
                    <template #title>{{ priceWarning }}</template>
                  </el-alert>
                </div>
              </el-form-item>

              <el-form-item
                v-if="costBase > 0 && selectedScenarioPrice > 0 && inputPrice != null && inputPrice > 0"
                :label="Math.abs(deviationPct ?? 0) < 0.0001 ? '与系统建议价匹配' : '偏离系统建议价'"
              >
                <el-tag v-if="Math.abs(deviationPct ?? 0) < 0.0001" type="success">完全一致</el-tag>
                <el-tag v-else :type="(deviationPct ?? 0) > 0.05 ? 'warning' : 'success'">
                  {{ (deviationPct ?? 0) > 0 ? '+' : '' }}{{ ((deviationPct ?? 0) * 100).toFixed(1) }}%
                </el-tag>
                <span class="text-xs text-gray-400 ml-2">当前基准价 ¥{{ formatMoney(selectedScenarioPrice) }}</span>
              </el-form-item>

              <!-- Specialist draft preview (shown to boss on pending_boss_approval) -->
              <div v-if="isBoss && specialistPrice" class="specialist-preview">
                <el-alert type="info" :closable="false" show-icon>
                  <template #title>
                    专员建议价：¥{{ formatMoney(specialistPrice) }}
                    <span v-if="specialistNotes" class="text-gray-500 text-xs"> — {{ specialistNotes }}</span>
                  </template>
                </el-alert>
              </div>
            </el-form>
          </el-card>
        </div>

      </div>

      <!-- Bottom dual-track action bar -->
      <div class="action-bar">
        <div class="action-bar-inner">
          <el-button size="large" class="btn-secondary" @click="saveDraft">
            <el-icon class="mr-1"><DocumentChecked /></el-icon>
            保存报价并进入下一步
          </el-button>
          <el-button type="primary" size="large" class="btn-primary" :disabled="!canSubmit" @click="submitToBoss">
            <el-icon class="mr-1"><UserFilled /></el-icon>
            提交老板定夺
          </el-button>
        </div>
        <p class="action-hint">
          <span v-if="costBase <= 0">请先在右侧填写并确认成本估算，才能进行定价</span>
          <span v-else-if="!isBoss">保存后可随时修改，提交后进入等待老板审批阶段</span>
          <span v-else>作为老板，您可以直接确认最终报价，或退回给专员修改</span>
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useAuthStore } from '@/stores/authStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Loading, DocumentChecked, UserFilled, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '@/api/client'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const authStore = useAuthStore()

// Reactive projectId — derived from route so it updates if route changes
const projectId = computed(() => {
  const raw = route.params.id
  if (!raw) return NaN
  const parsed = Number(raw)
  return isNaN(parsed) ? NaN : parsed
})

onMounted(() => {
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    loading.value = false
    return
  }
  loadDashboard()
})

const loading = ref(true)
const costBase = ref(0)
const budgetLimit = ref<number | null>(null)
const scenarios = ref<any[]>([])
const systemOptimal = ref(0)
// selectedScenarioPrice: dynamic benchmark — tracks the price of the currently selected scenario card.
// Changes every time the user clicks a different scenario on the left.
// Used as the denominator in deviationPct so deviation is relative to the SELECTED scenario, not always conservative.
const selectedScenarioPrice = ref(0)
const specialistPrice = ref<number | null>(null)
const specialistNotes = ref<string | null>(null)
const inputPrice = ref<number | undefined>(undefined)
const selectedScenario = ref<string | null>(null)

// Cost estimation state
// aiCostBreakdown: pure AI-estimated cost breakdown for the left READ-ONLY card.
// Must NEVER be derived from the right panel's manually entered values.
const aiCostBreakdown = ref<Record<string, number>>({})
const confirmedBreakdown = ref<Record<string, number>>({})
const foodCost = ref<number | undefined>(undefined)
const logisticsCost = ref<number | undefined>(undefined)
const laborCost = ref<number | undefined>(undefined)
const managementCost = ref<number | undefined>(undefined)
const otherCost = ref<number | undefined>(undefined)
const pendingEstimateId = ref<number | null>(null)
const savingCost = ref(false)

// Direct v-model bindings — no computed wrapper (avoids Vue diffing instability)
const totalCostPreview = computed(() =>
  (foodCost.value ?? 0) +
  (logisticsCost.value ?? 0) +
  (laborCost.value ?? 0) +
  (managementCost.value ?? 0) +
  (otherCost.value ?? 0)
)

const canSaveCost = computed(() => totalCostPreview.value > 0)

const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId.value))
const isBoss = computed(() => authStore.currentUser.role === 'boss')

// Left READ-ONLY card: pure AI estimated cost breakdown.
// source of truth is aiCostBreakdown — must NEVER mirror the right-panel manual inputs.
const costItems = computed(() => [
  {
    label: '食材成本',
    value: aiCostBreakdown.value['food_cost'] ?? 0,
  },
  {
    label: '人工成本',
    value: aiCostBreakdown.value['labor_cost'] ?? 0,
  },
  {
    label: '物流成本',
    value: aiCostBreakdown.value['logistics_cost'] ?? 0,
  },
  {
    label: '管理费用',
    value: aiCostBreakdown.value['management_cost'] ?? 0,
  },
  {
    label: '其他费用',
    value: aiCostBreakdown.value['other_cost'] ?? 0,
  },
])

// aiTotalCost: sum of AI-estimated cost breakdown for left READ-ONLY total display.
// Must NEVER use right-panel costBase.
const aiTotalCost = computed(() =>
  (aiCostBreakdown.value['food_cost'] ?? 0) +
  (aiCostBreakdown.value['logistics_cost'] ?? 0) +
  (aiCostBreakdown.value['labor_cost'] ?? 0) +
  (aiCostBreakdown.value['management_cost'] ?? 0) +
  (aiCostBreakdown.value['other_cost'] ?? 0)
)

const priceWarning = computed(() => {
  const price = inputPrice.value ?? 0
  if (price <= 0) return ''
  if (price < costBase.value) return '报价低于成本，将造成亏损！'
  if (budgetLimit.value && price > budgetLimit.value) return '报价超出预算上限！'
  return ''
})
const priceWarningType = computed(() => (inputPrice.value ?? 0) < costBase.value ? 'danger' : 'warning')

const deviationPct = computed(() => {
  if (!selectedScenarioPrice.value || inputPrice.value == null) return null
  return (inputPrice.value - selectedScenarioPrice.value) / selectedScenarioPrice.value
})

const canSubmit = computed(() => {
  if (costBase.value <= 0) return false
  if ((inputPrice.value ?? 0) <= 0) return false
  if ((inputPrice.value ?? 0) < costBase.value) return false  // allow zero-profit (===), block loss-making
  return true
})

function formatMoney(amount: number | undefined | null): string {
  if (amount == null) return '--'
  return amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function scenarioClass(s: any): string {
  if (s.risk_level === 'high') return 'bg-orange-50 border-orange-200 hover:border-orange-400'
  if (s.risk_level === 'low') return 'bg-green-50 border-green-200 hover:border-green-400'
  return 'bg-blue-50 border-blue-200 hover:border-blue-400'
}

function scenarioTextClass(s: any): string {
  if (s.risk_level === 'high') return 'text-orange-700'
  if (s.risk_level === 'low') return 'text-green-700'
  return 'text-blue-700'
}

function scenarioSubClass(s: any): string {
  if (s.risk_level === 'high') return 'text-orange-500'
  if (s.risk_level === 'low') return 'text-green-500'
  return 'text-blue-500'
}

function selectScenario(s: any) {
  selectedScenario.value = s.scenario
  selectedScenarioPrice.value = Number(s.price)  // sync benchmark — THIS is the fix
  inputPrice.value = Number(s.price)
}

async function loadDashboard() {
  try {
    // ── Step A: Always hydrate right-panel inputs FIRST ──
    // This breaks the old deadlock: we no longer gate cost-fetch on costBase > 0.
    // The cost API will 404 when no confirmed estimate exists, which is fine.
    try {
      const costResp = await apiClient.get(`/api/v1/projects/${projectId.value}/cost-estimates/current`) as any
      // Axios interceptor returns response.data → camelCased ResponseWrapper {code:200, data:{foodCost:10000,...}}
      // costResp = ResponseWrapper, costResp.data = inner payload object
      const payload = (costResp as any).data ?? {}
      // Interceptor converts snake_case → camelCase, so use camelCase keys
      // Never use || 0 — a missing field must stay undefined so el-input-number shows placeholder
      const food = payload.foodCost != null ? Number(payload.foodCost) : undefined
      const log = payload.logisticsCost != null ? Number(payload.logisticsCost) : undefined
      const lab = payload.laborCost != null ? Number(payload.laborCost) : undefined
      const mgmt = payload.managementCost != null ? Number(payload.managementCost) : undefined
      const oth = payload.otherCost != null ? Number(payload.otherCost) : undefined

      // Hydrate right-panel input fields for edit continuity (right panel = manual specialist input)
      foodCost.value = food
      logisticsCost.value = log
      laborCost.value = lab
      managementCost.value = mgmt
      otherCost.value = oth

      // costBase drives scenarios + priceWarning on the RIGHT panel only.
      // Left card uses aiCostBreakdown (all 0 until an AI cost-analysis API exists).
      costBase.value = (food ?? 0) + (log ?? 0) + (lab ?? 0) + (mgmt ?? 0) + (oth ?? 0)
    } catch {
      // No confirmed cost estimate yet — explicitly reset right-panel inputs to undefined
      // so el-input-number shows placeholder instead of forced 0
      foodCost.value = undefined
      logisticsCost.value = undefined
      laborCost.value = undefined
      managementCost.value = undefined
      otherCost.value = undefined
      costBase.value = 0
      // aiCostBreakdown stays as-is (all 0) — no AI analysis API has populated it
    }

    // ── Step B: Fetch dashboard (scenarios, budget, system-optimal price) ──
    const resp = await apiClient.get(`/api/v1/projects/${projectId.value}/pricing-dashboard`) as any
    const data = (resp as any).data || resp
    budgetLimit.value = data.budget_limit ? Number(data.budget_limit) : null
    scenarios.value = data.scenarios || []

    if (scenarios.value.length > 0) {
      const recommended = scenarios.value.find((s: any) => s.is_recommended)
      if (recommended) {
        systemOptimal.value = Number(recommended.price)
        selectedScenarioPrice.value = Number(recommended.price)
        // Only auto-fill inputPrice if user hasn't already set one locally
        if (!inputPrice.value) {
          inputPrice.value = Number(recommended.price)
        }
        selectedScenario.value = recommended.scenario
      } else {
        systemOptimal.value = Number(scenarios.value[0]?.price) || 0
        selectedScenarioPrice.value = Number(scenarios.value[0]?.price) || 0
      }
    }

    // Load existing pricing decision (specialist draft or boss final)
    await loadExistingDecision()
  } catch (err) {
    console.warn('Failed to load pricing dashboard:', err)
  } finally {
    loading.value = false
  }
}

async function refreshScenarios() {
  try {
    const resp = await apiClient.get(`/api/v1/projects/${projectId.value}/pricing-dashboard`) as any
    const data = (resp as any).data || resp
    budgetLimit.value = data.budget_limit ? Number(data.budget_limit) : null
    scenarios.value = data.scenarios || []

    if (scenarios.value.length > 0) {
      const recommended = scenarios.value.find((s: any) => s.is_recommended)
      if (recommended) {
        systemOptimal.value = Number(recommended.price)
        selectedScenarioPrice.value = Number(recommended.price)
        if (!inputPrice.value) {
          inputPrice.value = Number(recommended.price)
        }
        selectedScenario.value = recommended.scenario
      } else {
        systemOptimal.value = Number(scenarios.value[0]?.price) || 0
        selectedScenarioPrice.value = Number(scenarios.value[0]?.price) || 0
      }
    }
  } catch (err) {
    console.warn('Failed to refresh scenarios:', err)
  }
}

async function loadExistingDecision() {
  try {
    // Refresh project from store to get latest status
    await projectStore.fetchProjectById(projectId.value)
    const proj = currentProject.value
    // If specialist has already submitted a draft, inputPrice is pre-filled from
    // the scenarios (systemOptimal) by loadDashboard above — no override needed here.
    // Boss sees specialist's draft via the specialistPrice field below.
    if (proj?.status === 'pending_boss_approval') {
      // Specialist draft was submitted; boss can see specialist price in the
      // specialist-preview alert. inputPrice stays as systemOptimal for now.
      specialistPrice.value = inputPrice.value ?? null
    }
  } catch (err) {
    // Non-critical
  }
}

async function saveAndConfirmCost() {
  if (!canSaveCost.value || savingCost.value) return
  savingCost.value = true
  try {
    // Step 1: Create new cost estimate version (backend auto-increments version_number)
    const createResp = await apiClient.post(`/api/v1/projects/${projectId.value}/cost-estimates`, {
      food_cost: foodCost.value ?? 0,
      logistics_cost: logisticsCost.value ?? 0,
      labor_cost: laborCost.value ?? 0,
      management_cost: managementCost.value ?? 0,
      other_cost: otherCost.value ?? 0,
      estimate_reason: '专员录入',
    }) as { data: { id: number } }

    const estimateId = (createResp as any).data?.id ?? (createResp as any).id
    if (!estimateId) throw new Error('成本估算创建失败，未返回ID')

    // Step 2: Confirm it immediately
    await apiClient.post(`/api/v1/cost-estimates/${estimateId}/confirm`)

    ElMessage.success('成本已保存并确认')

    // Step 3: Targeted refresh — only refresh scenarios, do NOT re-fetch confirmed
    // cost estimate (which would overwrite the input refs we just saved).
    // After confirm, the confirmed cost is exactly what the user just entered,
    // so we simply re-compute costBase from local refs and pull fresh scenarios.
    const confirmed = foodCost.value ?? 0 + (logisticsCost.value ?? 0) + (laborCost.value ?? 0) + (managementCost.value ?? 0) + (otherCost.value ?? 0)
    costBase.value = confirmed
    // Do NOT write confirmedBreakdown — left card must NEVER mirror right panel inputs
    await refreshScenarios()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '成本确认失败，请重试'
    ElMessage.error(msg)
  } finally {
    savingCost.value = false
  }
}

async function saveDraft() {
  await callUpsert('specialist_draft', '报价已保存')
}

async function submitToBoss() {
  await callUpsert('submit_to_boss', '已提交老板定夺，等待老板审批')
}

async function callUpsert(action: 'specialist_draft' | 'submit_to_boss' | 'boss_final', successMsg: string) {
  try {
    const payload: Record<string, any> = {
      action_type: action,
      price: inputPrice.value,
    }
    const resp = await apiClient.put(`/api/v1/projects/${projectId.value}/pricing-decisions`, payload) as any
    const data = (resp as any).data || resp

    ElMessage.success(successMsg)

    // Update local project status
    const idx = projectStore.projects.findIndex(p => p.id === projectId.value)
    if (idx !== -1) {
      projectStore.projects[idx].status = data.new_project_status
    }

    // Navigate accordingly
    if (action === 'specialist_draft') {
      router.push(`/projects/${projectId.value}/formal-review`)
    } else if (action === 'submit_to_boss' && isBoss.value) {
      // Boss submitted → go to formal review
      router.push(`/projects/${projectId.value}/formal-review`)
    } else if (data.newProjectStatus === 'pending_boss_approval') {
      // Specialist submitted → stay or go to dashboard
      router.push('/dashboard')
    } else if (data.newProjectStatus === 'formal_review') {
      router.push(`/projects/${projectId.value}/formal-review`)
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '操作失败，请重试'
    ElMessage.error(msg)
  }
}
</script>

<style scoped>
.pricing-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  padding-bottom: 120px;
}
.page-header {
  margin-bottom: 24px;
}
.cost-card, .scenario-card, .decision-card, .cost-entry-card {
  border-radius: 12px;
}
.cost-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.price-input {
  width: 100%;
}
.price-input :deep(.el-input__inner) {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}
.price-warning :deep(.el-input__inner) {
  color: #e6a23c;
}
.price-danger :deep(.el-input__inner) {
  color: #f56c6c;
}
.specialist-preview {
  margin-top: 12px;
}
.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-top: 1px solid #e4e7ed;
  box-shadow: 0 -4px 16px rgba(0,0,0,0.08);
  z-index: 100;
  padding: 16px 24px;
}
.action-bar-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
.btn-secondary {
  min-width: 180px;
}
.btn-primary {
  min-width: 160px;
}
.action-hint {
  max-width: 1200px;
  margin: 8px auto 0;
  text-align: right;
  font-size: 12px;
  color: #909399;
}
.cost-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cost-input-label {
  width: 80px;
  font-size: 14px;
  color: #606266;
  flex-shrink: 0;
}
.cost-input-number {
  width: 140px;
}
.cost-input-number :deep(.el-input__inner) {
  text-align: center;
  font-weight: 600;
}
</style>
