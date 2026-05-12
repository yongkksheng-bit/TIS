<template>
  <div class="project-card-wrapper">
    <!-- Delete button (absolute, outside dropdown — never triggers card click) -->
    <el-button
      class="delete-btn"
      type="danger"
      :icon="Delete"
      circle
      size="small"
      text
      @click.stop="emit('delete', project)"
    />

    <!-- Context menu dropdown: wraps entire card, triggered by right-click -->
    <el-dropdown
      trigger="contextmenu"
      @command="(cmd: string) => emit('clone', project, cmd as 'rebid' | 'annual_renewal')"
    >
      <!-- Card body — acts as dropdown trigger; left-click = navigate -->
      <div
        class="project-card border rounded-xl p-4 bg-white shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer relative overflow-hidden"
        @click.stop="emit('click', project)"
      >
        <!-- Left status stripe -->
        <div
          class="absolute left-0 top-0 bottom-0 w-1"
          :class="statusStripeClass"
        />
        <div class="pl-3">
          <h3 class="text-base font-semibold text-gray-800 mb-2 leading-snug">{{ project.projectName }}</h3>
          <div class="mb-3">
            <StatusBadge :status="project.status" />
          </div>
          <div class="flex items-center gap-4 text-sm text-gray-500 mb-1">
            <span class="flex items-center gap-1">
              <el-icon size="12"><OfficeBuilding /></el-icon>
              {{ project.ownerUnit }}
            </span>
            <span class="flex items-center gap-1">
              <el-icon size="12"><Location /></el-icon>
              {{ project.region }}
            </span>
          </div>
          <p class="text-sm font-bold text-gray-900 mt-2">
            预算：
            <span class="text-blue-600">{{ formatMoney(project.budgetAmount) }}</span>
          </p>
          <p v-if="project.createdAt" class="text-xs text-gray-400 mt-2">
            创建于 {{ project.createdAt?.substring(0, 10) }}
          </p>
        </div>
      </div>

      <!-- Context menu items -->
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="rebid">
            <el-icon class="mr-1"><DocumentCopy /></el-icon>
            克隆：流标重投
          </el-dropdown-item>
          <el-dropdown-item command="annual_renewal">
            <el-icon class="mr-1"><Upload /></el-icon>
            克隆：新一期招标
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { OfficeBuilding, Location, Delete, DocumentCopy, Upload } from '@element-plus/icons-vue'

export interface Project {
  id: number
  projectName: string
  ownerUnit: string
  region: string
  budgetAmount: number
  status: string
  createdAt?: string
}

// Status-based left stripe colors
const STATUS_STRIPE_MAP: Record<string, string> = {
  uploaded: 'bg-gray-300',
  parsing: 'bg-blue-400',
  parsed: 'bg-blue-500',
  evaluating: 'bg-orange-400',
  evaluation_ready: 'bg-orange-500',
  pending_boss_approval: 'bg-orange-600',
  approved_by_specialist: 'bg-teal-400',
  generating_documents: 'bg-purple-400',
  awaiting_pricing: 'bg-purple-500',
  awaiting_review: 'bg-yellow-400',
  formal_review: 'bg-yellow-500',
  pricing: 'bg-red-400',
  completed: 'bg-green-500',
  worthy: 'bg-green-600',
  unworthy: 'bg-gray-400',
  terminated_by_boss: 'bg-red-600',
  discarded: 'bg-gray-500',
}

function formatMoney(amount: number | undefined | null): string {
  if (amount == null || amount === 0) return '未披露'
  if (amount >= 10000) {
    return (amount / 10000).toFixed(1) + ' 万元'
  }
  return amount.toLocaleString('zh-CN') + ' 元'
}

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  /** Left-click on card body — navigate */
  (e: 'click', project: Project): void
  /** Delete button (top-right, stop propagation) */
  (e: 'delete', project: Project): void
  /** Context menu: command = 'rebid' | 'annual_renewal' */
  (e: 'clone', project: Project, cloneType: 'rebid' | 'annual_renewal'): void
}>()

const statusStripeClass = computed(() => {
  return STATUS_STRIPE_MAP[props.project.status] || 'bg-gray-300'
})
</script>

<style scoped>
.project-card-wrapper {
  position: relative;
}
.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 10;
}
.project-card-wrapper:hover .delete-btn {
  opacity: 1;
}
/* Dropdown fills card body; trigger area for right-click */
:deep(.el-dropdown) {
  display: block;
}
</style>
