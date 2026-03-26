<template>
  <el-tag :type="tagType" :effect="effect">
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
}>()

const statusMap: Record<string, { type: string; effect: string; label: string }> = {
  uploaded: { type: 'info', effect: 'light', label: '已上传' },
  parsing: { type: 'warning', effect: 'light', label: '解析中' },
  parsed: { type: 'success', effect: 'light', label: '已解析' },
  evaluating: { type: 'warning', effect: 'light', label: '评审中' },
  evaluation_ready: { type: 'warning', effect: 'dark', label: '待评审' },
  worthy: { type: 'success', effect: 'dark', label: '合格' },
  unworthy: { type: 'danger', effect: 'dark', label: '不合格' },
  generating_documents: { type: 'warning', effect: 'light', label: '生成中' },
  awaiting_pricing: { type: 'warning', effect: 'dark', label: '待定价' },
  awaiting_review: { type: 'warning', effect: 'dark', label: '待审核' },
  completed: { type: 'success', effect: 'dark', label: '已完成' },
  terminated_by_boss: { type: 'danger', effect: 'dark', label: '已终止' },
  abandoned: { type: 'info', effect: 'plain', label: '已废弃' },
}

const tagType = computed(() => statusMap[props.status]?.type ?? 'info')
const effect = computed(() => statusMap[props.status]?.effect ?? 'light')
const label = computed(() => statusMap[props.status]?.label ?? props.status)
</script>
