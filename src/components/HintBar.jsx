import { useState, useEffect } from 'react'
import './HintBar.css'

function HintBar({ mapInteracted }) {
  const [visible, setVisible] = useState(true)
  const [fading, setFading] = useState(false)

  useEffect(() => {
    if (mapInteracted && visible) {
      setFading(true)
      const t = setTimeout(() => setVisible(false), 600)
      return () => clearTimeout(t)
    }
  }, [mapInteracted, visible])

  if (!visible) return null

  return (
    <div className={`hint-bar ${fading ? 'hint-bar--fade' : ''}`}>
      <span className="hint-text">
        scroll to zoom &nbsp;·&nbsp; click a marker to explore
      </span>
    </div>
  )
}

export default HintBar
