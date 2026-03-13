import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import socket from '../socket'

const NeoContext = createContext(null)

export function NeoProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const [connState, setConnState] = useState({ mqtt: false, openclaw: false, esp32: false })
  const [servo, setServo] = useState({ pan: 90, tilt: 90 })
  const [logs, setLogs] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [chatThinking, setChatThinking] = useState(false)
  const chatTimeoutRef = useRef(null)
  const streamingRef   = useRef(null)   // id du message en cours de streaming
  const [testResults, setTestResults] = useState({})
  const logsRef = useRef([])

  useEffect(() => {
    socket.connect()

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('conn_state', data => setConnState(data))
    socket.on('servo_state', data => setServo(data))

    socket.on('log_entry', entry => {
      logsRef.current = [...logsRef.current.slice(-399), entry]
      setLogs([...logsRef.current])
    })

    socket.on('logs_history', entries => {
      logsRef.current = entries
      setLogs([...entries])
    })

    socket.on('chat_history_init', (history) => {
      setChatMessages(history.map(m => ({
        type: m.role === 'neo' ? 'neo' : 'user',
        text: m.text,
        time: new Date(m.t * 1000),
      })))
    })

    socket.on('chat_thinking', () => {
      setChatThinking(true)
      streamingRef.current = null
      clearTimeout(chatTimeoutRef.current)
      chatTimeoutRef.current = setTimeout(() => {
        setChatThinking(false)
        streamingRef.current = null
        setChatMessages(prev => [...prev, {
          type: 'neo', text: '⏱ Pas de réponse d\'OpenClaw (timeout 45s)', time: new Date(), error: true
        }])
      }, 45000)
    })

    socket.on('chat_token', ({ token }) => {
      clearTimeout(chatTimeoutRef.current)
      setChatThinking(false)
      setChatMessages(prev => {
        // Premier token : créer le message streamé
        if (streamingRef.current === null) {
          const id = Date.now()
          streamingRef.current = id
          return [...prev, { id, type: 'neo', text: token, time: new Date(), streaming: true }]
        }
        // Tokens suivants : ajouter au message existant
        return prev.map(m =>
          m.id === streamingRef.current ? { ...m, text: m.text + token } : m
        )
      })
    })

    socket.on('chat_reply', data => {
      clearTimeout(chatTimeoutRef.current)
      setChatThinking(false)
      setChatMessages(prev => {
        // Finaliser le message streamé s'il existe
        if (streamingRef.current !== null) {
          const id = streamingRef.current
          streamingRef.current = null
          return prev.map(m =>
            m.id === id ? { ...m, text: data.text, streaming: false, error: !!data.error } : m
          )
        }
        // Sinon ajouter directement (cas sans streaming)
        streamingRef.current = null
        return [...prev, { type: 'neo', text: data.text, time: new Date(), error: !!data.error }]
      })
    })

    socket.on('test_result', data => {
      setTestResults(prev => ({ ...prev, [data.component]: data }))
    })

    socket.on('neo_status', data => {
      if (data.pan !== undefined || data.tilt !== undefined) {
        setServo(prev => ({
          pan: data.pan ?? prev.pan,
          tilt: data.tilt ?? prev.tilt,
        }))
      }
    })

    return () => {
      clearTimeout(chatTimeoutRef.current)
      socket.off('connect')
      socket.off('disconnect')
      socket.off('conn_state')
      socket.off('servo_state')
      socket.off('log_entry')
      socket.off('logs_history')
      socket.off('chat_thinking')
      socket.off('chat_token')
      socket.off('chat_reply')
      socket.off('test_result')
      socket.off('neo_status')
      socket.off('chat_history_init')
      socket.disconnect()
    }
  }, [])

  const sendCommand = useCallback((action, extra = {}) => {
    socket.emit('command', { action, ...extra })
  }, [])

  const setServoAngle = useCallback((pan, tilt) => {
    socket.emit('servo_angle', { pan, tilt })
  }, [])

  const sendChat = useCallback((message) => {
    setChatMessages(prev => [...prev, { type: 'user', text: message, time: new Date() }])
    socket.emit('chat', { message })
  }, [])

  const runTest = useCallback((component) => {
    setTestResults(prev => ({ ...prev, [component]: { component, ok: null, msg: 'En cours...' } }))
    socket.emit('test_component', { component })
  }, [])

  const clearLogs = useCallback(() => {
    logsRef.current = []
    setLogs([])
    socket.emit('clear_logs')
  }, [])

  const clearChat = useCallback(() => {
    clearTimeout(chatTimeoutRef.current)
    setChatMessages([])
    setChatThinking(false)
    fetch('/api/chat/clear', { method: 'POST' })
  }, [])

  const value = {
    connected, connState, servo, logs, chatMessages, chatThinking,
    testResults, sendCommand, setServoAngle, sendChat, runTest, clearLogs, clearChat,
  }

  return <NeoContext.Provider value={value}>{children}</NeoContext.Provider>
}

export function useNeo() {
  const ctx = useContext(NeoContext)
  if (!ctx) throw new Error('useNeo must be used within NeoProvider')
  return ctx
}
