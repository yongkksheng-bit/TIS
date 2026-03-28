<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="header-left">
        <div class="logo-mark">TIS</div>
        <div>
          <h1 class="app-title">招标智能系统</h1>
          <p class="app-subtitle">Tender Intelligence System</p>
        </div>
      </div>
      <div class="header-right">
        <el-select v-model="authStore.currentUser.role" class="role-select" @change="authStore.setRole">
          <template #prefix><el-icon><UserFilled /></el-icon></template>
          <el-option label="专员视角" value="specialist" />
          <el-option label="老板视角" value="boss" />
          <el-option label="财务视角" value="finance" />
        </el-select>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="app-sidebar">
        <el-menu :default-active="$route.path" :collapse="false" router>
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>项目列表</span>
          </el-menu-item>
          <el-divider class="my-2" />
          <div class="nav-section-label">工作流</div>
          <el-menu-item index="/projects/new/upload">
            <el-icon><UploadFilled /></el-icon>
            <span>上传标书</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/confirm">
            <el-icon><DocumentChecked /></el-icon>
            <span>资格确认</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/evaluation">
            <el-icon><DataAnalysis /></el-icon>
            <span>评估分析</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/tech-proposal">
            <el-icon><Reading /></el-icon>
            <span>技术标生成</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/pricing">
            <el-icon><Money /></el-icon>
            <span>博弈定价</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/formal-review">
            <el-icon><Finished /></el-icon>
            <span>形式审查</span>
          </el-menu-item>
          <el-menu-item index="/projects/new/output">
            <el-icon><Download /></el-icon>
            <span>最终输出</span>
          </el-menu-item>
          <el-divider class="my-2" />
          <div class="nav-section-label">管理与复盘</div>
          <el-menu-item index="/projects/new/review">
            <el-icon><TrendCharts /></el-icon>
            <span>复盘与洞察</span>
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
import {
  HomeFilled,
  UploadFilled,
  DocumentChecked,
  DataAnalysis,
  Reading,
  Money,
  Finished,
  Download,
  TrendCharts,
  UserFilled,
} from '@element-plus/icons-vue'

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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-bottom: none;
  padding: 0 24px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.logo-mark {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #409eff, #79bbff);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 800;
  font-size: 14px;
  letter-spacing: 0.5px;
}
.app-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1.2;
}
.app-subtitle {
  margin: 0;
  font-size: 10px;
  color: #94a3b8;
  letter-spacing: 1px;
  text-transform: uppercase;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.role-select {
  width: 120px;
}
:deep(.role-select .el-input__wrapper) {
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  box-shadow: none;
  color: #f1f5f9;
}
:deep(.role-select .el-input__inner) {
  color: #f1f5f9;
}
:deep(.role-select .el-select__caret) {
  color: #94a3b8;
}
.app-sidebar {
  background: #ffffff;
  border-right: 1px solid #e4e7ed;
  padding-top: 8px;
}
:deep(.el-menu) {
  border: none;
}
:deep(.el-menu-item) {
  border-radius: 8px;
  margin: 2px 8px;
  height: 40px;
  transition: all 0.2s;
}
:deep(.el-menu-item:hover) {
  background: #f0f7ff;
  color: #409eff;
}
:deep(.el-menu-item.is-active) {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}
.nav-section-label {
  padding: 8px 20px 4px;
  font-size: 10px;
  font-weight: 600;
  color: #c0c8d4;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}
.app-main {
  background: #f5f7fa;
  padding: 24px;
}
</style>
