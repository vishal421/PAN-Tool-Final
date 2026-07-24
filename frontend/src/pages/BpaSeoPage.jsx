import SeoHead from '../components/seo/SeoHead'
import FaqTiles from '../components/FaqTiles'
import { bpaSeoContent } from '../seo/content/bpaSeo'
import '../styles/landing.css'
import '../styles/seo.css'

// BPA is a fully separate app (its own server, its own Palo Alto SCM API
// login) on its own subdomain - this page's CTAs hand off there directly,
// rather than into this app's own signup flow like the migration SEO pages do.
function bpaToolUrl() {
  const ROOT_DOMAIN = import.meta.env.VITE_ROOT_DOMAIN
  return ROOT_DOMAIN ? `https://bpa.${ROOT_DOMAIN}/` : (import.meta.env.VITE_BPA_URL || 'http://localhost:4021/')
}

const SEVERITIES = [
  { key: 'critical', label: 'Critical', desc: 'Fix before your next change window' },
  { key: 'medium', label: 'Medium', desc: 'Plan into upcoming maintenance' },
  { key: 'informational', label: 'Informational', desc: 'Good to know, low urgency' },
  { key: 'pass', label: 'Pass', desc: 'Already meets best practice' },
]

export default function BpaSeoPage({ onGetStarted }) {
  const { path, title, description, h1, heroEyebrow, heroSub, intro, challenges, workflow, benefits, checklist, faq, closing } = bpaSeoContent
  const toolUrl = bpaToolUrl()

  const breadcrumbSchema = [
    { name: 'Home', path: '/' },
    { name: 'Palo Alto BPA Report Generator', path },
  ]

  return (
    <div className="lp-root" data-theme="light">
      <SeoHead title={title} description={description} path={path} breadcrumbs={breadcrumbSchema} faq={faq} />

      <header className="lp-nav">
        <div className="lp-nav-inner">
          <a href="/" className="lp-brand" style={{ textDecoration: 'none' }}>
            <span className="mark">FC</span>
            Firewall Config Converter
          </a>
          <nav className="lp-nav-links">
            <a href="/#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="lp-nav-cta">
            <button className="btn btn-secondary" onClick={() => onGetStarted('login')}>Log in</button>
            <a className="btn btn-primary" href={toolUrl} target="_blank" rel="noopener noreferrer">Open BPA Tool</a>
          </div>
        </div>
      </header>

      <div className="lp-section-inner seo-breadcrumb-wrap">
        <nav className="seo-breadcrumbs" aria-label="Breadcrumb">
          <ol>
            <li><a href="/">Home</a></li>
            <li aria-hidden="true">/</li>
            <li aria-current="page">Palo Alto BPA Report Generator</li>
          </ol>
        </nav>
      </div>

      <section className="lp-hero seo-hero">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <div className="lp-eyebrow">{heroEyebrow}</div>
            <h1>{h1}</h1>
            <p className="lp-sub">{heroSub}</p>
            <div className="lp-hero-actions">
              <a className="btn btn-primary btn-lg" href={toolUrl} target="_blank" rel="noopener noreferrer">Generate a BPA report free</a>
              <a className="lp-link" href="#faq">Jump to FAQ &darr;</a>
            </div>
          </div>
          <div className="lp-hero-visual">
            <div className="bpa-hero-card">
              <div className="bpa-hero-card-head">Sample findings breakdown</div>
              {SEVERITIES.map((s) => (
                <div key={s.key} className={`bpa-hero-row bpa-hero-row-${s.key}`}>
                  <span className={`bpa-hero-dot bpa-hero-dot-${s.key}`} />
                  <span className="bpa-hero-label">{s.label}</span>
                  <span className="bpa-hero-desc">{s.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section" id="overview">
        <div className="lp-section-inner seo-prose">
          {intro.map((p, i) => <p key={i}>{p}</p>)}
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="challenges">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Why teams put this off</div>
            <h2>{challenges.heading}</h2>
          </div>
          <div className="seo-tile-grid">
            {challenges.items.map((c) => (
              <div className="lp-feature-card" key={c.title}>
                <h3>{c.title}</h3>
                <p>{c.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section" id="how-it-works">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">BPA workflow</div>
            <h2>{workflow.heading}</h2>
          </div>
          <div className="lp-steps seo-workflow-diagram">
            {workflow.steps.map((s, i) => (
              <div className="lp-step seo-workflow-step" key={s.title}>
                <div className="lp-step-n">{String(i + 1).padStart(2, '0')}</div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
                {i < workflow.steps.length - 1 && <div className="seo-workflow-connector" aria-hidden="true">&darr;</div>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="benefits">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Why teams automate this</div>
            <h2>Benefits of an automated Palo Alto BPA report</h2>
          </div>
          <div className="seo-tile-grid">
            {benefits.map((b) => (
              <div className="lp-feature-card" key={b.title}>
                <h3>{b.title}</h3>
                <p>{b.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section" id="checklist">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Before you run it</div>
            <h2>{checklist.heading}</h2>
          </div>
          <div className="seo-checklist">
            {checklist.items.map((c) => (
              <div className="seo-checklist-item" key={c.title}>
                <div className="seo-checklist-mark" aria-hidden="true">&#10003;</div>
                <div>
                  <h3>{c.title}</h3>
                  <p>{c.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="faq">
        <div className="lp-section-inner lp-faq-wrap">
          <div className="lp-section-head">
            <div className="lp-eyebrow">FAQ</div>
            <h2>Palo Alto BPA report generator &mdash; frequently asked questions</h2>
          </div>
          <FaqTiles faq={faq} />
        </div>
      </section>

      <section className="lp-section seo-related" aria-label="Related tools">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Related tools</div>
            <h2>Already migrated to Palo Alto? Run a BPA next</h2>
          </div>
          <div className="seo-related-grid">
            <a className="seo-related-card" href="/">
              <span className="seo-related-vendor">&larr; Home</span>
              <span className="lp-link">Firewall Config Converter overview &rarr;</span>
            </a>
            <a className="seo-related-card" href="/fortigate-to-palo-alto-migration">
              <span className="seo-related-vendor">FortiGate &rarr; Palo Alto</span>
              <span className="lp-link">Migration guide &rarr;</span>
            </a>
            <a className="seo-related-card" href="/cisco-to-palo-alto-migration">
              <span className="seo-related-vendor">Cisco ASA &rarr; Palo Alto</span>
              <span className="lp-link">Migration guide &rarr;</span>
            </a>
          </div>
        </div>
      </section>

      <section className="lp-cta" id="contact">
        <div className="lp-section-inner lp-cta-inner">
          <h2>{closing.heading}</h2>
          <p>{closing.body}</p>
          <div className="lp-hero-actions" style={{ justifyContent: 'center' }}>
            <a className="btn btn-primary btn-lg" href={toolUrl} target="_blank" rel="noopener noreferrer">Open the BPA tool</a>
            <a className="lp-link" href="mailto:support@example.com">Contact us</a>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-section-inner lp-footer-inner">
          <a href="/" className="lp-brand" style={{ textDecoration: 'none' }}><span className="mark">FC</span>Firewall Config Converter</a>
          <div className="lp-footer-links">
            <a href="/fortigate-to-palo-alto-migration">FortiGate Migration</a>
            <a href="/cisco-to-palo-alto-migration">Cisco ASA Migration</a>
            <a href="/checkpoint-to-palo-alto-migration">Check Point Migration</a>
            <a href="/sophos-to-palo-alto-migration">Sophos Migration</a>
            <a href="#faq">FAQ</a>
            <a href="mailto:support@example.com">Contact</a>
          </div>
          <div className="lp-footer-copy">&copy; {new Date().getFullYear()} Firewall Config Converter. All rights reserved.</div>
        </div>
      </footer>
    </div>
  )
}
