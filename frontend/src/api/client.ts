import axios from 'axios'
import { mockClient } from './mock'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const baseURL = (import.meta.env.VITE_API_BASE_URL === undefined ? '' : import.meta.env.VITE_API_BASE_URL)

export const apiClient = axios.create({
  baseURL,
  timeout: 300000, // 300s — accommodates long-text chapter generation (应急预案/项目团队) — accommodates large PDF chunking + GPU embedding on RTX 3060
})

// Add request interceptor to convert camelCase -> snake_case
apiClient.interceptors.request.use((config) => {
  if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData) && !(config.data instanceof File)) {
    config.data = toSnakeCase(config.data)
  }
  return config
})

// Response interceptor: snake_case -> camelCase, then return data
apiClient.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object') {
      response.data = toCamelCase(response.data)
    }
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// Mock client — returns promise that resolves immediately
export const mock = mockClient

// --- Case conversion helpers ---

function toSnakeCase(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toSnakeCase)
  if (obj && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj)) {
      result[camelToSnake(key)] = toSnakeCase(value)
    }
    return result
  }
  return obj
}

function toCamelCase(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toCamelCase)
  if (obj && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj)) {
      result[snakeToCamel(key)] = toCamelCase(value)
    }
    return result
  }
  return obj
}

function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}
