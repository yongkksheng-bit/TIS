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
            <p class="text-gray-500 text-sm">项目：{{ currentProject?.project_name }}</p>

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
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { Document, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

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

function downloadPdf() {
  ElMessage.success('开始下载彩色高亮 PDF...')
}
function downloadWord() {
  ElMessage.success('开始下载最终 Word 标书...')
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
