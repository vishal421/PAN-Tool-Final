import { useEffect } from 'react'

const SITE_NAME = 'Firewall Config Converter'
// Was hardcoded to a domain this product doesn't own (firewallconfigconverter.com,
// with a www the site doesn't use), while sitemap.xml correctly points at
// pan-tool.com - every canonical/OG/Twitter/breadcrumb tag was telling
// crawlers the real page lives elsewhere. VITE_ROOT_DOMAIN is already set
// for the subdomain routing (login./signup./dash.<domain>), so reuse it
// here instead of a second hardcoded value that can drift out of sync.
const SITE_URL = `https://${import.meta.env.VITE_ROOT_DOMAIN || 'pan-tool.com'}`

function upsertMeta(attr, key, content) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
  return el
}

function upsertLink(rel, href) {
  let el = document.head.querySelector(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
  return el
}

function upsertJsonLd(id, data) {
  let el = document.getElementById(id)
  if (!el) {
    el = document.createElement('script')
    el.type = 'application/ld+json'
    el.id = id
    document.head.appendChild(el)
  }
  el.textContent = JSON.stringify(data)
  return el
}

/**
 * Manages <head> tags for a single SEO landing page: title, meta description,
 * canonical URL, Open Graph, Twitter Card, and JSON-LD (BreadcrumbList + FAQPage).
 *
 * NOTE: this app is a client-rendered SPA (no SSR/prerendering). Tags are
 * injected on mount via the DOM. Modern crawlers (Googlebot) execute JS and
 * will pick these up, but for maximum SEO reliability a prerendering step
 * (e.g. vite-plugin-ssr, Prerender.io, or a static build per route) is
 * recommended as a follow-up — this covers the in-app requirement without
 * requiring a build pipeline change.
 */
export default function SeoHead({ title, description, path, ogImage, breadcrumbs, faq }) {
  useEffect(() => {
    const prevTitle = document.title
    document.title = title
    upsertMeta('name', 'description', description)
    upsertMeta('property', 'og:title', title)
    upsertMeta('property', 'og:description', description)
    upsertMeta('property', 'og:type', 'website')
    upsertMeta('property', 'og:site_name', SITE_NAME)
    upsertMeta('property', 'og:url', `${SITE_URL}${path}`)
    if (ogImage) upsertMeta('property', 'og:image', `${SITE_URL}${ogImage}`)
    upsertMeta('name', 'twitter:card', 'summary_large_image')
    upsertMeta('name', 'twitter:title', title)
    upsertMeta('name', 'twitter:description', description)
    if (ogImage) upsertMeta('name', 'twitter:image', `${SITE_URL}${ogImage}`)
    upsertLink('canonical', `${SITE_URL}${path}`)

    if (breadcrumbs?.length) {
      upsertJsonLd('ld-breadcrumb', {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: breadcrumbs.map((b, i) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: b.name,
          item: `${SITE_URL}${b.path}`,
        })),
      })
    }

    if (faq?.length) {
      upsertJsonLd('ld-faq', {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: faq.map((f) => ({
          '@type': 'Question',
          name: f.q,
          acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
      })
    }

    return () => {
      // Restore a neutral title when navigating away; other tags are
      // overwritten by whichever page mounts next (or the app shell).
      document.title = prevTitle
      const bc = document.getElementById('ld-breadcrumb')
      const fq = document.getElementById('ld-faq')
      if (bc) bc.remove()
      if (fq) fq.remove()
    }
  }, [title, description, path, ogImage, breadcrumbs, faq])

  return null
}

export { SITE_URL, SITE_NAME }
