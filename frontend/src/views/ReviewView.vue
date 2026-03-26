<template>
  <div class="review-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">项目复盘台</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <p class="text-sm text-gray-500 mt-1">项目编号: {{ projectId }}</p>
    </div>

    <!-- Outcome entry form -->
    <el-card class="entry-card mb-4">
      <template #header>
        <span class="font-medium">结果录入</span>
      </template>

      <el-form label-position="top" class="entry-form">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <el-form-item label="竞标结果" class="outcome-select">
            <el-radio-group v-model="outcomeStatus" class="outcome-radio">
              <el-radio value="win">
                <span class="text-green-600 font-medium">中标</span>
              </el-radio>
              <el-radio value="lose">
                <span class="text-gray-600 font-medium">落标</span>
              </el-radio>
              <el-radio value="disqualified">
                <span class="text-red-600 font-medium">废标</span>
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="我们的报价（元）">
            <el-input-number
              v-model="ourPrice"
              :min="0"
              :step="10000"
              :precision="0"
              controls-position="right"
              class="w-full"
            />
          </el-form-item>

          <el-form-item label="竞争对手报价（元）" v-if="outcomeStatus !== 'win'">
            <el-input-number
              v-model="competitorPrice"
              :min="0"
              :step="10000"
              :precision="0"
              controls-position="right"
              class="w-full"
            />
          </el-form-item>
        </div>

        <el-form-item label="复盘反馈" class="mt-4">
          <el-input
            v-model="feedback"
            type="textarea"
            :rows="3"
            :placeholder="feedbackPlaceholder"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="mt-2"
          :loading="isAnalyzing"
          :disabled="!canSubmit"
          @click="submitAndAnalyze"
        >
          <el-icon v-if="!isAnalyzing" class="mr-1"><Cpu /></el-icon>
          {{ isAnalyzing ? '系统分析中...' : '提交并开始分析' }}
        </el-button>
      </el-form>
    </el-card>

    <!-- Analysis result -->
    <div v-if="analysisResult">
      <!-- Win analysis -->
      <div v-if="outcomeStatus === 'win'">
        <el-card class="result-card">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon color="#67c23a" :size="24"><Trophy /></el-icon>
              <span class="font-medium text-green-600">恭喜中标！系统已提取以下致胜基因</span>
            </div>
          </template>
          <div class="flex flex-col gap-3">
            <div v-for="dna in winningDnas" :key="dna.id" class="dna-card">
              <div class="flex items-start gap-3">
                <el-icon color="#67c23a" :size="20" class="mt-0.5"><Star /></el-icon>
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ dna.type }}</span>
                    <el-tag type="success" size="small">贡献分 {{ dna.score }}</el-tag>
                  </div>
                  <p class="text-sm text-gray-500 mt-1">{{ dna.description }}</p>
                  <p class="text-xs text-gray-400 mt-1">匹配评分项: {{ dna.scoringItem }}</p>
                </div>
              </div>
            </div>
          </div>
          <el-divider />
          <div class="flex items-center gap-4">
            <span class="text-sm text-gray-500">价格策略：</span>
            <el-tag type="success">{{ analysisResult.priceStrategy }}</el-tag>
            <span class="text-sm text-gray-500">折扣率：</span>
            <el-tag type="info">{{ analysisResult.discountRate }}</el-tag>
          </div>
        </el-card>
      </div>

      <!-- Disqualified analysis -->
      <div v-else-if="outcomeStatus === 'disqualified'">
        <el-card class="result-card">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon color="#f56c6c" :size="24"><WarningFilled /></el-icon>
              <span class="font-medium text-red-600">废标分析 — 避坑指南已生成</span>
            </div>
          </template>

          <div v-if="detectedTrap" class="trap-card">
            <div class="flex items-start gap-3">
              <el-icon color="#f56c6c" :size="20" class="mt-0.5"><WarnTriangleFilled /></el-icon>
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-red-600">检测到的致命陷阱</span>
                  <el-tag type="danger" size="small">{{ detectedTrap.category }}</el-tag>
                </div>
                <p class="text-sm text-gray-700 mt-1">{{ detectedTrap.description }}</p>
                <p class="text-xs text-gray-400 mt-2">{{ detectedTrap.occurrenceCount }} 次发生</p>
              </div>
            </div>
          </div>

          <div v-if="isManualError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div class="flex items-center gap-2 text-red-600">
              <el-icon><InfoFilled /></el-icon>
              <span class="font-medium text-sm">人工误判标记</span>
            </div>
            <p class="text-xs text-red-500 mt-1">
              形式审查阶段专员删除了系统警告项，导致本次废标。建议对该专员进行培训。
            </p>
          </div>

          <div class="mt-4">
            <p class="text-sm font-medium mb-2">预防措施建议：</p>
            <div v-for="(suggestion, i) in preventionSuggestions" :key="i" class="flex items-center gap-2 mb-1">
              <el-icon color="#e6a23c"><Check /></el-icon>
              <span class="text-sm text-gray-600">{{ suggestion }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <!-- Lose analysis -->
      <div v-else>
        <el-card class="result-card">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon color="#909399" :size="24"><CircleClose /></el-icon>
              <span class="font-medium text-gray-600">落标分析</span>
            </div>
          </template>
          <div class="flex flex-col gap-3">
            <div class="flex items-center gap-4">
              <div class="text-center">
                <p class="text-xs text-gray-400">我们的报价</p>
                <p class="text-lg font-bold text-gray-600">¥{{ ourPrice?.toLocaleString() }}</p>
              </div>
              <el-divider direction="vertical" />
              <div class="text-center">
                <p class="text-xs text-gray-400">竞争对手报价</p>
                <p class="text-lg font-bold text-green-600">¥{{ competitorPrice?.toLocaleString() }}</p>
              </div>
              <el-divider direction="vertical" />
              <div class="text-center">
                <p class="text-xs text-gray-400">价差</p>
                <p class="text-lg font-bold" :class="priceDiff > 0 ? 'text-red-500' : 'text-green-500'">
                  {{ priceDiff > 0 ? '+' : '' }}{{ priceDiff?.toLocaleString() }}元
                </p>
              </div>
            </div>
            <p class="text-sm text-gray-500 mt-2">{{ analysisResult?.loseAdvice }}</p>
          </div>
        </el-card>
      </div>

      <!-- Action buttons -->
      <div class="mt-4 flex gap-3 justify-center">
        <el-button @click="goBack">返回项目列表</el-button>
        <el-button type="primary" @click="confirmAndClose">
          确认分析结果
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Cpu, Trophy, Star, WarningFilled, WarnTriangleFilled, CircleClose, InfoFilled, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const outcomeStatus = ref<'win' | 'lose' | 'disqualified' | ''>('')
const ourPrice = ref(1450000)
const competitorPrice = ref(1420000)
const feedback = ref('')
const isAnalyzing = ref(false)
const analysisResult = ref<Record<string, unknown> | null>(null)
const winningDnas = ref<Array<{id: number, type: string, score: number, description: string, scoringItem: string}>>([])
const detectedTrap = ref<{category: string, description: string, occurrenceCount: number} | null>(null)
const isManualError = ref(false)
const preventionSuggestions = [
  '在形式审查阶段，将授权书签字检查项设为强制不可删除',
  '每次提交前由第二人复核所有签字页',
  '建立废标案例库，新项目上传时自动关联历史风险项',
]

const feedbackPlaceholder = computed(() => {
  if (outcomeStatus.value === 'disqualified') return '请描述废标原因，例如：授权书第5页缺少法定代表人签字'
  if (outcomeStatus.value === 'lose') return '请描述竞标情况，例如：竞争对手报价更低'
  return '请填写复盘总结...'
})

const canSubmit = computed(() => {
  if (!outcomeStatus.value) return false
  if (!ourPrice.value || ourPrice.value <= 0) return false
  if (outcomeStatus.value !== 'win' && (!competitorPrice.value || competitorPrice.value <= 0)) return false
  return true
})

const priceDiff = computed(() => ourPrice.value - (competitorPrice.value || 0))

async function submitAndAnalyze() {
  if (!canSubmit.value) return
  isAnalyzing.value = true
  await new Promise(r => setTimeout(r, 2500))
  isAnalyzing.value = false

  if (outcomeStatus.value === 'win') {
    winningDnas.value = [
      { id: 1, type: '高分段落策略', score: 9, description: '项目理解章节对业主需求分析透彻，贴近实际运营场景', scoringItem: '2.1 项目背景' },
      { id: 2, type: '应急预案完整性', score: 8, description: '应急预案覆盖了食品安全、配送延误等主要风险点', scoringItem: '2.4 风险管控' },
      { id: 3, type: '案例展示策略', score: 8, description: '列举了15个同类学校食堂配送成功案例，说服力强', scoringItem: '2.3 业绩证明' },
    ]
    analysisResult.value = {
      priceStrategy: '均衡策略（推荐）',
      discountRate: '8.3%',
    }
  } else if (outcomeStatus.value === 'disqualified') {
    detectedTrap.value = {
      category: 'fatal_formal',
      description: '授权委托书第5页缺少法定代表人签字，形式审查不合格',
      occurrenceCount: 3,
    }
    isManualError.value = true
    analysisResult.value = { status: 'analyzed' }
  } else {
    analysisResult.value = {
      loseAdvice: '本次报价略高于竞争对手，建议下次适当下调 5-8% 以提升中标概率。',
    }
  }
}

function confirmAndClose() {
  ElMessage.success('复盘结果已确认，知识库已更新')
  router.push('/')
}

function goBack() {
  router.push('/')
}
</script>

<style scoped>
.review-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.entry-card, .result-card {
  border-radius: 12px;
}
.outcome-radio {
  display: flex;
  gap: 16px;
}
.dna-card, .trap-card {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}
</style>
