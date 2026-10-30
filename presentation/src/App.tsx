import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { slides } from './slides'

// Slides are laid out on a fixed 1920x1080 canvas and scaled to the screen,
// so the deck looks the same on a laptop, a projector, or a shared Teams window.
const CANVAS_W = 1920
const CANVAS_H = 1080
const LAST = slides.length - 1

const clamp = (n: number) => Math.min(Math.max(n, 0), LAST)

function slideFromHash(): number {
  const match = window.location.hash.match(/^#\/(\d+)$/)
  return match ? clamp(Number(match[1]) - 1) : 0
}

function toggleFullscreen() {
  if (document.fullscreenElement) void document.exitFullscreen()
  else void document.documentElement.requestFullscreen()
}

export default function App() {
  const [index, setIndex] = useState(slideFromHash)
  const [scale, setScale] = useState(1)
  const go = useCallback((delta: number) => setIndex((i) => clamp(i + delta)), [])

  useEffect(() => {
    window.history.replaceState(null, '', `#/${index + 1}`)
  }, [index])

  useEffect(() => {
    const onHash = () => setIndex(slideFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useLayoutEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / CANVAS_W, window.innerHeight / CANVAS_H))
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      // Let a focused button handle its own Space and Enter.
      if ((e.key === ' ' || e.key === 'Enter') && (e.target as HTMLElement).closest('button')) return
      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':
        case 'PageDown':
        case ' ':
        case 'Enter':
          e.preventDefault()
          go(1)
          break
        case 'ArrowLeft':
        case 'ArrowUp':
        case 'PageUp':
        case 'Backspace':
          e.preventDefault()
          go(-1)
          break
        case 'Home':
          setIndex(0)
          break
        case 'End':
          setIndex(LAST)
          break
        case 'f':
        case 'F':
          toggleFullscreen()
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go])

  const { title, Component } = slides[index]

  return (
    <main className="viewport">
      <div
        className="stage"
        style={{ width: CANVAS_W, height: CANVAS_H, transform: `translate(-50%, -50%) scale(${scale})` }}
      >
        <header className="chrome chrome-top">
          <span>Sarasota MAS AI Pilot</span>
          <span>Sprint 2 sample dataset</span>
        </header>

        <section
          key={index}
          className="slide"
          aria-roledescription="slide"
          aria-label={`${index + 1} of ${slides.length}: ${title}`}
        >
          <Component />
        </section>

        <footer className="chrome chrome-bottom">
          <span className="chrome-hint">Arrow keys to move · F for full screen</span>
          <nav className="deck-nav" aria-label="Slides">
            <button type="button" className="nav-btn" onClick={() => go(-1)} disabled={index === 0} aria-label="Previous slide">
              <svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="15 5 8 12 15 19" /></svg>
            </button>
            <span className="deck-count" aria-live="polite">
              {index + 1} / {slides.length}
            </span>
            <button type="button" className="nav-btn" onClick={() => go(1)} disabled={index === LAST} aria-label="Next slide">
              <svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="9 5 16 12 9 19" /></svg>
            </button>
            <button type="button" className="nav-btn" onClick={toggleFullscreen} aria-label="Toggle full screen">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <polyline points="4 9 4 4 9 4" />
                <polyline points="15 4 20 4 20 9" />
                <polyline points="20 15 20 20 15 20" />
                <polyline points="9 20 4 20 4 15" />
              </svg>
            </button>
          </nav>
        </footer>
      </div>
    </main>
  )
}
