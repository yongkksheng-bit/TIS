import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Project {
  id: number
  project_name: string
  status: string
  budget_amount: number
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)

  return { projects, currentProject }
})
