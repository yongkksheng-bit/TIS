<template>
  <div class="formal-review-view">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold">形式审查</h2>
        <StatusBadge :status="currentProject?.status || ''" />
      </div>
      <p v-if="currentProject" class="text-sm text-gray-500 mt-1">
        {{ currentProject.projectName }} · {{ currentProject.ownerUnit }}
      </p>
    </div>

    <!-- Init banner (shown when no checklist exists) -->
    <el-alert
      v-if="!loading && checklistItems.length === 0"
      type="info"
      :closable="false"
      class="mb-4 init-banner"
    >
      <template #title>
        <span>尚未初始化质检清单</span>
      </template>
      <template #default>
        <span class="text-sm text-gray-600">点击下方按钮，系统将自动生成形式审查清单（基于资质有效期、报价合规性、技术标完整性等维度）。</span>
        <el-button type="primary" size="small" class="ml-4" :loading="initLoading" @click="initChecklist">
          初始化质检清单
        </el-button>
      </template>
    </el-alert>

    <!-- Split-pane layout -->
    <div v-if="!loading" class="split-pane">
      <!-- LEFT: Draft Preview (60%) -->
      <div class="preview-pane">
        <el-card class="preview-card">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-medium">标书初稿预览</span>
              <el-tag v-if="sections.length" type="success" size="small">
                {{ sections.length }} 个章节
              </el-tag>
              <el-tag v-else type="info" size="small">暂无内容</el-tag>
            </div>
          </template>

          <!-- Loading skeleton -->
          <div v-if="previewLoading" class="flex justify-center py-12">
            <el-icon class="is-loading text-2xl text-blue-400"><Loading /></el-icon>
          </div>

          <!-- Empty state -->
          <div v-else-if="!projectData" class="text-center text-gray-400 py-12">
            <el-icon :size="48" class="mb-3"><Document /></el-icon>
            <p>暂无预览内容</p>
            <p class="text-xs mt-1">请先完成技术标生成和定价决策</p>
          </div>

          <!-- Draft content -->
          <div v-else class="draft-content">
            <!-- Project info section -->
            <div class="draft-section project-info-section">
              <h3 class="draft-section-title">项目基础信息</h3>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">项目名称</span>
                  <span class="info-value">{{ projectData.projectName }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">业主单位</span>
                  <span class="info-value">{{ projectData.ownerUnit }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">地区</span>
                  <span class="info-value">{{ projectData.region }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">预算金额</span>
                  <span class="info-value text-blue-600 font-bold">
                    {{ projectData.budgetAmount ? '¥' + Number(projectData.budgetAmount).toLocaleString() : '未披露' }}
                  </span>
                </div>
                <div v-if="projectData.planCode" class="info-item">
                  <span class="info-label">计划编号</span>
                  <span class="info-value">{{ projectData.planCode }}</span>
                </div>
                <div v-if="projectData.relationshipFlag" class="info-item">
                  <span class="info-label">关系标识</span>
                  <el-tag type="warning" size="small">有关系渠道</el-tag>
                </div>
              </div>
            </div>

            <!-- Tech proposal sections -->
            <div v-for="sec in sections" :key="sec.sectionName" class="draft-section">
              <h3 class="draft-section-title">{{ sec.sectionName }}</h3>
              <div v-if="sec.content" class="section-content markdown-body" v-html="parseMarkdown(sec.content)" />
              <div v-else class="section-content text-gray-400">（内容为空）</div>
            </div>

            <!-- Pricing summary -->
            <div v-if="projectData.bossFinalPrice" class="draft-section pricing-summary">
              <h3 class="draft-section-title">最终报价</h3>
              <div class="final-price-display">
                <span class="final-price-label">竞标报价</span>
                <span class="final-price-value">¥{{ Number(projectData.bossFinalPrice).toLocaleString() }}</span>
                <span v-if="projectData.systemSuggestedOptimal" class="final-price-optimal ml-4">
                  系统建议价 ¥{{ Number(projectData.systemSuggestedOptimal).toLocaleString() }}
                </span>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- Divider -->
      <div class="pane-divider" />

      <!-- RIGHT: Checklist (40%) -->
      <div class="checklist-pane">
        <!-- Progress bar -->
        <el-card class="progress-card mb-3">
          <div class="progress-header">
            <span class="font-medium text-sm">审查进度</span>
            <span class="text-sm" :class="progressPct >= 100 ? 'text-green-500' : 'text-gray-500'">
              {{ confirmedCount }}/{{ mandatoryCount }} 项
            </span>
          </div>
          <el-progress
            :percentage="progressPct"
            :color="progressPct >= 100 ? '#67c23a' : '#409eff'"
            :show-text="true"
            :stroke-width="10"
            class="mt-2"
          />
          <p v-if="fatalPending > 0" class="text-xs text-red-500 mt-1">
            ⚠️ {{ fatalPending }} 项致命风险待处理
          </p>
        </el-card>

        <!-- 投标文件封装清单 -->
        <el-card class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-medium text-sm">投标文件封装清单</span>
              <el-tag type="info" size="small">全局就绪状态</el-tag>
            </div>
          </template>
          <div class="package-grid">
            <div
              v-for="pkg in packageList"
              :key="pkg.id"
              class="package-item"
              :class="{ 'package-ready': pkg.ready, 'package-pending': !pkg.ready }"
            >
              <div class="package-icon-wrap">
                <el-icon v-if="pkg.ready" class="package-icon text-green-500"><CircleCheck /></el-icon>
                <el-icon v-else class="package-icon text-gray-300"><Clock /></el-icon>
              </div>
              <div class="package-info">
                <div class="package-type">{{ pkg.type }}</div>
                <div class="package-desc">{{ pkg.desc }}</div>
              </div>
              <div class="package-status">
                <el-tag v-if="pkg.ready" type="success" size="small">已就绪</el-tag>
                <el-tag v-else type="warning" size="small">待生成</el-tag>
              </div>
            </div>
          </div>
        </el-card>

        <!-- Checklist categories -->
        <div v-for="cat in reviewCategories" :key="cat.key" class="category-block mb-3">
          <div class="category-header">
            <span class="category-name">{{ cat.label }}</span>
            <el-tag :type="cat.confirmed === cat.count ? 'success' : 'warning'" size="small">
              {{ cat.confirmed }}/{{ cat.count }}
            </el-tag>
          </div>

          <div class="checklist-items">
            <div
              v-for="item in cat.items"
              :key="item.id"
              class="checklist-item"
              :class="statusClass(item)"
            >
              <div class="item-main">
                <el-checkbox
                  :model-value="item.specialistStatus !== 'pending'"
                  size="small"
                  @change="toggleItem(item)"
                />
                <div class="item-body">
                  <span class="item-title">{{ item.checkTitle }}</span>
                  <div class="item-meta">
                    <el-tag :type="systemStatusTagType(item.systemStatus)" size="small" class="mr-1">
                      {{ systemStatusLabel(item.systemStatus) }}
                    </el-tag>
                    <el-tag v-if="item.riskLevel === 'fatal'" type="danger" size="small" effect="dark">致命</el-tag>
                    <el-tag v-else-if="item.riskLevel === 'warning'" type="warning" size="small">警告</el-tag>
                    <span v-if="item.referenceClause" class="text-xs text-gray-400 ml-1">
                      {{ item.referenceClause }}
                    </span>
                  </div>
                  <p v-if="item.specialistNotes" class="text-xs text-gray-500 mt-1 ml-6">
                    {{ item.specialistNotes }}
                  </p>
                </div>
              </div>
              <!-- Quick actions on each item -->
              <div class="item-actions">
                <el-button
                  size="small"
                  type="success"
                  :disabled="item.specialistStatus === 'confirmed'"
                  @click="confirmItem(item)"
                  title="确认"
                >
                  <el-icon><Check /></el-icon>
                </el-button>
                <el-button
                  size="small"
                  type="warning"
                  :disabled="item.specialistStatus === 'corrected'"
                  @click="correctItem(item)"
                  title="修正"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :disabled="item.specialistStatus === 'deleted'"
                  @click="deleteItem(item)"
                  title="删除"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- Bottom action bar -->
        <div class="bottom-action-bar">
          <el-button
            type="primary"
            size="large"
            class="unlock-btn"
            :disabled="progressPct < 100"
            :loading="completeLoading"
            @click="completeReview"
          >
            <el-icon class="mr-1"><CircleCheck /></el-icon>
            {{ progressPct < 100 ? `核对无误，生成最终标书` : '核对无误，生成最终标书' }}
          </el-button>
          <p v-if="progressPct < 100" class="action-hint">
            请完成全部 {{ mandatoryCount }} 项审查后解锁
          </p>
          <p v-else class="action-hint text-green-500">
            ✓ 所有风险项已处理，可以生成最终标书
          </p>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex justify-center py-16">
      <el-icon class="is-loading text-4xl text-blue-500"><Loading /></el-icon>
    </div>

    <!-- Correct dialog -->
    <el-dialog v-model="correctDialogVisible" title="修正审查项" width="480px">
      <el-form label-position="top">
        <el-form-item label="修正证据（页码或说明）">
          <el-input v-model="correctEvidence" type="textarea" :rows="3" placeholder="请输入修正证据，如：P45页已补充签字" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="correctNotes" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="submitCorrect">确认修正</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import StatusBadge from '@/components/StatusBadge.vue'
import { Loading, Document, Check, Edit, Delete, CircleCheck, Clock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiClient } from '@/api/client'
import { marked } from 'marked'

// Configure marked for safe HTML output
marked.setOptions({ breaks: true, gfm: true })

function parseMarkdown(content: string | null | undefined): string {
  if (!content) return ''
  return marked.parse(content) as string
}

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const raw = route.params.id
  if (!raw) return NaN
  const parsed = Number(raw)
  return isNaN(parsed) ? NaN : parsed
})

const loading = ref(true)
const previewLoading = ref(true)
const initLoading = ref(false)
const completeLoading = ref(false)
const currentProject = computed(() => projectStore.projects.find(p => p.id === projectId.value))

// ─── Draft preview data ────────────────────────────────────────────────────
const projectData = ref<any>(null)
const sections = ref<any[]>([])

// ─── 投标文件封装清单数据 ───────────────────────────────────────────────
const packageList = ref<Array<{ id: number; type: string; desc: string; ready: boolean }>>([])

function getDefaultPackageList() {
  return [
    { id: 1, type: '技术标',   desc: '技术方案正文（5章节）',  ready: false },
    { id: 2, type: '商务标',   desc: '商务资质及证照',           ready: false },
    { id: 3, type: '投标函',   desc: '法定代表人授权书',         ready: false },
    { id: 4, type: '报价单',   desc: '投标价格明细表',          ready: false },
    { id: 5, type: '封装清单', desc: '文件目录及页码索引',       ready: false },
    { id: 6, type: '电子签章', desc: 'PDF 签名及骑缝章',        ready: false },
  ]
}

async function loadPackageStatus() {
  try {
    const resp = await apiClient.get(`/api/v1/projects/${projectId.value}/document-packages`) as any
    const data = (resp as any).data || resp
    if (data && Array.isArray(data.packages) && data.packages.length > 0) {
      packageList.value = data.packages.map((pkg: any) => ({
        id: pkg.id ?? 0,
        type: pkg.type ?? '未知',
        desc: pkg.desc ?? '加载失败',
        ready: pkg.ready ?? false,
      }))
    } else {
      // 接口返回了但结构异常 → 保留骨架，降级 ready
      packageList.value = getDefaultPackageList()
    }
  } catch (err) {
    console.warn('document-packages load failed:', err)
    // 优雅降级：不清空，保留骨架，所有卡片 ready=false
    packageList.value = getDefaultPackageList()
  }
}

// ─── Checklist data ────────────────────────────────────────────────────────
interface ChecklistItem {
  id: number
  checkTitle: string
  checkCategory: string
  referenceClause: string | null
  systemStatus: string
  specialistStatus: string
  specialistNotes: string | null
  riskLevel: string
}

const checklistItems = ref<ChecklistItem[]>([])

// Correct dialog state
const correctDialogVisible = ref(false)
const correctEvidence = ref('')
const correctNotes = ref('')
const itemBeingCorrected = ref<ChecklistItem | null>(null)

// ─── Computed ──────────────────────────────────────────────────────────────
const reviewCategories = computed(() => {
  const cats = [
    { key: 'qualification_validity', label: '资质有效性' },
    { key: 'price_compliance', label: '报价合规性' },
    { key: 'document_integrity', label: '技术标完整性' },
    { key: 'signature_seal', label: '签字盖章' },
    { key: 'seal_requirements', label: '封装要求' },
  ]
  return cats
    .map(c => {
      const items = checklistItems.value.filter(i => i.checkCategory === c.key)
      return {
        ...c,
        items,
        count: items.length,
        confirmed: items.filter(i => i.specialistStatus !== 'pending').length,
      }
    })
    .filter(c => c.count > 0)
})

const mandatoryCount = computed(() =>
  checklistItems.value.filter(i => i.riskLevel === 'fatal' || i.riskLevel === 'warning').length
)
const confirmedCount = computed(() =>
  checklistItems.value.filter(i => i.specialistStatus !== 'pending').length
)
const fatalPending = computed(() =>
  checklistItems.value.filter(i => i.riskLevel === 'fatal' && i.specialistStatus === 'pending').length
)
const progressPct = computed(() => {
  if (mandatoryCount.value === 0) return 0
  return Math.round((confirmedCount.value / mandatoryCount.value) * 100)
})

// ─── Helpers ───────────────────────────────────────────────────────────────
function systemStatusTagType(status: string) {
  if (status === 'passed') return 'success'
  if (status === 'warning') return 'warning'
  return 'danger'
}
function systemStatusLabel(status: string) {
  if (status === 'passed') return '通过'
  if (status === 'warning') return '警告'
  return '失败'
}
function statusClass(item: ChecklistItem) {
  if (item.specialistStatus === 'confirmed') return 'item-confirmed'
  if (item.specialistStatus === 'corrected') return 'item-corrected'
  if (item.specialistStatus === 'deleted') return 'item-deleted'
  if (item.riskLevel === 'fatal') return 'item-fatal'
  if (item.riskLevel === 'warning') return 'item-warning'
  return ''
}

// ─── API calls ──────────────────────────────────────────────────────────────
async function loadDraftPreview() {
  previewLoading.value = true
  try {
    const resp = await apiClient.get(`/api/v1/projects/${projectId.value}/draft-preview`) as any
    const data = (resp as any).data || resp
    projectData.value = {
      projectName: data.projectName,
      ownerUnit: data.ownerUnit,
      region: data.region,
      budgetAmount: data.budgetAmount,
      planCode: data.planCode,
      relationshipFlag: data.relationshipFlag,
      bossFinalPrice: data.bossFinalPrice,
      systemSuggestedOptimal: data.systemSuggestedOptimal,
    }
    sections.value = data.sections || []
  } catch (err) {
    console.warn('draft-preview failed:', err)
    // 不清空数据，保留原状态，仅 warn
  } finally {
    previewLoading.value = false
  }
}

async function loadChecklist() {
  try {
    const resp = await apiClient.get(`/api/v1/projects/${projectId.value}/formal-review/items`) as any
    const data = (resp as any).data || resp
    checklistItems.value = (Array.isArray(data) ? data : []).map((item: any) => ({
      id: item.id,
      checkTitle: item.checkTitle,
      checkCategory: item.checkCategory,
      referenceClause: item.referenceClause,
      systemStatus: item.systemStatus,
      specialistStatus: item.specialistStatus,
      specialistNotes: item.specialistNotes,
      riskLevel: item.riskLevel,
    }))
  } catch (err) {
    console.warn('Failed to load checklist:', err)
    // 不清空数据，保留原状态，仅 warn
  }
}

async function initChecklist() {
  initLoading.value = true
  try {
    const resp = await apiClient.post(`/api/v1/projects/${projectId.value}/checklists/init`) as any
    const data = (resp as any).data || resp
    if (data.itemsCreated > 0) {
      ElMessage.success(`已生成 ${data.itemsCreated} 项质检清单（含 ${data.fatalCount} 项致命风险）`)
      await loadChecklist()
    } else {
      ElMessage.info('质检清单已存在，无需重复初始化')
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '初始化失败')
  } finally {
    initLoading.value = false
  }
}

async function toggleItem(item: ChecklistItem) {
  // Toggle reverses confirmed ↔ pending
  const newStatus = item.specialistStatus === 'confirmed' ? 'pending' : 'confirmed'
  const action = newStatus === 'confirmed' ? 'confirm' : 'toggle'
  try {
    const resp = await apiClient.put(
      `/api/v1/projects/${projectId.value}/checklists/${item.id}`,
      { action, notes: item.specialistNotes }
    ) as any
    const updated = ((resp as any).data || resp)
    item.specialistStatus = updated.specialistStatus
    item.specialistNotes = updated.specialistNotes
    ElMessage.success(`${item.checkTitle} 已标记为"${newStatus === 'confirmed' ? '已确认' : '待处理'}"`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

async function confirmItem(item: ChecklistItem) {
  try {
    const resp = await apiClient.put(
      `/api/v1/projects/${projectId.value}/checklists/${item.id}`,
      { action: 'confirm', notes: '' }
    ) as any
    const updated = ((resp as any).data || resp)
    item.specialistStatus = updated.specialistStatus
    item.specialistNotes = updated.specialistNotes
    ElMessage.success(`「${item.checkTitle}」已确认`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '确认失败')
  }
}

function correctItem(item: ChecklistItem) {
  itemBeingCorrected.value = item
  correctEvidence.value = ''
  correctNotes.value = ''
  correctDialogVisible.value = true
}

async function submitCorrect() {
  if (!correctEvidence.value.trim()) {
    ElMessage.warning('请填写修正证据')
    return
  }
  const item = itemBeingCorrected.value
  if (!item) return
  try {
    const resp = await apiClient.put(
      `/api/v1/projects/${projectId.value}/checklists/${item.id}`,
      { action: 'correct', notes: `${correctEvidence.value}${correctNotes.value ? ' | ' + correctNotes.value : ''}` }
    ) as any
    const updated = ((resp as any).data || resp)
    item.specialistStatus = updated.specialistStatus
    item.specialistNotes = updated.specialistNotes
    correctDialogVisible.value = false
    ElMessage.success(`「${item.checkTitle}」已修正`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '修正失败')
  }
}

async function deleteItem(item: ChecklistItem) {
  try {
    await ElMessageBox.confirm(`确定删除审查项「${item.checkTitle}」？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const resp = await apiClient.put(
      `/api/v1/projects/${projectId.value}/checklists/${item.id}`,
      { action: 'delete', notes: '' }
    ) as any
    const updated = ((resp as any).data || resp)
    item.specialistStatus = updated.specialistStatus
    item.specialistNotes = updated.specialistNotes
    ElMessage.warning(`「${item.checkTitle}」已删除`)
  } catch {
    // User cancelled
  }
}

async function completeReview() {
  if (progressPct.value < 100) return
  completeLoading.value = true
  try {
    // 1. Try to complete via the backend
    const resp = await apiClient.post(`/api/v1/projects/${projectId.value}/complete`) as any
    const data = (resp as any).data || resp

    // 2. Update local project status
    const idx = projectStore.projects.findIndex(p => p.id === projectId.value)
    if (idx !== -1) {
      projectStore.projects[idx].status = data.newStatus
    }

    ElMessage.success('形式审查通过！正在跳转至最终输出页面...')
    await projectStore.fetchProjectById(projectId.value)
    router.push(`/projects/${projectId.value}/output`)
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    if (detail) {
      ElMessage.error(detail)
    } else {
      ElMessage.error('推进失败，请检查清单是否全部完成')
    }
  } finally {
    completeLoading.value = false
  }
}

onMounted(async () => {
  if (isNaN(projectId.value)) {
    ElMessage.error('项目ID获取失败，请刷新页面后重试')
    return
  }
  loading.value = true
  await projectStore.fetchProjectById(projectId.value)
  await Promise.all([loadDraftPreview(), loadChecklist(), loadPackageStatus()])
  loading.value = false
})
</script>

<style scoped>
.formal-review-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}

/* ─── Split-pane layout ──────────────────────────────────────────── */
.split-pane {
  display: flex;
  gap: 0;
  align-items: flex-start;
  min-height: calc(100vh - 200px);
}

.preview-pane {
  width: 60%;
  flex-shrink: 0;
  padding-right: 12px;
}

.pane-divider {
  width: 1px;
  background: #e4e7ed;
  align-self: stretch;
  margin: 0 12px;
}

.checklist-pane {
  width: 40%;
  flex-shrink: 0;
  padding-left: 12px;
}

/* ─── Preview pane ───────────────────────────────────────────────── */
.preview-card {
  border-radius: 12px;
  position: sticky;
  top: 20px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.draft-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.draft-section {
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 16px;
}
.draft-section:last-child {
  border-bottom: none;
}

.draft-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-label {
  font-size: 11px;
  color: #909399;
  text-transform: uppercase;
}
.info-value {
  font-size: 14px;
  color: #303133;
}

.section-content {
  font-size: 13px;
  line-height: 1.8;
  color: #303133;
}

/* ─── Markdown body styles ─────────────────────────────────────── */
.markdown-body {
  overflow-y: visible;
}
.markdown-body h1 {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 6px;
  margin-bottom: 12px;
  margin-top: 0;
}
.markdown-body h2 {
  font-size: 15px;
  font-weight: 700;
  color: #409eff;
  margin: 16px 0 8px;
}
.markdown-body h3 {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin: 12px 0 6px;
}
.markdown-body p {
  margin: 6px 0;
  line-height: 1.8;
}
.markdown-body ul, .markdown-body ol {
  padding-left: 20px;
  margin: 6px 0;
}
.markdown-body li {
  line-height: 1.8;
  margin: 2px 0;
}
.markdown-body strong {
  font-weight: 700;
  color: #303133;
}
.markdown-body em {
  font-style: italic;
  color: #606266;
}
.markdown-body code {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
}
.markdown-body blockquote {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  margin: 8px 0;
  color: #606266;
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 0 4px 4px 0;
}
.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}
.markdown-body th, .markdown-body td {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  text-align: left;
}
.markdown-body th {
  background: #f5f7fa;
  font-weight: 600;
}

.pricing-summary {
  background: #f0f9eb;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #e1f3d8;
}
.final-price-display {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.final-price-label {
  font-size: 12px;
  color: #606266;
}
.final-price-value {
  font-size: 24px;
  font-weight: 700;
  color: #c0341d;
}
.final-price-optimal {
  font-size: 12px;
  color: #909399;
}

/* ─── Checklist pane ─────────────────────────────────────────────── */
.progress-card {
  border-radius: 12px;
  position: sticky;
  top: 20px;
  z-index: 10;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.category-block {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  overflow: hidden;
}
.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}
.category-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.checklist-items {
  display: flex;
  flex-direction: column;
}
.checklist-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}
.checklist-item:last-child {
  border-bottom: none;
}
.checklist-item:hover {
  background: #fafafa;
}
.item-fatal {
  border-left: 3px solid #f56c6c;
}
.item-warning {
  border-left: 3px solid #e6a23c;
}
.item-confirmed {
  background: #f0f9eb !important;
  border-left: 3px solid #67c23a;
}
.item-corrected {
  background: #fef0f0 !important;
  border-left: 3px solid #e6a23c;
}
.item-deleted {
  background: #f4f4f5 !important;
  opacity: 0.6;
}

.item-main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
}
.item-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.item-title {
  font-size: 13px;
  color: #303133;
  line-height: 1.4;
}
.item-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}

.item-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.checklist-item:hover .item-actions {
  opacity: 1;
}

/* ─── Bottom action bar ──────────────────────────────────────────── */
.bottom-action-bar {
  margin-top: 20px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  text-align: center;
}
.unlock-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
}
.unlock-btn:not(:disabled) {
  background: #67c23a;
  border-color: #67c23a;
}
.action-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* ─── Init banner ────────────────────────────────────────────────── */
.init-banner {
  border-radius: 12px;
}

/* ─── Package grid ─────────────────────────────────────────────── */
.package-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.package-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  transition: all 0.2s;
}
.package-ready {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.package-pending {
  background: #fff7ed;
  border-color: #fed7aa;
}
.package-icon-wrap {
  flex-shrink: 0;
}
.package-info {
  flex: 1;
}
.package-type {
  font-weight: 600;
  font-size: 13px;
  color: #374151;
}
.package-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 1px;
}
</style>
