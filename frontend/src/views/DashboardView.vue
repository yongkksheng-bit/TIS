<template>
  <div>
    <h2>项目列表</h2>
    <p>共 {{ projectStore.projects.length }} 个项目</p>
    <router-link to="/projects/1/upload">
      <el-button type="primary">新建项目</el-button>
    </router-link>
  </div>
</template>
<script setup lang="ts">
import { useProjectStore } from '@/stores/projectStore'
const projectStore = useProjectStore()
</script>
