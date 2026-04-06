import { useNeo } from '../context/NeoContext'
import { Wifi, Brain, Cpu, Zap, RotateCcw, ArrowLeft, ArrowRight, ArrowUp, ArrowDown } from 'lucide-react'

const STATUS_CARDS = [
  { id: 'mqtt',     label: 'MQTT BROKER',  icon: Wifi,  key: 'mqtt' },
  { id: 'openclaw', label: 'OPENCLAW IA',  icon: Brain, key: 'openclaw' },
  { id: 'esp32',    label: 'ESP32 ROBOT',  icon: Cpu,   key: 'esp32' },
]

export default function Dashboard() {
  const { connState, logs, sendCommand } = useNeo()

  const actions = [
    { label: 'Centre',    action: 'tete_centre',  icon: <Zap size={14} /> },
    { label: 'Repos',     action: 'repos',         icon: <RotateCcw size={14} /> },
    { label: '◀ Gauche',  action: 'tete_gauche',   icon: <ArrowLeft size={14} /> },
    { label: 'Droite ▶',  action: 'tete_droite',   icon: <ArrowRight size={14} /> },
    { label: '▲ Haut',    action: 'tete_haut',     icon: <ArrowUp size={14} /> },
    { label: 'Bas ▼',     action: 'tete_bas',      icon: <ArrowDown size={14} /> },
  ]

  const recentLogs = logs.slice(-15).reverse()

  return (
    <>
      <h1 className="page-title">Tableau de bord</h1>
      <p className="page-subtitle">Vue d'ensemble de l'état de Neo</p>

      <div className="status-cards">
        {STATUS_CARDS.map(({ id, label, icon: Icon, key }) => (
          <div key={id} className={`status-card ${connState[key] ? 'online' : ''}`}>
            <div className="sc-icon"><Icon size={20} /></div>
            <div>
              <div className="sc-label">{label}</div>
              <div className="sc-value">{connState[key] ? 'En ligne' : 'Hors ligne'}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="dash-bottom">
        <div className="card">
          <div className="card-header">
            <Zap size={14} className="header-icon" />
            Actions rapides
          </div>
          <div className="quick-actions">
            {actions.map(({ label, action, icon }) => (
              <button key={action} className="btn" onClick={() => sendCommand(action)}>
                {icon} {label}
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">Activité récente</div>
          <div className="activity-list">
            {recentLogs.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', padding: '12px 0' }}>
                Aucune activité pour le moment
              </div>
            )}
            {recentLogs.map((entry, i) => (
              <div className="activity-item" key={i}>
                <span className="a-time">{entry.t}</span>
                <span className={`log-badge ${entry.l}`}>{entry.l}</span>
                <span className="a-msg">{entry.m}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
