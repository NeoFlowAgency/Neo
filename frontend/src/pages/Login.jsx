import { useState } from 'react'
import { Lock } from 'lucide-react'

export default function Login({ onLogin }) {
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res  = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      const data = await res.json()
      if (data.ok) {
        onLogin()
      } else {
        setError('Mot de passe incorrect')
        setPassword('')
      }
    } catch {
      setError('Impossible de joindre le serveur')
    }
    setLoading(false)
  }

  return (
    <div className="login-wrapper">
      <div className="card login-card">
        <div className="login-logo">
          <div className="logo-text">NEO</div>
          <div className="logo-sub">CONTROL CENTER</div>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-input-wrap">
            <Lock size={14} className="login-icon" />
            <input
              className="input"
              type="password"
              placeholder="Mot de passe"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{ paddingLeft: 38 }}
              autoFocus
              autoComplete="current-password"
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading || !password}
            style={{ width: '100%', padding: '10px 0', justifyContent: 'center' }}
          >
            {loading ? <span className="spinner" /> : 'Accéder'}
          </button>
        </form>
      </div>
    </div>
  )
}
