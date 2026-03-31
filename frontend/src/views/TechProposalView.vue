<template>
  <div class="tech-proposal-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">技术标编辑台</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <div v-if="currentProject?.boss_insider_notes" class="boss-notes-alert mt-2">
        <el-alert type="warning" :closable="false">
          <template #title>
            <span class="text-sm">老板指导：</span>
            <span class="text-sm text-orange-600">{{ currentProject.boss_insider_notes }}</span>
          </template>
        </el-alert>
      </div>
    </div>

    <!-- Generation controls -->
    <el-card class="control-card mb-4">
      <div class="flex flex-wrap items-center gap-4">
        <span class="font-medium">生成模式：</span>
        <el-radio-group v-model="generationMode" :disabled="isModeLocked">
          <el-radio value="auto">AUTO 流水线</el-radio>
          <el-radio value="guided">GUIDED 强锁定</el-radio>
        </el-radio-group>
        <el-tag v-if="isModeLocked" type="warning" size="small">已锁定</el-tag>

        <div class="flex-1" />

        <el-button type="primary" :loading="isGenerating" :disabled="!canGenerate" @click="generateSection">
          <el-icon v-if="!isGenerating" class="mr-1"><MagicStick /></el-icon>
          {{ isGenerating ? '生成中...' : '生成选中章节' }}
        </el-button>
      </div>
    </el-card>

    <!-- Main area: section tree + editor -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <!-- Left: Section tree -->
      <el-card class="section-tree-card">
        <template #header>
          <span class="font-medium">章节列表</span>
        </template>
        <el-tree
          :data="sections"
          :props="{ label: 'title', children: 'children' }"
          node-key="id"
          default-expand-all
          :current-node-key="selectedSectionId"
          highlight-current
          @node-click="handleSectionClick"
        >
          <template #default="{ node, data }">
            <div class="section-node">
              <span>{{ data.title }}</span>
              <el-tag v-if="data.generated" type="success" size="small" class="ml-2">已生成</el-tag>
              <el-tag v-else size="small" class="ml-2">待生成</el-tag>
            </div>
          </template>
        </el-tree>
      </el-card>

      <!-- Right: Editor + metadata -->
      <div class="lg:col-span-3 flex flex-col gap-4">
        <!-- Selected section editor -->
        <el-card class="editor-card">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-medium">{{ selectedSection?.title || '请选择章节' }}</span>
              <div class="flex gap-2">
                <el-button size="small" :disabled="!selectedSection?.generated" @click="regenerateSection">
                  <el-icon><RefreshRight /></el-icon>
                  重新生成
                </el-button>
              </div>
            </div>
          </template>
          <div v-if="selectedSection">
            <p class="text-sm text-gray-500 mb-2">评分项: {{ selectedSection.scoring_item }}</p>
            <el-input
              v-model="selectedSection.content"
              type="textarea"
              :rows="12"
              placeholder="点击「生成选中章节」按钮，AI 将为您生成内容..."
              class="section-textarea"
            />
          </div>
          <div v-else class="text-center text-gray-400 py-12">
            请从左侧选择要编辑的章节
          </div>
        </el-card>

        <!-- Bottom actions -->
        <div class="flex justify-end gap-3">
          <el-button @click="goBack">返回评估</el-button>
          <el-button type="success" @click="confirmAllSections">
            <el-icon class="mr-1"><Check /></el-icon>
            确认全部章节
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { apiClient } from '@/api/client'
import StatusBadge from '@/components/StatusBadge.vue'
import { MagicStick, RefreshRight, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const generationMode = ref<'auto' | 'guided'>('auto')
const isGenerating = ref(false)
const selectedSectionId = ref<number | null>(null)

const isModeLocked = computed(() => !!currentProject.value?.boss_insider_notes)

const sections = ref([
  { id: 1, title: '项目理解', scoring_item: '2.1 项目背景', content: '', generated: false, children: [] },
  { id: 2, title: '服务方案', scoring_item: '2.2 服务内容', content: '', generated: false, children: [] },
  { id: 3, title: '质量管理', scoring_item: '2.3 质量保障', content: '', generated: false, children: [] },
  { id: 4, title: '应急预案', scoring_item: '2.4 风险管控', content: '', generated: false, children: [] },
  { id: 5, title: '项目团队', scoring_item: '2.5 人员配置', content: '', generated: false, children: [] },
])

const selectedSection = computed(() => sections.value.find(s => s.id === selectedSectionId.value))
const canGenerate = computed(() => selectedSectionId.value !== null && !isGenerating.value)

onMounted(async () => {
  // Refresh project status from backend (in case changed via API approval)
  await projectStore.fetchProjectById(projectId)

  // Set generation mode from project
  if (currentProject.value?.generation_mode === 'guided') {
    generationMode.value = 'guided'
  }
  // Load existing generated sections from backend
  try {
    const data = await apiClient.get(`/v1/projects/${projectId}/sections`) as {
      data: {
        sections: Array<{ section_name: string; content: string; mode: string; generation_timestamp: string }>
      }
    }
    if (data.data?.sections) {
      for (const sec of data.data.sections) {
        const section = sections.value.find(s => s.title === sec.section_name)
        if (section) {
          section.content = sec.content
          section.generated = true
        }
      }
    }
  } catch (err) {
    console.warn('Failed to load existing sections:', err)
  }
})

function handleSectionClick(data: typeof sections.value[0]) {
  selectedSectionId.value = data.id
}

async function generateSection() {
  if (!selectedSection.value) return
  isGenerating.value = true
  try {
    const insiderNotes = generationMode.value === 'guided' ? (currentProject.value?.boss_insider_notes || '') : undefined
    const result = await apiClient.post(`/v1/projects/${projectId}/generate-section`, {
      section_name: selectedSection.value.title,
      generation_mode: generationMode.value,
      insider_notes: insiderNotes,
      top_k: generationMode.value === 'auto' ? 5 : 3,
    }) as { data: { content: string; generation_timestamp: string } }
    selectedSection.value.content = result.data.content
    selectedSection.value.generated = true
    ElMessage.success(`${selectedSection.value.title} 生成完成`)
  } catch (err) {
    ElMessage.error('生成失败：' + (err instanceof Error ? err.message : String(err)))
  } finally {
    isGenerating.value = false
  }
}

async function regenerateSection() {
  // Same as generateSection — calls the same endpoint
  await generateSection()
}

function confirmAllSections() {
  const allGenerated = sections.value.every(s => s.generated)
  if (!allGenerated) {
    ElMessage.warning('请先生成所有章节')
    return
  }
  const project = projectStore.projects.find(p => p.id === projectId)
  if (project) {
    project.status = 'awaiting_pricing'
    ElMessage.success('技术标已确认！进入定价流程')
  }
  router.push(`/projects/${projectId}/pricing`)
}

function goBack() {
  router.push(`/projects/${projectId}/evaluation`)
}
</script>

<style scoped>
.tech-proposal-view {
  max-width: 1300px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 16px;
}
.boss-notes-alert {
  border-radius: 8px;
}
.control-card, .section-tree-card, .editor-card {
  border-radius: 12px;
}
.section-tree-card :deep(.el-tree-node__content) {
  height: 36px;
}
.section-node {
  display: flex;
  align-items: center;
}
.section-textarea :deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.8;
}
</style>
