import React, { useState } from 'react'
import { Plus, MessageSquare, Trash2, Settings, LogOut, Sparkles, ChevronLeft, ChevronRight } from 'lucide-react'

export default function Sidebar({ 
  sessions, 
  currentSession, 
  onSelectSession, 
  onNewSession, 
  onDeleteSession,
  onOpenSettings,
  isCollapsed,
  onToggleCollapse
}) {
  const [hoveredSession, setHoveredSession] = useState(null)
  const username = localStorage.getItem('cipher_user') || 'User'
  const userInitial = (username.charAt(0) || 'U').toUpperCase()

  const logout = () => { 
    localStorage.clear()
    window.location.href = '/login' 
  }

  return (
    <aside style={{
      ...styles.sidebar,
      width: isCollapsed ? 68 : 260,
      minWidth: isCollapsed ? 68 : 260,
    }}>
      {/* Brand Header */}
      <div style={styles.header}>
        <div style={styles.brandRow}>
          <div style={styles.brandIcon}>
            <Sparkles size={16} color="#818cf8" />
          </div>
          {!isCollapsed && (
            <div style={styles.brandInfo}>
              <span style={styles.brandTitle}>CIPHER</span>
              <span style={styles.brandBadge}>AI</span>
            </div>
          )}
        </div>
        {onToggleCollapse && (
          <button 
            onClick={onToggleCollapse} 
            style={styles.collapseBtn}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        )}
      </div>

      {/* New Chat Button */}
      <div style={styles.actionContainer}>
        <button 
          onClick={onNewSession} 
          style={styles.newChatBtn}
          title="Start a new chat"
        >
          <Plus size={16} />
          {!isCollapsed && <span>New chat</span>}
        </button>
      </div>

      {/* Session History List */}
      <div style={styles.sessionSection}>
        {!isCollapsed && (
          <div style={styles.sectionHeader}>
            <span>Recent</span>
          </div>
        )}

        <div style={styles.sessionList}>
          {sessions.length === 0 ? (
            !isCollapsed && <div style={styles.emptyNotice}>No previous chats</div>
          ) : (
            sessions.map(sess => {
              const isActive = sess.id === currentSession
              const isHovered = hoveredSession === sess.id

              return (
                <div 
                  key={sess.id}
                  onClick={() => onSelectSession(sess.id)}
                  onMouseEnter={() => setHoveredSession(sess.id)}
                  onMouseLeave={() => setHoveredSession(null)}
                  style={{
                    ...styles.sessionItem,
                    ...(isActive ? styles.sessionActive : {}),
                    ...(isHovered && !isActive ? styles.sessionHover : {})
                  }}
                  title={sess.title || 'New Chat'}
                >
                  <MessageSquare 
                    size={15} 
                    style={{
                      flexShrink: 0,
                      color: isActive ? '#818cf8' : '#64748b'
                    }} 
                  />

                  {!isCollapsed && (
                    <>
                      <span style={{
                        ...styles.sessionTitle,
                        color: isActive ? '#f1f3f9' : '#94a3b8'
                      }}>
                        {sess.title || 'New Chat'}
                      </span>

                      {(isHovered || isActive) && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onDeleteSession(sess.id)
                          }}
                          style={styles.deleteBtn}
                          title="Delete chat"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* User Footer & Settings */}
      <div style={styles.footer}>
        <div style={styles.userProfile}>
          <div style={styles.userAvatar}>
            {userInitial}
          </div>
          {!isCollapsed && (
            <div style={styles.userInfo}>
              <span style={styles.userName}>{username}</span>
              <span style={styles.userStatus}>Free plan</span>
            </div>
          )}
        </div>

        {!isCollapsed && (
          <div style={styles.footerActions}>
            <button 
              onClick={onOpenSettings} 
              style={styles.iconActionBtn}
              title="Settings & API Key"
            >
              <Settings size={16} />
            </button>
            <button 
              onClick={logout} 
              style={styles.iconActionBtn}
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

const styles = {
  sidebar: {
    height: '100vh',
    backgroundColor: 'var(--bg-sidebar)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    transition: 'width 0.2s ease',
    userSelect: 'none',
    zIndex: 20
  },
  header: {
    padding: '16px 14px 12px 14px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)'
  },
  brandRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10
  },
  brandIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: 'var(--accent-subtle)',
    border: '1px solid var(--accent-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  brandInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: 6
  },
  brandTitle: {
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: '0.04em',
    color: '#f8fafc'
  },
  brandBadge: {
    fontSize: 10,
    fontWeight: 600,
    color: '#818cf8',
    backgroundColor: 'rgba(99, 102, 241, 0.14)',
    padding: '1px 5px',
    borderRadius: 4
  },
  collapseBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: 4,
    borderRadius: 4,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color 0.15s ease'
  },
  actionContainer: {
    padding: '12px 12px 6px 12px'
  },
  newChatBtn: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: 10,
    padding: '9px 12px',
    borderRadius: 8,
    backgroundColor: 'transparent',
    border: '1px solid var(--border-medium)',
    color: 'var(--text-primary)',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s ease'
  },
  sessionSection: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px 10px 12px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4
  },
  sectionHeader: {
    padding: '8px 6px 4px 6px',
    fontSize: 11,
    fontWeight: 500,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    color: 'var(--text-muted)'
  },
  sessionList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2
  },
  emptyNotice: {
    padding: '16px 8px',
    fontSize: 12,
    color: 'var(--text-muted)',
    textAlign: 'center'
  },
  sessionItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 10px',
    borderRadius: 7,
    cursor: 'pointer',
    position: 'relative',
    transition: 'background-color 0.12s ease'
  },
  sessionHover: {
    backgroundColor: 'var(--bg-surface-hover)'
  },
  sessionActive: {
    backgroundColor: 'var(--bg-surface-hover)',
    borderLeft: '2px solid var(--accent)'
  },
  sessionTitle: {
    flex: 1,
    fontSize: 13,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    lineHeight: 1.2
  },
  deleteBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: 3,
    borderRadius: 4,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color 0.15s ease'
  },
  footer: {
    padding: '12px 14px',
    borderTop: '1px solid rgba(255, 255, 255, 0.05)',
    backgroundColor: 'rgba(13, 15, 23, 0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  userProfile: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    overflow: 'hidden'
  },
  userAvatar: {
    width: 30,
    height: 30,
    borderRadius: '50%',
    backgroundColor: '#272b3d',
    color: '#e2e8f0',
    fontSize: 12,
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0
  },
  userInfo: {
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden'
  },
  userName: {
    fontSize: 13,
    fontWeight: 500,
    color: 'var(--text-primary)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  userStatus: {
    fontSize: 11,
    color: 'var(--text-muted)'
  },
  footerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 4
  },
  iconActionBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    padding: 6,
    borderRadius: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s ease'
  }
}
