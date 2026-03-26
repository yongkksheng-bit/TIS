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
  created_at?: string
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([
    {
      id: 1,
      project_name: 'XX学校2026年食堂配送项目',
      project_type: 'service',
      owner_unit: '深圳市XX学校',
      region: '华南',
      budget_amount: 1500000,
      status: 'evaluation_ready',
      relationship_flag: false,
      generation_mode: 'auto',
      bid_open_date: '2026-04-15',
      created_at: '2026-03-20',
    },
    {
      id: 2,
      project_name: 'YY单位办公楼保洁服务',
      project_type: 'service',
      owner_unit: '广州市YY单位',
      region: '华南',
      budget_amount: 800000,
      status: 'completed',
      relationship_flag: true,
      generation_mode: 'guided',
      bid_open_date: '2026-03-01',
      created_at: '2026-02-15',
    },
    {
      id: 3,
      project_name: 'ZZ医院物业管理服务',
      project_type: 'service',
      owner_unit: '佛山市ZZ医院',
      region: '华南',
      budget_amount: 3200000,
      status: 'worthy',
      relationship_flag: false,
      generation_mode: 'auto',
      bid_open_date: '2026-05-10',
      created_at: '2026-03-18',
    },
    {
      id: 4,
      project_name: 'AA学院空调维护保养',
      project_type: 'maintenance',
      owner_unit: '东莞市AA学院',
      region: '华南',
      budget_amount: 450000,
      status: 'awaiting_pricing',
      relationship_flag: false,
      generation_mode: 'auto',
      bid_open_date: '2026-04-20',
      created_at: '2026-03-22',
    },
  ] as Project[])
  const currentProject = ref<Project | null>(null)

  function setCurrentProject(project: Project) {
    currentProject.value = project
  }

  return { projects, currentProject, setCurrentProject }
})
