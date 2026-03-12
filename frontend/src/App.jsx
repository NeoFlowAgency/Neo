import { useState, useEffect } from 'react'
import { useNeo } from './context/NeoContext'
import { NeoProvider } from './context/NeoContext'
import { LayoutDashboard, MessageCircle, Bot, Monitor, Wrench, LogOut } from 'lucide-react'
import Dashboard     from './pages/Dashboard'
import Communication from './pages/Communication'
import BodyControl   from './pages/BodyControl'
import Display       from './pages/Display'
import Diagnostics   from './pages/Diagnostics'
import Login         from './pages/Login'

const PAGES = [
  { id: 'dashboard', label: 'Board',  icon: LayoutDashboard, Component: Dashboard },
  { id: 'comm',      label: 'Chat',   icon: MessageCircle,   Component: Communication },
  { id: 'body',      label: 'Corps',  icon: Bot,             Component: BodyControl },
  { id: 'display',   label: 'LCD',    icon: Monitor,         Component: Display },
  { id: 'diag',      label: 'Diag',   icon: Wrench,          Component: Diagnostics },
]

function AppLayout({ onLogout }) {
  const [page, setPage] = useState('dashboard')
  const { connected, connState } = useNeo()

  const pill = (id, label, ok) => (
    <div className={`conn-pill ${ok ? 'online' : 'offline'}`} key={id}>
      <div className="conn-dot" />
      {label}
    </div>
  )

  return (
    <div className="app-layout">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="logo-text">NEO</div>
          <div className="logo-sub">CONTROL CENTER</div>
        </div>
        <div className="topbar-spacer" />
        <div className="conn-pills">
          {pill('mqtt',     'MQTT',     connState.mqtt)}
          {pill('openclaw', 'OPENCLAW', connState.openclaw)}
          {pill('esp32',    'ESP32',    connState.esp32)}
        </div>
        <div className={`conn-pill ${connected ? 'online' : 'offline'}`}>
          <div className="conn-dot" />
          {connected ? 'CONNECTÉ' : 'HORS LIGNE'}
        </div>
        <button
          className="btn btn-sm"
          onClick={onLogout}
          title="Déconnexion"
          style={{ marginLeft: 8, gap: 6 }}
        >
          <LogOut size={13} />
          Quitter
        </button>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        {PAGES.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`nav-btn ${page === id ? 'active' : ''}`}
            onClick={() => setPage(id)}
          >
            <Icon size={18} />
            <span className="nav-label">{label}</span>
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="content">
        {PAGES.map(({ id, Component }) => (
          <div key={id} className={`page ${page === id ? 'active' : ''}`}>
            <Component />
          </div>
        ))}
      </main>
    </div>
  )
}

export default function App() {
  const [auth, setAuth] = useState(null) // null=loading, false=not auth, true=auth

  useEffect(() => {
    fetch('/api/me')
      .then(r => r.json())
      .then(d => setAuth(d.authenticated))
      .catch(() => setAuth(false))
  }, [])

  async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' })
    setAuth(false)
  }

  if (auth === null) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
      }}>
        <span className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
      </div>
    )
  }

  if (!auth) {
    return <Login onLogin={() => setAuth(true)} />
  }

  return (
    <NeoProvider>
      <AppLayout onLogout={handleLogout} />
    </NeoProvider>
  )
}
