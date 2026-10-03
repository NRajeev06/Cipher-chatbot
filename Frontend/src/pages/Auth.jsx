import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sparkles, Loader2, AlertCircle, CheckCircle2, Mail, ArrowLeft, RefreshCw } from 'lucide-react'
import api from '../api/client'

export default function Auth({ initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode) // 'login' | 'signup' | 'verify'
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [verifyEmail, setVerifyEmail] = useState('')
  const [verifyCode, setVerifyCode] = useState('')
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [unverifiedEmail, setUnverifiedEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  const navigate = useNavigate()
  const location = useLocation()

  // Cooldown timer for resend verification
  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [cooldown])

  // Check for email verification link parameters in URL
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const token = params.get('token')
    const emailParam = params.get('email')
    const verifiedParam = params.get('verified')

    if (verifiedParam === 'true' && token) {
      localStorage.setItem('cipher_token', token)
      if (params.get('user')) {
        localStorage.setItem('cipher_user', params.get('user'))
      }
      navigate('/')
      return
    }

    if (token) {
      setMode('verify')
      handleTokenVerify(token)
    } else if (emailParam) {
      setVerifyEmail(emailParam)
      if (initialMode === 'verify' || location.pathname.includes('/verify')) {
        setMode('verify')
      }
    }
  }, [location])

  const handleTokenVerify = async (token) => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/auth/verify', { token })
      localStorage.setItem('cipher_token', data.token)
      localStorage.setItem('cipher_user', data.username)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired verification link.')
    } finally {
      setLoading(false)
    }
  }

  const handle = e => setForm({ ...form, [e.target.name]: e.target.value })

  const submitAuth = async (e) => {
    if (e) e.preventDefault()
    setError('')
    setInfoMessage('')
    setUnverifiedEmail('')

    if (!form.email || !form.password) {
      setError('Please fill in all required fields.')
      return
    }
    if (mode === 'signup' && !form.username) {
      setError('Username is required for signup.')
      return
    }

    setLoading(true)
    try {
      if (mode === 'signup') {
        const { data } = await api.post('/auth/signup', {
          username: form.username,
          email: form.email,
          password: form.password
        })

        setVerifyEmail(data.email || form.email)
        setMode('verify')
        setInfoMessage('Verification code sent! Please check your email inbox.')
      } else {
        // Mode is login
        const { data } = await api.post('/auth/login', {
          email: form.email,
          password: form.password
        })

        localStorage.setItem('cipher_token', data.token)
        localStorage.setItem('cipher_user', data.username)
        navigate('/')
      }
    } catch (err) {
      const status = err.response?.status
      const msg = err.response?.data?.detail || 'Authentication failed. Please verify your credentials.'
      
      if (status === 403) {
        // Email not verified yet
        setUnverifiedEmail(form.email)
        setError('Your email has not been verified yet.')
      } else if (status === 429) {
        setError("Rate limit exceeded: Too many attempts. Please wait a moment before trying again.")
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  const submitCodeVerify = async (e) => {
    if (e) e.preventDefault()
    setError('')
    setInfoMessage('')

    const codeClean = verifyCode.trim()
    if (!codeClean || codeClean.length !== 6) {
      setError('Please enter the 6-digit verification code.')
      return
    }

    setLoading(true)
    try {
      const { data } = await api.post('/auth/verify', {
        email: verifyEmail,
        code: codeClean
      })

      localStorage.setItem('cipher_token', data.token)
      localStorage.setItem('cipher_user', data.username)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired verification code.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    const targetEmail = verifyEmail || unverifiedEmail || form.email
    if (!targetEmail) {
      setError('Please enter your email to resend verification code.')
      return
    }

    setResending(true)
    setError('')
    try {
      const { data } = await api.post('/auth/resend-verification', { email: targetEmail })
      setInfoMessage(data.message || 'Verification code resent. Please check your inbox.')
      setCooldown(60)
      if (mode !== 'verify') {
        setVerifyEmail(targetEmail)
        setMode('verify')
      }
    } catch (err) {
      if (err.response?.status === 429) {
        setError("Too many resend requests. Please wait a few minutes before trying again.")
      } else {
        setError(err.response?.data?.detail || 'Failed to resend verification email.')
      }
    } finally {
      setResending(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logoHeader}>
          <div style={styles.logoIcon}>
            {mode === 'verify' ? <Mail size={22} color="#818cf8" /> : <Sparkles size={22} color="#818cf8" />}
          </div>
          <h1 style={styles.title}>
            {mode === 'verify' ? 'Verify Email' : 'CIPHER'}
          </h1>
          <p style={styles.subtitle}>
            {mode === 'verify'
              ? `Enter the 6-digit code sent to ${verifyEmail || 'your email'}`
              : mode === 'login'
                ? 'Sign in to continue to your conversations'
                : 'Create an account to start using CIPHER'}
          </p>
        </div>

        {/* Tab Switcher (Only visible for Login / Signup) */}
        {mode !== 'verify' && (
          <div style={styles.tabs}>
            <button 
              type="button"
              onClick={() => { setMode('login'); setError(''); setInfoMessage(''); setUnverifiedEmail('') }}
              style={{ ...styles.tab, ...(mode === 'login' ? styles.tabActive : {}) }}
            >
              Sign in
            </button>
            <button 
              type="button"
              onClick={() => { setMode('signup'); setError(''); setInfoMessage(''); setUnverifiedEmail('') }}
              style={{ ...styles.tab, ...(mode === 'signup' ? styles.tabActive : {}) }}
            >
              Sign up
            </button>
          </div>
        )}

        {/* Verification View */}
        {mode === 'verify' ? (
          <form onSubmit={submitCodeVerify} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Email Address</label>
              <input 
                value={verifyEmail}
                onChange={e => setVerifyEmail(e.target.value)}
                placeholder="user@example.com"
                style={styles.input}
                type="email"
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>6-Digit Verification Code</label>
              <input 
                value={verifyCode}
                onChange={e => setVerifyCode(e.target.value.replace(/[^0-9]/g, '').slice(0, 6))}
                placeholder="482910"
                style={styles.codeInput}
                maxLength={6}
                autoFocus
                required
              />
            </div>

            {infoMessage && (
              <div style={styles.infoAlert}>
                <CheckCircle2 size={15} color="#10b981" style={{ flexShrink: 0 }} />
                <span>{infoMessage}</span>
              </div>
            )}

            {error && (
              <div style={styles.errorAlert}>
                <AlertCircle size={15} color="#ef4444" style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading} style={styles.btn}>
              {loading ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : 'Verify & Continue'}
            </button>

            <div style={styles.verifyActions}>
              <button 
                type="button" 
                onClick={handleResend} 
                disabled={resending || cooldown > 0} 
                style={styles.resendBtn}
              >
                {resending ? 'Sending...' : cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend verification email'}
              </button>

              <button 
                type="button" 
                onClick={() => { setMode('login'); setError(''); setInfoMessage('') }} 
                style={styles.backBtn}
              >
                <ArrowLeft size={14} /> Back to Sign in
              </button>
            </div>
          </form>
        ) : (
          /* Login / Signup View */
          <form onSubmit={submitAuth} style={styles.form}>
            {mode === 'signup' && (
              <div style={styles.inputGroup}>
                <label style={styles.label}>Username</label>
                <input 
                  name="username" 
                  placeholder="johndoe" 
                  value={form.username}
                  onChange={handle} 
                  style={styles.input} 
                  required
                />
              </div>
            )}
            
            <div style={styles.inputGroup}>
              <label style={styles.label}>Email address</label>
              <input 
                name="email" 
                placeholder="name@example.com" 
                value={form.email}
                onChange={handle} 
                style={styles.input} 
                type="email" 
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Password</label>
              <input 
                name="password" 
                placeholder="••••••••••••" 
                value={form.password}
                onChange={handle} 
                style={styles.input} 
                type="password"
                required
              />
            </div>

            {error && (
              <div style={styles.errorAlert}>
                <AlertCircle size={15} color="#ef4444" style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Unverified prompt if user attempts login before verifying */}
            {unverifiedEmail && (
              <div style={styles.unverifiedBanner}>
                <div style={styles.unverifiedText}>
                  Please verify your email before signing in.
                </div>
                <div style={styles.unverifiedButtons}>
                  <button 
                    type="button" 
                    onClick={() => {
                      setVerifyEmail(unverifiedEmail)
                      setMode('verify')
                      setError('')
                    }} 
                    style={styles.unverifiedActionBtn}
                  >
                    Enter 6-digit code
                  </button>
                  <button 
                    type="button" 
                    onClick={handleResend} 
                    disabled={resending || cooldown > 0} 
                    style={styles.unverifiedResendBtn}
                  >
                    {resending ? 'Sending...' : cooldown > 0 ? `Wait ${cooldown}s` : 'Resend email'}
                  </button>
                </div>
              </div>
            )}

            <button type="submit" disabled={loading} style={styles.btn}>
              {loading ? (
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              ) : mode === 'login' ? (
                'Sign in'
              ) : (
                'Create account'
              )}
            </button>
          </form>
        )}

        <div style={styles.footerNote}>
          Protected by encrypted JWT & rate limiting security
        </div>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-base)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20
  },
  card: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 16,
    padding: '36px 32px',
    boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center'
  },
  logoHeader: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    marginBottom: 22
  },
  logoIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: 'var(--accent-subtle)',
    border: '1px solid var(--accent-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: '#f8fafc',
    letterSpacing: '-0.02em',
    marginBottom: 6
  },
  subtitle: {
    fontSize: 13,
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
    maxWidth: 320
  },
  tabs: {
    display: 'flex',
    width: '100%',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: 8,
    padding: 3,
    marginBottom: 20
  },
  tab: {
    flex: 1,
    padding: '8px 0',
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    fontSize: 13,
    fontWeight: 500,
    borderRadius: 6,
    cursor: 'pointer',
    transition: 'all 0.15s ease'
  },
  tabActive: {
    backgroundColor: 'var(--bg-user-bubble)',
    color: '#ffffff',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
  },
  form: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 16
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6
  },
  label: {
    fontSize: 12,
    fontWeight: 500,
    color: '#e2e8f0'
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    borderRadius: 8,
    backgroundColor: '#0f111a',
    border: '1px solid var(--border-medium)',
    color: '#f8fafc',
    fontSize: 14,
    outline: 'none',
    transition: 'border-color 0.15s ease'
  },
  codeInput: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: 8,
    backgroundColor: '#0f111a',
    border: '1px solid var(--accent-border)',
    color: '#a5b4fc',
    fontSize: 22,
    fontWeight: 700,
    letterSpacing: '8px',
    textAlign: 'center',
    outline: 'none'
  },
  errorAlert: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    borderRadius: 8,
    backgroundColor: 'var(--danger-subtle)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    color: '#fca5a5',
    fontSize: 13,
    lineHeight: 1.4
  },
  infoAlert: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    borderRadius: 8,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid rgba(16, 185, 129, 0.25)',
    color: '#6ee7b7',
    fontSize: 13,
    lineHeight: 1.4
  },
  unverifiedBanner: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    border: '1px solid rgba(245, 158, 11, 0.3)',
    borderRadius: 8,
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  unverifiedText: {
    fontSize: 12,
    color: '#fcd34d'
  },
  unverifiedButtons: {
    display: 'flex',
    gap: 8
  },
  unverifiedActionBtn: {
    flex: 1,
    padding: '6px 10px',
    borderRadius: 6,
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    border: '1px solid rgba(245, 158, 11, 0.4)',
    color: '#fbbf24',
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer'
  },
  unverifiedResendBtn: {
    padding: '6px 10px',
    borderRadius: 6,
    backgroundColor: 'transparent',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    color: 'var(--text-secondary)',
    fontSize: 12,
    cursor: 'pointer'
  },
  btn: {
    width: '100%',
    padding: '11px 0',
    borderRadius: 8,
    backgroundColor: 'var(--accent)',
    border: 'none',
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
    transition: 'background-color 0.15s ease'
  },
  verifyActions: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    marginTop: 8
  },
  resendBtn: {
    background: 'none',
    border: 'none',
    color: '#818cf8',
    fontSize: 13,
    cursor: 'pointer',
    textDecoration: 'underline',
    textUnderlineOffset: 3
  },
  backBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: 12,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 6
  },
  footerNote: {
    marginTop: 24,
    fontSize: 11,
    color: 'var(--text-muted)',
    textAlign: 'center'
  }
}
