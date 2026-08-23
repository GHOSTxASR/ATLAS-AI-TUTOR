import { useEffect, useRef } from "react";

/**
 * Ambient particle swarm for the landing page.
 *
 * Deliberately cheap: the whole field is one canvas, positions are integrated
 * with plain arithmetic, and neighbour links use squared distances so the
 * per-frame cost stays well inside a 16ms budget on a laptop GPU.
 *
 * It also knows when to stop. A full-viewport animation that keeps running in
 * a background tab is a battery leak, and one that keeps running under
 * `prefers-reduced-motion` is an accessibility failure -- so it renders a
 * single static frame instead.
 */

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  /** Accent particles are a small minority; the rest are neutral grey. */
  accent: boolean;
}

const LINK_DISTANCE = 128;
const LINK_DISTANCE_SQ = LINK_DISTANCE * LINK_DISTANCE;
const POINTER_RADIUS = 170;
const POINTER_RADIUS_SQ = POINTER_RADIUS * POINTER_RADIUS;
const MAX_PARTICLES = 110;
const MIN_PARTICLES = 34;
/** One particle per this many CSS px² -- keeps phones sparse and desktops full. */
const AREA_PER_PARTICLE = 15000;
const ACCENT_SHARE = 0.16;

export function ParticleSwarm() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    let particles: Particle[] = [];
    let width = 0;
    let height = 0;
    let frame = 0;
    let running = false;
    // Off-screen until the pointer actually moves, so nothing is attracted
    // toward a phantom cursor at the origin on touch devices.
    let pointerX = -9999;
    let pointerY = -9999;

    const styles = getComputedStyle(document.documentElement);
    const accentRgb = styles.getPropertyValue("--accent-rgb").trim() || "255, 77, 94";

    const seed = () => {
      const target = Math.round((width * height) / AREA_PER_PARTICLE);
      const count = Math.max(MIN_PARTICLES, Math.min(MAX_PARTICLES, target));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.5 + 0.7,
        accent: Math.random() < ACCENT_SHARE,
      }));
    };

    const resize = () => {
      // Cap DPR: past 2 the extra pixels cost real time and buy nothing here.
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      // Links first so dots sit on top of the web rather than under it.
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const distSq = dx * dx + dy * dy;
          if (distSq > LINK_DISTANCE_SQ) continue;
          const strength = 1 - distSq / LINK_DISTANCE_SQ;
          const pair = a.accent || b.accent;
          ctx.strokeStyle = pair
            ? `rgba(${accentRgb}, ${strength * 0.22})`
            : `rgba(150, 150, 155, ${strength * 0.14})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      for (const p of particles) {
        ctx.fillStyle = p.accent
          ? `rgba(${accentRgb}, 0.75)`
          : "rgba(178, 178, 184, 0.5)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const step = () => {
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;

        // Wrap with a margin so particles glide off and back rather than
        // popping at the exact edge.
        if (p.x < -20) p.x = width + 20;
        else if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        else if (p.y > height + 20) p.y = -20;

        const dx = pointerX - p.x;
        const dy = pointerY - p.y;
        const distSq = dx * dx + dy * dy;
        if (distSq < POINTER_RADIUS_SQ && distSq > 1) {
          // Gentle pull toward the cursor, fading out at the radius edge.
          const pull = (1 - distSq / POINTER_RADIUS_SQ) * 0.035;
          const dist = Math.sqrt(distSq);
          p.vx += (dx / dist) * pull;
          p.vy += (dy / dist) * pull;
        }

        // Damping keeps the pointer impulse from accumulating into chaos.
        p.vx *= 0.994;
        p.vy *= 0.994;

        // Re-energise anything that has damped to a standstill.
        const speedSq = p.vx * p.vx + p.vy * p.vy;
        if (speedSq < 0.0016) {
          p.vx += (Math.random() - 0.5) * 0.04;
          p.vy += (Math.random() - 0.5) * 0.04;
        }
      }

      draw();
      frame = requestAnimationFrame(step);
    };

    const start = () => {
      if (running || reduceMotion.matches) return;
      running = true;
      frame = requestAnimationFrame(step);
    };

    const stop = () => {
      running = false;
      cancelAnimationFrame(frame);
    };

    const onPointerMove = (e: PointerEvent) => {
      pointerX = e.clientX;
      pointerY = e.clientY;
    };

    const onPointerLeave = () => {
      pointerX = -9999;
      pointerY = -9999;
    };

    const onVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    const onMotionPreferenceChange = () => {
      stop();
      draw();
      start();
    };

    let resizeTimer: number | undefined;
    const onResize = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        resize();
        draw();
      }, 150);
    };

    resize();
    draw(); // Paint one frame immediately -- reduced motion stops here.
    start();

    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerleave", onPointerLeave);
    document.addEventListener("visibilitychange", onVisibility);
    reduceMotion.addEventListener("change", onMotionPreferenceChange);

    return () => {
      stop();
      window.clearTimeout(resizeTimer);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerleave", onPointerLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      reduceMotion.removeEventListener("change", onMotionPreferenceChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 h-full w-full"
    />
  );
}
