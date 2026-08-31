import BceLoss from '../../content/diagrams/BceLoss'
import LearningRate from '../../content/diagrams/LearningRate'
import Neuron from '../../content/diagrams/Neuron'
import Sigmoid from '../../content/diagrams/Sigmoid'
import { XorBoundary, XorPoints } from '../../content/diagrams/Xor'
import type { Step0Stage } from '../../content/step0/walkthrough'
import TrainingStage from './TrainingStage'

// What the top half of the player draws, for one step0 scene.
//
// Per-model on purpose. The player, the clock, the transport and the code panel are
// all generic and take a walkthrough as data, but deciding that `{ kind: 'sigmoid' }`
// means <Sigmoid> is the one part that cannot be: it is a mapping from this model's
// vocabulary to this model's diagrams. So each model brings its own, handed to the
// registry through `walkthrough()` in content/types.ts, and step1 has a sibling of
// this file rather than a branch inside it.
//
// Every branch is an existing diagram from content/diagrams/ or, for the training
// scenes, one built on the same plot.ts helpers. Reusing them rather than drawing
// walkthrough-specific pictures keeps one visual language across the site, and it
// means the diagrams stay computed rather than hand-drawn: the geometry comes out of
// the same functions whether it is sitting still in a figure or moving here.
//
// `progress` runs 0 to 1 within the current scene. Only the branches that animate
// use it; the rest ignore it and simply hold, which is what a figure being talked
// about should do.

export default function Step0Stage({ stage, progress }: { stage: Step0Stage; progress: number }) {
  switch (stage.kind) {
    case 'neuron':
      return <Neuron reveal={stage.reveal} progress={progress} />
    case 'sigmoid':
      return <Sigmoid tangent={stage.derivative ?? false} progress={progress} />
    case 'bceLoss':
      return <BceLoss />
    case 'learningRate':
      return <LearningRate />
    case 'xor':
      return stage.boundary ? <XorBoundary /> : <XorPoints />
    case 'training':
      return <TrainingStage dataset={stage.dataset} progress={progress} />
    case 'none':
      // Beats that are pure maths hold the stage empty rather than showing
      // something unrelated. The container keeps its height so the layout below
      // does not jump.
      return null
  }
}
