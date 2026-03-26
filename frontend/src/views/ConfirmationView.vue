<template>
  <div class="confirmation-view">
    <div class="page-header">
      <h2 class="text-xl font-semibold">招标文件信息确认</h2>
      <p class="text-sm text-gray-500 mt-1">请核对 AI 提取的信息，如有错误请修正</p>
    </div>

    <div class="flex gap-6">
      <!-- Left: PDF info placeholder -->
      <div class="pdf-placeholder">
        <el-card class="pdf-card">
          <div class="flex flex-col items-center justify-center h-full">
            <el-icon :size="48" class="text-gray-300"><Document /></el-icon>
            <p class="text-sm text-gray-400 mt-3">招标文件预览</p>
            <p class="text-xs text-gray-300 mt-1">{{ project.pdf_file || '未上传文件' }}</p>
          </div>
        </el-card>
      </div>

      <!-- Right: Editable form -->
      <div class="flex-1">
        <el-card class="form-card">
          <el-form :model="formData" label-position="top" class="ocr-form">
            <el-form-item label="项目名称">
              <el-input v-model="formData.project_name" placeholder="项目名称" />
            </el-form-item>
            <el-form-item label="业主单位">
              <el-input v-model="formData.owner_unit" placeholder="业主单位" />
            </el-form-item>
            <el-form-item label="项目预算（元）">
              <el-input-number
                v-model="formData.budget_amount"
                :min="0"
                :step="10000"
                :precision="0"
                class="w-full"
              />
            </el-form-item>
            <el-form-item label="地区">
              <el-input v-model="formData.region" placeholder="如：华南、华东" />
            </el-form-item>
            <el-form-item label="项目类型">
              <el-select v-model="formData.project_type" class="w-full">
                <el-option label="服务类" value="service" />
                <el-option label="货物类" value="goods" />
                <el-option label="工程类" value="engineering" />
              </el-select>
            </el-form-item>
            <el-form-item label="开标日期">
              <el-date-picker
                v-model="formData.bid_open_date"
                type="date"
                placeholder="选择日期"
                class="w-full"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item label="关系标识">
              <el-switch v-model="formData.relationship_flag" />
              <span class="text-sm text-gray-400 ml-2">是否涉及关联关系</span>
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="mt-6 flex gap-4">
      <el-button type="primary" size="large" :loading="isConfirming" @click="confirmAndProceed">
        <el-icon v-if="!isConfirming" class="mr-1"><Check /></el-icon>
        确认无误并立项
      </el-button>
      <el-button size="large" @click="goBack">返回上传</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore, type Project } from '@/stores/projectStore'
import { Document, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = Number(route.params.id)
const isConfirming = ref(false)

const project = reactive<Project>({
  id: projectId,
  project_name: '',
  project_type: 'service',
  owner_unit: '',
  region: '',
  budget_amount: 0,
  status: 'parsing',
  relationship_flag: false,
  generation_mode: 'auto',
  bid_open_date: '',
  pdf_file: '招标文件.pdf',
})

const formData = reactive({
  project_name: 'XX学校2026年食堂配送项目',
  owner_unit: '深圳市XX学校',
  budget_amount: 1500000,
  region: '华南',
  project_type: 'service',
  bid_open_date: '2026-04-15',
  relationship_flag: false,
})

function confirmAndProceed() {
  isConfirming.value = true
  setTimeout(() => {
    // Update project with confirmed data
    Object.assign(project, formData, { status: 'parsed' })
    projectStore.projects.push({ ...project })
    ElMessage.success('项目立项成功！')
    isConfirming.value = false
    router.push('/')
  }, 800)
}

function goBack() {
  router.push(`/projects/${projectId}/upload`)
}
</script>

<style scoped>
.confirmation-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.pdf-placeholder {
  width: 260px;
  flex-shrink: 0;
}
.pdf-card {
  height: 100%;
  min-height: 400px;
  border-radius: 12px;
}
.form-card {
  border-radius: 12px;
}
.ocr-form :deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
