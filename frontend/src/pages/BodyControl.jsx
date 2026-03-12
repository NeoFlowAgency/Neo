import { useState, useRef, useCallback, useEffect } from 'react'
import { useNeo } from '../context/NeoContext'
import { Bot, Crosshair } from 'lucide-react'

const PAN_MIN = 30, PAN_MAX = 150
const TILT_MIN = 50, TILT_MAX = 130

export default function BodyControl() {
  const { servo, sendCommand, setServoAngle } = useNeo()
  const [speed, setSpeed] = useState(3)
  const [localPan, setLocalPan] = useState(servo.pan)
  const [localTilt, setLocalTilt] = useState(servo.tilt)
  const [dragging, setDragging] = useState(false)
  const holdRef    = useRef(null)
  const [pressedKey, setPressedKey] = useState(null)

  // Sync with server state when not dragging
  useEffect(() => {
    if (!dragging) {
      setLocalPan(servo.pan)
      setLocalTilt(servo.tilt)
    }
  }, [servo.pan, servo.tilt, dragging])

  const holdCmd = useCallback((action) => {
    if (holdRef.current) return
    sendCommand(action)
    setPressedKey(action)
    holdRef.current = setInterval(() => sendCommand(action), Math.max(80, 400 - speed * 60))
  }, [sendCommand, speed])

  const stopHold = useCallback(() => {
    clearInterval(holdRef.current)
    holdRef.current = null
    setPressedKey(null)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const keyMap = {
      ArrowUp: 'tete_haut', ArrowDown: 'tete_bas',
      ArrowLeft: 'tete_gauche', ArrowRight: 'tete_droite',
      ' ': 'tete_centre', r: 'repos', R: 'repos',
    }

    const onKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (keyMap[e.key]) { e.preventDefault(); holdCmd(keyMap[e.key]) }
    }
    const onKeyUp = (e) => { if (keyMap[e.key]) stopHold() }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [holdCmd, stopHold])

  // SVG viz coordinates
  const vizX = ((servo.pan - PAN_MIN) / (PAN_MAX - PAN_MIN)) * 140 + 20
  const vizY = ((servo.tilt - TILT_MIN) / (TILT_MAX - TILT_MIN)) * 140 + 20

  const handleSliderPan = (e) => {
    setDragging(true)
    setLocalPan(parseInt(e.target.value))
  }
  const handleSliderTilt = (e) => {
    setDragging(true)
    setLocalTilt(parseInt(e.target.value))
  }
  const commitSliders = () => {
    setDragging(false)
    setServoAngle(localPan, localTilt)
  }

  const poses = [
    { label: 'Centre',     fn: () => setServoAngle(90, 90) },
    { label: 'Repos',      fn: () => sendCommand('repos') },
    { label: 'Gauche max', fn: () => setServoAngle(40, 90) },
    { label: 'Droite max', fn: () => setServoAngle(140, 90) },
    { label: 'Haut max',   fn: () => setServoAngle(90, 55) },
    { label: 'Bas max',    fn: () => setServoAngle(90, 125) },
  ]

  return (
    <>
      <h1 className="page-title">
        <Bot size={24} className="title-icon" />
        Contrôle du corps
      </h1>
      <p className="page-subtitle">Contrôle la tête de Neo — 4 servos MG996R</p>

      <div className="body-layout">
        {/* Head position visualizer */}
        <div className="card head-viz-card">
          <div className="card-header">
            <Crosshair size={14} className="header-icon" />
            Position
          </div>
          <div className="head-viz">
            <svg viewBox="0 0 180 180">
              <defs>
                <radialGradient id="glow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%"   stopColor="#3b82f6" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                </radialGradient>
              </defs>
              {/* Grid */}
              <line x1="90" y1="10" x2="90" y2="170" stroke="#1a1a38" strokeWidth="1" />
              <line x1="10" y1="90" x2="170" y2="90" stroke="#1a1a38" strokeWidth="1" />
              <circle cx="90" cy="90" r="60" fill="none" stroke="#1a1a38" strokeWidth="1" />
              <circle cx="90" cy="90" r="30" fill="none" stroke="#111128" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="90" cy="90" r="65" fill="url(#glow)" />
              {/* Target */}
              <circle cx={vizX} cy={vizY} r="7" fill="#3b82f6" opacity="0.9">
                <animate attributeName="r" values="6;8;6" dur="2s" repeatCount="indefinite" />
              </circle>
              <line x1={vizX - 16} y1={vizY} x2={vizX + 16} y2={vizY} stroke="#3b82f6" strokeWidth="1" opacity="0.4" />
              <line x1={vizX} y1={vizY - 16} x2={vizX} y2={vizY + 16} stroke="#3b82f6" strokeWidth="1" opacity="0.4" />
            </svg>
          </div>
          <div className="viz-info">
            <div>PAN <span>{servo.pan}°</span></div>
            <div>TILT <span>{servo.tilt}°</span></div>
          </div>
        </div>

        {/* D-Pad */}
        <div className="card">
          <div className="card-header">D-Pad directionnel</div>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
            <div className="dpad-grid">
              <div className="dpad-btn empty" />
              <button className={`dpad-btn ${pressedKey === 'tete_haut' ? 'pressed' : ''}`}
                      onMouseDown={() => holdCmd('tete_haut')}  onMouseUp={stopHold} onMouseLeave={stopHold}
                      onTouchStart={() => holdCmd('tete_haut')} onTouchEnd={stopHold}>▲</button>
              <div className="dpad-btn empty" />

              <button className={`dpad-btn ${pressedKey === 'tete_gauche' ? 'pressed' : ''}`}
                      onMouseDown={() => holdCmd('tete_gauche')}  onMouseUp={stopHold} onMouseLeave={stopHold}
                      onTouchStart={() => holdCmd('tete_gauche')} onTouchEnd={stopHold}>◀</button>
              <button className="dpad-btn center-btn" onClick={() => sendCommand('tete_centre')}>CTR</button>
              <button className={`dpad-btn ${pressedKey === 'tete_droite' ? 'pressed' : ''}`}
                      onMouseDown={() => holdCmd('tete_droite')}  onMouseUp={stopHold} onMouseLeave={stopHold}
                      onTouchStart={() => holdCmd('tete_droite')} onTouchEnd={stopHold}>▶</button>

              <div className="dpad-btn empty" />
              <button className={`dpad-btn ${pressedKey === 'tete_bas' ? 'pressed' : ''}`}
                      onMouseDown={() => holdCmd('tete_bas')}  onMouseUp={stopHold} onMouseLeave={stopHold}
                      onTouchStart={() => holdCmd('tete_bas')} onTouchEnd={stopHold}>▼</button>
              <div className="dpad-btn empty" />
            </div>
          </div>
          <div className="speed-control">
            <span>Vitesse</span>
            <input type="range" min="1" max="5" value={speed} onChange={e => setSpeed(parseInt(e.target.value))} />
            <span style={{ color: 'var(--blue-400)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{speed}</span>
          </div>
        </div>

        {/* Sliders */}
        <div className="card">
          <div className="card-header">Contrôle précis</div>
          <div className="slider-group">
            <div className="slider-label">
              Pan (gauche/droite)
              <span>{dragging ? localPan : servo.pan}°</span>
            </div>
            <input type="range" className="servo-slider" min={PAN_MIN} max={PAN_MAX}
                   value={dragging ? localPan : servo.pan}
                   onInput={handleSliderPan} onChange={commitSliders} />
          </div>
          <div className="slider-group">
            <div className="slider-label">
              Tilt (haut/bas)
              <span>{dragging ? localTilt : servo.tilt}°</span>
            </div>
            <input type="range" className="servo-slider" min={TILT_MIN} max={TILT_MAX}
                   value={dragging ? localTilt : servo.tilt}
                   onInput={handleSliderTilt} onChange={commitSliders} />
          </div>
        </div>

        {/* Quick poses */}
        <div className="card full-span">
          <div className="card-header">Poses rapides</div>
          <div className="poses-grid">
            {poses.map(({ label, fn }) => (
              <button key={label} className="btn" onClick={fn}>{label}</button>
            ))}
          </div>
        </div>

        {/* Keyboard hint */}
        <div className="kb-hint full-span">
          <span className="key-badge">↑</span>
          <span className="key-badge">↓</span>
          <span className="key-badge">←</span>
          <span className="key-badge">→</span>
          Tête &nbsp;|&nbsp;
          <span className="key-badge">Espace</span> Centre &nbsp;|&nbsp;
          <span className="key-badge">R</span> Repos
        </div>
      </div>
    </>
  )
}
