import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Plus, X } from "lucide-react";

import { ParticleSwarm } from "../components/landing/ParticleSwarm";
import { useProfileStore } from "../stores/profileStore";
import { ProfileType } from "../types";

const PROFILE_TYPES: ProfileType[] = ["JEE", "GATE", "Semester Study", "Custom Learning"];

/** Two-digit index label, matching the `[ 01 ]` mono motif. */
const pad = (n: number) => String(n + 1).padStart(2, "0");

export function LandingPage() {
  const navigate = useNavigate();
  const { profiles, isLoading, error, loadProfiles, createProfile, setActiveProfile } =
    useProfileStore();

  const [loaded, setLoaded] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<ProfileType>("JEE");
  const [submitting, setSubmitting] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadProfiles().finally(() => setLoaded(true));
  }, [loadProfiles]);

  // With no profiles there is nothing to choose between, so the form is the
  // page rather than something hidden behind a button.
  const hasProfiles = profiles.length > 0;
  const formOpen = creating || (loaded && !isLoading && !hasProfiles);

  useEffect(() => {
    if (formOpen) nameRef.current?.focus();
  }, [formOpen]);

  const enterProfile = (id: string) => {
    setActiveProfile(id);
    navigate("/dashboard");
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name || submitting) return;
    setSubmitting(true);
    try {
      await createProfile({ name, profile_type: newType });
      setNewName("");
      setCreating(false);
    } finally {
      setSubmitting(false);
    }
  };

  // Staggered entrance, 45ms apart. The cap matters: cards are translated
  // during their animation, so anything still animating is a target that has
  // not settled where the user sees it. Everything is in place by ~1.4s.
  const cardDelay = useMemo(
    () => (i: number) => `${Math.min(0.5 + i * 0.045, 0.95)}s`,
    [],
  );

  return (
    <div className="atlas-landing relative min-h-dvh overflow-x-hidden bg-[#0A0A0B] text-[#EDEDED]">
      <ParticleSwarm />
      <div className="atlas-grain pointer-events-none fixed inset-0 z-50" aria-hidden="true" />

      <div className="relative z-10 mx-auto flex min-h-dvh w-full max-w-6xl flex-col px-5 py-8 sm:px-8 sm:py-10">
        <header className="appear appear--soft" style={{ "--d": "0.05s" } as React.CSSProperties}>
          <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-[#7A7A80]">
            <span className="text-[#FF4D5E]">[</span> Local-first{" "}
            <span className="text-[#FF4D5E]">]</span>
          </span>
        </header>

        <main className="flex flex-1 flex-col justify-center py-12 sm:py-16">
          {/* ---- Wordmark + one-liner ---- */}
          <div className="max-w-3xl">
            <h1
              className="appear appear--mask font-sans text-[clamp(3.5rem,13vw,8rem)] font-medium leading-[0.92] tracking-[-0.05em] text-[#F2F2F2]"
              style={{ "--d": "0.14s" } as React.CSSProperties}
            >
              Atlas
            </h1>
            <p
              className="appear appear--soft mt-5 max-w-xl text-[clamp(1rem,2.2vw,1.35rem)] leading-[1.45] tracking-[-0.02em] text-[#9A9A9A]"
              style={{ "--d": "0.3s" } as React.CSSProperties}
            >
              Your personal AI{" "}
              <span className="font-medium text-[#EDEDED]">learning</span> platform —
              private, local, and built around what you actually study.
            </p>
          </div>

          {/* ---- Profile selection ---- */}
          <section
            aria-labelledby="choose-profile"
            className="appear appear--soft mt-14 sm:mt-20"
            style={{ "--d": "0.46s" } as React.CSSProperties}
          >
            <div className="flex items-baseline justify-between gap-4 border-t border-white/10 pt-5">
              <h2
                id="choose-profile"
                className="font-mono text-[11px] uppercase tracking-[0.26em] text-[#8A8A90]"
              >
                {hasProfiles ? "Choose a profile" : "Create your first profile"}
              </h2>
              {hasProfiles && (
                <span className="font-mono text-[11px] tabular-nums text-[#5F5F66]">
                  {profiles.length} {profiles.length === 1 ? "profile" : "profiles"}
                </span>
              )}
            </div>

            {error && (
              <p
                role="alert"
                className="mt-5 border-l-2 border-[#FF4D5E] bg-[#FF4D5E]/8 px-4 py-3 text-sm text-[#FF8A95]"
              >
                {error}
              </p>
            )}

            {!loaded || isLoading ? (
              <ul className="atlas-profile-grid mt-6" aria-hidden="true">
                {Array.from({ length: 3 }).map((_, i) => (
                  <li
                    key={i}
                    className="h-[168px] w-full animate-pulse border-x border-b border-t-2 border-white/10 bg-white/[0.02]"
                  />
                ))}
              </ul>
            ) : (
              <ul className="atlas-profile-grid mt-6">
                {profiles.map((p, i) => (
                  <li
                    key={p.id}
                    className="appear appear--card"
                    style={{ "--d": cardDelay(i) } as React.CSSProperties}
                  >
                    <button
                      type="button"
                      onClick={() => enterProfile(p.id)}
                      aria-label={`Open ${p.name} — ${p.profile_type}`}
                      className="group relative flex h-full w-full flex-col justify-between border-x border-b border-t-2 border-x-white/10 border-b-white/10 border-t-[#E11D48] bg-white/[0.02] p-5 text-left transition-colors duration-200 hover:bg-white/[0.05] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FF4D5E]"
                    >
                      <span
                        className="font-mono text-[11px] tracking-[0.18em] text-[#FF4D5E]"
                        aria-hidden="true"
                      >
                        [ {pad(i)} ]
                      </span>

                      <span className="mt-8 block text-[1.6rem] leading-[1.1] tracking-[-0.03em] text-[#E8E8E8] [overflow-wrap:anywhere]">
                        {p.name}
                      </span>

                      <span className="mt-6 flex items-end justify-between gap-3">
                        <span
                          className="font-mono text-[11px] leading-snug text-[#7A7A80]"
                          aria-hidden="true"
                        >
                          [ {p.profile_type} ]
                          <span className="mt-1 block text-[#5F5F66]">
                            {new Date(p.created_at).toLocaleDateString(undefined, {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })}
                          </span>
                        </span>
                        <ArrowRight
                          className="h-4 w-4 shrink-0 translate-x-0 text-[#5F5F66] transition-all duration-200 group-hover:translate-x-1 group-hover:text-[#FF4D5E]"
                          aria-hidden="true"
                        />
                      </span>
                    </button>
                  </li>
                ))}

                {hasProfiles && !creating && (
                  <li
                    className="appear appear--card"
                    style={{ "--d": cardDelay(profiles.length) } as React.CSSProperties}
                  >
                    <button
                      type="button"
                      onClick={() => setCreating(true)}
                      aria-label="Create a new profile"
                      className="group flex h-full min-h-[168px] w-full flex-col items-start justify-between border-x border-b border-t-2 border-dashed border-white/15 bg-transparent p-5 text-left transition-colors duration-200 hover:border-[#FF4D5E]/60 hover:bg-white/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FF4D5E]"
                    >
                      <span
                        className="font-mono text-[11px] tracking-[0.18em] text-[#7A7A80]"
                        aria-hidden="true"
                      >
                        [ ++ ]
                      </span>
                      <span className="mt-8 flex items-center gap-2 text-[1.6rem] leading-[1.1] tracking-[-0.03em] text-[#8A8A90] transition-colors group-hover:text-[#E8E8E8]">
                        <Plus className="h-5 w-5" aria-hidden="true" />
                        New profile
                      </span>
                      <span className="mt-6 font-mono text-[11px] text-[#5F5F66]">
                        [ separate documents, memory &amp; progress ]
                      </span>
                    </button>
                  </li>
                )}
              </ul>
            )}

            {/* ---- Inline create form ---- */}
            {formOpen && (
              <form
                onSubmit={handleCreate}
                className="atlas-form mt-8 border-t-2 border-[#E11D48] bg-white/[0.02] p-5 sm:p-6"
              >
                <div className="flex items-center justify-between gap-4">
                  <h3 className="font-mono text-[11px] uppercase tracking-[0.26em] text-[#FF4D5E]">
                    [ New profile ]
                  </h3>
                  {hasProfiles && (
                    <button
                      type="button"
                      onClick={() => setCreating(false)}
                      className="-m-2 grid h-11 w-11 place-items-center text-[#7A7A80] transition-colors hover:text-[#EDEDED] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FF4D5E]"
                      aria-label="Cancel creating a profile"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  )}
                </div>

                <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_auto] sm:items-end">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="profile-name"
                        className="block font-mono text-[11px] uppercase tracking-[0.18em] text-[#8A8A90]"
                      >
                        Name <span className="text-[#FF4D5E]">*</span>
                      </label>
                      <input
                        id="profile-name"
                        ref={nameRef}
                        type="text"
                        required
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder="e.g. Ashmit (JEE 2026)"
                        className="mt-2 min-h-[44px] w-full border-b border-white/20 bg-transparent pb-2 text-base text-[#EDEDED] placeholder:text-[#5F5F66] focus:border-[#FF4D5E] focus:outline-none"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="profile-type"
                        className="block font-mono text-[11px] uppercase tracking-[0.18em] text-[#8A8A90]"
                      >
                        Track
                      </label>
                      <select
                        id="profile-type"
                        value={newType}
                        onChange={(e) => setNewType(e.target.value as ProfileType)}
                        className="mt-2 min-h-[44px] w-full border-b border-white/20 bg-transparent pb-2 text-base text-[#EDEDED] focus:border-[#FF4D5E] focus:outline-none"
                      >
                        {PROFILE_TYPES.map((t) => (
                          <option key={t} value={t} className="bg-[#141416] text-[#EDEDED]">
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting || !newName.trim()}
                    className="inline-flex h-11 items-center justify-center gap-2 bg-[#E11D48] px-6 text-sm font-medium tracking-[-0.01em] text-white transition-colors duration-200 hover:bg-[#FF2D45] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FF4D5E]"
                  >
                    {submitting ? "Creating…" : "Create profile"}
                    {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
                  </button>
                </div>
              </form>
            )}
          </section>
        </main>

        <footer
          className="appear appear--soft flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-white/10 pt-5 font-mono text-[11px] text-[#5F5F66]"
          style={{ "--d": "0.8s" } as React.CSSProperties}
        >
          <span>[ Runs entirely on your machine ]</span>
          <span>[ Documents, notes &amp; keys never leave it ]</span>
        </footer>
      </div>
    </div>
  );
}
