import { useState, useEffect } from 'react'
import Header from './components/Header'
import MapView from './components/MapView'
import './App.css'

function App() {
  const [theme, setTheme] = useState('dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} />
      <MapView theme={theme} />
    </div>
  )
}

export default App
