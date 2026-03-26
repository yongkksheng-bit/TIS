// Mock API client for VITE_USE_MOCK=true mode
// Returns resolved promises with mock data

const mockClient = {
  get: async (url: string) => {
    console.log(`[MOCK GET] ${url}`)
    return { data: null }
  },
  post: async (url: string, data?: unknown) => {
    console.log(`[MOCK POST] ${url}`, data)
    return { data: { success: true } }
  },
  put: async (url: string, data?: unknown) => {
    console.log(`[MOCK PUT] ${url}`, data)
    return { data: { success: true } }
  },
  delete: async (url: string) => {
    console.log(`[MOCK DELETE] ${url}`)
    return { data: { success: true } }
  },
}

export { mockClient as mockClient }
