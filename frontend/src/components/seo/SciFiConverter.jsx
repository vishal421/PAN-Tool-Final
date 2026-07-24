import { useEffect, useMemo, useState } from 'react'

const STAGES = ['Parsing source config', 'Resolving zones & interfaces', 'Validating object references', 'Generating PAN-OS CLI']

/**
 * A purely cosmetic, self-running "sci-fi" preview of the conversion engine.
 * It cycles through the vendor's sample rules and a fake pipeline of stage
 * labels + a progress bar. Nothing here calls the real API — it's a visual
 * hook for the landing page, not the actual product (see Workbench.jsx /
 * ExportCenter.jsx for the real conversion flow).
 */
export default function SciFiConverter({ vendorLabel, samples }) {
  const [sampleIdx, setSampleIdx] = useState(0)
  const [stageIdx, setStageIdx] = useState(0)
  const [progress, setProgress] = useState(0)
  const [lines, setLines] = useState([])

  const sample = samples[sampleIdx % samples.length]

  useEffect(() => {
    setLines([])
    setStageIdx(0)
    setProgress(0)
  }, [sampleIdx])

  useEffect(() => {
    const tick = setInterval(() => {
      setProgress((p) => {
        const next = p + 4
        if (next >= 100) {
          return 100
        }
        return next
      })
    }, 90)
    return () => clearInterval(tick)
  }, [sampleIdx])

  useEffect(() => {
    const stageEvery = 100 / STAGES.length
    setStageIdx(Math.min(STAGES.length - 1, Math.floor(progress / stageEvery)))
  }, [progress])

  useEffect(() => {
    if (progress < 40) return
    const revealCount = Math.min(sample.out.length, Math.ceil(((progress - 40) / 60) * sample.out.length))
    setLines(sample.out.slice(0, revealCount))
  }, [progress, sample])

  useEffect(() => {
    if (progress < 100) return
    const t = setTimeout(() => setSampleIdx((i) => (i + 1) % samples.length), 1600)
    return () => clearTimeout(t)
  }, [progress, samples.length])

  const stageLabel = STAGES[stageIdx]

  const scanlineStyle = useMemo(() => ({ animationDuration: '3.2s' }), [])

  return (
    <div className="sf-console" role="img" aria-label={`Animated preview of ${vendorLabel} configuration being converted to Palo Alto PAN-OS CLI`}>
      <div className="sf-console-glow" />
      <div className="sf-console-scanline" style={scanlineStyle} />
      <div className="sf-console-head">
        <div className="sf-console-dots"><span /><span /><span /></div>
        <div className="sf-console-title">MIGRATION-ENGINE // {vendorLabel.toUpperCase()} &rarr; PAN-OS</div>
        <div className="sf-console-status"><span className="sf-pulse" />LIVE PREVIEW</div>
      </div>

      <div className="sf-console-body">
        <div className="sf-console-col">
          <div className="sf-console-label">SOURCE // {vendorLabel}</div>
          <pre className="sf-console-src">{sample.in}</pre>
        </div>
        <div className="sf-console-arrow">
          <div className="sf-arrow-track">
            <div className="sf-arrow-fill" style={{ width: `${progress}%` }} />
          </div>
          <span>&#9656;</span>
        </div>
        <div className="sf-console-col">
          <div className="sf-console-label">OUTPUT // PAN-OS CLI</div>
          <pre className="sf-console-out">
            {lines.length ? lines.join('\n') : <span className="sf-dim">awaiting stage...</span>}
          </pre>
        </div>
      </div>

      <div className="sf-console-footer">
        <div className="sf-stage-label">{stageLabel}</div>
        <div className="sf-progress-track">
          <div className="sf-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="sf-stage-count">{Math.min(100, progress)}%</div>
      </div>
      <div className="sf-console-note">Illustrative preview using sample data — not connected to your live configuration.</div>
    </div>
  )
}
