import axios from 'axios'
import { mockClient } from './mock'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL,
  timeout: 30000,
})

// Response interceptor
apiClient.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// Mock client — returns promise that resolves immediately
export const mock = mockClient
