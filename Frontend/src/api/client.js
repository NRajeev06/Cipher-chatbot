import axios from 'axios'

/**
 * Dynamic API base URL resolution:
 * - Local development: defaults to '/api' to use Vite dev proxy (vite.config.js -> http://localhost:8000)
 * - Production: uses VITE_API_URL (e.g., https://your-backend.onrender.com or https://your-backend.onrender.com/api)
 */
export const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  if (!envUrl || envUrl.trim() === '' || envUrl.trim() === '/api') {
    return '/api'
  }
  const cleanUrl = envUrl.trim().replace(/\/+$/, '')
  return cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`
}

export const API_BASE_URL = getApiBaseUrl()

// Debug log to verify environment variable resolution in browser console
console.log('[CIPHER API CONFIG]', {
  raw_vite_env: import.meta.env.VITE_API_URL,
  computed_base_url: API_BASE_URL,
  mode: import.meta.env.MODE
})

const api = axios.create({ 
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Attach token to every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('cipher_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

// Handle 401 Unauthorized globally
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response && err.response.status === 401) {
      // Don't auto-redirect if we are already on login page
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('cipher_token')
        localStorage.removeItem('cipher_user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api
