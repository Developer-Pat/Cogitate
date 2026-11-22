/**
 * THE ACTIVATION ASK - one implementation, two doors.
 *
 * Activation provisions Exa's home, and a home with no model answers as plain Hermes - or, measured
 * on the 2026-11-22 release run, not at all: the runtime's session came back as an opaque
 * `RequestError: Internal error`. The switch cannot decide the model, so the page asks ONE question
 * with this install's chat model already named.
 *
 * It lived only on the integrations page, so pressing Activate on the Exa CHAT page - the door the
 * readiness verdict links to - said "say something to wake it up" over a model-less runtime. Two
 * copies of this markup is how that happens, so it is one component now.
 */
import type { ExaModelOffer } from '../../../services/externalAgentService'

export type { ExaModelOffer }

interface Props {
  /** The offered model, or null when there is nothing to ask. */
  offer: ExaModelOffer | null
  saving?: boolean
  onAccept: () => void
  onDismiss: () => void
}

export default function ExaModelAskDialog({ offer, saving = false, onAccept, onDismiss }: Props) {
  return (
    // DaisyUI v5 needs the <dialog className="modal"> wrapper.
    <dialog className="modal" open={!!offer}>
      <div className="modal-box">
        <h3 className="font-bold text-lg">Exa is on — it has no model yet</h3>
        <p className="py-3 text-sm">
          Without one it answers as a plain agent with none of its own character. This
          install answers chat with{' '}
          <span className="font-mono">{offer?.model}</span> via{' '}
          <span className="font-mono">{offer?.provider}</span>.
        </p>
        <div className="modal-action">
          <div className="tooltip tooltip-top" data-tip="Pick any provider and model on the Model card instead">
            <button className="btn btn-ghost btn-sm" onClick={onDismiss}>
              Choose on the card
            </button>
          </div>
          <div className="tooltip tooltip-top" data-tip="Write this install's chat model into Exa — one model, one key, one place">
            <button className="btn btn-primary btn-sm" onClick={onAccept} disabled={saving}>
              {saving ? 'Saving…' : 'Use this model'}
            </button>
          </div>
        </div>
      </div>
      <form method="dialog" className="modal-backdrop">
        <button onClick={onDismiss}>close</button>
      </form>
    </dialog>
  )
}
