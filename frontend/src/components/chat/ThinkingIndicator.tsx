/**
 * What the tutor shows while it is working.
 *
 * A spinner says "busy" the way any loading state does. This says the same
 * thing in the product's own colour, and reads as something thinking rather
 * than something fetching -- which is what is actually happening, and can
 * take a while on a long answer.
 *
 * The blob is gradients and a morphing border-radius, not the exported
 * artwork: that file is 3.5 MB of blurred layers and would dwarf the rest of
 * the bundle. Both animations stop under prefers-reduced-motion.
 */

interface AtlasBlobProps {
  /** Tailwind sizing for the blob itself, e.g. "w-6 h-6". */
  className?: string;
}

export function AtlasBlob({ className = "w-6 h-6" }: AtlasBlobProps) {
  return <span className={`atlas-blob ${className}`} aria-hidden="true" />;
}

/**
 * The blob with a word next to it, for the wait before any text arrives.
 *
 * Once tokens start coming the answer speaks for itself, so the caller drops
 * the label and keeps the blob as the avatar.
 */
export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2.5 min-h-8" role="status" aria-live="polite">
      <span className="atlas-thinking-text font-sans text-xs sm:text-sm tracking-tight">
        Atlas is thinking
      </span>
      <span className="sr-only">The tutor is preparing an answer.</span>
    </div>
  );
}
