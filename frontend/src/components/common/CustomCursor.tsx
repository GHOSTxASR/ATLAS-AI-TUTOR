import { useEffect, useRef, useState } from "react";

/**
 * Pointer overlay: a dot that tracks exactly, and a ring that trails it.
 *
 * The dot is placed straight from the pointer event so the thing under the
 * user's hand never lags -- latency is the one flaw a custom cursor cannot
 * hide. Only the ring is eased, which is what reads as weight.
 *
 * Deliberately conservative about when it takes over:
 *   - `(pointer: fine)` only. Hiding the system cursor on a touch or stylus
 *     device buys nothing and can strand a user with a hybrid setup.
 *   - `prefers-reduced-motion` keeps the cursor but drops the trailing, so the
 *     ring sits on the dot instead of chasing it.
 *   - `forced-colors` (Windows high contrast) bails out entirely; the system
 *     cursor there is a deliberate accessibility choice, not a default.
 *   - Text fields keep the native I-beam, since a dot cannot show a caret
 *     position between two characters.
 */

const RING_EASE = 0.18;
/** Below this, the ring has arrived and the loop can stop until the next move. */
const SETTLE_EPSILON = 0.1;

const INTERACTIVE = 'a,button,[role="button"],[role="menuitem"],[role="menuitemradio"],input,select,textarea,summary,[tabindex]:not([tabindex="-1"])';

export function CustomCursor() {
  const [enabled, setEnabled] = useState(false);
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  // Decide once whether this input device and these preferences want a custom
  // cursor at all, and keep listening in case the user changes them.
  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)");
    const forced = window.matchMedia("(forced-colors: active)");
    const sync = () => setEnabled(fine.matches && !forced.matches);
    sync();
    fine.addEventListener("change", sync);
    forced.addEventListener("change", sync);
    return () => {
      fine.removeEventListener("change", sync);
      forced.removeEventListener("change", sync);
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const dot = dotRef.current;
    const ring = ringRef.current;
    if (!dot || !ring) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    let pointerX = window.innerWidth / 2;
    let pointerY = window.innerHeight / 2;
    let ringX = pointerX;
    let ringY = pointerY;
    let frame = 0;
    let running = false;
    let visible = false;

    document.documentElement.classList.add("atlas-cursor-active");

    const paintRing = () => {
      ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%)`;
    };

    const step = () => {
      const dx = pointerX - ringX;
      const dy = pointerY - ringY;

      if (Math.abs(dx) < SETTLE_EPSILON && Math.abs(dy) < SETTLE_EPSILON) {
        ringX = pointerX;
        ringY = pointerY;
        paintRing();
        running = false; // Settled: stop burning frames until the next move.
        return;
      }

      ringX += dx * RING_EASE;
      ringY += dy * RING_EASE;
      paintRing();
      frame = requestAnimationFrame(step);
    };

    const kick = () => {
      if (running || reduceMotion.matches) return;
      running = true;
      frame = requestAnimationFrame(step);
    };

    const show = () => {
      if (visible) return;
      visible = true;
      dot.style.opacity = "1";
      ring.style.opacity = "1";
    };

    const hide = () => {
      visible = false;
      dot.style.opacity = "0";
      ring.style.opacity = "0";
    };

    const onMove = (e: PointerEvent) => {
      pointerX = e.clientX;
      pointerY = e.clientY;
      // The dot is positioned from the event itself, never interpolated.
      dot.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0) translate(-50%, -50%)`;
      show();

      if (reduceMotion.matches) {
        ringX = pointerX;
        ringY = pointerY;
        paintRing();
      } else {
        kick();
      }

      const target = e.target as Element | null;
      const interactive = !!target?.closest?.(INTERACTIVE);
      ring.classList.toggle("is-interactive", interactive);
    };

    const onDown = () => ring.classList.add("is-pressed");
    const onUp = () => ring.classList.remove("is-pressed");

    // Leaving to another window or tab should take the overlay with it,
    // otherwise a stale dot sits on the page after the pointer is gone.
    const onLeave = (e: PointerEvent) => {
      if (!e.relatedTarget) hide();
    };
    const onBlur = () => hide();
    const onVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(frame);
        running = false;
        hide();
      }
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerup", onUp, { passive: true });
    document.addEventListener("pointerout", onLeave);
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(frame);
      document.documentElement.classList.remove("atlas-cursor-active");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointerout", onLeave);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <>
      <div ref={dotRef} className="atlas-cursor-dot" aria-hidden="true" />
      <div ref={ringRef} className="atlas-cursor-ring" aria-hidden="true" />
    </>
  );
}
