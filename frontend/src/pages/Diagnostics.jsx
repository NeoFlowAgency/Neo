import { useState, useRef, useEffect } from 'react'
import { useNeo } from '../context/NeoContext'
import { Wrench, Wifi, Brain, Gauge, Monitor as MonitorIcon, Volume2, PlayCircle, Terminal, Send } from 'lucide-react'

const TESTS = [
  { id: 'mqtt',       name: 'MQTT Broker',     desc: 'Vérifier la connexion au broker MQTT',        icon: Wifi },
  { id: 'openclaw',   name: 'OpenClaw IA',     desc: 'Ping le WebSocket Gateway d\'OpenClaw',       icon: Brain },
  { id: 'servo_pan',  name: 'Servo PAN',       desc: 'Sweep gauche → droite → centre',              icon: Gauge },
  { id: 'servo_tilt', name: 'Servo TILT',      desc: 'Sweep haut → bas → centre',                   icon: Gauge },
  { id: 'lcd',        name: 'Affichage LCD',   desc: 'Envoyer un pattern de test au LCD',           icon: MonitorIcon },
  { id: 'buzzer',     name: 'Buzzer / Speaker', desc: 'Signal audio de test',                       icon: Volume2 },
  { id: 'full',       name: 'TEST COMPLET',    desc: 'Tous les composants en séquence',             icon: PlayCircle },
]

export default function Diagnostics() {
  const { testResults, runTest, logs, clearLogs, connState, servo } = useNeo()
  const [rawCmd, setRawCmd] = useState('')
  const logEndRef = useRef(null)
  const { sendCommand } = useNeo()

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const getBadgeClass = (id) => {
    const r = testResults[id]
    if (!r) return 'idle'
    if (r.ok === null) return 'running'
    return r.ok ? 'ok' : 'fail'
  }

  const getBadgeText = (id) => {
    const r = testResults[id]
    if (!r) return 'IDLE'
    if (r.ok === null) return '...'
    return r.ok ? 'OK' : 'FAIL'
  }

  const sendRaw = () => {
    if (!rawCmd.trim()) return
    try {
      const data = JSON.parse(rawCmd)
      sendCommand(data.action, data)
      setRawCmd('')
    } catch (e) {
      alert('JSON invalide: ' + e.message)
    }
  }

  return (
    <>
      <h1 className="page-title">
        <Wrench size={24} className="title-icon" />
        Diagnostics & Réparation
      </h1>
      <p className="page-subtitle">Tests de composants, surveillance et commandes manuelles</p>

      <div className="diag-layout">
        {/* Tests */}
        <div className="card">
          <div className="card-header">
            <Wrench size={14} className="header-icon" />
            Tests composants
          </div>
          <div className="test-list">
            {TESTS.map(({ id, name, desc, icon: Icon }) => (
              <div className="test-row" key={id}>
                <Icon size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <div className="test-info">
                  <div className="test-name">{name}</div>
                  <div className="test-desc">{desc}</div>
                </div>
                <span className={`test-badge ${getBadgeClass(id)}`}>{getBadgeText(id)}</span>
                <button
                  className={`btn btn-sm ${id === 'full' ? 'btn-primary' : ''}`}
                  onClick={() => runTest(id)}
                >
                  {id === 'full' ? 'LANCER' : 'TEST'}
                </button>
              </div>
            ))}
          </div>

          {/* Show last test message */}
          {Object.values(testResults).some(r => r.msg) && (
            <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              {Object.entries(testResults)
                .filter(([, r]) => r.msg && r.ok !== null)
                .slice(-3)
                .map(([id, r]) => (
                  <div key={id} style={{ marginBottom: 4 }}>
                    <span style={{ color: r.ok ? 'var(--green-500)' : 'var(--red-500)', fontWeight: 600 }}>
                      {id}:
                    </span>{' '}
                    {r.msg}
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* System info + raw command */}
        <div className="card">
          <div className="card-header">
            <Terminal size={14} className="header-icon" />
            Informations système
          </div>
          <div className="info-table">
            <div className="info-row"><span className="info-key">VPS IP</span><span className="info-val">72.61.111.8</span></div>
            <div className="info-row"><span className="info-key">MQTT Port</span><span className="info-val">1883</span></div>
            <div className="info-row"><span className="info-key">OpenClaw WS</span><span className="info-val">:18789</span></div>
            <div className="info-row"><span className="info-key">Servo Pan</span><span className="info-val">{servo.pan}°</span></div>
            <div className="info-row"><span className="info-key">Servo Tilt</span><span className="info-val">{servo.tilt}°</span></div>
            <div className="info-row"><span className="info-key">MQTT Status</span><span className="info-val" style={{ color: connState.mqtt ? 'var(--green-500)' : 'var(--red-500)' }}>{connState.mqtt ? 'Connecté' : 'Déconnecté'}</span></div>
            <div className="info-row"><span className="info-key">OpenClaw</span><span className="info-val" style={{ color: connState.openclaw ? 'var(--green-500)' : 'var(--red-500)' }}>{connState.openclaw ? 'Connecté' : 'Déconnecté'}</span></div>
            <div className="info-row"><span className="info-key">Firmware</span><span className="info-val">neo_v1.ino</span></div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div className="card-header">
              <Send size={14} className="header-icon" />
              Commande MQTT manuelle
            </div>
            <div className="flex-col">
              <input
                className="input"
                type="text"
                value={rawCmd}
                onChange={e => setRawCmd(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendRaw()}
                placeholder='{"action":"repos"}'
                style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}
              />
              <button className="btn" onClick={sendRaw}>
                <Send size={14} /> Publier sur neo/commandes
              </button>
            </div>
          </div>
        </div>

        {/* Log console */}
        <div className="card full" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <Terminal size={14} className="header-icon" />
            Console de logs
          </div>
          <div className="log-console">
            {logs.length === 0 && (
              <div style={{ color: 'var(--text-muted)', padding: 8 }}>Aucun log pour le moment…</div>
            )}
            {logs.map((entry, i) => (
              <div className="log-line" key={i}>
                <span className="log-time">{entry.t}</span>
                <span className={`log-badge ${entry.l}`}>{entry.l}</span>
                <span className="log-msg">{entry.m}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
          <div className="log-controls">
            <span className="log-count">{logs.length} entrées</span>
            <button className="btn btn-sm btn-danger" onClick={clearLogs}>Effacer</button>
          </div>
        </div>
      </div>
    </>
  )
}
