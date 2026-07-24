import SeoHead from './SeoHead'
import SciFiConverter from './SciFiConverter'
import FaqTiles from '../FaqTiles'
import '../../styles/landing.css'
import '../../styles/seo.css'

const ALL_PAGES = [
  { key: 'fortigate', label: 'FortiGate', path: '/fortigate-to-palo-alto-migration' },
  { key: 'checkpoint', label: 'Check Point', path: '/checkpoint-to-palo-alto-migration' },
  { key: 'cisco', label: 'Cisco ASA', path: '/cisco-to-palo-alto-migration' },
  { key: 'sophos', label: 'Sophos', path: '/sophos-to-palo-alto-migration' },
]

function Breadcrumbs({ vendorLabel, path }) {
  return (
    <nav className="seo-breadcrumbs" aria-label="Breadcrumb">
      <ol>
        <li><a href="/">Home</a></li>
        <li aria-hidden="true">/</li>
        <li><a href="#faq">Migration Tools</a></li>
        <li aria-hidden="true">/</li>
        <li aria-current="page">{vendorLabel} to Palo Alto</li>
      </ol>
    </nav>
  )
}

function InternalLinks({ currentKey }) {
  const others = ALL_PAGES.filter((p) => p.key !== currentKey)
  return (
    <section className="lp-section seo-related" aria-label="Related migration guides">
      <div className="lp-section-inner">
        <div className="lp-section-head">
          <div className="lp-eyebrow">More migration guides</div>
          <h2>Convert other firewall vendors to Palo Alto, or head back home</h2>
        </div>
        <div className="seo-related-grid">
          <a className="seo-related-card" href="/">
            <span className="seo-related-vendor">&larr; Home</span>
            <span className="lp-link">Firewall Config Converter overview &rarr;</span>
          </a>
          {others.map((p) => (
            <a key={p.key} className="seo-related-card" href={p.path}>
              <span className="seo-related-vendor">{p.label} &rarr; Palo Alto</span>
              <span className="lp-link">Read the guide &rarr;</span>
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function MigrationPage({ data, onGetStarted }) {
  const {
    key, vendorLabel, path, title, description, h1, heroEyebrow, heroSub,
    intro, challenges, workflow, comparison, sciFiSamples, benefits, checklist, faq, closing,
  } = data

  const breadcrumbSchema = [
    { name: 'Home', path: '/' },
    { name: `${vendorLabel} to Palo Alto Migration`, path },
  ]

  return (
    <div className="lp-root" data-theme="light">
      <SeoHead
        title={title}
        description={description}
        path={path}
        breadcrumbs={breadcrumbSchema}
        faq={faq}
      />

      <header className="lp-nav">
        <div className="lp-nav-inner">
          <a href="/" className="lp-brand" style={{ textDecoration: 'none' }}>
            <span className="mark">FC</span>
            Firewall Config Converter
          </a>
          <nav className="lp-nav-links">
            <a href="/#features">Features</a>
            <a href="/#how-it-works">How it works</a>
            <a href="/#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="lp-nav-cta">
            <button className="btn btn-secondary" onClick={() => onGetStarted('login')}>Log in</button>
            <button className="btn btn-primary" onClick={() => onGetStarted('signup')}>Get started</button>
          </div>
        </div>
      </header>

      <div className="lp-section-inner seo-breadcrumb-wrap">
        <Breadcrumbs vendorLabel={vendorLabel} path={path} />
      </div>

      <section className="lp-hero seo-hero">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <div className="lp-eyebrow">{heroEyebrow}</div>
            <h1>{h1}</h1>
            <p className="lp-sub">{heroSub}</p>
            <div className="lp-hero-actions">
              <button className="btn btn-primary btn-lg" onClick={() => onGetStarted('signup')}>Start your migration free</button>
              <a className="lp-link" href="#faq">Jump to FAQ &darr;</a>
            </div>
          </div>
          <div className="lp-hero-visual">
            <SciFiConverter vendorLabel={vendorLabel} samples={sciFiSamples} />
          </div>
        </div>
      </section>

      <section className="lp-section" id="overview">
        <div className="lp-section-inner seo-prose">
          {intro.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="challenges">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Why it's hard by hand</div>
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
            <div className="lp-eyebrow">Migration workflow</div>
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

      <section className="lp-section lp-section-alt" id="comparison">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Side-by-side</div>
            <h2>{comparison.heading}</h2>
          </div>
          <div className="seo-table-wrap">
            <table className="seo-comparison-table">
              <thead>
                <tr>
                  <th scope="col">Concept</th>
                  <th scope="col">{vendorLabel}</th>
                  <th scope="col">Palo Alto PAN-OS</th>
                </tr>
              </thead>
              <tbody>
                {comparison.rows.map((r) => (
                  <tr key={r.concept}>
                    <th scope="row">{r.concept}</th>
                    <td>{r.source}</td>
                    <td>{r.target}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="lp-section" id="benefits">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Why teams automate this</div>
            <h2>Benefits of an automated {vendorLabel} to Palo Alto migration</h2>
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

      {checklist && (
        <section className="lp-section" id="checklist">
          <div className="lp-section-inner">
            <div className="lp-section-head">
              <div className="lp-eyebrow">Before you cut over</div>
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
      )}

      <section className="lp-section lp-section-alt" id="faq">
        <div className="lp-section-inner lp-faq-wrap">
          <div className="lp-section-head">
            <div className="lp-eyebrow">FAQ</div>
            <h2>{vendorLabel} to Palo Alto migration — frequently asked questions</h2>
          </div>
          <FaqTiles faq={faq} />
        </div>
      </section>

      <InternalLinks currentKey={key} />

      <section className="lp-cta" id="contact">
        <div className="lp-section-inner lp-cta-inner">
          <h2>{closing.heading}</h2>
          <p>{closing.body}</p>
          <div className="lp-hero-actions" style={{ justifyContent: 'center' }}>
            <button className="btn btn-primary btn-lg" onClick={() => onGetStarted('signup')}>Get started free</button>
            <a className="lp-link" href="mailto:support@example.com">Contact us</a>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-section-inner lp-footer-inner">
          <a href="/" className="lp-brand" style={{ textDecoration: 'none' }}><span className="mark">FC</span>Firewall Config Converter</a>
          <div className="lp-footer-links">
            {ALL_PAGES.map((p) => (
              <a key={p.key} href={p.path}>{p.label} Migration</a>
            ))}
            <a href="#faq">FAQ</a>
            <a href="mailto:support@example.com">Contact</a>
          </div>
          <div className="lp-footer-copy">&copy; {new Date().getFullYear()} Firewall Config Converter. All rights reserved.</div>
        </div>
      </footer>
    </div>
  )
}

export { ALL_PAGES }
