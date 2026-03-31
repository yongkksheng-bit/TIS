<template>
  <div
    class="project-card border rounded-xl p-4 bg-white shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer relative overflow-hidden"
    @click="emit('click', project)"
  >
    <!-- Left status stripe -->
    <div
      class="absolute left-0 top-0 bottom-0 w-1"
      :class="statusStripeClass"
    />
    <!-- Delete button (top-right, stops card click) -->
    <el-button
      class="delete-btn"
      type="danger"
      :icon="Delete"
      circle
      size="small"
      text
      @click.stop="emit('delete', project)"
    />
    <div class="pl-3">
      <h3 class="text-base font-semibold text-gray-800 mb-2 leading-snug">{{ project.project_name }}</h3>
      <div class="mb-3">
        <StatusBadge :status="project.status" />
      </div>
      <div class="flex items-center gap-4 text-sm text-gray-500 mb-1">
        <span class="flex items-center gap-1">
          <el-icon size="12"><OfficeBuilding /></el-icon>
          {{ project.owner_unit }}
        </span>
        <span class="flex items-center gap-1">
          <el-icon size="12"><Location /></el-icon>
          {{ project.region }}
        </span>
      </div>
      <p class="text-sm font-bold text-gray-900 mt-2">
        预算：
        <span class="text-blue-600">{{ formatMoney(project.budget_amount) }}</span>
      </p>
      <p v-if="project.created_at" class="text-xs text-gray-400 mt-2">
        创建于 {{ project.created_at?.substring(0, 10) }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { OfficeBuilding, Location, Delete } from '@element-plus/icons-vue'

export interface Project {
  id: number
  project_name: string
  owner_unit: string
  region: string
  budget_amount: number
  status: string
  created_at?: string
  // Additional fields may exist in store models but are not rendered in the card
}

// Status-based left stripe colors for enterprise UX
const STATUS_STRIPE_MAP: Record<string, string> = {
  uploaded: 'bg-gray-300',
  parsing: 'bg-blue-400',
  parsed: 'bg-blue-500',
  evaluating: 'bg-orange-400',
  evaluation_ready: 'bg-orange-500',
  generating_documents: 'bg-purple-400',
  awaiting_pricing: 'bg-purple-500',
  awaiting_review: 'bg-yellow-400',
  formal_review: 'bg-yellow-500',
  pricing: 'bg-red-400',
  completed: 'bg-green-500',
  worthy: 'bg-green-600',
  unworthy: 'bg-gray-400',
  terminated_by_boss: 'bg-red-600',
  abandoned: 'bg-gray-500',
}

function formatMoney(amount: number): string {
  if (!amount) return '未披露'
  if (amount >= 10000) {
    return (amount / 10000).toFixed(1) + ' 万元'
  }
  return amount.toLocaleString('zh-CN') + ' 元'
}

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  (e: 'click', project: Project): void
  (e: 'delete', project: Project): void
}>()

const statusStripeClass = computed(() => {
  return STATUS_STRIPE_MAP[props.project.status] || 'bg-gray-300'
})
</script>

<style scoped>
.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}
.project-card:hover .delete-btn {
  opacity: 1;
}
</style>
