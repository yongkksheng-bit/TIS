<template>
  <div class="final-output-view">
    <div class="output-container">
      <el-result
        icon="success"
        title="标书生成完成！"
        sub-title="恭喜！您的最终投标文件已准备就绪"
      >
        <template #extra>
          <div class="flex flex-col gap-4 items-center">
            <p class="text-gray-500 text-sm">项目：{{ currentProject?.projectName }}</p>

            <!-- Download buttons -->
            <div class="flex gap-4 flex-wrap justify-center">
              <el-button type="primary" size="large" class="download-btn" @click="downloadPdf">
                <el-icon class="mr-2" :size="20"><Document /></el-icon>
                下载彩色高亮 PDF
              </el-button>
              <el-button type="success" size="large" class="download-btn" @click="downloadWord">
                <el-icon class="mr-2" :size="20"><Document /></el-icon>
                下载最终 Word 标书
              </el-button>
            </div>

            <!-- Packaging guide checklist -->
            <el-card class="packaging-card mt-4">
              <template #header>
                <span class="font-medium">封装检查清单</span>
              </template>
              <div class="flex flex-col gap-2">
                <div v-for="item in packagingChecklist" :key="item" class="flex items-center gap-2">
                  <el-icon color="#67c23a"><Check /></el-icon>
                  <span class="text-sm">{{ item }}</span>
                </div>
              </div>
            </el-card>

            <el-button type="default" size="large" class="mt-4" @click="goBack">
              返回项目大厅
            </el-button>
          </div>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { Document, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '@/api/client'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = Number(route.params.id)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId))

const packagingChecklist = [
  '投标文件正本 1 份、副本 4 份',
  '电子版 U 盘 1 个（含全套扫描件）',
  '授权委托书（加盖公章）',
  '报价函（单独密封）',
  '技术标与商务标分开装订',
  '封条完整且骑缝章齐全',
]

/* ─── 真实 Word 下载 ─────────────────────────────────────── */
async function downloadWord() {
  try {
    // Step 1: 调用生成接口，确保文档已生成并获取 docId
    const genResp = await apiClient.post(`/api/v1/projects/${projectId}/final-documents/generate`) as any
    const docId = genResp?.data?.id
    if (!docId) {
      ElMessage.error('生成失败：未返回文档ID')
      return
    }

    // Step 2: 用原生 fetch 绕过 axios 拦截器的 camelCase 二进制破坏
    // nginx proxy_pass /api/ → backend:8000$request_uri，路径保持 /api/v1/...
    const downloadUrl = `/api/v1/projects/${projectId}/final-documents/${docId}/download`
    const fetchResp = await fetch(downloadUrl)
    if (!fetchResp.ok) {
      throw new Error(`下载请求失败: ${fetchResp.status}`)
    }
    const blob = await fetchResp.blob()

    // Step 3: 触发浏览器下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `投标标书_${projectId}.docx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    ElMessage.success('Word 标书下载完成')
  } catch (err) {
    console.error('Word 下载失败:', err)
    ElMessage.error('Word 下载失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

/* ─── PDF Mock Blob 下载（后端 PDF 引擎就绪后替换此处） ── */
function downloadPdf() {
  try {
    const mockText = 'PDF 渲染引擎即将上线，敬请期待。\n\n— TIS 招标智能系统'
    const blob = new Blob([mockText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `投标标书_${projectId}_placeholder.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('PDF 预览文件下载完成（占位符）')
  } catch (err) {
    ElMessage.error('下载失败：' + (err instanceof Error ? err.message : String(err)))
  }
}

function goBack() {
  router.push('/')
}
</script>

<style scoped>
.final-output-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
}
.output-container {
  width: 100%;
  max-width: 700px;
}
.download-btn {
  min-width: 220px;
  height: 48px;
  font-size: 15px;
}
.packaging-card {
  border-radius: 12px;
  width: 100%;
}
</style>
