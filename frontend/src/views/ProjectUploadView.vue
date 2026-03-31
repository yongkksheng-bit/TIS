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
            <p class="font-medium">AI 正在解析招标文件...</p>
            <p class="text-sm text-gray-500 mt-1">预计需要 1-2 秒</p>
          </div>
        </div>
        <el-progress :percentage="parsingProgress" :stroke-width="8" class="mt-3" />
      </el-card>
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
    // Step 1: Create project via API
    const createRes = await apiClient.post<{ id: number }>('/projects', {
      project_name: '待解析项目',
      owner_unit: '未知',
    })
    const projectId = (createRes as unknown as { id: number }).id

    // Step 2: Upload PDF with progress simulation
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    // Simulate progress while uploading
    interval = setInterval(() => {
      parsingProgress.value = Math.min(parsingProgress.value + Math.floor(Math.random() * 15) + 5, 85)
    }, 300)

    await apiClient.post(`/projects/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (interval) clearInterval(interval)
    parsingProgress.value = 100

    setTimeout(() => {
      isParsing.value = false
      router.push(`/projects/${projectId}/confirm`)
    }, 300)
  } catch (err) {
    isParsing.value = false
    if (interval) clearInterval(interval)
    const errDetail = (err as any)?.response?.data?.detail
    if (errDetail?.code === 'DUPLICATE_TENDER') {
      const existingName = errDetail?.existing_project_name || '未知'
      const dupCode = errDetail?.duplicate_code || ''
      const dupMsg = dupCode ? ` (${dupCode})` : ''
      await ElMessageBox.confirm(
        `检测到系统已存在该项目：【${existingName}】${dupMsg}。\n\n如果这是流标后的重新招标，请点击【确认作为二次投标】放行上传。`,
        '项目重复 — 二次投标确认',
        {
          confirmButtonText: '确认作为二次投标',
          cancelButtonText: '取消',
          type: 'warning',
          center: true,
        }
      ).then(async () => {
        // User confirmed — retry with force_retender=true
        isParsing.value = true
        try {
          const createRes = await apiClient.post<{ id: number }>('/projects', {
            project_name: '待解析项目',
            owner_unit: '未知',
            force_retender: true,
            parent_id: errDetail?.existing_project_id || undefined,
          })
          const retryProjectId = (createRes as unknown as { id: number }).id
          const formDataRetry = new FormData()
          formDataRetry.append('file', selectedFile.value!)
          await apiClient.post(`/projects/${retryProjectId}/upload`, formDataRetry, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          ElMessage.success('二次投标项目创建成功！')
          router.push(`/projects/${retryProjectId}/confirm`)
        } catch (retryErr) {
          ElMessage.error('二次投标创建失败：' + (retryErr instanceof Error ? retryErr.message : String(retryErr)))
        } finally {
          isParsing.value = false
        }
      }).catch(() => {
        // User cancelled — do nothing
      })
    } else {
      ElMessage.error('文件解析失败，请重试')
    }
    console.error(err)
  }
}

function goBack() {
  router.push('/')
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
