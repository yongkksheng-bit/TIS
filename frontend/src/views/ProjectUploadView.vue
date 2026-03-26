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
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { DocumentAdd, Cpu, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

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

function startParsing() {
  if (!selectedFile.value) return
  isParsing.value = true
  parsingProgress.value = 0

  // Mock progress simulation
  const interval = setInterval(() => {
    parsingProgress.value += Math.floor(Math.random() * 20) + 10
    if (parsingProgress.value >= 100) {
      parsingProgress.value = 100
      clearInterval(interval)
      setTimeout(() => {
        isParsing.value = false
        // Navigate to confirmation page
        const projectId = projectStore.projects.length > 0 ? projectStore.projects[0].id + 1 : 1
        router.push(`/projects/${projectId}/confirm`)
      }, 300)
    }
  }, 200)
}

function goBack() {
  router.push('/')
}
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
