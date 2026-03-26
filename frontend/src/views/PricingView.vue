<template>
  <div class="pricing-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">定价博弈沙盘</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <p class="text-sm text-gray-500 mt-1">项目预算：¥{{ formatMoney(budgetLimit) }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Left: Cost analysis -->
      <div class="flex flex-col gap-4">
        <!-- Cost breakdown -->
        <el-card class="cost-card">
          <template #header>
            <span class="font-medium">成本明细分析</span>
          </template>
          <div class="flex flex-col gap-3">
            <div v-for="item in costItems" :key="item.label" class="cost-item">
              <span class="text-sm text-gray-600">{{ item.label }}</span>
              <span class="font-medium">¥{{ item.value.toLocaleString() }}</span>
            </div>
            <el-divider class="my-2" />
            <div class="cost-item font-bold text-lg">
              <span>总成本</span>
              <span class="text-blue-600">¥{{ totalCost.toLocaleString() }}</span>
            </div>
          </div>
        </el-card>

        <!-- Game theory scenarios -->
        <el-card class="scenario-card">
          <template #header>
            <span class="font-medium">博弈论建议报价</span>
          </template>
          <div class="flex flex-col gap-3">
            <div class="scenario-item bg-green-50 border border-green-200 rounded-lg p-3">
              <div class="flex justify-between items-center">
                <span class="text-sm font-medium text-green-700">保守策略（高利润）</span>
                <span class="text-green-600 font-bold">¥{{ recommendedHigh.toLocaleString() }}</span>
              </div>
              <p class="text-xs text-green-500 mt-1">利润率 {{ highMargin }}% · 中标概率 {{ lowWinProb }}%</p>
            </div>
            <div class="scenario-item bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div class="flex justify-between items-center">
                <span class="text-sm font-medium text-blue-700">均衡策略（推荐）</span>
                <span class="text-blue-600 font-bold">¥{{ recommendedMid.toLocaleString() }}</span>
              </div>
              <p class="text-xs text-blue-500 mt-1">利润率 {{ midMargin }}% · 中标概率 {{ midWinProb }}%</p>
            </div>
            <div class="scenario-item bg-orange-50 border border-orange-200 rounded-lg p-3">
              <div class="flex justify-between items-center">
                <span class="text-sm font-medium text-orange-700">激进策略（抢市场）</span>
                <span class="text-orange-600 font-bold">¥{{ recommendedLow.toLocaleString() }}</span>
              </div>
              <p class="text-xs text-orange-500 mt-1">利润率 {{ lowMargin }}% · 中标概率 {{ highWinProb }}%</p>
            </div>
          </div>
        </el-card>
      </div>

      <!-- Right: Boss decision -->
      <el-card class="decision-card">
        <template #header>
          <span class="font-medium">老板最终报价</span>
        </template>

        <div v-if="authStore.currentUser.role !== 'boss'" class="no-boss-notice">
          <el-icon :size="48" class="text-gray-300"><Lock /></el-icon>
          <p class="mt-3 text-gray-500">仅老板可填写最终报价</p>
        </div>

        <div v-else>
          <el-form label-position="top">
            <el-form-item label="最终报价（元）">
              <el-input-number
                v-model="finalPrice"
                :min="0"
                :step="10000"
                :precision="0"
                :controls="false"
                size="large"
                class="price-input"
                :class="{ 'price-warning': priceWarning }"
              />
              <div v-if="priceWarning" class="mt-2">
                <el-alert :type="priceWarningType" :closable="false" show-icon>
                  <template #title>
                    {{ priceWarning }}
                  </template>
                </el-alert>
              </div>
            </el-form-item>

            <el-form-item label="决策说明">
              <el-input
                v-model="decisionNotes"
                type="textarea"
                :rows="3"
                placeholder="请填写定价决策依据..."
              />
            </el-form-item>
          </el-form>

          <div class="mt-4">
            <el-button type="primary" size="large" class="w-full" :disabled="!canSubmit" @click="submitPricing">
              确认最终报价
            </el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useAuthStore } from '@/stores/authStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const authStore = useAuthStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const budgetLimit = 1500000
const costItems = [
  { label: '食材成本', value: 600000 },
  { label: '人工成本', value: 300000 },
  { label: '物流成本', value: 150000 },
  { label: '管理费用', value: 100000 },
  { label: '其他费用', value: 50000 },
]
const totalCost = costItems.reduce((sum, item) => sum + item.value, 0)
const recommendedHigh = Math.round(totalCost * 1.25)
const recommendedMid = Math.round(totalCost * 1.15)
const recommendedLow = Math.round(totalCost * 1.08)
const highMargin = 20
const midMargin = 15
const lowMargin = 8
const highWinProb = 75
const midWinProb = 60
const lowWinProb = 40

const finalPrice = ref(recommendedMid)
const decisionNotes = ref('')

const priceWarning = computed(() => {
  if (finalPrice.value < totalCost) return '⚠️ 报价低于成本，将造成亏损！'
  if (finalPrice.value > budgetLimit) return '⚠️ 报价超出预算上限！'
  return ''
})
const priceWarningType = computed(() => finalPrice.value < totalCost ? 'danger' : 'warning')
const canSubmit = computed(() => finalPrice.value > 0 && (!priceWarning.value || priceWarning.value.includes('超出')))

function formatMoney(amount: number): string {
  return amount.toLocaleString()
}

function submitPricing() {
  const project = projectStore.projects.find(p => p.id === projectId)
  if (project) {
    project.status = 'awaiting_review'
    ElMessage.success(`最终报价 ¥${finalPrice.value.toLocaleString()} 已确认！进入形式审查`)
  }
  router.push(`/projects/${projectId}/formal-review`)
}
</script>

<style scoped>
.pricing-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.cost-card, .scenario-card, .decision-card {
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
.no-boss-notice {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #c0c4cc;
}
</style>
