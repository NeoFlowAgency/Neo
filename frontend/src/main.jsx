import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './App.css'
import { NeoProvider } from './context/NeoContext'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <NeoProvider>
      <App />
    </NeoProvider>
  </React.StrictMode>
)
