import { useEffect, useState } from 'react'

/**
 * Renders a FAQ list as a grid of clickable tiles. Clicking a tile opens a
 * small modal with the full question and answer, instead of an accordion
 * that only ever shows one long column of text. The underlying `faq` data
 * (array of { q, a }) is unchanged - this only changes how it's presented,
 * so FAQPage structured data (see SeoHead) still reflects the same content.
 */
export default function FaqTiles({ faq }) {
  const [openIdx, setOpenIdx] = useState(null)

  useEffect(() => {
    if (openIdx === null) return
    const onKey = (e) => { if (e.key === 'Escape') setOpenIdx(null) }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [openIdx])

  const active = openIdx !== null ? faq[openIdx] : null

  return (
    <>
      <div className="faq-tile-grid">
        {faq.map((f, i) => (
          <button
            type="button"
            key={f.q}
            className="faq-tile"
            onClick={() => setOpenIdx(i)}
            aria-haspopup="dialog"
          >
            <span className="faq-tile-q">{f.q}</span>
            <span className="faq-tile-hint">Read answer &rarr;</span>
          </button>
        ))}
      </div>

      {active && (
        <div
          className="faq-modal-backdrop"
          onClick={() => setOpenIdx(null)}
        >
          <div
            className="faq-modal"
            role="dialog"
            aria-modal="true"
            aria-label={active.q}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="faq-modal-close"
              onClick={() => setOpenIdx(null)}
              aria-label="Close"
            >
              &#10005;
            </button>
            <div className="faq-modal-eyebrow">FAQ</div>
            <h3>{active.q}</h3>
            <p>{active.a}</p>
          </div>
        </div>
      )}
    </>
  )
}
