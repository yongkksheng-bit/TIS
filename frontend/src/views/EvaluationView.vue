<template>
  <div class="evaluation-view">
    <!-- Header -->
    <div class="page-header">
      <h2 class="text-xl font-semibold">智能初筛评估</h2>
      <div class="flex items-center gap-4 mt-2">
        <StatusBadge :status="currentProject?.status || ''" />
        <span class="text-sm text-gray-400">项目编号: {{ projectId }}</span>
      </div>
    </div>

    <!-- Pre-report: generate button -->
    <div v-if="!hasReport && !isGenerating" class="text-center py-16">
      <el-button type="primary" size="large" @click="generateReport">
        开始生成评估报告
      </el-button>
    </div>

    <!-- Loading overlay -->
    <div v-if="isGenerating" class="text-center py-16">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p class="mt-4 text-gray-500">正在生成评估报告...</p>
    </div>

    <!-- Report dashboard (shown after report is generated) -->
    <div v-if="hasReport && !isGenerating">
      <!-- Score dashboard -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <el-card class="score-card">
          <div class="flex items-center gap-4">
            <el-progress type="dashboard" :percentage="qualificationScore" :width="80" :color="scoreColor">
              <template #default>
                <span class="text-xl font-bold">{{ qualificationScore }}</span>
              </template>
            </el-progress>
            <div>
              <p class="font-medium">资质匹配得分</p>
              <p class="text-sm text-gray-500">{{ passCount }}/{{ totalCount }} 项通过</p>
              <p class="text-xs mt-1" :class="scoreLabelColor">{{ scoreLabel }}</p>
            </div>
          </div>
        </el-card>

        <el-card class="score-card">
          <div class="flex items-center gap-4">
            <div class="text-3xl font-bold text-center" style="min-width:80px">{{ timeUrgency }}</div>
            <div>
              <p class="font-medium">时间紧迫度</p>
              <p class="text-sm text-gray-500">距离投标准备</p>
            </div>
          </div>
        </el-card>

        <el-card class="score-card">
          <div class="flex items-center gap-4">
            <div class="text-3xl font-bold text-blue-500 text-center" style="min-width:80px">{{ winProbability }}%</div>
            <div>
              <p class="font-medium">中标概率</p>
              <p class="text-sm text-gray-500">综合评估结果</p>
            </div>
          </div>
        </el-card>
      </div>

      <!-- Main content: two columns -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Left: Qualification table -->
        <el-card class="cert-card">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-medium">资质匹配详情</span>
              <el-tag :type="passRateType" size="small">{{ passRate }}% 通过率</el-tag>
            </div>
          </template>
          <el-table :data="qualifications" stripe>
            <el-table-column prop="cert_name" label="资质名称" min-width="160" />
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="certStatusType(row.status)" size="small" effect="dark">
                  {{ certStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="说明" min-width="120">
              <template #default="{ row }">
                <span class="text-sm text-gray-500">{{ row.notes }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- Right: Specialist initial review (role = specialist/employee) -->
        <el-card v-if="authStore.currentUser.role === 'specialist'" class="approval-card">
          <template #header>
            <span class="font-medium">员工初审</span>
          </template>

          <div>
            <!-- 关系标识（Week 2 锚点 — 必填） -->
            <div class="mb-4">
              <p class="text-sm text-gray-500 mb-2">是否涉及内幕关系？<span class="text-red-400">*</span></p>
              <el-radio-group v-model="specialistRelationInvolved">
                <el-radio value="yes">是（有关系）</el-radio>
                <el-radio value="no">否（无关系）</el-radio>
              </el-radio-group>
              <p v-if="specialistRelationInvolved === 'yes' && !specialistInsiderNotes.trim()" class="text-xs text-red-400 mt-1">
                选择"是"时，下方内幕信息为必填项
              </p>
            </div>

            <div v-if="specialistRelationInvolved === 'yes'" class="mb-4">
              <el-form-item label="内幕与差异化指导" required>
                <el-input
                  v-model="specialistInsiderNotes"
                  type="textarea"
                  :rows="3"
                  placeholder="请填写对该项目内幕的了解、差异化竞争策略..."
                />
              </el-form-item>
            </div>

            <p class="text-sm text-gray-500 mb-4">请选择初审意见：</p>

            <div class="approval-options">
              <div class="approval-option" :class="{ selected: specialistApproval === 'recommend' }" @click="specialistApproval = 'recommend'">
                <el-radio v-model="specialistApproval" value="recommend" class="approval-radio">
                  <div class="option-content">
                    <el-icon :size="32" class="text-green-500"><CircleCheck /></el-icon>
                    <div class="option-text">
                      <p class="font-medium text-green-600">推荐投标</p>
                      <p class="text-xs text-gray-400">由您决定后续操作</p>
                    </div>
                  </div>
                </el-radio>
              </div>

              <div class="approval-option" :class="{ selected: specialistApproval === 'not_recommend' }" @click="specialistApproval = 'not_recommend'">
                <el-radio v-model="specialistApproval" value="not_recommend" class="approval-radio">
                  <div class="option-content">
                    <el-icon :size="32" class="text-red-500"><CircleClose /></el-icon>
                    <div class="option-text">
                      <p class="font-medium text-red-600">不推荐投标</p>
                      <p class="text-xs text-gray-400">终止本项目流程</p>
                    </div>
                  </div>
                </el-radio>
              </div>
            </div>

            <!-- Layer 2: Dynamic notes input based on recommendation -->
            <div v-if="specialistApproval === 'recommend'" class="mt-4">
              <el-form-item label="初审意见（选填）">
                <el-input v-model="specialistNotes" type="textarea" :rows="3" placeholder="选填 — 可补充资质情况、风险提示等..." />
              </el-form-item>
            </div>

            <div v-if="specialistApproval === 'not_recommend'" class="mt-4">
              <el-form-item label="终止原因">
                <el-input v-model="specialistRejectReason" type="textarea" :rows="2" placeholder="请填写终止原因..." />
              </el-form-item>
            </div>

            <!-- Layer 3: Progressive 3-button console (after radio selection) -->
            <div v-if="specialistApproval === 'recommend'" class="mt-4">
              <div class="action-btn-row">
                <el-button type="primary" size="large" style="width: 200px" @click="submitToBoss">
                  <el-icon class="mr-1"><Top /></el-icon>
                  提交老板审批
                </el-button>
                <el-button type="success" size="large" style="width: 200px" @click="directExecute">
                  <el-icon class="mr-1"><CaretRight /></el-icon>
                  自己直接执行
                  <el-tag size="small" type="warning" class="ml-2">越级放行</el-tag>
                </el-button>
                <el-button type="info" size="large" style="width: 200px" @click="showTerminateDialog = true">
                  <el-icon class="mr-1"><Close /></el-icon>
                  终止项目
                </el-button>
              </div>
            </div>

            <div v-if="specialistApproval === 'not_recommend'" class="mt-4">
              <div class="action-btn-row">
                <el-button type="primary" size="large" style="width: 200px" @click="submitToBoss">
                  <el-icon class="mr-1"><Top /></el-icon>
                  提交老板审批
                </el-button>
                <el-button type="danger" size="large" style="width: 200px" :disabled="!specialistRejectReason.trim()" @click="terminateProject">
                  <el-icon class="mr-1"><CircleClose /></el-icon>
                  确认终止项目
                </el-button>
              </div>
            </div>
          </div>
        </el-card>

        <!-- Right: Boss approval -->
        <el-card v-else-if="authStore.currentUser.role === 'boss'" class="approval-card">
          <template #header>
            <span class="font-medium">老板审批</span>
          </template>

          <div>
            <!-- 关系确认 -->
            <div class="relation-confirm mb-4">
              <p class="text-sm text-gray-500 mb-2">是否涉及关联关系？</p>
              <el-radio-group v-model="approvalRelationInvolved">
                <el-radio value="yes">是</el-radio>
                <el-radio value="no">否</el-radio>
              </el-radio-group>
            </div>

            <p class="text-sm text-gray-500 mb-4">请选择审批决策：</p>

            <div class="approval-options">
              <div class="approval-option" :class="{ selected: selectedApproval === 'worthy' }" @click="selectedApproval = 'worthy'">
                <el-radio v-model="selectedApproval" value="worthy" class="approval-radio">
                  <div class="option-content">
                    <el-icon :size="32" class="text-green-500"><CircleCheck /></el-icon>
                    <div class="option-text">
                      <p class="font-medium text-green-600">强锁定战略</p>
                      <p class="text-xs text-gray-400">进入技术标生成流程</p>
                    </div>
                  </div>
                </el-radio>
              </div>

              <div class="approval-option" :class="{ selected: selectedApproval === 'unworthy' }" @click="selectedApproval = 'unworthy'">
                <el-radio v-model="selectedApproval" value="unworthy" class="approval-radio">
                  <div class="option-content">
                    <el-icon :size="32" class="text-red-500"><CircleClose /></el-icon>
                    <div class="option-text">
                      <p class="font-medium text-red-600">放弃投标</p>
                      <p class="text-xs text-gray-400">终止本项目流程</p>
                    </div>
                  </div>
                </el-radio>
              </div>
            </div>

            <div v-if="selectedApproval === 'worthy'" class="mt-4">
              <el-form-item
                label="内幕与差异化指导"
                :required="approvalRelationInvolved === 'yes'"
              >
                <el-input v-model="bossInsiderNotes" type="textarea" :rows="3" :placeholder="approvalRelationInvolved === 'yes' ? '涉及关联关系时必填 — 请填写内幕了解、差异化竞争策略...' : '选填（可不填写）'" />
              </el-form-item>
              <span
                v-if="approvalRelationInvolved === 'yes' && !bossInsiderNotes.trim()"
                class="text-xs text-red-400 mt-1 block"
              >涉及关联关系时，此项为必填项</span>
              <el-form-item label="生成模式" class="mt-2">
                <el-radio-group v-model="selectedMode">
                  <el-radio value="auto">AUTO 流水线</el-radio>
                  <el-radio value="guided">GUIDED 强锁定</el-radio>
                </el-radio-group>
              </el-form-item>
            </div>

            <div v-if="selectedApproval === 'unworthy'" class="mt-4">
              <el-form-item label="终止原因">
                <el-input v-model="terminationReason" type="textarea" :rows="2" placeholder="请填写终止原因..." />
              </el-form-item>
            </div>

            <el-button type="primary" size="large" class="mt-4 w-full" :disabled="!canSubmit" @click="submitApproval">
              确认并提交
            </el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/api/client'
import StatusBadge from '@/components/StatusBadge.vue'
import { Lock, CircleCheck, CircleClose, Loading, Top, CaretRight, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const authStore = useAuthStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const isGenerating = ref(false)
const hasReport = ref(false)

const reportId = ref<number | null>(null)
const qualificationScore = ref(0)
const timeUrgency = ref('—')
const winProbability = ref(0)
const totalCount = ref(0)
const passCount = ref(0)

const qualifications = ref<Array<{ cert_name: string; status: string; notes: string }>>([])

const selectedApproval = ref<'worthy' | 'unworthy' | ''>('')
const approvalRelationInvolved = ref<'yes' | 'no' | ''>('')
const bossInsiderNotes = ref('')
const selectedMode = ref<'auto' | 'guided'>('auto')
const terminationReason = ref('')

const specialistApproval = ref<'recommend' | 'not_recommend' | ''>('')
const specialistNotes = ref('')
const specialistRejectReason = ref('')
const specialistRelationInvolved = ref<'yes' | 'no' | ''>('')
const specialistInsiderNotes = ref('')
const showTerminateDialog = ref(false)

const passRate = computed(() => totalCount.value > 0 ? Math.round((passCount.value / totalCount.value) * 100) : 0)
const passRateType = computed(() => passRate.value >= 75 ? 'success' : passRate.value >= 50 ? 'warning' : 'danger')
const scoreColor = computed(() => qualificationScore.value >= 70 ? '#67c23a' : qualificationScore.value >= 40 ? '#e6a23c' : '#f56c6c')
const scoreLabel = computed(() => qualificationScore.value >= 70 ? '具备投标条件' : qualificationScore.value >= 40 ? '需补充资质' : '资质不足')
const scoreLabelColor = computed(() => qualificationScore.value >= 70 ? 'text-green-500' : qualificationScore.value >= 40 ? 'text-yellow-500' : 'text-red-500')
const canSubmit = computed(() => {
  if (!selectedApproval.value) return false
  if (!approvalRelationInvolved.value) return false
  if (selectedApproval.value === 'worthy' && approvalRelationInvolved.value === 'yes' && !bossInsiderNotes.value.trim()) return false
  if (selectedApproval.value === 'unworthy' && !terminationReason.value.trim()) return false
  return true
})
const canSpecialistSubmit = computed(() => {
  if (!specialistApproval.value) return false
  if (specialistApproval.value === 'not_recommend' && !specialistRejectReason.value.trim()) return false
  return true
})
const canDirectExecute = computed(() => {
  // 选"推荐投标"即可直接执行，初审意见完全选填
  return specialistApproval.value === 'recommend'
})

function certStatusType(status: string) {
  return status === 'pass' ? 'success' : status === 'warning' ? 'warning' : 'danger'
}
function certStatusLabel(status: string) {
  return status === 'pass' ? '通过' : status === 'warning' ? '警告' : '失败'
}

async function generateReport() {
  isGenerating.value = true
  try {
    const result = await apiClient.post(`/v1/projects/${projectId}/evaluations/generate`) as {
      code: number
      message: string
      data: {
        reportId: number
        qualification: {
          qualificationMatchScore: number
          isQualificationPass: boolean
          matchedCerts: Array<{ certName: string; notes: string }>
          missingMandatoryCerts: Array<{ certName: string; reason: string }>
          missingOptionalCerts: Array<{ certName: string; reason: string }>
        }
        time: { daysUntilBidOpen: number; timeUrgencyLevel: string }
        probability: { overallWinProbability: number }
      }
    }
    // result IS the full ResponseWrapper: {code, message, data}
    const d = result.data
    qualificationScore.value = d?.qualification?.qualificationMatchScore ?? 0
    winProbability.value = Math.round((d?.probability?.overallWinProbability ?? 0) * 100)

    // Build cert table
    const matched = d?.qualification?.matchedCerts || []
    const missingMandatory = d?.qualification?.missingMandatoryCerts || []
    const missingOptional = d?.qualification?.missingOptionalCerts || []
    qualifications.value = [
      ...matched.map((c: { certName: string; notes: string }) => ({ cert_name: c.certName, status: 'pass', notes: c.notes || '已核验' })),
      ...missingMandatory.map((c: { certName: string; reason: string }) => ({ cert_name: c.certName, status: 'fail', notes: c.reason === 'expired' ? '已过期' : '缺失' })),
      ...missingOptional.map((c: { certName: string; reason: string }) => ({ cert_name: c.certName, status: 'warning', notes: c.reason === 'expired' ? '即将到期' : '可选缺失' })),
    ]
    totalCount.value = qualifications.value.length
    passCount.value = matched.length

    // Time urgency (toCamelCase converts time_urgency_level → timeUrgencyLevel)
    const urgencyMap: Record<string, string> = {
      urgent: '时间紧张', tight: '时间合理', normal: '时间充裕', relaxed: '时间充裕', expired: '已过期', unknown: '—', low: '时间充裕'
    }
    timeUrgency.value = urgencyMap[d?.time?.timeUrgencyLevel || ''] || '—'

    hasReport.value = true
    reportId.value = d?.reportId ?? null
  } catch (err) {
    ElMessage.error('评估生成失败：' + (err instanceof Error ? err.message : String(err)))
  } finally {
    isGenerating.value = false
  }
}

async function submitApproval() {
  if (!canSubmit.value) return
  if (!reportId.value) {
    ElMessage.error('报告ID不存在，请重新生成评估报告')
    return
  }
  try {
    const action = selectedApproval.value === 'worthy' ? 'approve' : 'reject'
    const overrideReason = selectedApproval.value === 'worthy'
      ? bossInsiderNotes.value
      : terminationReason.value
    await apiClient.post(`/v1/evaluations/${reportId.value}/approve`, {
      action,
      generation_mode: selectedMode.value.toUpperCase(),
      user_id: authStore.currentUser?.id || 1,
      role: authStore.currentUser?.role || 'boss',
      override_reason: overrideReason,
      relationship_flag: approvalRelationInvolved.value === 'yes',
      differentiation_guidance: bossInsiderNotes.value || undefined,
    })
    if (selectedApproval.value === 'worthy') {
      ElMessage.success('审批通过！进入技术标生成流程')
      router.push(`/projects/${projectId}/tech-proposal`)
    } else {
      ElMessage.warning('项目已终止')
      router.push('/')
    }
  } catch (err) {
    ElMessage.error('审批提交失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

// --- Progressive specialist console (3 action paths) ---

async function submitToBoss() {
  if (!reportId.value) {
    ElMessage.error('报告ID不存在，请重新生成评估报告')
    return
  }
  try {
    // First: update relationship flag if changed
    if (specialistRelationInvolved.value) {
      await apiClient.put(`/projects/${projectId}/relationship`, {
        relationship_flag: specialistRelationInvolved.value === 'yes',
        differentiation_guidance: specialistRelationInvolved.value === 'yes' ? specialistInsiderNotes.value : undefined,
      })
    }
    await apiClient.post(`/v1/evaluations/${reportId.value}/approve`, {
      action: 'submit_to_boss',
      generation_mode: 'AUTO',
      user_id: authStore.currentUser?.id || 1,
      role: 'specialist',
      override_reason: specialistNotes.value || undefined,
    })
    ElMessage.success('已提交老板审批')
    router.push('/')
  } catch (err) {
    ElMessage.error('提交失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

async function directExecute() {
  if (!canDirectExecute.value) return
  if (!reportId.value) {
    ElMessage.error('报告ID不存在，请重新生成评估报告')
    return
  }
  try {
    await apiClient.post(`/v1/evaluations/${reportId.value}/approve`, {
      action: 'direct_execute',
      generation_mode: 'AUTO',
      user_id: authStore.currentUser?.id || 1,
      role: 'specialist',
      override_reason: specialistNotes.value || undefined,
    })
    ElMessage.success('已直接放行！跳过老板审批，进入技术标生成')
    router.push(`/projects/${projectId}/tech-proposal`)
  } catch (err) {
    ElMessage.error('执行失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

async function terminateProject() {
  if (!reportId.value) {
    ElMessage.error('报告ID不存在，请重新生成评估报告')
    return
  }
  try {
    await apiClient.post(`/v1/evaluations/${reportId.value}/approve`, {
      action: 'terminate',
      generation_mode: 'AUTO',
      user_id: authStore.currentUser?.id || 1,
      role: 'specialist',
      override_reason: specialistRejectReason.value || '专员终止',
    })
    showTerminateDialog.value = false
    ElMessage.warning('项目已终止')
    router.push('/')
  } catch (err) {
    ElMessage.error('终止失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

onMounted(() => {
  generateReport()
})
</script>

<style scoped>
.evaluation-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.score-card, .cert-card, .approval-card {
  border-radius: 12px;
}
.approval-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.approval-option {
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.approval-option:hover {
  border-color: #409eff;
  background: #f5f7fa;
}
.approval-option.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.approval-radio {
  width: 100%;
}
.action-btn-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.option-content {
  display: flex;
  align-items: center;
  gap: 12px;
}
.option-text p {
  margin: 0;
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
