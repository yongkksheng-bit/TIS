<template>
  <div class="upload-view">
    <div class="page-header">
      <h2 class="text-xl font-semibold">上传招标文件</h2>
      <p class="text-sm text-gray-500">支持 PDF 格式，大小不超过 50MB</p>
    </div>

    <!-- Upload area -->
    <div class="upload-container">
      <el-upload
        ref="uploadRef"
        class="upload-area"
        :class="{ 'is-dragover': isDragover }"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".pdf"
        @change="handleFileChange"
        @dragover="isDragover = true"
        @dragleave="isDragover = false"
        @drop="isDragover = false"
      >
        <div class="upload-content">
          <el-icon class="upload-icon" :size="64"><DocumentAdd /></el-icon>
          <p class="text-lg font-medium mt-4">拖拽 PDF 文件到此处</p>
          <p class="text-sm text-gray-400 mt-1">或点击选择文件</p>
          <p v-if="selectedFile" class="mt-3 text-sm text-blue-500">
            已选择: {{ selectedFile.name }}
          </p>
        </div>
      </el-upload>
    </div>

    <!-- Action buttons -->
    <div class="mt-6 flex gap-4">
      <el-button
        type="primary"
        size="large"
        :loading="isParsing"
        :disabled="!selectedFile"
        @click="startParsing"
      >
        <el-icon v-if="!isParsing" class="mr-1"><Cpu /></el-icon>
        {{ isParsing ? '智能解析中...' : '开始智能解析' }}
      </el-button>
      <el-button size="large" @click="goBack">返回</el-button>
    </div>

    <!-- Parsing progress -->
    <div v-if="isParsing" class="mt-6">
      <el-card class="parsing-card">
        <div class="flex items-center gap-3">
          <el-icon class="text-blue-500" :size="24"><Loading /></el-icon>
          <div>
            <p class="font-medium">{{ parsingProgress < 85 ? 'AI 正在解析招标文件...' : '正在深度提取法务与特定资质...' }}</p>
            <p class="text-sm text-gray-500 mt-1">
              {{ parsingProgress < 85 ? '预计需要 1-2 秒' : '大模型处理时间较长，请耐心等待（约需 1-2 分钟）...' }}
            </p>
          </div>
        </div>
        <el-progress :percentage="parsingProgress" :stroke-width="8" class="mt-3" />
      </el-card>
    </div>

    <!-- Parse failed: retry UI -->
    <div v-if="showRetry && !isParsing" class="mt-6">
      <el-alert type="error" :closable="false" show-icon>
        <template #title>
          文件解析失败
        </template>
        文件无法被正常解析，可能是 PDF 损坏、密码保护或纯扫描件。<br />
        请尝试：
        <ul class="mt-2 mb-0 pl-5 list-disc text-sm">
          <li>确认 PDF 未加密（可使用 Adobe Reader 另存为无加密版本）</li>
          <li>如是扫描件，请确保扫描仪已启用文字识别（OCR）输出</li>
          <li>使用其他 PDF 尝试排除文件问题</li>
        </ul>
      </el-alert>
      <div class="mt-4 flex gap-4">
        <el-button type="primary" @click="retryParse">重新解析</el-button>
        <el-button @click="resetUpload">重新上传</el-button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { apiClient } from '@/api/client'
import { DocumentAdd, Cpu, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const selectedFile = ref<File | null>(null)
const isParsing = ref(false)
const parsingProgress = ref(0)
const isDragover = ref(false)
const showRetry = ref(false)

function handleFileChange(file: unknown) {
  const f = (file as { raw: File }).raw
  if (f && f.type === 'application/pdf') {
    selectedFile.value = f
  } else {
    ElMessage.warning('请上传 PDF 文件')
  }
}

async function startParsing() {
  if (!selectedFile.value) return
  isParsing.value = true
  parsingProgress.value = 0

  let interval: ReturnType<typeof setInterval> | null = null
  try {
    // Step 1: Create initial project
    const createRes = await apiClient.post<{ id: number }>('/api/projects', {
      project_name: selectedFile.value?.name || '待解析项目',
      owner_unit: '未知',
    })
    const projectId = (createRes as unknown as { id: number }).id

    // Step 2: Upload PDF
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    interval = setInterval(() => {
      parsingProgress.value = Math.min(parsingProgress.value + Math.floor(Math.random() * 15) + 5, 85)
    }, 300)

    await apiClient.post(`/api/projects/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (interval) clearInterval(interval)
    parsingProgress.value = 100

    // ── Step 3: Handle pending clone (annual_renewal) ───────────────────────
    const pending = projectStore.pendingClone
    if (pending?.cloneType === 'annual_renewal') {
      // Fetch project to get extracted plan_code
      const projData = await apiClient.get(`/api/projects/${projectId}`) as Record<string, unknown>
      const planCode = (projData as any)?.plan_code || null
      // Extract year from plan_code (e.g. "441301-2025-03605" → "2025")
      let year: string | undefined
      if (planCode) {
        const m = planCode.match(/20\d{2}/)
        year = m ? m[0] : undefined
      }
      // Clone: creates new project with year suffix and new plan_code
      const cloneRes = await apiClient.post(`/api/projects/${pending.sourceProjectId}/clone`, {
        clone_type: 'annual_renewal',
        plan_code: planCode,
        year,
      }) as { data: { new_project_id: number; new_project_name: string } }
      const clonedId = (cloneRes as any).data.new_project_id

      // Upload PDF to the cloned project
      const formDataClone = new FormData()
      formDataClone.append('file', selectedFile.value!)
      await apiClient.post(`/api/projects/${clonedId}/upload`, formDataClone, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      projectStore.clearPendingClone()
      ElMessage.success(`已创建新一期招标项目：${(cloneRes as any).data.new_project_name}`)
      isParsing.value = false
      router.push(`/projects/${clonedId}/confirm`)
      return
    }

    // ── Step 3b: Normal flow — navigate to confirm page ─────────────────
    isParsing.value = false
    router.push(`/projects/${projectId}/confirm`)
  } catch (err) {
    isParsing.value = false
    if (interval) clearInterval(interval)
    const errDetail = (err as any)?.response?.data?.detail
    if (errDetail?.code === 'DUPLICATE_TENDER') {
      const existingName = errDetail?.existing_project_name || '未知'
      const dupCode = errDetail?.duplicate_code || ''
      const dupMsg = dupCode ? ` (${dupCode})` : ''
      await ElMessageBox.confirm(
        `检测到系统已存在该项目：【${existingName}】${dupMsg}。\n\n如需重新上传，请先废弃原有项目。`,
        '项目重复',
        {
          confirmButtonText: '确认为流标重投',
          cancelButtonText: '取消',
          type: 'warning',
          center: true,
        }
      ).then(async () => {
        isParsing.value = true
        try {
          // Clone via API — creates new project linked to existing one
          const cloneRes = await apiClient.post(`/api/projects/${errDetail.existing_project_id}/clone`, {
            clone_type: 'rebid',
          }) as { data: { new_project_id: number; new_project_name: string } }
          const clonedId = (cloneRes as any).data.new_project_id
          const formDataRetry = new FormData()
          formDataRetry.append('file', selectedFile.value!)
          await apiClient.post(`/api/projects/${clonedId}/upload`, formDataRetry, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          ElMessage.success('已创建流标重投项目')
          router.push(`/projects/${clonedId}/confirm`)
        } catch (retryErr) {
          ElMessage.error('创建失败：' + (retryErr instanceof Error ? retryErr.message : String(retryErr)))
        } finally {
          isParsing.value = false
        }
      }).catch(() => {
        // User cancelled
      })
    } else {
      const errMsg = (err as any)?.response?.data?.detail || '文件解析失败，请重试'
      ElMessage.error(errMsg)
      showRetry.value = true
    }
    console.error(err)
  }
}

function goBack() {
  router.push('/')
}

function retryParse() {
  showRetry.value = false
  selectedFile.value = null
  startParsing()
}

function resetUpload() {
  showRetry.value = false
  selectedFile.value = null
}

onMounted(() => {
})
</script>

<style scoped>
.upload-view {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.upload-container {
  margin-top: 16px;
}
.upload-area {
  width: 100%;
}
.upload-area :deep(.el-upload) {
  width: 100%;
}
.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  border: 2px dashed #dcdfe6;
  background: #fafafa;
  transition: all 0.2s;
}
.upload-area :deep(.el-upload-dragger:hover),
.upload-area.is-dragover :deep(.el-upload-dragger) {
  border-color: #409eff;
  background: #ecf5ff;
}
.upload-content {
  text-align: center;
  color: #606266;
}
.upload-icon {
  color: #c0c4cc;
}
.parsing-card {
  border-radius: 12px;
}
</style>
