<template>
  <div>
    <h2>项目回顾</h2>
    <p>回顾项目执行情况</p>
  </div>
</template>
<script setup lang="ts">
import { useProjectStore } from '@/stores/projectStore'
const projectStore = useProjectStore()
</script>
