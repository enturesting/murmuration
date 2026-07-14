import { useEffect, useState } from 'react';
import type { Phase } from '../types';

interface Props {
  /** Increments each time a new phase fires; component listens for changes to trigger flash */
  trigger: number;
  /** The phase whose flash data to render */
  phase: Phase | null;
  /** Called when the user dismisses the flash (click / ESC / ✕). Used by the engine
   *  to advance to the next phase. */
  onDismiss?: () => void;
}

export function FlashBanner({ trigger, phase, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);

  // Show whenever a new flash fires; user dismisses manually.
  useEffect(() => {
    if (!phase?.flash) {
      setVisible(false);
      return;
    }
    setVisible(true);
  }, [trigger, phase]);

  // ESC dismisses (only when visible)
  useEffect(() => {
    if (!visible) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setVisible(false);
        onDismiss?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [visible, onDismiss]);

  function dismiss() {
    setVisible(false);
    onDismiss?.();
  }

  if (!visible || !phase?.flash) return null;
  const f = phase.flash;
  return (
    <div
      className={`flash-banner flash-${f.tone}`}
      role="alert"
      aria-live="polite"
      onClick={dismiss}
    >
      <button
        type="button"
        className="flash-dismiss"
        aria-label="Dismiss"
        onClick={(e) => {
          e.stopPropagation();
          dismiss();
        }}
      >
        ✕
      </button>
      <div className="flash-icon" aria-hidden="true">
        {f.icon}
      </div>
      <div className="flash-body">
        <div className="flash-title">{f.title}</div>
        {f.lines.map((line, i) => (
          <div key={i} className="flash-line">
            {line}
          </div>
        ))}
        <div className="flash-hint">click anywhere or press ESC to advance →</div>
      </div>
    </div>
  );
}
