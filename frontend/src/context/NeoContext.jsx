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

    socket.on('chat_thinking', () => {
      setChatThinking(true)
      clearTimeout(chatTimeoutRef.current)
      chatTimeoutRef.current = setTimeout(() => {
        setChatThinking(false)
        setChatMessages(prev => [...prev, {
          type: 'neo', text: '⏱ Pas de réponse d\'OpenClaw (timeout 45s)', time: new Date(), error: true
        }])
      }, 45000)
    })

    socket.on('chat_reply', data => {
      clearTimeout(chatTimeoutRef.current)
      setChatThinking(false)
      setChatMessages(prev => [...prev, { type: 'neo', text: data.text, time: new Date() }])
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
      socket.off('chat_reply')
      socket.off('test_result')
      socket.off('neo_status')
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
