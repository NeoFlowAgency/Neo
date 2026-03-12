import { useState, useRef, useEffect } from 'react'
import { useNeo } from '../context/NeoContext'
import { MessageCircle, Send, Trash2 } from 'lucide-react'

const QUICK_PHRASES = [
  'Bonjour Neo !',
  'Comment tu vas ?',
  'Qui es-tu ?',
  'Dis-moi une blague',
  'Présente-toi',
  'Quelle heure est-il ?',
]

export default function Communication() {
  const { chatMessages, chatThinking, sendChat, connState, clearChat } = useNeo()
  const [input, setInput] = useState('')
  const messagesEnd = useRef(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, chatThinking])

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || chatThinking) return
    sendChat(msg)
    setInput('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (date) => {
    if (!date) return ''
    return new Date(date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <>
      <h1 className="page-title">
        <MessageCircle size={24} className="title-icon" />
        Communication
      </h1>
      <p className="page-subtitle">
        Parle directement à Neo via OpenClaw
        {!connState.openclaw && (
          <span style={{ color: 'var(--red-500)', marginLeft: 12, fontSize: '0.72rem' }}>
            ⚠ OpenClaw non connecté — les messages ne seront pas délivrés
          </span>
        )}
      </p>

      <div className="chat-layout">
        <div className="chat-messages">
          {chatMessages.length === 0 && !chatThinking && (
            <div className="msg msg-system">Envoie un message pour commencer la conversation avec Neo.</div>
          )}

          {chatMessages.map((msg, i) => (
            <div key={i} className={`msg msg-${msg.type}${msg.error ? ' msg-error' : ''}`}>
              <div className="msg-sender">{msg.type === 'user' ? 'Toi' : 'Neo'}</div>
              <div>{msg.text}</div>
              <div className="msg-time">{formatTime(msg.time)}</div>
            </div>
          ))}

          {chatThinking && (
            <div className="thinking-indicator">
              <div className="thinking-dot" />
              <div className="thinking-dot" />
              <div className="thinking-dot" />
            </div>
          )}

          <div ref={messagesEnd} />
        </div>

        <div className="quick-phrases">
          {QUICK_PHRASES.map(phrase => (
            <button
              key={phrase}
              className="btn btn-sm"
              onClick={() => sendChat(phrase)}
              disabled={chatThinking}
            >
              {phrase}
            </button>
          ))}
        </div>

        <div className="chat-input-row">
          <input
            className="input"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={connState.openclaw ? 'Écris quelque chose à Neo…' : 'OpenClaw non connecté…'}
            disabled={chatThinking}
          />
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={chatThinking || !input.trim()}
            title="Envoyer (Entrée)"
          >
            <Send size={16} />
            Envoyer
          </button>
          {chatMessages.length > 0 && (
            <button
              className="btn btn-sm btn-danger"
              onClick={clearChat}
              title="Effacer la conversation"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
    </>
  )
}
