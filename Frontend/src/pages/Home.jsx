import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { 
  Paperclip, 
  ArrowUp, 
  FileText, 
  X, 
  Image as ImageIcon, 
  Sparkles, 
  Bot, 
  Copy, 
  Check, 
  Loader2, 
  Settings as SettingsIcon,
  HelpCircle,
  ExternalLink
} from 'lucide-react'
import api from '../api/client'
import Sidebar from '../components/Sidebar'

// Custom code block component with copy button
function CodeBlock({ children, className }) {
  const [copied, setCopied] = useState(false)
  const language = className ? className.replace(/language-/, '') : ''
  const codeText = String(children).replace(/\n$/, '')

  const handleCopy = () => {
    navigator.clipboard.writeText(codeText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={styles.codeContainer}>
      <div style={styles.codeHeader}>
        <span style={styles.codeLang}>{language || 'code'}</span>
        <button onClick={handleCopy} style={styles.copyBtn} title="Copy code">
          {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre style={styles.codePre}>
        <code>{children}</code>
      </pre>
    </div>
  )
}

export default function Home() {
  const [sessions, setSessions] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [imageMode, setImageMode] = useState(false)
  const [ragStatus, setRagStatus] = useState(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [maskedKey, setMaskedKey] = useState('')
  const [isCollapsed, setIsCollapsed] = useState(false)
  
  const bottomRef = useRef(null)
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('cipher_token')
    if (!token) {
      navigate('/login')
    } else {
      initApp()
    }
  }, [])

  useEffect(() => { 
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) 
  }, [messages, streaming])

  // Clean legacy internal debug messages from assistant messages
  const sanitizeText = (text) => {
    if (!text) return ''
    return text.replace(/\[CIPHER System:.*?\]\n*/g, '').replace(/\[CIPHER System Error:.*?\]\n*/g, '').trim()
  }

  const initApp = async () => {
    await fetchSessions()
    await fetchUserProfile()
  }

  const fetchUserProfile = async () => {
    try {
      const { data } = await api.get('/auth/me')
      setApiKey(data.api_key || '')
      setMaskedKey(data.api_key || '')
    } catch (err) {
      console.error("Failed to fetch user profile:", err)
    }
  }

  const saveSettings = async () => {
    try {
      await api.put('/auth/settings', { api_key: apiKey })
      setShowSettings(false)
      fetchUserProfile()
    } catch (err) {
      alert("Failed to commit settings: " + (err.response?.data?.detail || err.message))
    }
  }

  const fetchSessions = async () => {
    try {
      const { data } = await api.get('/chat/sessions')
      setSessions(data)
      if (data.length > 0 && !currentSession) {
        selectSession(data[0].id)
      } else if (data.length === 0) {
        newSession()
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err)
    }
  }

  const fetchRagStatus = async (sessionId) => {
    const targetSession = sessionId || currentSession
    if (!targetSession) return
    try {
      const { data } = await api.get('/upload/document/status', {
        params: { session_id: targetSession }
      })
      if (data.active) {
        setRagStatus(data)
      } else {
        setRagStatus(null)
      }
    } catch (err) {
      console.error("Failed to fetch RAG status:", err)
      setRagStatus(null)
    }
  }

  const selectSession = async (id) => {
    setCurrentSession(id)
    try {
      const { data } = await api.get(`/chat/history/${id}`)
      const cleaned = data.map(m => ({
        ...m,
        content: m.role === 'assistant' ? sanitizeText(m.content) : m.content
      }))
      setMessages(cleaned)
      fetchRagStatus(id)
    } catch (err) {
      console.error("Failed to load history:", err)
    }
  }

  const newSession = async () => {
    try {
      const { data } = await api.post('/chat/session')
      setSessions(prev => [data, ...prev])
      setCurrentSession(data.id || data.session_id)
      setMessages([])
      setRagStatus(null)
    } catch (err) {
      console.error("Failed to create session:", err)
    }
  }

  const deleteSession = async (id) => {
    try {
      await api.delete(`/chat/session/${id}`)
      const remaining = sessions.filter(s => s.id !== id)
      setSessions(remaining)
      if (currentSession === id) {
        if (remaining.length > 0) {
          selectSession(remaining[0].id)
        } else {
          newSession()
        }
      }
    } catch (err) {
      console.error("Failed to delete session:", err)
    }
  }

  // Handle document attachment from the chat input
  const handleFileAttach = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!currentSession) {
      await newSession()
    }

    setUploadingFile(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('session_id', currentSession)

    try {
      await api.post('/upload/document', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      await fetchRagStatus(currentSession)
    } catch (err) {
      if (err.response?.status === 429) {
        alert("Upload rate limit reached: You can upload up to 5 documents per hour. Please wait a while before uploading another file.")
      } else {
        alert(err.response?.data?.detail || 'Document upload failed. Please try a valid .pdf, .docx, or .txt file.')
      }
    } finally {
      setUploadingFile(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // Remove attached document from active conversation
  const removeAttachedDocument = async () => {
    if (!currentSession) return
    try {
      await api.delete('/upload/document', {
        params: { session_id: currentSession }
      })
      setRagStatus(null)
    } catch (err) {
      console.error("Failed to remove document:", err)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || streaming || !currentSession) return
    const text = input.trim()
    setInput('')

    // Auto-adjust textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    // Check if Image Mode or prompt starts with 'generate:'
    const isImageReq = imageMode || text.toLowerCase().startsWith('generate:')

    if (isImageReq) {
      const prompt = text.toLowerCase().startsWith('generate:') ? text.slice('generate:'.length).trim() : text
      setMessages(prev => [...prev, { role: 'user', content: text, type: 'text' }])
      setStreaming(true)
      try {
        const { data } = await api.post('/chat/image', { prompt, session_id: currentSession })
        setMessages(prev => [...prev, { role: 'assistant', content: data.image_b64, type: 'image' }])
      } catch (err) {
        const errorMsg = err.response?.status === 429
          ? "Rate limit reached: Image generation is limited to 10 requests per hour. Please wait a moment and try again."
          : 'Image generation request failed. Please verify your prompt or API settings.'
        setMessages(prev => [...prev, { role: 'assistant', content: errorMsg, type: 'text' }])
      } finally { 
        setStreaming(false) 
      }
      return
    }

    // Regular Token-by-Token Streaming Chat
    setMessages(prev => [...prev, { role: 'user', content: text, type: 'text' }])
    setStreaming(true)

    const token = localStorage.getItem('cipher_token')
    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json', 
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ message: text, session_id: currentSession })
      })

      if (!response.ok) {
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After') || '60'
          throw new Error(`RATE_LIMIT:You're sending messages too quickly. Please wait ${retryAfter} seconds before sending another message.`)
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let reply = ''

      setMessages(prev => [...prev, { role: 'assistant', content: '', type: 'text', streaming: true }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const tokenText = decoder.decode(value, { stream: true })
        reply += tokenText

        const cleanReply = sanitizeText(reply)

        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: cleanReply, type: 'text', streaming: true }
          return updated
        })
      }

      const finalReply = sanitizeText(reply)
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: finalReply, type: 'text', streaming: false }
        return updated
      })

      // Refresh session list to reflect title change
      fetchSessions()
    } catch (err) {
      const errorMsg = err.message?.startsWith('RATE_LIMIT:')
        ? err.message.replace('RATE_LIMIT:', '')
        : 'Connection lost while streaming the response. Please try again.'
      setMessages(prev => [...prev, { role: 'assistant', content: errorMsg, type: 'text' }])
    } finally {
      setStreaming(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleTextareaInput = (e) => {
    setInput(e.target.value)
    // Auto-expand textarea up to 180px
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`
  }

  const getEngineBadgeText = () => {
    if (apiKey.startsWith("gsk_")) return "Groq Llama 3.3"
    if (apiKey.startsWith("sk-")) return "GPT-4o mini"
    if (apiKey.startsWith("AIzaSy")) return "Gemini 1.5 Flash"
    if (apiKey.startsWith("hf_")) return "Hugging Face"
    return "Groq Llama 3.3"
  }

  // Quick starter prompts for empty state
  const starterPrompts = [
    {
      title: "Analyze a document",
      desc: "Upload a PDF, DOCX, or TXT to ask questions about its content",
      action: () => fileInputRef.current?.click()
    },
    {
      title: "Explain a concept",
      desc: "Explain quantum computing in simple terms with an analogy",
      prompt: "Explain quantum computing in simple terms with an analogy."
    },
    {
      title: "Write & refactor code",
      desc: "Write a modern Python utility script for data processing",
      prompt: "Write a clean Python script to parse and analyze JSON data with error handling."
    },
    {
      title: "Generate an image",
      desc: "Switch to synthesis mode to create AI imagery",
      action: () => {
        setImageMode(true)
        setInput("A futuristic smart city in twilight with clean architectural lines and lush hanging gardens")
      }
    }
  ]

  return (
    <div style={styles.container}>
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelectSession={selectSession}
        onNewSession={newSession}
        onDeleteSession={deleteSession}
        onOpenSettings={() => setShowSettings(true)}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
      />

      {/* Main Chat Workspace */}
      <main style={styles.chatArea}>
        {/* Top Header */}
        <header style={styles.topHeader}>
          <div style={styles.headerLeft}>
            <div style={styles.modelPill}>
              <Sparkles size={14} color="#818cf8" />
              <span style={styles.modelName}>{getEngineBadgeText()}</span>
            </div>

            {ragStatus?.active && (
              <div style={styles.docActivePill} title={`Context active: ${ragStatus.filename}`}>
                <FileText size={13} color="#10b981" />
                <span style={styles.docActiveText}>{ragStatus.filename}</span>
              </div>
            )}
          </div>

          <div style={styles.headerRight}>
            <button
              onClick={() => setImageMode(!imageMode)}
              style={{
                ...styles.modeToggleBtn,
                ...(imageMode ? styles.modeToggleActive : {})
              }}
              title="Toggle Image Synthesis Mode"
            >
              <ImageIcon size={15} />
              <span>Image Mode</span>
            </button>

            <button
              onClick={() => setShowSettings(true)}
              style={styles.headerIconBtn}
              title="Pipeline Settings"
            >
              <SettingsIcon size={16} />
            </button>
          </div>
        </header>

        {/* Message Stream */}
        <div style={styles.messageScrollArea}>
          <div style={styles.messageColumn}>
            {messages.length === 0 ? (
              /* Welcome Hero / Empty State */
              <div style={styles.emptyHero}>
                <div style={styles.heroLogo}>
                  <Sparkles size={28} color="#818cf8" />
                </div>
                <h1 style={styles.heroTitle}>How can I help you today?</h1>
                <p style={styles.heroSubtitle}>
                  Chat with CIPHER, attach documents for instant analysis, or generate visuals.
                </p>

                <div style={styles.starterGrid}>
                  {starterPrompts.map((card, i) => (
                    <div 
                      key={i} 
                      onClick={() => {
                        if (card.action) card.action()
                        else if (card.prompt) setInput(card.prompt)
                      }}
                      style={styles.starterCard}
                    >
                      <div style={styles.starterCardTitle}>{card.title}</div>
                      <div style={styles.starterCardDesc}>{card.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Messages List */
              messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  style={{
                    ...styles.msgRow,
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                  }}
                >
                  {msg.role === 'assistant' && (
                    <div style={styles.aiAvatar}>
                      <Bot size={16} color="#818cf8" />
                    </div>
                  )}

                  <div style={{
                    ...styles.bubble,
                    ...(msg.role === 'user' ? styles.userBubble : styles.aiBubble)
                  }}>
                    {msg.type === 'image' ? (
                      <div style={styles.imageWrapper}>
                        <img 
                          src={`data:image/png;base64,${msg.content}`} 
                          style={styles.renderedImage} 
                          alt="AI synthesis result" 
                        />
                      </div>
                    ) : (
                      <div className="markdown-content">
                        <ReactMarkdown
                          components={{
                            code({ node, inline, className, children, ...props }) {
                              const match = /language-(\w+)/.exec(className || '')
                              return !inline && match ? (
                                <CodeBlock className={className}>
                                  {children}
                                </CodeBlock>
                              ) : (
                                <code className={className} {...props}>
                                  {children}
                                </code>
                              )
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                        {msg.streaming && <span className="streaming-cursor" />}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={bottomRef} style={{ height: 20 }} />
          </div>
        </div>

        {/* Floating Input Dock */}
        <div style={styles.inputDock}>
          <div style={styles.inputCard}>
            {/* Active Document Chip above input */}
            {(ragStatus?.active || uploadingFile) && (
              <div style={styles.chipBar}>
                <div style={styles.docChip}>
                  {uploadingFile ? (
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                  ) : (
                    <FileText size={14} color="#818cf8" />
                  )}
                  <span style={styles.chipName}>
                    {uploadingFile ? 'Uploading document...' : ragStatus.filename}
                  </span>
                  {!uploadingFile && (
                    <button 
                      onClick={removeAttachedDocument} 
                      style={styles.chipRemoveBtn}
                      title="Detach document from this chat"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Input Controls */}
            <div style={styles.inputRow}>
              {/* Paperclip Attachment Button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingFile || streaming}
                style={styles.attachBtn}
                title="Attach document (.pdf, .docx, .txt)"
              >
                <Paperclip size={18} />
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileAttach}
                style={{ display: 'none' }}
              />

              {/* Chat Textarea */}
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleTextareaInput}
                onKeyDown={handleKeyDown}
                placeholder={
                  imageMode 
                    ? "Describe the image you want to generate..." 
                    : ragStatus?.active 
                      ? "Ask questions about your attached document..." 
                      : "Message CIPHER..."
                }
                style={styles.textarea}
                rows={1}
                disabled={streaming || !currentSession}
              />

              {/* Send Button */}
              <button
                onClick={sendMessage}
                disabled={streaming || !currentSession || (!input.trim() && !ragStatus?.active)}
                style={{
                  ...styles.sendBtn,
                  ...((input.trim() && !streaming) ? styles.sendBtnActive : {})
                }}
                title="Send message (Enter)"
              >
                {streaming ? (
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <ArrowUp size={18} />
                )}
              </button>
            </div>
          </div>

          <div style={styles.disclaimerText}>
            CIPHER may make mistakes. Verify important information.
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <div style={styles.modalOverlay} onClick={() => setShowSettings(false)}>
          <div style={styles.modalCard} onClick={e => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div style={styles.modalTitleRow}>
                <SettingsIcon size={18} color="#818cf8" />
                <h2 style={styles.modalTitle}>Inference Settings</h2>
              </div>
              <button onClick={() => setShowSettings(false)} style={styles.modalCloseBtn}>
                <X size={16} />
              </button>
            </div>

            <div style={styles.modalBody}>
              <p style={styles.modalDesc}>
                Configure your custom API key to route completions directly to OpenAI, Google Gemini, or Hugging Face.
              </p>

              <div style={styles.providerList}>
                <div style={styles.providerItem}>
                  <span style={styles.providerKey}>Groq (Fast LLM):</span>
                  <span style={styles.providerVal}>Prefix <code>gsk_...</code> (Llama 3.3 70B)</span>
                </div>
                <div style={styles.providerItem}>
                  <span style={styles.providerKey}>OpenAI:</span>
                  <span style={styles.providerVal}>Prefix <code>sk-...</code> (GPT-4o mini)</span>
                </div>
                <div style={styles.providerItem}>
                  <span style={styles.providerKey}>Google Gemini:</span>
                  <span style={styles.providerVal}>Prefix <code>AIzaSy...</code> (Gemini 1.5 Flash)</span>
                </div>
                <div style={styles.providerItem}>
                  <span style={styles.providerKey}>Hugging Face:</span>
                  <span style={styles.providerVal}>Prefix <code>hf_...</code> (Image SDXL)</span>
                </div>
              </div>

              <div style={styles.inputGroup}>
                <label style={styles.inputLabel}>API Key</label>
                <div style={styles.keyInputWrapper}>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="Enter gsk_..., sk-..., AIzaSy..., or hf_..."
                    style={styles.keyInput}
                  />
                  {apiKey && apiKey !== maskedKey && (
                    <button 
                      onClick={() => setApiKey(maskedKey)} 
                      style={styles.resetBtn} 
                      title="Revert to saved key"
                    >
                      Revert
                    </button>
                  )}
                </div>
              </div>

              <div style={styles.activeEngineNotice}>
                <span style={styles.engineNoticeLabel}>Selected Engine:</span>
                <span style={styles.engineNoticeBadge}>
                  {apiKey.startsWith("gsk_") ? "Groq (Llama 3.3 70B)" :
                   apiKey.startsWith("sk-") ? "OpenAI (GPT-4o mini)" :
                   apiKey.startsWith("AIzaSy") ? "Google Gemini (1.5 Flash)" :
                   apiKey.startsWith("hf_") ? "Hugging Face (SDXL)" :
                   apiKey ? "Custom Inference Token" : "Default System Model (Groq Llama 3.3 70B)"}
                </span>
              </div>
            </div>

            <div style={styles.modalFooter}>
              <button onClick={() => setShowSettings(false)} style={styles.cancelBtn}>
                Cancel
              </button>
              <button onClick={saveSettings} style={styles.saveBtn}>
                Save settings
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    height: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-base)',
    overflow: 'hidden',
    position: 'relative'
  },
  chatArea: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    position: 'relative',
    overflow: 'hidden'
  },
  topHeader: {
    height: 56,
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid var(--border-subtle)',
    backgroundColor: 'rgba(13, 15, 23, 0.75)',
    backdropFilter: 'blur(10px)',
    zIndex: 10
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 10
  },
  modelPill: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '5px 12px',
    borderRadius: 'var(--radius-full)',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    border: '1px solid var(--border-subtle)',
    fontSize: 13,
    fontWeight: 500,
    color: 'var(--text-primary)'
  },
  modelName: {
    color: '#e2e8f0'
  },
  docActivePill: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 10px',
    borderRadius: 'var(--radius-full)',
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    border: '1px solid rgba(16, 185, 129, 0.25)',
    fontSize: 12,
    color: '#10b981',
    maxWidth: 200,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  docActiveText: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 8
  },
  modeToggleBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '6px 12px',
    borderRadius: 'var(--radius-full)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'transparent',
    color: 'var(--text-secondary)',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s ease'
  },
  modeToggleActive: {
    backgroundColor: 'var(--accent-subtle)',
    borderColor: 'var(--accent-border)',
    color: '#a5b4fc'
  },
  headerIconBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    padding: 8,
    borderRadius: 8,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color 0.15s ease'
  },
  messageScrollArea: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    paddingBottom: 160
  },
  messageColumn: {
    width: '100%',
    maxWidth: 800,
    margin: '0 auto',
    padding: '24px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 24
  },
  emptyHero: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    textAlign: 'center',
    padding: '40px 16px 20px 16px'
  },
  heroLogo: {
    width: 52,
    height: 52,
    borderRadius: 16,
    backgroundColor: 'var(--accent-subtle)',
    border: '1px solid var(--accent-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20
  },
  heroTitle: {
    fontSize: 26,
    fontWeight: 600,
    color: '#f8fafc',
    marginBottom: 8,
    letterSpacing: '-0.02em'
  },
  heroSubtitle: {
    fontSize: 14,
    color: 'var(--text-secondary)',
    maxWidth: 440,
    lineHeight: 1.5,
    marginBottom: 36
  },
  starterGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 12,
    width: '100%',
    maxWidth: 680
  },
  starterCard: {
    padding: '14px 16px',
    backgroundColor: 'rgba(255, 255, 255, 0.025)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-md)',
    textAlign: 'left',
    cursor: 'pointer',
    transition: 'all 0.15s ease'
  },
  starterCardTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: 'var(--text-primary)',
    marginBottom: 4
  },
  starterCardDesc: {
    fontSize: 12,
    color: 'var(--text-muted)',
    lineHeight: 1.4
  },
  msgRow: {
    display: 'flex',
    width: '100%',
    gap: 14,
    alignItems: 'flex-start'
  },
  aiAvatar: {
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-full)',
    backgroundColor: 'var(--accent-subtle)',
    border: '1px solid var(--accent-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2
  },
  bubble: {
    maxWidth: '85%',
    fontSize: 15,
    lineHeight: 1.6
  },
  userBubble: {
    backgroundColor: 'var(--bg-user-bubble)',
    color: '#f8fafc',
    padding: '12px 18px',
    borderRadius: '20px 20px 4px 20px',
    border: '1px solid rgba(255, 255, 255, 0.06)'
  },
  aiBubble: {
    backgroundColor: 'transparent',
    color: 'var(--text-primary)',
    padding: '4px 0',
    flex: 1
  },
  imageWrapper: {
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
    border: '1px solid var(--border-subtle)',
    marginTop: 8
  },
  renderedImage: {
    width: '100%',
    maxHeight: 512,
    objectFit: 'contain',
    display: 'block'
  },
  codeContainer: {
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--bg-code)',
    border: '1px solid var(--border-subtle)',
    margin: '12px 0',
    overflow: 'hidden'
  },
  codeHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '6px 14px',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderBottom: '1px solid var(--border-subtle)'
  },
  codeLang: {
    fontSize: 11,
    fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-muted)',
    textTransform: 'lowercase'
  },
  copyBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    fontSize: 11,
    cursor: 'pointer',
    padding: '3px 6px',
    borderRadius: 4
  },
  codePre: {
    margin: 0,
    padding: '14px 16px',
    overflowX: 'auto'
  },
  inputDock: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: '0 20px 16px 20px',
    background: 'linear-gradient(to top, var(--bg-base) 70%, transparent 100%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center'
  },
  inputCard: {
    width: '100%',
    maxWidth: 800,
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-medium)',
    borderRadius: 20,
    padding: '10px 14px',
    boxShadow: '0 10px 30px -5px rgba(0, 0, 0, 0.5)',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    transition: 'border-color 0.15s ease'
  },
  chipBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    paddingBottom: 4
  },
  docChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '5px 10px',
    borderRadius: 8,
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    border: '1px solid var(--accent-border)',
    fontSize: 12,
    color: '#e0e7ff'
  },
  chipName: {
    maxWidth: 260,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontWeight: 500
  },
  chipRemoveBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: 2,
    borderRadius: 3,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 2
  },
  inputRow: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 10
  },
  attachBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    padding: '8px 6px',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color 0.15s ease',
    flexShrink: 0
  },
  textarea: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    color: 'var(--text-primary)',
    fontSize: 14,
    lineHeight: 1.5,
    resize: 'none',
    outline: 'none',
    padding: '7px 4px',
    maxHeight: 180,
    overflowY: 'auto',
    fontFamily: 'inherit'
  },
  sendBtn: {
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-full)',
    border: 'none',
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    color: 'var(--text-muted)',
    cursor: 'not-allowed',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'all 0.15s ease'
  },
  sendBtnActive: {
    backgroundColor: 'var(--accent)',
    color: '#ffffff',
    cursor: 'pointer'
  },
  disclaimerText: {
    fontSize: 11,
    color: 'var(--text-muted)',
    marginTop: 8,
    textAlign: 'center'
  },
  modalOverlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    backdropFilter: 'blur(5px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    padding: 20
  },
  modalCard: {
    width: '100%',
    maxWidth: 480,
    backgroundColor: '#161925',
    border: '1px solid var(--border-medium)',
    borderRadius: 16,
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
    overflow: 'hidden'
  },
  modalHeader: {
    padding: '18px 20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid var(--border-subtle)'
  },
  modalTitleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: '#f8fafc'
  },
  modalCloseBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: 4,
    borderRadius: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  modalBody: {
    padding: 20
  },
  modalDesc: {
    fontSize: 13,
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
    marginBottom: 16
  },
  providerList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.025)',
    padding: '12px 14px',
    borderRadius: 8,
    border: '1px solid var(--border-subtle)',
    marginBottom: 20
  },
  providerItem: {
    fontSize: 12,
    display: 'flex',
    gap: 6
  },
  providerKey: {
    fontWeight: 600,
    color: '#e2e8f0',
    minWidth: 90
  },
  providerVal: {
    color: 'var(--text-secondary)'
  },
  inputGroup: {
    marginBottom: 16
  },
  inputLabel: {
    display: 'block',
    fontSize: 12,
    fontWeight: 500,
    color: '#e2e8f0',
    marginBottom: 6
  },
  keyInputWrapper: {
    display: 'flex',
    gap: 8
  },
  keyInput: {
    flex: 1,
    padding: '9px 12px',
    borderRadius: 8,
    backgroundColor: '#0f111a',
    border: '1px solid var(--border-medium)',
    color: '#f8fafc',
    fontSize: 13,
    outline: 'none'
  },
  resetBtn: {
    padding: '8px 12px',
    borderRadius: 8,
    backgroundColor: 'transparent',
    border: '1px solid var(--border-subtle)',
    color: 'var(--text-secondary)',
    fontSize: 12,
    cursor: 'pointer'
  },
  activeEngineNotice: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12
  },
  engineNoticeLabel: {
    color: 'var(--text-muted)'
  },
  engineNoticeBadge: {
    color: '#818cf8',
    fontWeight: 500
  },
  modalFooter: {
    padding: '14px 20px',
    backgroundColor: 'rgba(13, 15, 23, 0.5)',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 10
  },
  cancelBtn: {
    padding: '8px 14px',
    borderRadius: 8,
    backgroundColor: 'transparent',
    border: '1px solid var(--border-subtle)',
    color: 'var(--text-secondary)',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer'
  },
  saveBtn: {
    padding: '8px 16px',
    borderRadius: 8,
    backgroundColor: 'var(--accent)',
    border: 'none',
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer'
  }
}
