import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { NarrationProvider } from './Beat'
import CodePanel from './CodePanel'
import Transport from './Transport'
import { useTimeline } from './useTimeline'
import { chapterAt, chapterStart, sceneAt, totalDuration } from '../../content/walkthrough/timeline'
import { draws } from '../../content/walkthrough/types'
import type { WalkthroughContent } from '../../content/types'
import type { NarrationMode } from '../../content/walkthrough/types'

// A walkthrough learn flow: one continuous timeline instead of a stack of pages.
//
// The rail is still the rail, but its entries SEEK rather than navigate. That is the
// whole difference between this and the page-based flow: there is one document and
// one clock, and a chapter is a timestamp in it. Old /learn/:slug links still work,
// because the chapter slugs are the slugs those pages had; arriving on one starts
// the walkthrough at that chapter.
//
// Two views of the same content, never two copies of it:
//   PLAY  renders the active beat beside the stage and the code panel.
//   TEXT  renders every beat in order, each with its own picture and code.
// Both read the same compiled narration MDX and the same scene manifest, so nothing
// can be in one and missing from the other.
//
// Reduced motion starts in TEXT. The house rule is that reduced motion renders the
// finished state rather than a faster animation, and for a timeline this long the
// finished state is the whole thing written down.
//
// Nothing in here names a model. Everything model-specific arrives on `content`:
// the scenes, the narration, the source bundle, and the Stage component that turns
// a stage into a picture.

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export default function Walkthrough({
  modelId,
  content,
  chapterSlug,
}: {
  modelId: string
  content: WalkthroughContent
  chapterSlug?: string
}) {
  // Stage comes from the content, not from an import: it is the model's own mapping
  // from its stage vocabulary to its diagrams. See walkthrough() in content/types.ts.
  const { chapters, scenes, Narration, Stage, sources, epilogue } = content
  const navigate = useNavigate()
  const playerRef = useRef<HTMLDivElement>(null)

  const total = useMemo(() => totalDuration(scenes), [scenes])
  const { t, playing, rate, toggle, seek, setRate, play } = useTimeline(total)

  // Read the preference once, at mount, the way NeuronDemo.tsx does: what is being
  // suppressed is a timer rather than a declaration, so it belongs in JS and not in
  // a media query.
  const [mode, setMode] = useState<NarrationMode>(() => (prefersReducedMotion() ? 'text' : 'play'))

  // A /learn/:slug link is a deep link into the timeline. Runs on slug changes only:
  // seeking here on every render would fight the reader's own scrubbing.
  useEffect(() => {
    if (!chapterSlug) return
    const known = chapters.some((c) => c.slug === chapterSlug)
    if (known) seek(chapterStart(scenes, chapterSlug))
  }, [chapterSlug, chapters, scenes, seek])

  const { scene, index, progress } = sceneAt(scenes, t)
  const currentChapter = chapterAt(scenes, t)

  // A scene with no stage of its own HOLDS the last picture rather than blanking.
  // Nine of the beats are pure maths or pure code, and clearing the stage for those
  // left a tall empty box above the transport; collapsing it instead would shift
  // the whole page mid-sentence. Holding is also the better reading: the loss curve
  // staying up while its gradient is derived is exactly what you would leave on a
  // whiteboard. A held stage renders finished, never mid-animation.
  const held = useMemo(() => {
    if (draws(scene.stage)) return { stage: scene.stage, progress }
    for (let i = index - 1; i >= 0; i--) {
      if (draws(scenes[i].stage)) return { stage: scenes[i].stage, progress: 1 }
    }
    return null
  }, [scene, index, progress, scenes])

  const seekChapter = useCallback(
    (slug: string) => {
      seek(chapterStart(scenes, slug))
      // replace, not push: a reader clicking through four chapters should not have
      // to press Back four times to leave the page.
      navigate(`/training/${modelId}/learn/${slug}`, { replace: true })
      if (!playing) play()
    },
    [scenes, seek, navigate, modelId, playing, play],
  )

  function onKeyDown(e: React.KeyboardEvent) {
    // Only when focus is inside the player, so these never hijack the page. The
    // range input handles its own arrow keys, so leave it alone when it has focus.
    const onRange = (e.target as HTMLElement).tagName === 'INPUT'
    if (e.key === ' ' || e.key === 'k') {
      e.preventDefault()
      toggle()
    } else if (e.key === 'ArrowLeft' && !onRange) {
      e.preventDefault()
      seek(t - 5)
    } else if (e.key === 'ArrowRight' && !onRange) {
      e.preventDefault()
      seek(t + 5)
    }
  }

  // In the text view each beat carries its own picture and code, which live in the
  // manifest rather than in the MDX. The Beat asks for them by id.
  const extrasFor = useCallback(
    (id: string) => {
      const i = scenes.findIndex((x) => x.id === id)
      if (i === -1) return null
      const s = scenes[i]

      // A run of consecutive beats sharing a stage draws it ONCE, after the last of
      // them, in its most complete state. Playing, the seven overview beats build a
      // neuron a piece at a time and that progression is the point; read as a
      // document it would be seven nearly identical pictures down the page. So the
      // text view shows the finished figure where the run ends, which is also where
      // the prose has finished describing it.
      const next = scenes[i + 1]
      const endsRun = !next || next.stage.kind !== s.stage.kind

      return (
        <>
          {draws(s.stage) && endsRun && (
            <div className="walkthrough__stage walkthrough__stage--static figure-surface">
              <Stage stage={s.stage} progress={1} />
            </div>
          )}
          {s.code && sources && <CodePanel code={s.code} sources={sources} />}
        </>
      )
    },
    [scenes, sources, Stage],
  )

  return (
    <div className="learn-grid">
      <nav className="learn-rail" aria-label="Chapters">
        <Link to="/training" className="learn-rail__back">
          &larr; All models
        </Link>
        <div className="learn-rail__model">{content.name}</div>
        <div className="learn-rail__count">
          {mode === 'play' ? 'Walkthrough' : 'Full text'}
        </div>

        <div className="learn-rail__list">
          {chapters.map((c) => (
            <button
              key={c.slug}
              type="button"
              className={
                mode === 'play' && c.slug === currentChapter
                  ? 'learn-rail__item learn-rail__item--current'
                  : 'learn-rail__item'
              }
              aria-current={mode === 'play' && c.slug === currentChapter ? 'true' : undefined}
              onClick={() => {
                if (mode === 'text') setMode('play')
                seekChapter(c.slug)
              }}
            >
              {c.title}
            </button>
          ))}
          {/* A Link, not a seek button: this one leaves the timeline rather than
              moving inside it, and it should feel like a different kind of step. */}
          {epilogue && (
            <Link
              to={`/training/${modelId}/learn/${epilogue.slug}`}
              className="learn-rail__item learn-rail__item--after"
            >
              {epilogue.title}
            </Link>
          )}
        </div>

        <div className="learn-rail__foot">
          <Link to={`/training/${modelId}/bridge`}>Find a dataset &rarr;</Link>
          <Link to={`/training/${modelId}`}>Start training &rarr;</Link>
        </div>
      </nav>

      <div className="learn-body">
        <div className="walkthrough__modes" role="group" aria-label="How to read this">
          <button
            type="button"
            className={mode === 'play' ? 'walkthrough__mode walkthrough__mode--on' : 'walkthrough__mode'}
            aria-pressed={mode === 'play'}
            onClick={() => setMode('play')}
          >
            Watch
          </button>
          <button
            type="button"
            className={mode === 'text' ? 'walkthrough__mode walkthrough__mode--on' : 'walkthrough__mode'}
            aria-pressed={mode === 'text'}
            onClick={() => setMode('text')}
          >
            Read as text
          </button>
        </div>

        {mode === 'play' ? (
          // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
          <div className="walkthrough" ref={playerRef} onKeyDown={onKeyDown} tabIndex={-1}>
            <div className="walkthrough__stage figure-surface">
              {held && <Stage stage={held.stage} progress={held.progress} />}
            </div>

            <Transport
              t={t}
              total={total}
              playing={playing}
              rate={rate}
              scenes={scenes}
              chapters={chapters}
              onToggle={toggle}
              onSeek={seek}
              onRate={setRate}
            />

            {/* Deliberately not a live region. NeuronDemo.tsx works through the
                same problem: announcing every beat as it arrives is dozens of
                interruptions to say one thing. The chapter status below announces
                position once per chapter instead, and anyone who wants the words
                read to them has the text view. */}
            <div className="walkthrough__caption prose">
              <NarrationProvider value={{ mode: 'play', activeId: scene.id }}>
                <Narration />
              </NarrationProvider>
            </div>

            {sources && <CodePanel code={scene.code} sources={sources} />}

            <p className="walkthrough__status" role="status">
              {chapters.find((c) => c.slug === currentChapter)?.title}
            </p>
          </div>
        ) : (
          <div className="walkthrough-text prose">
            <NarrationProvider value={{ mode: 'text', activeId: null, extrasFor }}>
              <Narration />
            </NarrationProvider>
          </div>
        )}
      </div>
    </div>
  )
}
