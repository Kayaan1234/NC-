import { useEffect, useRef, useState } from 'react'

/**
 * A small MLP that trains forever in a loop:
 *   forward pass  — cyan activations flow input -> output
 *   loss computed — output layer flashes
 *   backward pass — amber gradients flow output -> input
 *   step          — edges pulse (weights updated), loss ticks down, repeat
 *
 * Pure canvas + requestAnimationFrame. The rAF handle is cancelled on unmount.
 */

const LAYERS = [4, 6, 5, 3] // node counts per column
const LAYER_LABELS = ['input', 'hidden', 'hidden', 'output']

// Phase timings (ms)
const FORWARD = 1500
const LOSS = 450
const BACKWARD = 1500
const STEP = 550
const CYCLE = FORWARD + LOSS + BACKWARD + STEP

const COLOR_FWD = '#2de2e6'
const COLOR_BWD = '#ff9f45'
const COLOR_IDLE = 'rgba(120, 160, 255, 0.18)'
const COLOR_NODE_IDLE = 'rgba(123, 140, 255, 0.35)'

interface Node {
  x: number
  y: number
  layer: number
}

function buildNodes(w: number, h: number): Node[] {
  const nodes: Node[] = []
  const padX = w * 0.12
  const usableW = w - padX * 2
  LAYERS.forEach((count, layer) => {
    const x = padX + (usableW * layer) / (LAYERS.length - 1)
    const padY = h * 0.14
    const usableH = h - padY * 2
    for (let i = 0; i < count; i++) {
      const y = count === 1 ? h / 2 : padY + (usableH * i) / (count - 1)
      nodes.push({ x, y, layer })
    }
  })
  return nodes
}

function gauss(d: number, sigma: number) {
  return Math.exp(-(d * d) / (2 * sigma * sigma))
}

export default function NeuralNetAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [phaseLabel, setPhaseLabel] = useState('forward pass')
  const [epoch, setEpoch] = useState(1)
  const lossRef = useRef(1.84)
  const [loss, setLoss] = useState(lossRef.current)

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let nodes: Node[] = []
    let W = 0
    let H = 0
    let dpr = Math.min(window.devicePixelRatio || 1, 2)

    function resize() {
      const rect = wrap!.getBoundingClientRect()
      W = rect.width
      H = rect.height
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas!.width = Math.round(W * dpr)
      canvas!.height = Math.round(H * dpr)
      canvas!.style.width = `${W}px`
      canvas!.style.height = `${H}px`
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      nodes = buildNodes(W, H)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(wrap)

    let raf = 0
    let start = performance.now()
    let lastEpoch = -1
    let lastLabel = ''

    // edges grouped by the gap they cross (layer L -> L+1)
    const layerOffsets: number[] = []
    let acc = 0
    for (const c of LAYERS) {
      layerOffsets.push(acc)
      acc += c
    }

    function draw(now: number) {
      const elapsed = (now - start) % CYCLE
      const cycleIndex = Math.floor((now - start) / CYCLE)

      // Determine phase + a 0..1 progress within it, and the wavefront column.
      let phase: 'forward' | 'loss' | 'backward' | 'step'
      let front = 0 // position along the layer axis [0 .. LAYERS.length-1]
      let label = 'forward pass'
      if (elapsed < FORWARD) {
        phase = 'forward'
        const p = elapsed / FORWARD
        front = p * (LAYERS.length - 1)
        label = 'forward pass'
      } else if (elapsed < FORWARD + LOSS) {
        phase = 'loss'
        front = LAYERS.length - 1
        label = 'compute loss'
      } else if (elapsed < FORWARD + LOSS + BACKWARD) {
        phase = 'backward'
        const p = (elapsed - FORWARD - LOSS) / BACKWARD
        front = (LAYERS.length - 1) * (1 - p)
        label = 'backward pass'
      } else {
        phase = 'step'
        front = 0
        label = 'update weights'
      }

      const color = phase === 'backward' || phase === 'step' ? COLOR_BWD : COLOR_FWD

      // React state updates (throttled to real changes)
      if (label !== lastLabel) {
        lastLabel = label
        setPhaseLabel(label)
      }
      if (cycleIndex !== lastEpoch) {
        lastEpoch = cycleIndex
        // loss decays toward a floor with a little noise — "training"
        lossRef.current = Math.max(0.04, lossRef.current * 0.93 - 0.002 + (Math.random() - 0.5) * 0.01)
        setLoss(lossRef.current)
        setEpoch(cycleIndex + 1)
      }

      ctx!.clearRect(0, 0, W, H)

      // --- edges ---
      for (let L = 0; L < LAYERS.length - 1; L++) {
        const fromStart = layerOffsets[L]
        const toStart = layerOffsets[L + 1]
        const fromCount = LAYERS[L]
        const toCount = LAYERS[L + 1]

        // how "lit" is this gap right now (wavefront proximity)
        const gapCenter = L + 0.5
        const proximity = phase === 'step' ? 0.6 : gauss(front - gapCenter, 0.55)
        const local = Math.max(0, Math.min(1, front - L)) // 0..1 across this gap

        for (let a = 0; a < fromCount; a++) {
          for (let b = 0; b < toCount; b++) {
            const n1 = nodes[fromStart + a]
            const n2 = nodes[toStart + b]

            ctx!.beginPath()
            ctx!.moveTo(n1.x, n1.y)
            ctx!.lineTo(n2.x, n2.y)
            ctx!.strokeStyle = COLOR_IDLE
            ctx!.lineWidth = 1
            ctx!.stroke()

            if (proximity > 0.02 && phase !== 'loss') {
              ctx!.beginPath()
              ctx!.moveTo(n1.x, n1.y)
              ctx!.lineTo(n2.x, n2.y)
              ctx!.strokeStyle = withAlpha(color, 0.12 + proximity * 0.55)
              ctx!.lineWidth = 1 + proximity * 1.4
              ctx!.stroke()
            }

            // travelling signal particle on active gaps
            if (proximity > 0.15 && phase !== 'loss' && phase !== 'step') {
              // `local` is the wavefront position across this gap. Forward: it
              // rises 0->1 so the dot moves n1->n2 (left->right). Backward: the
              // wavefront recedes, so `local` already falls 1->0 and the dot
              // moves n2->n1 (right->left). Use `local` directly for both —
              // negating it would cancel the recede and wrongly run left->right.
              const t = local
              const px = n1.x + (n2.x - n1.x) * t
              const py = n1.y + (n2.y - n1.y) * t
              const r = 1.6 + proximity * 2.2
              const glow = ctx!.createRadialGradient(px, py, 0, px, py, r * 3)
              glow.addColorStop(0, withAlpha(color, 0.9))
              glow.addColorStop(1, withAlpha(color, 0))
              ctx!.fillStyle = glow
              ctx!.beginPath()
              ctx!.arc(px, py, r * 3, 0, Math.PI * 2)
              ctx!.fill()
            }
          }
        }
      }

      // --- nodes ---
      nodes.forEach((n) => {
        let activation = gauss(front - n.layer, 0.5)
        if (phase === 'loss' && n.layer === LAYERS.length - 1) {
          // output flash while loss is computed
          activation = 0.6 + 0.4 * Math.abs(Math.sin(now / 90))
        }
        if (phase === 'step') activation *= 0.3

        const baseR = 7
        // halo
        if (activation > 0.05) {
          const haloR = baseR + activation * 16
          const g = ctx!.createRadialGradient(n.x, n.y, 0, n.x, n.y, haloR)
          g.addColorStop(0, withAlpha(color, 0.45 * activation))
          g.addColorStop(1, withAlpha(color, 0))
          ctx!.fillStyle = g
          ctx!.beginPath()
          ctx!.arc(n.x, n.y, haloR, 0, Math.PI * 2)
          ctx!.fill()
        }
        // core
        ctx!.beginPath()
        ctx!.arc(n.x, n.y, baseR, 0, Math.PI * 2)
        ctx!.fillStyle = '#0a1024'
        ctx!.fill()
        ctx!.lineWidth = 2
        ctx!.strokeStyle = activation > 0.05 ? withAlpha(color, 0.4 + 0.6 * activation) : COLOR_NODE_IDLE
        ctx!.stroke()
        // inner dot
        ctx!.beginPath()
        ctx!.arc(n.x, n.y, 2.4, 0, Math.PI * 2)
        ctx!.fillStyle = activation > 0.05 ? color : COLOR_NODE_IDLE
        ctx!.fill()
      })

      // --- layer captions ---
      ctx!.font = '11px ui-monospace, monospace'
      ctx!.textAlign = 'center'
      LAYERS.forEach((_, L) => {
        const n = nodes[layerOffsets[L]]
        ctx!.fillStyle = 'rgba(151, 163, 199, 0.55)'
        ctx!.fillText(LAYER_LABELS[L], n.x, H - 10)
      })

      if (!reduced) raf = requestAnimationFrame(draw)
    }

    if (reduced) {
      // Static representative frame.
      start = performance.now() - FORWARD * 0.5
      draw(performance.now())
    } else {
      raf = requestAnimationFrame(draw)
    }

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [])

  return (
    <div ref={wrapRef} className="nn-anim">
      <canvas ref={canvasRef} />
      <div className="nn-hud">
        <span className="nn-hud-phase">
          <span
            className="nn-dot"
            style={{
              background:
                phaseLabel === 'backward pass' || phaseLabel === 'update weights'
                  ? 'var(--backward)'
                  : 'var(--forward)',
            }}
          />
          {phaseLabel}
        </span>
        <span>epoch {epoch}</span>
        <span>loss {loss.toFixed(3)}</span>
      </div>
    </div>
  )
}

function withAlpha(hex: string, a: number): string {
  // hex like #2de2e6
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}
