<template>
  <div class="tech-proposal-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">技术标编辑台</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <div v-if="currentProject?.bossInsiderNotes" class="boss-notes-alert mt-2">
        <el-alert type="warning" :closable="false">
          <template #title>
            <span class="text-sm">老板指导：</span>
            <span class="text-sm text-orange-600">{{ currentProject.bossInsiderNotes }}</span>
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

// Computed so it stays reactive if route changes; guards against undefined/NaN
const projectId = computed(() => {
  const raw = route.params.id
  if (!raw) return NaN
  const parsed = Number(raw)
  return isNaN(parsed) ? NaN : parsed
})
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId.value))

const generationMode = ref<'auto' | 'guided'>('auto')
const isGenerating = ref(false)
const selectedSectionId = ref<number | null>(null)

const isModeLocked = computed(() => !!currentProject.value?.bossInsiderNotes)

const sections = ref([
  { id: 1, title: '第一章 项目理解', scoring_item: '2.1 项目背景', content: '', generated: false, children: [] },
  { id: 2, title: '第二章 服务方案', scoring_item: '2.2 服务内容', content: '', generated: false, children: [] },
  { id: 3, title: '第三章 质量管理', scoring_item: '2.3 质量保障', content: '', generated: false, children: [] },
  { id: 4, title: '第四章 应急预案', scoring_item: '2.4 风险管控', content: '', generated: false, children: [] },
  { id: 5, title: '第五章 项目团队', scoring_item: '2.5 人员配置', content: '', generated: false, children: [] },
])

const selectedSection = computed(() => sections.value.find(s => s.id === selectedSectionId.value))
const canGenerate = computed(() => selectedSectionId.value !== null && !isGenerating.value)

onMounted(async () => {
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    return
  }
  // Refresh project status from backend (in case changed via API approval)
  await projectStore.fetchProjectById(projectId.value)

  // Set generation mode from project
  if (currentProject.value?.generationMode === 'guided') {
    generationMode.value = 'guided'
  }
  // Load existing generated sections from backend
  try {
    const resp = await apiClient.get(`/v1/projects/${projectId.value}/sections`) as {
      data: {
        sections: Array<{ sectionName: string; content: string; mode: string; generationTimestamp: string }>
      }
    }
    if (resp.data?.sections) {
      for (const sec of resp.data.sections) {
        // 兼容旧数据（无章节前缀如"项目理解"）和新数据（有前缀如"第一章 项目理解"）
        const section = sections.value.find(s =>
          s.title === sec.sectionName ||
          s.title.endsWith(sec.sectionName) ||
          sec.sectionName.endsWith(s.title.split(' ')[1] || s.title)
        )
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
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    return
  }
  if (!selectedSection.value) return
  isGenerating.value = true
  try {
    const insiderNotes = generationMode.value === 'guided' ? (currentProject.value?.bossInsiderNotes || '') : undefined
    // rag.py returns ResponseWrapper(data=GeneratedSectionResponse), interceptor strips Axios HTTP
    // wrapper but NOT the application-level ResponseWrapper, so result = {code:200, data:{content:"..."}}
    const result = await apiClient.post(`/v1/projects/${projectId.value}/generate-section`, {
      section_name: selectedSection.value.title,
      generation_mode: generationMode.value,
      insider_notes: insiderNotes,
      top_k: generationMode.value === 'auto' ? 5 : 3,
    }) as { data: { content: string; generationTimestamp: string } }
    selectedSection.value.content = result.data.content
    selectedSection.value.generated = true
    // Upsert to ProjectSection (authoritative DB storage — non-blocking)
    try {
      await apiClient.put(`/api/v1/projects/${projectId.value}/sections/${encodeURIComponent(selectedSection.value.title)}`, {
        section_name: selectedSection.value.title,
        content: result.data.content,
        mode: generationMode.value,
      })
    } catch (upsertErr) {
      console.warn('Section auto-save failed (content is in memory):', upsertErr)
      ElMessage.warning('内容已生成但自动保存失败，请手动重新生成以保存')
    }
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

async function confirmAllSections() {
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    return
  }
  const allGenerated = sections.value.every(s => s.generated)
  if (!allGenerated) {
    ElMessage.warning('请先生成所有章节')
    return
  }
  try {
    await apiClient.post(`/v1/projects/${projectId.value}/advance-to-pricing`)
    ElMessage.success('技术标已确认！进入定价阶段')
    await projectStore.fetchProjects()
    router.push(`/projects/${projectId.value}/pricing`)
  } catch (err: unknown) {
    const errObj = err as { response?: { data?: { detail?: string } } }
    const detail = errObj?.response?.data?.detail
    ElMessage.error(detail || '推进定价流程失败，请重试')
  }
}

function goBack() {
  router.push(`/projects/${projectId.value}/evaluation`)
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
