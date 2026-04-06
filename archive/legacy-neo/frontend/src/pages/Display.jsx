import { useState } from 'react'
import { useNeo } from '../context/NeoContext'
import { Monitor, Type, Bookmark } from 'lucide-react'

const PRESETS = [
  { label: 'READY',       l1: 'NEO READY       ', l2: '                ' },
  { label: 'ÉCOUTE',      l1: 'ECOUTE...       ', l2: '                ' },
  { label: 'RÉFLEXION',   l1: 'REFLEXION...    ', l2: '                ' },
  { label: 'BONJOUR',     l1: 'BONJOUR !       ', l2: 'JE SUIS NEO     ' },
  { label: 'SYS OK',      l1: 'SYSTEME OK      ', l2: 'ALL SYSTEMS GO  ' },
  { label: 'VERSION',     l1: '>> NEO V1 <<    ', l2: 'ROBOT ANIMATRON.' },
]

export default function Display() {
  const { sendCommand } = useNeo()
  const [lcdL1, setLcdL1] = useState('NEO READY       ')
  const [lcdL2, setLcdL2] = useState('                ')
  const [text, setText] = useState('')

  const sendText = () => {
    if (!text) return
    const l1 = text.substring(0, 16).padEnd(16)
    const l2 = (text.substring(16, 32) || '').padEnd(16)
    setLcdL1(l1)
    setLcdL2(l2)
    sendCommand('lcd', { texte: text })
    setText('')
  }

  const applyPreset = (l1, l2) => {
    setLcdL1(l1)
    setLcdL2(l2)
    sendCommand('lcd', { texte: l1 + l2 })
  }

  const clearLcd = () => {
    const empty = '                '
    setLcdL1(empty)
    setLcdL2(empty)
    sendCommand('lcd', { texte: empty + empty })
  }

  return (
    <>
      <h1 className="page-title">
        <Monitor size={24} className="title-icon" />
        Affichage LCD
      </h1>
      <p className="page-subtitle">Contrôle de l'écran LCD 16×2 I2C</p>

      <div className="lcd-layout">
        <div className="card full">
          <div className="card-header">
            <Monitor size={14} className="header-icon" />
            Aperçu en temps réel
          </div>
          <div className="lcd-screen">
            <div className="lcd-line">{lcdL1}</div>
            <div className="lcd-line">{lcdL2}</div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <Type size={14} className="header-icon" />
            Envoyer du texte
          </div>
          <div className="flex-col">
            <input
              className="input"
              type="text"
              maxLength={32}
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendText()}
              placeholder="Texte (max 32 caractères)…"
            />
            <div className="flex-row">
              <button className="btn btn-primary" onClick={sendText} style={{ flex: 1 }}>
                Afficher sur LCD
              </button>
              <button className="btn btn-danger" onClick={clearLcd}>
                Effacer
              </button>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              Ligne 1 : caractères 1-16 &nbsp;|&nbsp; Ligne 2 : caractères 17-32
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <Bookmark size={14} className="header-icon" />
            Messages prédéfinis
          </div>
          <div className="presets-grid">
            {PRESETS.map(({ label, l1, l2 }) => (
              <button key={label} className="btn" onClick={() => applyPreset(l1, l2)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
