import axios from 'axios'
import { clearAuth, getToken } from '../auth'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const status = err?.response?.status
    if (status === 401) {
      clearAuth()
      import('../router').then(({ router }) => {
        if (router.currentRoute.value.path !== '/login') router.push('/login')
      })
    }
    const message =
      err?.response?.data?.error?.message || err?.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)
