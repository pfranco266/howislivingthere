import locations from '../data/locations.json'
import './Header.css'

function Header({ theme, onToggleTheme }) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">
          How Is Living There<span className="header-title-accent">?</span>
        </h1>
        <span className="header-subtitle">
          {locations.length} cities · real reviews from Reddit
        </span>
      </div>

      <div className="header-right">
        <button
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          )}
        </button>

        <a
          className="reddit-badge"
          href="https://reddit.com/r/howislivingthere"
          target="_blank"
          rel="noopener noreferrer"
        >
          <span className="reddit-dot" aria-hidden="true" />
          r/howislivingthere
        </a>
      </div>
    </header>
  )
}

export default Header
