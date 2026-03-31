<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-gray-800">项目列表</h1>
        <p class="text-sm text-gray-500 mt-1">共 {{ projectStore.projects.length }} 个项目</p>
      </div>
      <div class="flex gap-3">
        <el-statistic title="进行中" :value="countByStatus('in_progress')" />
        <el-divider direction="vertical" />
        <el-statistic title="已完成" :value="countByStatus('completed')" />
        <el-divider direction="vertical" />
        <el-statistic title="待处理" :value="countByStatus('pending')" />
        <el-divider direction="vertical" />
        <el-button type="primary" size="large" @click="router.push('/projects/new/upload')">
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
        {{ tab.label }} ({{ countByStatus(tab.value) }})
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
        @click="handleCardClick(project)"
        @delete="handleDelete"
      />
    </div>

    <!-- Empty state -->
    <el-empty v-else description="暂无项目" class="my-12" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useAuthStore } from '@/stores/authStore'
import ProjectCard, { type Project } from '@/components/ProjectCard.vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { apiClient } from '@/api/client'

const router = useRouter()
const projectStore = useProjectStore()
const authStore = useAuthStore()
const activeTab = ref('all')

const statusTabs = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '待处理', value: 'pending' },
]

const IN_PROGRESS_STATUSES = ['parsing', 'parsed', 'evaluating', 'evaluation_ready', 'generating_documents', 'awaiting_pricing', 'awaiting_review', 'pending_boss_approval']
const COMPLETED_STATUSES = ['completed', 'worthy']
// Boss waiting list: projects approved by specialist and awaiting boss decision
const PENDING_STATUSES = ['uploaded', 'unworthy', 'terminated_by_boss', 'abandoned', 'evaluation_ready', 'approved_by_specialist', 'pending_boss_approval', 'discarded']

const filteredProjects = computed(() => {
  if (activeTab.value === 'all') return projectStore.projects
  if (activeTab.value === 'in_progress') return projectStore.projects.filter(p => IN_PROGRESS_STATUSES.includes(p.status))
  if (activeTab.value === 'completed') return projectStore.projects.filter(p => COMPLETED_STATUSES.includes(p.status))
  if (activeTab.value === 'pending') return projectStore.projects.filter(p => PENDING_STATUSES.includes(p.status))
  return projectStore.projects
})

function countByStatus(tab: string): number {
  if (tab === 'all') return projectStore.projects.length
  if (tab === 'in_progress') return projectStore.projects.filter(p => IN_PROGRESS_STATUSES.includes(p.status)).length
  if (tab === 'completed') return projectStore.projects.filter(p => COMPLETED_STATUSES.includes(p.status)).length
  if (tab === 'pending') return projectStore.projects.filter(p => PENDING_STATUSES.includes(p.status)).length
  return 0
}

function handleCardClick(project: typeof projectStore.projects[0]) {
  projectStore.setCurrentProject(project)
  router.push(`/projects/${project.id}/upload`)
}

// Debounce map — prevents rapid successive delete clicks
const deleteLock = new Set<number>()

async function handleDelete(project: Project) {
  if (deleteLock.has(project.id)) return  // Already deleting
  deleteLock.add(project.id)

  try {
    await ElMessageBox.confirm(
      `确定移入回收站吗？移入后您可以重新上传同名项目。`,
      '移入回收站',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        center: true,
      }
    )
    await apiClient.delete(`/projects/${project.id}`)
    ElMessage.success('已移入回收站，可重新上传同名项目')
    // Refresh list
    await projectStore.fetchProjects(authStore.currentUser.role)
  } catch {
    // User cancelled or API error — silently ignore
  } finally {
    deleteLock.delete(project.id)
  }
}

onMounted(() => {
  projectStore.fetchProjects(authStore.currentUser.role)
})

// Re-fetch when role changes (e.g., boss reviewing as different user)
watch(() => authStore.currentUser.role, (newRole) => {
  projectStore.fetchProjects(newRole)
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}
</style>
