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

      <!-- Right: Boss approval -->
      <el-card class="approval-card">
        <template #header>
          <span class="font-medium">老板审批</span>
        </template>

        <div v-if="authStore.currentUser.role !== 'boss'" class="no-boss-notice">
          <el-icon :size="48" class="text-gray-300"><Lock /></el-icon>
          <p class="mt-3 text-gray-500">仅老板可见</p>
        </div>

        <div v-else>
          <p class="text-sm text-gray-500 mb-4">请选择审批决策：</p>

          <div class="approval-options">
            <!-- Option A: Proceed -->
            <div
              class="approval-option"
              :class="{ selected: selectedApproval === 'worthy' }"
              @click="selectedApproval = 'worthy'"
            >
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

            <!-- Option B: Terminate -->
            <div
              class="approval-option"
              :class="{ selected: selectedApproval === 'unworthy' }"
              @click="selectedApproval = 'unworthy'"
            >
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

          <!-- Insider notes (required for Option A) -->
          <div v-if="selectedApproval === 'worthy'" class="mt-4">
            <el-form-item label="内幕与差异化指导" required>
              <el-input
                v-model="bossInsiderNotes"
                type="textarea"
                :rows="3"
                placeholder="请填写老板对该项目的内幕了解、差异化竞争策略..."
              />
            </el-form-item>
            <el-form-item label="生成模式">
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

          <el-button
            type="primary"
            size="large"
            class="mt-4 w-full"
            :disabled="!canSubmit"
            @click="submitApproval"
          >
            确认并提交
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useAuthStore } from '@/stores/authStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Lock, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const authStore = useAuthStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const qualificationScore = ref(72)
const timeUrgency = ref('高')
const winProbability = ref(65)
const totalCount = ref(8)
const passCount = ref(6)

const qualifications = ref([
  { cert_name: '营业执照（有效期内）', status: 'pass', notes: '已核验' },
  { cert_name: '食品安全许可证', status: 'pass', notes: '已核验' },
  { cert_name: 'ISO9001质量体系认证', status: 'pass', notes: '已核验' },
  { cert_name: '近3年类似项目业绩', status: 'warning', notes: '仅2个，偏低' },
  { cert_name: '项目经理资质', status: 'pass', notes: '已核验' },
  { cert_name: '财务报表（最新年度）', status: 'fail', notes: '缺少年报' },
  { cert_name: '社保缴纳证明', status: 'pass', notes: '已核验' },
  { cert_name: '环保资质', status: 'warning', notes: '即将到期' },
])

const selectedApproval = ref<'worthy' | 'unworthy' | ''>('')
const bossInsiderNotes = ref('')
const selectedMode = ref<'auto' | 'guided'>('auto')
const terminationReason = ref('')

const passRate = computed(() => Math.round((passCount.value / totalCount.value) * 100))
const passRateType = computed(() => passRate.value >= 75 ? 'success' : passRate.value >= 50 ? 'warning' : 'danger')
const scoreColor = computed(() => qualificationScore.value >= 70 ? '#67c23a' : qualificationScore.value >= 40 ? '#e6a23c' : '#f56c6c')
const scoreLabel = computed(() => qualificationScore.value >= 70 ? '具备投标条件' : qualificationScore.value >= 40 ? '需补充资质' : '资质不足')
const scoreLabelColor = computed(() => qualificationScore.value >= 70 ? 'text-green-500' : qualificationScore.value >= 40 ? 'text-yellow-500' : 'text-red-500')
const canSubmit = computed(() => {
  if (!selectedApproval.value) return false
  if (selectedApproval.value === 'worthy' && !bossInsiderNotes.value.trim()) return false
  if (selectedApproval.value === 'unworthy' && !terminationReason.value.trim()) return false
  return true
})

function certStatusType(status: string) {
  return status === 'pass' ? 'success' : status === 'warning' ? 'warning' : 'danger'
}
function certStatusLabel(status: string) {
  return status === 'pass' ? '通过' : status === 'warning' ? '警告' : '失败'
}

function submitApproval() {
  if (!canSubmit.value) return
  const project = projectStore.projects.find(p => p.id === projectId)
  if (!project) return

  if (selectedApproval.value === 'worthy') {
    project.status = 'evaluation_ready'
    project.generation_mode = selectedMode.value
    project.boss_insider_notes = bossInsiderNotes.value
    ElMessage.success('审批通过！进入技术标生成流程')
    router.push(`/projects/${projectId}/tech-proposal`)
  } else {
    project.status = 'terminated_by_boss'
    ElMessage.warning('项目已终止')
    router.push('/')
  }
}
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
