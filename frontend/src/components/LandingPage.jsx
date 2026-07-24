import React, { useEffect, useRef, useState } from 'react'
import FaqTiles from './FaqTiles'
import '../styles/landing.css'
import '../styles/seo.css'

const VENDORS = [
  { key: 'fortigate', label: 'FortiGate', line: 'edit firewall policy' },
  { key: 'checkpoint', label: 'Check Point', line: '/config/gateway-rules' },
  { key: 'cisco', label: 'Cisco ASA', line: 'access-list OUTSIDE_IN extended' },
  { key: 'sophos', label: 'Sophos XG', line: '<Firewall><Rule>' },
]

const MIGRATION_PAGES = [
  { key: 'fortigate', label: 'FortiGate', path: '/fortigate-to-palo-alto-migration', blurb: 'FortiOS address objects, VDOMs, and UTM profiles converted to PAN-OS.', footerText: 'FortiGate Migration' },
  { key: 'checkpoint', label: 'Check Point', path: '/checkpoint-to-palo-alto-migration', blurb: 'R80/R81 objects, Access & NAT layers converted to PAN-OS CLI.', footerText: 'Check Point Migration' },
  { key: 'cisco', label: 'Cisco ASA', path: '/cisco-to-palo-alto-migration', blurb: 'Object-groups, access-lists, and both NAT styles converted to PAN-OS.', footerText: 'Cisco ASA Migration' },
  { key: 'sophos', label: 'Sophos XG', path: '/sophos-to-palo-alto-migration', blurb: 'SF-OS hosts, zones, and firewall rules converted to PAN-OS CLI.', footerText: 'Sophos Migration' },
  { key: 'bpa', label: 'BPA Report', path: '/palo-alto-bpa-report-generator', blurb: 'Generate a Palo Alto Best Practice Assessment report, ranked by severity, as Excel.', footerText: 'Palo Alto BPA Report' },
]

const TRANSFORM_STEPS = [
  { from: 'set srcintf "port12"', to: 'from = "ethernet1/2"' },
  { from: 'permit tcp any any eq 443', to: 'application = ["ssl"]' },
  { from: 'action Accept', to: 'action = "allow"' },
]

const FEATURES = [
  {
    title: 'Deterministic parsing',
    body: 'Every object, zone, and rule is parsed against an explicit vendor grammar — not regex guesswork. Same input, same output, every run.',
  },
  {
    title: 'Interface & zone mapping',
    body: 'A guided wizard resolves source-vendor interfaces and zones to PAN-OS equivalents before a single rule is written.',
  },
  {
    title: 'Securely hosted in the cloud',
    body: 'Configs are processed on encrypted, access-controlled infrastructure — parsing, mapping, and generation all happen in your own account, never shared across customers.',
  },
  {
    title: 'Validation before export',
    body: 'Object references, duplicate rules, and unmapped zones are flagged before you commit to a PAN-OS config.',
  },
  {
    title: 'Editable at every step',
    body: 'Review and adjust addresses, services, and policies in an editable grid before final export — nothing is a black box.',
  },
  {
    title: 'Job history, not one-shot scripts',
    body: 'Every conversion is saved as a resumable job, so a large migration can be paused, reviewed, and picked back up.',
  },
]

const STEPS = [
  { n: '01', title: 'Upload a config', body: 'Drop in a FortiGate, Check Point, Cisco ASA, or Sophos XG export.' },
  { n: '02', title: 'Map interfaces & zones', body: 'Resolve source-vendor interfaces to PAN-OS zones and interfaces.' },
  { n: '03', title: 'Review the summary', body: 'Check object and rule counts, then fix anything flagged by validation.' },
  { n: '04', title: 'Export PAN-OS config', body: 'Download a ready-to-load Palo Alto configuration set.' },
]

const FAQ = [
  {
    q: 'Which vendors are supported?',
    a: 'FortiGate, Check Point, Cisco ASA, and Sophos XG configurations can be converted to Palo Alto Networks PAN-OS format today.',
  },
  {
    q: 'Does my configuration get uploaded anywhere?',
    a: 'Your configuration is uploaded securely over an encrypted connection and processed in your own account on our cloud infrastructure. It is never shared with other customers or sent to a third party.',
  },
  {
    q: 'What happens to rules that reference something the wizard can\'t map?',
    a: 'The validation step flags unmapped interfaces, zones, and object references before export, so you can resolve them instead of discovering it after import.',
  },
  {
    q: 'Can I stop partway through a large migration?',
    a: 'Yes. Every conversion is saved as a job — close the tab and resume from job history whenever you\'re ready.',
  },
  {
    q: 'Does the tool generate Palo Alto CLI I can load directly?',
    a: 'Yes. Output is standard PAN-OS `set` command syntax in dependency order, ready to paste into the CLI, load through Panorama, or apply via your existing configuration-management pipeline.',
  },
  {
    q: 'How are interface and zone names resolved between vendors?',
    a: 'A guided mapping wizard lets you explicitly resolve each source-vendor interface and zone to its Palo Alto equivalent before any policy is translated — nothing is guessed from name similarity alone.',
  },
  {
    q: 'What happens if my configuration has objects that reference something missing?',
    a: 'The validation pass flags missing referenced objects, duplicate objects, and empty groups per tab with error counts, so you can resolve them before exporting instead of discovering the gap after import.',
  },
  {
    q: 'Is there a free plan?',
    a: 'Yes, the Starter plan is free and covers a single migration or proof of concept, with a limited number of jobs per month across all four supported source vendors.',
  },
]

function TypedDiff() {
  const [visible, setVisible] = useState(0)
  useEffect(() => {
    if (visible >= TRANSFORM_STEPS.length) return
    const t = setTimeout(() => setVisible((v) => v + 1), 700)
    return () => clearTimeout(t)
  }, [visible])
  return (
    <div className="lp-diff" role="img" aria-label="Example configuration line rewritten from source vendor syntax to PAN-OS syntax">
      {TRANSFORM_STEPS.map((s, i) => (
        <div key={i} className={`lp-diff-row ${i < visible ? 'is-in' : ''}`}>
          <span className="lp-diff-from">{s.from}</span>
          <span className="lp-diff-arrow">&rarr;</span>
          <span className="lp-diff-to">{s.to}</span>
        </div>
      ))}
    </div>
  )
}

const SAMPLE_CONVERSIONS = [
  {
    vendor: 'FortiGate',
    rows: [
      { type: 'Address', source: 'edit "SRV-WEB-01" / subnet 10.10.10.5/32', target: 'address SRV-WEB-01 = 10.10.10.5/32' },
      { type: 'Service', source: 'edit "HTTPS" / tcp-portrange 443', target: 'service HTTPS = tcp/443' },
      { type: 'Policy', source: 'set action accept / set service HTTPS', target: 'action = allow, application = ssl' },
      { type: 'Interface', source: 'set srcintf "port12"', target: 'zone = Trust, interface ethernet1/2' },
    ],
  },
  {
    vendor: 'Cisco ASA',
    rows: [
      { type: 'Object', source: 'object network SRV-WEB-01 / host 10.10.10.5', target: 'address SRV-WEB-01 = 10.10.10.5/32' },
      { type: 'Access List', source: 'access-list OUTSIDE_IN extended permit tcp any any eq 443', target: 'rule: any → any, service HTTPS, action allow' },
      { type: 'NAT', source: 'nat (inside,outside) source static SRV-WEB-01 SRV-WEB-01', target: 'source-translation static-ip 10.10.10.5' },
      { type: 'Interface', source: 'nameif outside', target: 'zone = Untrust, interface ethernet1/1' },
    ],
  },
  {
    vendor: 'Check Point',
    rows: [
      { type: 'Host Object', source: '/config/gateway-rules host SRV-WEB-01', target: 'address SRV-WEB-01 = 10.10.10.5/32' },
      { type: 'Service', source: 'service-tcp HTTPS port 443', target: 'service HTTPS = tcp/443' },
      { type: 'Rule', source: 'action Accept / track Log', target: 'action = allow, log-end = yes' },
      { type: 'Zone', source: 'interface eth0 topology internal', target: 'zone = Trust, interface ethernet1/1' },
    ],
  },
  {
    vendor: 'Sophos XG',
    rows: [
      { type: 'Address', source: '<Host><Name>SRV-WEB-01</Name><IP>10.10.10.5</IP>', target: 'address SRV-WEB-01 = 10.10.10.5/32' },
      { type: 'Service', source: '<Service><Name>HTTPS</Name><Port>443</Port>', target: 'service HTTPS = tcp/443' },
      { type: 'Rule', source: '<Firewall><Rule><Action>Accept</Action>', target: 'action = allow' },
      { type: 'Zone', source: '<Zone>LAN</Zone>', target: 'zone = Trust' },
    ],
  },
]

function LiveConverterDemo() {
  const [setIdx, setSetIdx] = useState(0)
  const [visible, setVisible] = useState(0)
  const rows = SAMPLE_CONVERSIONS[setIdx].rows

  useEffect(() => {
    if (visible < rows.length) {
      const t = setTimeout(() => setVisible((v) => v + 1), 650)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => {
      setVisible(0)
      setSetIdx((i) => {
        let next = Math.floor(Math.random() * SAMPLE_CONVERSIONS.length)
        if (next === i) next = (next + 1) % SAMPLE_CONVERSIONS.length
        return next
      })
    }, 2600)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, setIdx])

  return (
    <div className="lp-screenshot-frame">
      <div className="lp-screenshot-bar">
        <span className="dot" /><span className="dot" /><span className="dot" />
        <span className="lp-terminal-title" style={{ marginLeft: 8 }}>
          {SAMPLE_CONVERSIONS[setIdx].vendor} &rarr; PAN-OS &middot; live sample
        </span>
      </div>
      <div className="lp-demo-table">
        <div className="lp-demo-row lp-demo-head">
          <span>Object</span>
          <span>Source config</span>
          <span>Palo Alto PAN-OS</span>
        </div>
        {rows.map((r, i) => (
          <div className={`lp-demo-row ${i < visible ? 'is-in' : ''}`} key={r.type}>
            <span className="lp-demo-type">{r.type}</span>
            <span className="lp-demo-src">{r.source}</span>
            <span className="lp-demo-target">{i < visible ? r.target : ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function FeatureSlider() {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % FEATURES.length), 3800)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="lp-slider">
      <div className="lp-slider-track" style={{ transform: `translateX(-${idx * 100}%)` }}>
        {FEATURES.map((f) => (
          <div className="lp-slide" key={f.title}>
            <div className="lp-slide-inner">
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="lp-slider-dots">
        {FEATURES.map((f, i) => (
          <button
            key={f.title}
            type="button"
            className={`lp-slider-dot ${i === idx ? 'is-active' : ''}`}
            onClick={() => setIdx(i)}
            aria-label={`Show feature ${i + 1}`}
          />
        ))}
      </div>
    </div>
  )
}

export default function LandingPage({ onGetStarted, loggedIn = false }) {
  const [vendorIdx, setVendorIdx] = useState(0)
  const rotRef = useRef(null)

  useEffect(() => {
    rotRef.current = setInterval(() => setVendorIdx((i) => (i + 1) % VENDORS.length), 2400)
    return () => clearInterval(rotRef.current)
  }, [])

  return (
    <div className="lp-root" data-theme="light">
      <header className="lp-nav">
        <div className="lp-nav-inner">
          <div className="lp-brand">
            <span className="mark">FC</span>
            Firewall Config Converter
          </div>
          <nav className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="lp-nav-cta">
            {loggedIn ? (
              <button className="btn btn-primary" onClick={() => onGetStarted('open')}>Open App</button>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={() => onGetStarted('login')}>Log in</button>
                <button className="btn btn-primary" onClick={() => onGetStarted('signup')}>Get started</button>
              </>
            )}
          </div>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <div className="lp-eyebrow">Cloud-hosted &middot; Deterministic &middot; Secure</div>
            <h1>
              Migrate firewall rules to PAN-OS<br />without rewriting them by hand.
            </h1>
            <p className="lp-sub">
              Convert FortiGate, Check Point, Cisco ASA, and Sophos XG configurations into
              Palo Alto Networks policy sets — parsed deterministically, mapped through a
              guided wizard, and validated before you export a single rule.
            </p>
            <div className="lp-hero-actions">
              <button className="btn btn-primary btn-lg" onClick={() => onGetStarted(loggedIn ? 'open' : 'signup')}>
                {loggedIn ? 'Open App' : 'Get started free'}
              </button>
              <a className="lp-link" href="#how-it-works">See how it works &darr;</a>
            </div>
            <div className="lp-vendor-row">
              <span className="lp-vendor-label">Reads</span>
              {VENDORS.map((v, i) => (
                <span key={v.key} className={`lp-vendor-chip ${i === vendorIdx ? 'is-active' : ''}`}>{v.label}</span>
              ))}
              <span className="lp-vendor-arrow">&rarr;</span>
              <span className="lp-vendor-chip lp-vendor-chip-target">Palo Alto PAN-OS</span>
            </div>
          </div>
          <div className="lp-hero-visual">
            <div className="lp-terminal">
              <div className="lp-terminal-bar">
                <span className="dot" /><span className="dot" /><span className="dot" />
                <span className="lp-terminal-title">{VENDORS[vendorIdx].label} &rarr; PAN-OS</span>
              </div>
              <div className="lp-terminal-body">
                <div className="lp-terminal-src">{VENDORS[vendorIdx].line}</div>
                <TypedDiff />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section lp-guides-top" id="migration-guides">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Pick your source firewall — or assess what you already have</div>
            <h2>More tools to get (and keep) Palo Alto right</h2>
          </div>
          <div className="seo-related-grid">
            {MIGRATION_PAGES.map((p) => (
              <a key={p.key} className="seo-related-card" href={p.path}>
                <span className="seo-related-vendor">{p.label} &rarr; Palo Alto</span>
                <p style={{ margin: 0, fontSize: 13.5, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{p.blurb}</p>
                <span className="lp-link">Read the guide &rarr;</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section" id="features">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Features</div>
            <h2>Built for people who read rule tables for a living</h2>
          </div>
          <div className="lp-feature-grid">
            {FEATURES.map((f) => (
              <div className="lp-feature-card" key={f.title}>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="how-it-works">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">How it works</div>
            <h2>Four steps from legacy config to PAN-OS export</h2>
          </div>
          <div className="lp-steps">
            {STEPS.map((s) => (
              <div className="lp-step" key={s.n}>
                <div className="lp-step-n">{s.n}</div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section" id="screenshot">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Inside a job</div>
            <h2>Review every object before it becomes policy</h2>
          </div>
          <LiveConverterDemo />
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="tour">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-eyebrow">Take a tour</div>
            <h2>Everything the tool handles for you</h2>
          </div>
          <FeatureSlider />
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="benefits">
        <div className="lp-section-inner">
          <div className="lp-benefits">
            <div className="lp-benefit">
              <div className="lp-benefit-stat">0</div>
              <div className="lp-benefit-label">configs shared with other customers</div>
            </div>
            <div className="lp-benefit">
              <div className="lp-benefit-stat">4</div>
              <div className="lp-benefit-label">source vendors supported</div>
            </div>
            <div className="lp-benefit">
              <div className="lp-benefit-stat">1</div>
              <div className="lp-benefit-label">validation pass before export</div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section" id="pricing">
        <div className="lp-section-inner lp-pricing-wrap">
          <div className="lp-section-head lp-section-head-center">
            <div className="lp-eyebrow">Pricing</div>
            <h2>Simple plans for one-off migrations and ongoing work</h2>
          </div>
          <div className="lp-pricing-grid">
            <div className="lp-price-card">
              <h3>Starter</h3>
              <div className="lp-price">Free</div>
              <p>For a single migration or a proof of concept.</p>
              <ul>
                <li>Limited jobs per month</li>
                <li>All four source vendors</li>
                <li>Full validation &amp; export</li>
              </ul>
              <button className="btn btn-secondary" onClick={() => onGetStarted(loggedIn ? 'open' : 'signup')}>{loggedIn ? 'Open App' : 'Get started'}</button>
            </div>
            <div className="lp-price-card lp-price-card-highlight">
              <h3>Team</h3>
              <div className="lp-price">Contact us</div>
              <p>For engineers running ongoing migrations across multiple sites.</p>
              <ul>
                <li>Higher job limits</li>
                <li>Job history &amp; resumable migrations</li>
                <li>Priority support</li>
              </ul>
              <button className="btn btn-primary" onClick={() => onGetStarted(loggedIn ? 'open' : 'signup')}>{loggedIn ? 'Open App' : 'Get started'}</button>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="faq">
        <div className="lp-section-inner lp-faq-wrap">
          <div className="lp-section-head">
            <div className="lp-eyebrow">FAQ</div>
            <h2>Questions we get from network teams</h2>
          </div>
          <FaqTiles faq={FAQ} />
        </div>
      </section>

      <section className="lp-cta" id="contact">
        <div className="lp-section-inner lp-cta-inner">
          <h2>Ready to stop rewriting rules by hand?</h2>
          <p>Upload a config and see your first converted policy set in minutes.</p>
          <div className="lp-hero-actions" style={{ justifyContent: 'center' }}>
            <button className="btn btn-primary btn-lg" onClick={() => onGetStarted(loggedIn ? 'open' : 'signup')}>
              {loggedIn ? 'Open App' : 'Get started free'}
            </button>
            <a className="lp-link" href="mailto:support@example.com">Contact us</a>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-section-inner lp-footer-inner">
          <div className="lp-brand"><span className="mark">FC</span>Firewall Config Converter</div>
          <div className="lp-footer-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
            {MIGRATION_PAGES.map((p) => (
              <a key={p.key} href={p.path}>{p.footerText}</a>
            ))}
            <a href="mailto:support@example.com">Contact</a>
          </div>
          <div className="lp-footer-copy">&copy; {new Date().getFullYear()} Firewall Config Converter. All rights reserved.</div>
        </div>
      </footer>
    </div>
  )
}
