<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-gray-800">项目列表</h1>
        <p class="text-sm text-gray-500 mt-1">共 {{ projectStore.projects.length }} 个项目</p>
      </div>
      <!-- 右侧状态栏：回收站 + 三个统计数字 + 新建项目 -->
      <div class="flex gap-4 items-center">
        <!-- 回收站按钮：醒目红色，在"进行中"最左侧 -->
        <el-button type="danger" plain size="default" @click="router.push('/trash')">
          <el-icon class="mr-1"><Delete /></el-icon>
          回收站
        </el-button>

        <!-- 状态过滤器 + 数字，同一水平线，居中对齐 -->
        <div class="flex gap-3 items-center">
          <div
            v-for="stat in statusStats"
            :key="stat.key"
            class="stat-item"
          >
            <span class="stat-label">{{ stat.label }}</span>
            <span class="stat-value">{{ stat.value }}</span>
          </div>
        </div>

        <el-divider direction="vertical" class="!mx-1" />

        <el-button type="primary" size="default" @click="router.push('/projects/new/upload')">
          <el-icon class="mr-1"><Plus /></el-icon>
          新建项目
        </el-button>
      </div>
    </div>

    <!-- Filter tabs -->
    <div class="flex gap-2 mb-6">
      <el-tag
        v-for="tab in statusTabs"
        :key="tab.value"
        :type="activeTab === tab.value ? 'primary' : 'info'"
        class="cursor-pointer"
        @click="activeTab = tab.value"
      >
        {{ tab.label }} ({{ countByTab(tab.value) }})
      </el-tag>
    </div>

    <!-- Project grid -->
    <div
      v-if="filteredProjects.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    >
      <ProjectCard
        v-for="project in filteredProjects"
        :key="project.id"
        :project="project"
        class="cursor-pointer"
        @click="handleCardClick"
        @delete="handleDelete"
        @clone="handleClone"
      />
    </div>

    <!-- Empty state -->
    <el-empty v-else description="暂无项目" class="my-12" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import ProjectCard, { type Project } from '@/components/ProjectCard.vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { apiClient } from '@/api/client'

const router = useRouter()
const projectStore = useProjectStore()
const activeTab = ref('all')

// ─── 状态映射字典（互斥枚举）────────────────────────────────────────────────
// 待处理 (Pending)：AI 预处理阶段，尚未进入人类实质性工作流
const PENDING_STATUSES = new Set(['created', 'uploaded', 'parsing'])

// 进行中 (In Progress)：人类专家已介入，正在进行审核与正文生成
const IN_PROGRESS_STATUSES = new Set([
  'parsed', 'evaluating', 'evaluation_ready',
  'pending_boss_approval', 'approved_by_specialist',
  'generating_documents', 'awaiting_pricing', 'awaiting_review',
])

// 已完成 (Completed)
const COMPLETED_STATUSES = new Set(['completed'])

// 废弃/终止（不显示在列表，也不计入任何 Tab）
const DISCARDED_STATUSES = new Set(['discarded', 'terminated_by_boss'])

const statusTabs = [
  { label: '全部',    value: 'all' },
  { label: '待处理',  value: 'pending' },
  { label: '进行中',  value: 'in_progress' },
  { label: '已完成',  value: 'completed' },
]

// ─── 统计数字（Header 右侧）───────────────────────────────────────────────
const statusStats = computed(() => [
  { key: 'pending',     label: '待处理',  value: countByTab('pending') },
  { key: 'in_progress', label: '进行中',  value: countByTab('in_progress') },
  { key: 'completed',   label: '已完成',  value: countByTab('completed') },
])

function countByTab(tab: string): number {
  if (tab === 'all') {
    return projectStore.projects.filter(p => !DISCARDED_STATUSES.has(p.status)).length
  }
  if (tab === 'pending') {
    return projectStore.projects.filter(p => PENDING_STATUSES.has(p.status)).length
  }
  if (tab === 'in_progress') {
    return projectStore.projects.filter(p => IN_PROGRESS_STATUSES.has(p.status)).length
  }
  if (tab === 'completed') {
    return projectStore.projects.filter(p => COMPLETED_STATUSES.has(p.status)).length
  }
  return 0
}

const filteredProjects = computed(() => {
  if (activeTab.value === 'all') {
    return projectStore.projects.filter(p => !DISCARDED_STATUSES.has(p.status))
  }
  if (activeTab.value === 'pending') {
    return projectStore.projects.filter(p => PENDING_STATUSES.has(p.status))
  }
  if (activeTab.value === 'in_progress') {
    return projectStore.projects.filter(p => IN_PROGRESS_STATUSES.has(p.status))
  }
  if (activeTab.value === 'completed') {
    return projectStore.projects.filter(p => COMPLETED_STATUSES.has(p.status))
  }
  return projectStore.projects.filter(p => !DISCARDED_STATUSES.has(p.status))
})

// ─── 路由分发（基于状态）─────────────────────────────────────────────────
function handleCardClick(project: Project) {
  switch (project.status) {
    // Week 1 上传解析 → 确认页面
    case 'created':
    case 'uploaded':
    case 'parsing':
      router.push(`/projects/${project.id}/confirm`)
      break

    // Week 2 评估审核
    case 'parsed':
    case 'evaluating':
    case 'evaluation_ready':
    case 'pending_boss_approval':
    case 'approved_by_specialist':
      router.push(`/projects/${project.id}/evaluation`)
      break

    // Week 3 技术标生成
    case 'generating_documents':
      router.push(`/projects/${project.id}/tech-proposal`)
      break

    // Week 3 定价决策
    case 'awaiting_pricing':
      router.push(`/projects/${project.id}/pricing`)
      break

    // Week 4 形式审查
    case 'awaiting_review':
      router.push(`/projects/${project.id}/formal-review`)
      break

    // Week 5 最终输出
    case 'completed':
      router.push(`/projects/${project.id}/output`)
      break

    // 废弃/终止状态 → 回收站
    case 'abandoned':
    case 'discarded':
    case 'terminated_by_boss':
      router.push('/trash')
      break

    default:
      router.push(`/projects/${project.id}/confirm`)
  }
}

async function handleDelete(project: Project) {
  try {
    await ElMessageBox.confirm('确认将项目移入回收站？', '移入回收站', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await apiClient.delete(`/api/projects/${project.id}`)
    ElMessage.success('项目已移入回收站')
    await projectStore.fetchProjects()
  } catch (err: unknown) {
    const errObj = err as { type?: string; response?: { data?: { detail?: string } } }
    if (errObj?.type === 'cancel' || errObj?.type === 'close') return
    const detail = errObj?.response?.data?.detail
    ElMessage.error(detail ? `删除失败：${detail}` : '删除失败，请重试')
  }
}

async function handleClone(project: Project, cloneType: 'rebid' | 'annual_renewal') {
  if (cloneType === 'rebid') {
    // Path A: immediate clone — same plan_code, parent_project_id bound
    try {
      const result = await apiClient.post(`/projects/${project.id}/clone`, {
        clone_type: 'rebid',
      }) as { data: { new_project_id: number; new_project_name: string } }
      const d = (result as any).data
      ElMessage.success(`已创建克隆项目：${d.new_project_name}`)
      await projectStore.fetchProjects()
      router.push(`/projects/${d.new_project_id}/confirm`)
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } }
      ElMessage.error(errObj?.response?.data?.detail || '克隆失败，请重试')
    }
  } else {
    // Path B: annual renewal — store pending clone, navigate to upload
    projectStore.setPendingClone(project.id, project.projectName, 'annual_renewal')
    router.push('/projects/new/upload')
  }
}

onMounted(async () => {
  await projectStore.fetchProjects()
})
</script>

<style scoped>
/* 状态数字居中对齐：文字在上，数字在下，水平居中 */
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 52px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  line-height: 1.2;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}
</style>
