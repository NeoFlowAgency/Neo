import { io } from 'socket.io-client'

const socket = io({
  autoConnect: false,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 10,
})

export default socket
