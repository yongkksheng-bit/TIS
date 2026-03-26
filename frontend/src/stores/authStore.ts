import { defineStore } from 'pinia'
import { ref } from 'vue'

interface User {
  id: number
  username: string
  role: 'specialist' | 'boss' | 'finance'
}

export const useAuthStore = defineStore('auth', () => {
  const currentUser = ref<User>({
    id: 1,
    username: 'specialist',
    role: 'specialist'
  })

  function setRole(role: User['role']) {
    currentUser.value.role = role
  }

  return { currentUser, setRole }
})
