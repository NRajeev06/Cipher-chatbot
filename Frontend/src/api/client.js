import axios from 'axios'

const api = axios.create({ 
  baseURL: '/api',
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
