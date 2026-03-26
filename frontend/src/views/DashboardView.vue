<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-gray-800">项目列表</h1>
        <p class="text-sm text-gray-500 mt-1">共 {{ projectStore.projects.length }} 个项目</p>
      </div>
      <el-button type="primary" size="large">
        <el-icon class="mr-1"><Plus /></el-icon>
        新建项目
      </el-button>
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
import ProjectCard from '@/components/ProjectCard.vue'
import { Plus } from '@element-plus/icons-vue'

const router = useRouter()
const projectStore = useProjectStore()
const activeTab = ref('all')

const statusTabs = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '待处理', value: 'pending' },
]

const IN_PROGRESS_STATUSES = ['parsing', 'parsed', 'evaluating', 'evaluation_ready', 'generating_documents', 'awaiting_pricing', 'awaiting_review']
const COMPLETED_STATUSES = ['completed', 'worthy']
const PENDING_STATUSES = ['uploaded', 'unworthy', 'terminated_by_boss', 'abandoned']

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
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}
</style>
