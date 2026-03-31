<template>
  <el-config-provider :locale="zhCn">
    <AppLayout />
  </el-config-provider>
</template>
<script setup lang="ts">
import AppLayout from '@/layout/AppLayout.vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
</script>
