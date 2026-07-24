import { useEffect } from 'react'
import '../styles/landing.css'
import '../styles/seo.css'

// Shown for any path on the marketing domain that isn't the homepage or one
// of the known SEO/migration pages - previously those all silently fell
// through to the homepage, which is confusing and bad for SEO (duplicate
// content on every made-up URL). noindex,nofollow so search engines never
// treat this as a real page.
export default function NotFoundPage({ onGetStarted }) {
  useEffect(() => {
    const prevTitle = document.title
    document.title = 'Page not found - Firewall Config Converter'

    let meta = document.head.querySelector('meta[name="robots"]')
    const hadMeta = Boolean(meta)
    const prevContent = meta?.getAttribute('content')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'robots')
      document.head.appendChild(meta)
    }
    meta.setAttribute('content', 'noindex, nofollow')

    return () => {
      document.title = prevTitle
      if (hadMeta) meta.setAttribute('content', prevContent || 'index, follow')
      else meta.remove()
    }
  }, [])

  return (
    <div className="lp-root" data-theme="light">
      <header className="lp-nav">
        <div className="lp-nav-inner">
          <a href="/" className="lp-brand" style={{ textDecoration: 'none' }}>
            <span className="mark">FC</span>
            Firewall Config Converter
          </a>
          <div className="lp-nav-cta">
            <button className="btn btn-secondary" onClick={() => onGetStarted('login')}>Log in</button>
            <a className="btn btn-primary" href="/">Back to home</a>
          </div>
        </div>
      </header>

      <section className="lp-hero" style={{ textAlign: 'center', paddingBottom: 100 }}>
        <div className="lp-hero-inner" style={{ display: 'block' }}>
          <div className="lp-eyebrow" style={{ justifyContent: 'center' }}>404</div>
          <h1>Page not found</h1>
          <p className="lp-sub" style={{ margin: '0 auto 28px' }}>
            The page you're looking for doesn't exist or may have moved.
          </p>
          <a className="btn btn-primary btn-lg" href="/">Back to home</a>
        </div>
      </section>
    </div>
  )
}
