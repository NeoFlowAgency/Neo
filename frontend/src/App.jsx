import { useState } from 'react'
import { useNeo } from './context/NeoContext'
import { LayoutDashboard, MessageCircle, Bot, Monitor, Wrench } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Communication from './pages/Communication'
import BodyControl from './pages/BodyControl'
import Display from './pages/Display'
import Diagnostics from './pages/Diagnostics'

const PAGES = [
  { id: 'dashboard', label: 'Board',  icon: LayoutDashboard, Component: Dashboard },
  { id: 'comm',      label: 'Chat',   icon: MessageCircle,   Component: Communication },
  { id: 'body',      label: 'Corps',  icon: Bot,             Component: BodyControl },
  { id: 'display',   label: 'LCD',    icon: Monitor,         Component: Display },
  { id: 'diag',      label: 'Diag',   icon: Wrench,          Component: Diagnostics },
]

export default function App() {
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
          {pill('mqtt', 'MQTT', connState.mqtt)}
          {pill('openclaw', 'OPENCLAW', connState.openclaw)}
          {pill('esp32', 'ESP32', connState.esp32)}
        </div>
        <div className={`conn-pill ${connected ? 'online' : 'offline'}`}>
          <div className="conn-dot" />
          {connected ? 'CONNECTÉ' : 'HORS LIGNE'}
        </div>
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
