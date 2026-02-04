import axios from 'axios'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api',
  timeout: 30000,
})

http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const message =
      err?.response?.data?.error?.message || err?.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)
