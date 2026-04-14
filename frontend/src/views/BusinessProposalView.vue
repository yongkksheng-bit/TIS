<template>
  <div class="business-proposal-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">商务标生成台</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <p v-if="currentProject" class="text-sm text-gray-500 mt-1">
        {{ currentProject.projectName }} · {{ currentProject.ownerUnit }}
      </p>
    </div>

    <!-- 匹配状态概览 -->
    <div class="grid grid-cols-3 gap-4 mb-4">
      <el-card shadow="never" class="stat-card">
        <div class="stat-inner">
          <div class="stat-icon bg-green-100 text-green-600">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-800">{{ matchedCount }}</div>
            <div class="text-xs text-gray-400">已自动匹配</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-inner">
          <div class="stat-icon bg-blue-100 text-blue-600">
            <el-icon><Document /></el-icon>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-800">{{ totalCount }}</div>
            <div class="text-xs text-gray-400">所需资质项</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-inner">
          <div class="stat-icon bg-orange-100 text-orange-600">
            <el-icon><Warning /></el-icon>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-800">{{ pendingCount }}</div>
            <div class="text-xs text-gray-400">待人工确认</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 主内容：商务资质匹配台 -->
    <el-card class="mb-4">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">企业资质自动匹配</span>
          <el-tag type="success" size="small">AI 知识库驱动</el-tag>
        </div>
      </template>

      <el-table :data="credentialItems" stripe style="width: 100%">
        <el-table-column label="状态" width="60" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.status === 'matched'" class="text-green-500 text-lg"><CircleCheck /></el-icon>
            <el-icon v-else-if="row.status === 'pending'" class="text-orange-400 text-lg"><Clock /></el-icon>
            <el-icon v-else class="text-gray-300 text-lg"><CloseBold /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="资质名称" min-width="200" />
        <el-table-column prop="source" label="来源" min-width="160">
          <template #default="{ row }">
            <span v-if="row.source" class="text-gray-600 text-sm">{{ row.source }}</span>
            <span v-else class="text-gray-400 text-sm italic">待匹配</span>
          </template>
        </el-table-column>
        <el-table-column prop="matchType" label="匹配方式" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.matchType === 'auto'" type="success" size="small">自动</el-tag>
            <el-tag v-else-if="row.matchType === 'manual'" type="warning" size="small">人工</el-tag>
            <el-tag v-else type="info" size="small">—</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'matched'" type="success" size="small">已匹配</el-tag>
            <el-tag v-else-if="row.status === 'pending'" type="warning" size="small">待确认</el-tag>
            <el-tag v-else type="danger" size="small">缺失</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'matched'"
              type="primary"
              text
              size="small"
              @click="viewDetail(row)"
            >查看</el-button>
            <el-button
              v-else
              type="primary"
              text
              size="small"
              @click="uploadCredential(row)"
            >上传</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Footer Actions -->
    <div class="footer-action-bar">
      <el-button type="primary" size="large" class="footer-btn" @click="goToPricing">
        <el-icon class="mr-1"><CircleCheck /></el-icon>
        确认商务资质并进入下一步
      </el-button>
      <p class="footer-hint">请确保所有资质项已完成匹配后再进入定价流程</p>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="资质详情" width="500px">
      <div v-if="currentItem" class="detail-body">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="资质名称">{{ currentItem.name }}</el-descriptions-item>
          <el-descriptions-item label="来源">
            <span class="text-green-600">{{ currentItem.source }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="匹配方式">AI 知识库自动匹配</el-descriptions-item>
          <el-descriptions-item label="关联项目">{{ currentProject?.projectName || '—' }}</el-descriptions-item>
          <el-descriptions-item label="有效期">{{ currentItem.expiry || '长期有效' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { CircleCheck, Clock, CloseBold, Document, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const raw = route.params.id
  if (!raw) return NaN
  const parsed = Number(raw)
  return isNaN(parsed) ? NaN : parsed
})

const currentProject = computed(() =>
  projectStore.projects.find(p => p.id === projectId.value)
)

// 商务资质匹配数据（Mock）
const credentialItems = ref([
  {
    id: 1,
    name: '营业执照',
    source: '企业证照库 · 已提取',
    matchType: 'auto',
    status: 'matched',
    expiry: '长期有效',
  },
  {
    id: 2,
    name: '食品经营许可证',
    source: '经营资质库 · 已匹配',
    matchType: 'auto',
    status: 'matched',
    expiry: '2027-08-31',
  },
  {
    id: 3,
    name: '近三年财务审计报告',
    source: '财务报表库 · 已匹配',
    matchType: 'auto',
    status: 'matched',
    expiry: '2024年度',
  },
  {
    id: 4,
    name: 'ISO 9001 质量管理体系认证',
    source: '',
    matchType: 'manual',
    status: 'pending',
    expiry: '—',
  },
  {
    id: 5,
    name: '项目经理执业资格证书',
    source: '人员证书库 · 已匹配',
    matchType: 'auto',
    status: 'matched',
    expiry: '2028-03-15',
  },
  {
    id: 6,
    name: ' HLA 合规声明文件',
    source: '',
    matchType: 'manual',
    status: 'missing',
    expiry: '—',
  },
])


const matchedCount = computed(() => credentialItems.value.filter(i => i.status === 'matched').length)
const pendingCount = computed(() => credentialItems.value.filter(i => i.status !== 'matched').length)
const totalCount = computed(() => credentialItems.value.length)

const detailVisible = ref(false)
const currentItem = ref<typeof credentialItems.value[0] | null>(null)

function viewDetail(row: typeof credentialItems.value[0]) {
  currentItem.value = row
  detailVisible.value = true
}

function uploadCredential(row: typeof credentialItems.value[0]) {
  ElMessage.info(`上传功能开发中：${row.name}`)
}

function goToPricing() {
  router.push(`/projects/${route.params.id}/pricing`)
}

onMounted(async () => {
  if (isNaN(projectId.value)) return
  await projectStore.fetchProjectById(projectId.value)
})
</script>

<style scoped>
.business-proposal-view {
  max-width: 1100px;
}

.page-header {
  margin-bottom: 20px;
}

.stat-card {
  border: 1px solid #f0f0f0;
}

.stat-inner {
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.package-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.package-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  transition: all 0.2s;
}

.package-ready {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.package-pending {
  background: #fff7ed;
  border-color: #fed7aa;
}

.package-icon-wrap {
  flex-shrink: 0;
}

.package-info {
  flex: 1;
}

.package-type {
  font-weight: 600;
  font-size: 14px;
  color: #374151;
}

.package-desc {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.detail-body {
  padding: 8px 0;
}

.footer-action-bar {
  margin-top: 24px;
  padding: 20px 24px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  text-align: center;
}
.footer-btn {
  height: 48px;
  font-size: 16px;
  min-width: 280px;
  background: #409eff;
  border-color: #409eff;
}
.footer-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}
</style>
