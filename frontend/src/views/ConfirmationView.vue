<template>
  <div class="confirmation-view">
    <div class="page-header">
      <h2 class="text-xl font-semibold">招标文件信息确认</h2>
      <p class="text-sm text-gray-500 mt-1">请核对 AI 提取的信息，如有错误请修正</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6" style="align-items: start;">
      <!-- Left: PDF preview — 50% width, tall -->
      <div class="pdf-preview-wrapper">
        <el-card class="pdf-card" style="border-radius: 12px;">
          <template #header>
            <span class="font-medium text-sm">招标文件预览</span>
          </template>
          <div v-if="pdfUrl" class="pdf-viewer">
            <iframe :src="pdfUrl" class="pdf-iframe" title="招标文件预览" />
          </div>
          <div v-else class="flex flex-col items-center justify-center py-12">
            <el-icon :size="48" class="text-gray-300"><Document /></el-icon>
            <p class="text-sm text-gray-400 mt-3">正在加载预览...</p>
          </div>
        </el-card>
      </div>

      <!-- Right: Editable form — 2-column compact grid -->
      <div>
        <el-card v-loading="isLoadingOcr" class="form-card">
          <el-form :model="formData" label-position="top" class="ocr-form" @submit.prevent="confirmAndProceed">
            <!-- Row 1: 项目名称（full width） -->
            <el-row :gutter="12">
              <el-col :span="24">
                <el-form-item label="项目名称" class="compact-label">
                  <el-input v-model="formData.project_name" placeholder="项目名称" />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Row 2: 业主单位 -->
            <el-row :gutter="12">
              <el-col :span="24">
                <el-form-item label="业主单位" class="compact-label">
                  <el-input v-model="formData.owner_unit" placeholder="业主单位" />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Row 3: 预算 + 地区 -->
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="项目预算（元）" class="compact-label">
                  <el-input-number
                    v-model="formData.budget_amount"
                    :min="0"
                    :step="10000"
                    :precision="0"
                    class="w-full"
                    controls-position="right"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="地区" class="compact-label">
                  <el-input v-model="formData.region" placeholder="如：广东省广州市" />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Row 4: 项目类型 + 截止时间 -->
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="项目类型" class="compact-label">
                  <el-select v-model="formData.project_type" class="w-full">
                    <el-option label="服务类" value="service" />
                    <el-option label="货物类" value="goods" />
                    <el-option label="工程类" value="engineering" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="提交投标文件截止时间" class="compact-label">
                  <el-date-picker
                    v-model="formData.bid_open_date"
                    type="date"
                    placeholder="选择日期"
                    class="w-full"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Row 5: 采购计划编号 + 采购项目编号 -->
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="采购计划编号" class="compact-label">
                  <el-input
                    v-model="formData.plan_code"
                    placeholder="如：441301-2025-03605"
                    clearable
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="采购项目编号（选填）" class="compact-label">
                  <el-input
                    v-model="formData.agency_project_code"
                    placeholder="如：HZJJ-2025118号"
                    clearable
                  />
                </el-form-item>
              </el-col>
            </el-row>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore, type Project } from '@/stores/projectStore'
import { apiClient } from '@/api/client'
import { Document, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const raw = route.params.id
  if (!raw) return NaN
  const parsed = Number(raw)
  return isNaN(parsed) ? NaN : parsed
})
const isConfirming = ref(false)
const isLoadingOcr = ref(false)
const pdfUrl = ref('')

const project = reactive<Project>({
  id: projectId.value as number,
  projectName: '',
  projectType: 'service',
  ownerUnit: '',
  region: '',
  budgetAmount: 0,
  status: 'parsing',
  relationshipFlag: false,
  generationMode: 'auto',
  bidOpenDate: '',
  pdfFile: '',
})

const formData = ref({
  project_name: '',
  owner_unit: '',
  budget_amount: 0,
  region: '',
  project_type: 'service',
  bid_open_date: '',
  plan_code: '',
  agency_project_code: '',
})

// Map OCR field names (camelCase after response interceptor) to formData keys
const FIELD_NAME_MAP: Record<string, keyof typeof formData.value> = {
  projectName: 'project_name',
  ownerUnit: 'owner_unit',
  budgetAmount: 'budget_amount',
  region: 'region',
  projectType: 'project_type',
  bidOpenDate: 'bid_open_date',
  planCode: 'plan_code',
  agencyProjectCode: 'agency_project_code',
}

function extractFieldValue(fields: Array<{ fieldName: string; fieldValue: string; normalizedValue?: string }>, key: string): string | number | boolean {
  const field = fields.find(f => FIELD_NAME_MAP[f.fieldName] === key || f.fieldName === key)
  if (!field) return ''
  const val = field.normalizedValue ?? field.fieldValue
  if (key === 'budget_amount') {
    const num = parseFloat(val)
    return isNaN(num) ? 0 : num
  }
  return val
}

onMounted(async () => {
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    return
  }
  isLoadingOcr.value = true
  try {
    const data = await apiClient.get(`/projects/${projectId.value}/confirmation-data`) as {
      images: Array<{
        id: number
        fields: Array<{ fieldName: string; fieldValue: string; normalizedValue?: string }>
      }>
      tenderPdfUrl?: string
    }
    // Set PDF preview URL from first page's image path (backend serves it as PDF)
    if (data.images && data.images.length > 0) {
      const firstPageId = data.images[0].id
      pdfUrl.value = `/api/document-images/${firstPageId}/view`
    } else if (data.tenderPdfUrl) {
      pdfUrl.value = data.tenderPdfUrl
    }
    // Merge all fields from all images
    const allFields = data.images.flatMap((img: { fields: Array<{ fieldName: string; fieldValue: string; normalizedValue?: string }> }) => img.fields)
    formData.value = {
      project_name: extractFieldValue(allFields, 'project_name') as string || '待确认项目',
      owner_unit: extractFieldValue(allFields, 'owner_unit') as string || '未知',
      budget_amount: extractFieldValue(allFields, 'budget_amount') as number || 0,
      region: extractFieldValue(allFields, 'region') as string || '',
      project_type: (extractFieldValue(allFields, 'project_type') as string) || 'service',
      bid_open_date: (extractFieldValue(allFields, 'bid_open_date') as string) || '',
      plan_code: extractFieldValue(allFields, 'plan_code') as string || '',
      agency_project_code: extractFieldValue(allFields, 'agency_project_code') as string || '',
    }
  } catch (err) {
    ElMessage.warning('无法加载OCR数据请手动填写')
    console.error(err)
  } finally {
    isLoadingOcr.value = false
  }
})

async function confirmAndProceed() {
  // Validation: bid_open_date is required
  if (!formData.value.bid_open_date) {
    ElMessage.error('未填写提交投标文件截止时间')
    return
  }
  isConfirming.value = true
  try {
    await apiClient.post(`/projects/${projectId.value}/confirm-parsing`, {
      confirmations: [],
      project_name: formData.value.project_name,
      owner_unit: formData.value.owner_unit,
      budget_amount: formData.value.budget_amount,
      region: formData.value.region,
      project_type: formData.value.project_type,
      bid_open_date: formData.value.bid_open_date,
      plan_code: formData.value.plan_code || undefined,
      agency_project_code: formData.value.agency_project_code || undefined,
    })
    ElMessage.success('项目立项成功！')
    router.push(`/projects/${projectId.value}/evaluation`)
  } catch (err) {
    ElMessage.error('确认失败：' + (err instanceof Error ? err.message : String(err)))
  } finally {
    isConfirming.value = false
  }
}

function goBack() {
  router.push(`/projects/${projectId.value}/upload`)
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
.pdf-preview-wrapper {
  position: sticky;
  top: 20px;
}
.pdf-card {
  border-radius: 12px;
}
.pdf-viewer {
  height: calc(100vh - 220px);
  min-height: 700px;
  width: 100%;
}
.pdf-iframe {
  width: 100%;
  height: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}
.form-card {
  border-radius: 12px;
}
.ocr-form :deep(.el-form-item__label) {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 2px !important;
}
.ocr-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.ocr-form :deep(.el-input__wrapper),
.ocr-form :deep(.el-select__wrapper) {
  border-radius: 6px;
}
</style>
