import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('@/views/DashboardView.vue'),
    },
    {
      path: '/projects/:id/upload',
      component: () => import('@/views/ProjectUploadView.vue'),
    },
    {
      path: '/projects/:id/confirm',
      component: () => import('@/views/ConfirmationView.vue'),
    },
    {
      path: '/projects/:id/evaluation',
      component: () => import('@/views/EvaluationView.vue'),
    },
    {
      path: '/projects/:id/tech-proposal',
      component: () => import('@/views/TechProposalView.vue'),
    },
    {
      path: '/projects/:id/business-proposal',
      component: () => import('@/views/BusinessProposalView.vue'),
    },
    {
      path: '/projects/:id/pricing',
      component: () => import('@/views/PricingView.vue'),
    },
    {
      path: '/projects/:id/formal-review',
      component: () => import('@/views/FormalReviewView.vue'),
    },
    {
      path: '/projects/:id/output',
      component: () => import('@/views/FinalOutputView.vue'),
    },
    {
      path: '/projects/:id/review',
      component: () => import('@/views/ReviewView.vue'),
    },
    {
      path: '/trash',
      component: () => import('@/views/TrashView.vue'),
    },
  ],
})

export default router
