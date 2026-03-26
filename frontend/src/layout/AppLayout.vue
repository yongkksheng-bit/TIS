<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="header-left">
        <h1 class="app-title">TIS 招标智能系统</h1>
      </div>
      <div class="header-right">
        <el-tag>{{ authStore.currentUser.role }}</el-tag>
        <el-select v-model="authStore.currentUser.role" class="role-select" @change="authStore.setRole">
          <el-option label="专员" value="specialist" />
          <el-option label="老板" value="boss" />
          <el-option label="财务" value="finance" />
        </el-select>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" class="app-sidebar">
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>项目列表</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore'
import { HomeFilled } from '@element-plus/icons-vue'

const authStore = useAuthStore()
</script>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.app-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.role-select {
  width: 100px;
}
.app-sidebar {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.app-main {
  background: #f5f7fa;
  padding: 20px;
}
</style>
