import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Project {
  id: number
  projectName: string
  projectType: string
  ownerUnit: string
  region: string
  budgetAmount: number
  status: string
  relationshipFlag: boolean
  generationMode: string
  bidOpenDate: string
  pdfFile?: string
  bossInsiderNotes?: string
  createdAt?: string
  isRetender?: boolean
  parentProjectId?: number | null
  planCode?: string | null
  agencyProjectCode?: string | null
}

export interface TrashProject {
  id: number
  projectName: string
  projectType: string
  ownerUnit: string
  region: string
  budgetAmount: number
  status: string
  planCode: string | null
  agencyProjectCode: string | null
  createdAt: string
}

/** Pending clone state — set when user right-clicks "克隆：新一期招标" */
export interface PendingClone {
  sourceProjectId: number
  sourceProjectName: string
  cloneType: 'rebid' | 'annual_renewal'
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const trashProjects = ref<TrashProject[]>([])
  const currentProject = ref<Project | null>(null)
  /** Set when context-menu "新一期招标" is clicked; cleared after clone or cancel */
  const pendingClone = ref<PendingClone | null>(null)

  function setCurrentProject(project: Project) {
    currentProject.value = project
  }

  function setPendingClone(sourceProjectId: number, sourceProjectName: string, cloneType: 'rebid' | 'annual_renewal') {
    pendingClone.value = { sourceProjectId, sourceProjectName, cloneType }
  }

  function clearPendingClone() {
    pendingClone.value = null
  }

  async function fetchTrashProjects(): Promise<void> {
    try {
      const { apiClient } = await import('@/api/client')
      const data = await apiClient.get('/projects/trash') as TrashProject[]
      trashProjects.value = data || []
    } catch (err) {
      console.error('fetchTrashProjects failed:', err)
      trashProjects.value = []
    }
  }

  async function restoreProject(projectId: number): Promise<void> {
    try {
      const { apiClient } = await import('@/api/client')
      await apiClient.post(`/projects/${projectId}/restore`)
      trashProjects.value = trashProjects.value.filter(p => p.id !== projectId)
    } catch (err) {
      console.error('restoreProject failed:', err)
      throw err
    }
  }

  async function hardDeleteProject(projectId: number): Promise<void> {
    try {
      const { apiClient } = await import('@/api/client')
      await apiClient.delete(`/projects/${projectId}/hard-delete`)
      trashProjects.value = trashProjects.value.filter(p => p.id !== projectId)
    } catch (err) {
      console.error('hardDeleteProject failed:', err)
      throw err
    }
  }

  async function clearTrash(): Promise<{ cleared: unknown[]; errors: unknown[] }> {
    try {
      const { apiClient } = await import('@/api/client')
      const result = await apiClient.post('/projects/clear-trash') as { cleared: unknown[]; errors: unknown[] }
      trashProjects.value = []
      return result
    } catch (err) {
      console.error('clearTrash failed:', err)
      throw err
    }
  }

  async function fetchProjects(role?: string): Promise<void> {
    try {
      const { apiClient } = await import('@/api/client')
      const url = role ? `/projects?role=${encodeURIComponent(role)}` : '/projects'
      const data = await apiClient.get(url) as Project[]
      if (Array.isArray(data)) {
        projects.value = data
      } else {
        console.error('fetchProjects: API 异常，收到非数组数据:', data)
      }
    } catch (err) {
      // 不清空原数据！保留缓存防止网络抖动导致白屏
      console.warn('fetchProjects failed, preserving existing data:', err)
    }
  }

  async function fetchProjectById(id: number): Promise<Project | null> {
    try {
      const { apiClient } = await import('@/api/client')
      const data = await apiClient.get(`/projects/${id}`) as Project
      // Update in-place if exists, otherwise add
      const idx = projects.value.findIndex(p => p.id === id)
      if (idx >= 0) {
        projects.value[idx] = data
      } else {
        projects.value.push(data)
      }
      return data
    } catch (err) {
      console.error('fetchProjectById failed:', err)
      return null
    }
  }

  return {
    projects,
    trashProjects,
    currentProject,
    pendingClone,
    setCurrentProject,
    setPendingClone,
    clearPendingClone,
    fetchProjects,
    fetchProjectById,
    fetchTrashProjects,
    restoreProject,
    hardDeleteProject,
    clearTrash,
  }
})
