import { Tanh, Relu } from '../../content/diagrams/Activations'
import { LayerForward, LayerBackward } from '../../content/diagrams/LayerFlow'
import { SoftmaxWorked, CrossEntropyWorked } from '../../content/diagrams/Losses'
import MatrixFlat from '../../content/diagrams/MatrixFlat'
import MatrixIndex from '../../content/diagrams/MatrixIndex'
import {
  ApplySigmoid,
  BiasBroadcast,
  Hadamard,
  Scale,
  Subtract,
} from '../../content/diagrams/MatrixOps'
import MiniBatch from '../../content/diagrams/MiniBatch'
import Mlp from '../../content/diagrams/Mlp'
import MlpStack from '../../content/diagrams/MlpStack'
import MnistSample from '../../content/diagrams/MnistSample'
import XorHidden, { XorTransform } from '../../content/diagrams/XorHidden'
import type { Step1Stage as Stage } from '../../content/step1/walkthrough'

// What the top half of the player draws, for one step1 scene. The sibling of
// Step0Stage.tsx; read that file's header for why each model brings its own.
//
// Nearly every branch here is a diagram the six .mdx pages already used, imported
// unchanged. Those figures were the best part of the pages: computed from real
// arithmetic rather than drawn, checked, and already in the site's visual language.
// Replacing the prose was never a reason to redraw them.
//
// Only `xorTransform` takes `progress`. The rest hold, which is what a figure being
// talked about should do, and it means seeking to any of those scenes shows a
// finished picture rather than a half-built one.

export default function Step1Stage({ stage, progress }: { stage: Stage; progress: number }) {
  switch (stage.kind) {
    case 'mlp':
      return <Mlp />
    case 'mlpStack':
      return <MlpStack />
    case 'xorTransform':
      return <XorTransform moved={stage.moved ?? false} progress={progress} />
    case 'xorHidden':
      return <XorHidden />
    case 'matrixFlat':
      return <MatrixFlat />
    case 'matrixIndex':
      return <MatrixIndex />
    case 'matrixOp': {
      // A lookup rather than a nested switch: five one-line cases inside a case is
      // the shape that grows an accidental fallthrough later.
      const Op = {
        bias: BiasBroadcast,
        subtract: Subtract,
        hadamard: Hadamard,
        scale: Scale,
        apply: ApplySigmoid,
      }[stage.op]
      return <Op />
    }
    case 'activation':
      return stage.fn === 'tanh' ? <Tanh /> : <Relu />
    case 'loss':
      return stage.of === 'softmax' ? <SoftmaxWorked /> : <CrossEntropyWorked />
    case 'layerFlow':
      return stage.pass === 'forward' ? <LayerForward /> : <LayerBackward />
    case 'miniBatch':
      return <MiniBatch />
    case 'mnist':
      return <MnistSample />
    case 'none':
      // Beats that are pure maths hold the previous picture rather than showing
      // something unrelated; the player does the holding, see draws() in
      // content/walkthrough/types.ts.
      return null
  }
}
