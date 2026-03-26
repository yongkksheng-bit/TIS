<template>
  <div class="formal-review-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">形式审查清单</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
    </div>

    <!-- Status summary -->
    <el-card class="summary-card mb-4">
      <div class="flex items-center gap-6">
        <div class="flex items-center gap-2">
          <span class="text-2xl font-bold text-green-500">{{ confirmedCount }}</span>
          <span class="text-sm text-gray-500">已确认</span>
        </div>
        <el-divider direction="vertical" />
        <div class="flex items-center gap-2">
          <span class="text-2xl font-bold text-yellow-500">{{ warningCount }}</span>
          <span class="text-sm text-gray-500">警告</span>
        </div>
        <el-divider direction="vertical" />
        <div class="flex items-center gap-2">
          <span class="text-2xl font-bold text-red-500">{{ fatalCount }}</span>
          <span class="text-sm text-gray-500">致命风险</span>
        </div>
        <div class="flex-1" />
        <div v-if="canGenerate" class="flex items-center gap-2 text-green-500">
          <el-icon><CircleCheck /></el-icon>
          <span class="text-sm font-medium">可生成最终标书</span>
        </div>
        <div v-else class="flex items-center gap-2 text-red-500">
          <el-icon><CircleClose /></el-icon>
          <span class="text-sm font-medium">存在未处理风险项</span>
        </div>
      </div>
    </el-card>

    <!-- Checklist by category -->
    <div v-for="category in reviewCategories" :key="category.key" class="category-section mb-4">
      <el-card class="category-card">
        <template #header>
          <div class="flex items-center gap-2">
            <el-icon :size="20" :color="category.color"><component :is="category.icon" /></el-icon>
            <span class="font-medium">{{ category.label }}</span>
            <el-tag :type="category.count === category.confirmed ? 'success' : 'warning'" size="small" class="ml-2">
              {{ category.confirmed }}/{{ category.count }}
            </el-tag>
          </div>
        </template>

        <el-table :data="category.items">
          <el-table-column prop="check_title" label="检查项" min-width="200" />
          <el-table-column prop="reference" label="参考条款" width="120">
            <template #default="{ row }">
              <span class="text-xs text-gray-400">{{ row.reference }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="system_status" label="系统结果" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="systemStatusType(row.system_status)" size="small" effect="dark">
                {{ systemStatusLabel(row.system_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="specialist_status" label="专员确认" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.specialist_status === 'confirmed'" type="success" size="small">
                已确认
              </el-tag>
              <el-tag v-else-if="row.specialist_status === 'corrected'" type="warning" size="small">
                已修正
              </el-tag>
              <el-tag v-else-if="row.specialist_status === 'deleted'" type="info" size="small">
                已删除
              </el-tag>
              <span v-else class="text-gray-400 text-sm">待处理</span>
            </template>
          </el-table-column>
          <el-table-column prop="risk_level" label="风险" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.risk_level === 'fatal'" type="danger" size="small" effect="dark">致命</el-tag>
              <el-tag v-else-if="row.risk_level === 'warning'" type="warning" size="small">警告</el-tag>
              <el-tag v-else type="info" size="small">提示</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <div class="flex gap-1 justify-center">
                <el-button size="small" type="success" @click="confirmItem(row)">确认</el-button>
                <el-button size="small" type="warning" @click="correctItem(row)">修正</el-button>
                <el-button size="small" type="danger" @click="deleteItem(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Generate button -->
    <div class="mt-6 flex justify-center">
      <el-button
        type="primary"
        size="large"
        class="generate-btn"
        :loading="isGenerating"
        :disabled="!canGenerate"
        @click="generateFinalDocument"
      >
        <el-icon v-if="!isGenerating" class="mr-1"><Document /></el-icon>
        {{ isGenerating ? '正在生成最终标书...' : '生成最终标书' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { CircleCheck, CircleClose, Document, Check, Warning, CircleCheckFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const isGenerating = ref(false)

const reviewItems = ref([
  // 资质有效性
  { id: 1, category: 'qualification', check_title: '营业执照有效期核验', reference: '§3.1.1', system_status: 'passed', specialist_status: 'confirmed', risk_level: 'fatal' },
  { id: 2, category: 'qualification', check_title: '食品安全许可证核验', reference: '§3.1.2', system_status: 'passed', specialist_status: 'confirmed', risk_level: 'fatal' },
  { id: 3, category: 'qualification', check_title: '近3年业绩证明', reference: '§3.1.3', system_status: 'warning', specialist_status: 'pending', risk_level: 'warning' },
  // 签字盖章
  { id: 4, category: 'signature', check_title: '授权委托书签字完整性', reference: '§4.2.1', system_status: 'failed', specialist_status: 'pending', risk_level: 'fatal' },
  { id: 5, category: 'signature', check_title: '法定代表人签字', reference: '§4.2.2', system_status: 'passed', specialist_status: 'pending', risk_level: 'fatal' },
  // 技术标完整性
  { id: 6, category: 'tech_integrity', check_title: '技术方案章节齐全', reference: '§5.1', system_status: 'passed', specialist_status: 'confirmed', risk_level: 'info' },
  { id: 7, category: 'tech_integrity', check_title: '评分项逐项对应', reference: '§5.2', system_status: 'passed', specialist_status: 'pending', risk_level: 'warning' },
  // 报价合规性
  { id: 8, category: 'price', check_title: '报价不超过预算上限', reference: '§6.1', system_status: 'passed', specialist_status: 'pending', risk_level: 'fatal' },
  // 封装检查
  { id: 9, category: 'packaging', check_title: '投标文件密封完好', reference: '§7.1', system_status: 'passed', specialist_status: 'pending', risk_level: 'fatal' },
  { id: 10, category: 'packaging', check_title: '页码连续无缺页', reference: '§7.2', system_status: 'warning', specialist_status: 'pending', risk_level: 'warning' },
])

const reviewCategories = computed(() => {
  const cats = [
    { key: 'qualification', label: '资质有效性', icon: CircleCheck, color: '#67c23a' },
    { key: 'signature', label: '签字盖章', icon: Check, color: '#409eff' },
    { key: 'tech_integrity', label: '技术标完整性', icon: Document, color: '#909399' },
    { key: 'price', label: '报价合规性', icon: CircleCheckFilled, color: '#e6a23c' },
    { key: 'packaging', label: '封装检查', icon: Warning, color: '#f56c6c' },
  ]
  return cats.map(c => {
    const items = reviewItems.value.filter(i => i.category === c.key)
    return {
      ...c,
      items,
      count: items.length,
      confirmed: items.filter(i => ['confirmed', 'corrected', 'deleted'].includes(i.specialist_status)).length,
    }
  })
})

const confirmedCount = computed(() => reviewItems.value.filter(i => ['confirmed', 'corrected', 'deleted'].includes(i.specialist_status)).length)
const warningCount = computed(() => reviewItems.value.filter(i => i.specialist_status === 'pending' && i.system_status === 'warning').length)
const fatalCount = computed(() => reviewItems.value.filter(i => i.risk_level === 'fatal' && !['confirmed', 'corrected', 'deleted'].includes(i.specialist_status)).length)
const canGenerate = computed(() => fatalCount.value === 0)

function systemStatusType(status: string) {
  return status === 'passed' ? 'success' : status === 'warning' ? 'warning' : 'danger'
}
function systemStatusLabel(status: string) {
  return status === 'passed' ? '通过' : status === 'warning' ? '警告' : '失败'
}

function confirmItem(row: typeof reviewItems.value[0]) {
  row.specialist_status = 'confirmed'
  ElMessage.success(`「${row.check_title}」已确认`)
}
function correctItem(row: typeof reviewItems.value[0]) {
  row.specialist_status = 'corrected'
  ElMessage.success(`「${row.check_title}」已修正`)
}
function deleteItem(row: typeof reviewItems.value[0]) {
  row.specialist_status = 'deleted'
  ElMessage.warning(`「${row.check_title}」已删除`)
}

async function generateFinalDocument() {
  if (!canGenerate.value) return
  isGenerating.value = true
  await new Promise(r => setTimeout(r, 2500))
  isGenerating.value = false
  const project = projectStore.projects.find(p => p.id === projectId)
  if (project) {
    project.status = 'completed'
    ElMessage.success('最终标书生成成功！')
  }
  router.push(`/projects/${projectId}/output`)
}
</script>

<style scoped>
.formal-review-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.summary-card, .category-card {
  border-radius: 12px;
}
.category-section :deep(.el-card__header) {
  padding: 12px 20px;
}
.generate-btn {
  width: 280px;
  height: 48px;
  font-size: 16px;
}
</style>
