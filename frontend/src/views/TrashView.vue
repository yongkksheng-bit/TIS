<template>
  <div class="trash-view">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-gray-800">回收站</h1>
        <p class="text-sm text-gray-500 mt-1">共 {{ projectStore.trashProjects.length }} 个已删除项目</p>
      </div>
      <div class="flex gap-3">
        <el-button
          v-if="projectStore.trashProjects.length > 0"
          type="danger"
          size="large"
          @click="handleClearAll"
        >
          <el-icon class="mr-1"><Delete /></el-icon>
          清空全部
        </el-button>
        <el-button size="large" @click="router.push('/')">
          <el-icon class="mr-1"><Back /></el-icon>
          返回项目列表
        </el-button>
      </div>
    </div>

    <!-- Trash project grid -->
    <div
      v-if="projectStore.trashProjects.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    >
      <div
        v-for="project in projectStore.trashProjects"
        :key="project.id"
        class="trash-card"
      >
        <!-- Card header with status stripe -->
        <div class="card-header">
          <div class="status-stripe discarded"></div>
          <div class="flex-1">
            <h3 class="project-name">{{ project.projectName }}</h3>
            <p class="project-unit">{{ project.ownerUnit || '未知单位' }}</p>
          </div>
        </div>

        <!-- Card body -->
        <div class="card-body">
          <div class="info-row">
            <span class="label">项目类型</span>
            <span class="value">{{ project.projectType || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="label">采购计划编号</span>
            <span class="value code">{{ project.planCode || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="label">采购项目编号</span>
            <span class="value code">{{ project.agencyProjectCode || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="label">预算金额</span>
            <span class="value">¥{{ formatBudget(project.budgetAmount) }}</span>
          </div>
          <div class="info-row">
            <span class="label">删除时间</span>
            <span class="value">{{ formatDate(project.createdAt) }}</span>
          </div>
        </div>

        <!-- Card footer actions -->
        <div class="card-footer">
          <el-button type="success" @click="handleRestore(project.id)">
            <el-icon class="mr-1"><RefreshRight /></el-icon>
            恢复项目
          </el-button>
          <el-button type="danger" @click="handleHardDelete(project.id, project.projectName)">
            <el-icon class="mr-1"><Delete /></el-icon>
            永久销毁
          </el-button>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <el-empty
      v-else
      description="回收站为空，没有已删除的项目"
      class="my-12"
    >
      <el-button type="primary" @click="router.push('/')">返回项目列表</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Delete, Back, RefreshRight } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import type { TrashProject } from '@/stores/projectStore'

const router = useRouter()
const projectStore = useProjectStore()

onMounted(async () => {
  await projectStore.fetchTrashProjects()
})

function formatBudget(amount: number): string {
  if (!amount) return '0.00'
  return amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return dateStr
  }
}

async function handleRestore(projectId: number) {
  try {
    await projectStore.restoreProject(projectId)
    ElMessage.success('项目已从回收站恢复')
  } catch {
    ElMessage.error('恢复失败，请重试')
  }
}

async function handleHardDelete(projectId: number, projectName: string) {
  try {
    await ElMessageBox.confirm(
      `「${projectName}」将永久销毁，数据库记录、归档文件、知识向量将被三方联动清除，此操作不可恢复！`,
      '危险：永久销毁确认',
      {
        confirmButtonText: '永久销毁',
        cancelButtonText: '取消',
        type: 'error',
        icon: Delete,
      }
    )
    await projectStore.hardDeleteProject(projectId)
    ElMessage.success('项目已永久销毁')
    // 重新拉取列表，确保与后端同步
    await projectStore.fetchTrashProjects()
  } catch (err: unknown) {
    const errObj = err as { type?: string; response?: { data?: { detail?: string } } }
    if (errObj?.type === 'cancel' || errObj?.type === 'close') return
    const detail = errObj?.response?.data?.detail
    ElMessage.error(detail ? `销毁失败：${detail}` : '销毁失败，请重试')
  }
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      `回收站中全部 ${projectStore.trashProjects.length} 个项目将被永久销毁，数据库记录、归档文件、知识向量将被三方联动清除，此操作不可恢复！`,
      '危险：清空回收站确认',
      {
        confirmButtonText: '全部永久销毁',
        cancelButtonText: '取消',
        type: 'error',
        icon: Delete,
      }
    )
    const result = await projectStore.clearTrash()
    // 重新拉取列表，确保与后端同步
    await projectStore.fetchTrashProjects()
    if (result.errors && result.errors.length > 0) {
      ElMessage.warning(`部分项目处理失败：${(result.errors[0] as { error: string }).error}`)
    } else {
      ElMessage.success('回收站已清空')
    }
  } catch (err: unknown) {
    const errObj = err as { type?: string; response?: { data?: { detail?: string } } }
    if (errObj?.type === 'cancel' || errObj?.type === 'close') return
    const detail = errObj?.response?.data?.detail
    ElMessage.error(detail ? `清空失败：${detail}` : '清空失败，请重试')
  }
}
</script>

<style scoped>
.trash-view {
  padding: 24px;
}

.trash-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s;
}

.trash-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  align-items: stretch;
  padding: 0;
  position: relative;
  background: #fafafa;
}

.status-stripe {
  width: 6px;
  flex-shrink: 0;
}

.status-stripe.discarded {
  background: linear-gradient(180deg, #909399 0%, #606266 100%);
}

.flex-1 {
  flex: 1;
  padding: 16px;
}

.project-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 4px 0;
  line-height: 1.3;
}

.project-unit {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.card-body {
  padding: 12px 16px;
  flex: 1;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}

.label {
  color: #909399;
}

.value {
  color: #303133;
  font-weight: 500;
}

.value.code {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: #606266;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  background: #fafafa;
}
</style>
