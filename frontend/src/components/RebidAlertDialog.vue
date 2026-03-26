<template>
  <el-dialog
    v-model="visible"
    title="⚠️ 检测到同类历史项目"
    width="520px"
    :close-on-click-modal="false"
  >
    <div v-if="alertData">
      <el-alert type="warning" :closable="false" class="mb-4">
        <template #title>
          <span class="font-medium">新项目与历史项目高度相似</span>
        </template>
      </el-alert>

      <div class="flex flex-col gap-3 mb-4">
        <div class="flex items-center gap-3">
          <el-icon color="#409eff" :size="20"><Document /></el-icon>
          <div>
            <p class="text-sm font-medium">历史项目</p>
            <p class="text-xs text-gray-500">{{ alertData.historicalProject }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <el-icon color="#f56c6c" :size="20"><WarningFilled /></el-icon>
          <div>
            <p class="text-sm font-medium text-red-600">历史结果</p>
            <p class="text-xs text-gray-500">{{ alertData.historicalOutcome }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <el-icon color="#67c23a" :size="20"><Clock /></el-icon>
          <div>
            <p class="text-sm font-medium">时间差</p>
            <p class="text-xs text-gray-500">{{ alertData.timeDiff }}</p>
          </div>
        </div>
      </div>

      <div v-if="alertData.warnings && alertData.warnings.length > 0" class="mb-4">
        <p class="text-sm font-medium mb-2">风险提醒：</p>
        <div v-for="(warning, i) in alertData.warnings" :key="i" class="flex items-start gap-2 mb-1">
          <el-icon color="#f56c6c" :size="16" class="mt-0.5"><WarnTriangleFilled /></el-icon>
          <span class="text-sm text-red-600">{{ warning }}</span>
        </div>
      </div>

      <div v-if="alertData.revivableDraft" class="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
        <div class="flex items-center gap-2 mb-2">
          <el-icon color="#67c23a"><MagicStick /></el-icon>
          <span class="text-sm font-medium text-green-700">可复活草稿</span>
        </div>
        <p class="text-sm text-green-600 mb-2">{{ alertData.revivableDraft.description }}</p>
        <div class="flex items-center justify-between">
          <el-tag type="success" size="small">{{ alertData.revivableDraft.reusability }}% 可复用</el-tag>
          <el-button type="primary" size="small" @click="handleRevive">
            立即复活草稿
          </el-button>
        </div>
      </div>

      <div class="text-xs text-gray-400 text-center mt-2">
        系统已自动关联历史复盘数据，供您参考
      </div>
    </div>

    <template #footer>
      <el-button @click="handleDismiss">暂不处理</el-button>
      <el-button type="primary" @click="handleProceed">继续新建项目</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Document, WarningFilled, Clock, MagicStick, WarnTriangleFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

export interface RebidAlertData {
  historicalProject: string
  historicalOutcome: string
  timeDiff: string
  warnings: string[]
  revivableDraft?: {
    id: number
    description: string
    reusability: string
  }
}

const props = defineProps<{
  modelValue: boolean
  alertData?: RebidAlertData | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const router = useRouter()
const visible = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function handleDismiss() {
  visible.value = false
  router.push('/')
}

function handleProceed() {
  visible.value = false
  router.push('/projects/1/confirm')
}

function handleRevive() {
  visible.value = false
  ElMessage.success('草稿复活成功！正在跳转到技术标编辑台...')
  setTimeout(() => {
    router.push('/projects/2/tech-proposal')
  }, 500)
}
</script>
