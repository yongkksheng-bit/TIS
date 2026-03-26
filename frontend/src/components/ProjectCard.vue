<template>
  <div
    class="border rounded-xl p-4 bg-white shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-200 cursor-pointer"
    @click="emit('click', project)"
  >
    <h3 class="text-lg font-medium text-gray-800 mb-2">{{ project.project_name }}</h3>
    <div class="mb-3">
      <StatusBadge :status="project.status" />
    </div>
    <p class="text-sm text-gray-600 mb-1">{{ project.owner_unit }} · {{ project.region }}</p>
    <p class="text-sm text-gray-900 font-medium mb-1">¥{{ formatMoney(project.budget_amount) }}</p>
    <p v-if="project.created_at" class="text-xs text-gray-400 mt-2">{{ project.created_at }}</p>
  </div>
</template>

<script setup lang="ts">
import StatusBadge from './StatusBadge.vue'

interface Project {
  id: number
  project_name: string
  owner_unit: string
  region: string
  budget_amount: number
  status: string
  created_at?: string
}

defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  (e: 'click', project: Project): void
}>()

function formatMoney(amount: number): string {
  if (amount >= 10000) {
    return (amount / 10000).toFixed(1) + '万'
  }
  return amount.toLocaleString()
}
</script>
