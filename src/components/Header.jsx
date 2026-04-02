import locations from '../data/locations.json'
import './Header.css'

function Header({ theme, onToggleTheme }) {
  return (
    <header className="header">
      {/* Brand */}
      <div className="header-brand">
        <span className="header-brand-icon" aria-hidden="true">🌍</span>
        <h1 className="header-title">
          How Is Living There<span className="header-title-accent">?</span>
        </h1>
      </div>

      {/* Center nav slot — empty in V1, ready for tabs in V2 */}
      <nav className="header-nav" aria-label="Main navigation" />

      {/* Right controls */}
      <div className="header-controls">
        <span className="header-loc-count">
          {locations.length.toLocaleString()} cities
        </span>

        <a
          className="reddit-badge"
          href="https://reddit.com/r/howislivingthere"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Visit r/howislivingthere on Reddit"
        >
          <span className="reddit-dot" aria-hidden="true" />
          <span className="reddit-badge-text">r/howislivingthere</span>
        </a>

        <button
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? '☀' : '☽'}
        </button>
      </div>
    </header>
  )
}

export default Header
