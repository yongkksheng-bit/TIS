import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Project {
  id: number
  project_name: string
  project_type: string
  owner_unit: string
  region: string
  budget_amount: number
  status: string
  relationship_flag: boolean
  generation_mode: string
  bid_open_date: string
  pdf_file?: string
  boss_insider_notes?: string
  created_at?: string
  is_retender?: boolean
  parent_project_id?: number | null
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)

  function setCurrentProject(project: Project) {
    currentProject.value = project
  }

  async function fetchProjects(role?: string): Promise<void> {
    try {
      const { apiClient } = await import('@/api/client')
      const url = role ? `/projects?role=${encodeURIComponent(role)}` : '/projects'
      const data = await apiClient.get(url) as Project[]
      projects.value = data || []
    } catch (err) {
      console.error('fetchProjects failed:', err)
      projects.value = []
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

  return { projects, currentProject, setCurrentProject, fetchProjects, fetchProjectById }
})
