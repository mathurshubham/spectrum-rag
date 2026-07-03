"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { fetchDemos, type DemoMeta } from "@/lib/api"
import { ThemeToggle } from "./components/ThemeToggle"

const DEMO_META: Record<string, {
  icon: string
  accent: string
  accentBg: string   // light mode tint
  accentBgDark: string // dark mode tint
  tags: string[]
}> = {
  law:       { icon: "⚖",  accent: "#4f46e5", accentBg: "#eef2ff", accentBgDark: "#1e1b4b", tags: ["BNS 2023", "Constitution", "DPDP"] },
  insurance: { icon: "🛡",  accent: "#0d9488", accentBg: "#f0fdfa", accentBgDark: "#042f2e", tags: ["IRDAI", "Term Life", "Accident"] },
  health:    { icon: "⚕",  accent: "#059669", accentBg: "#f0fdf4", accentBgDark: "#052e16", tags: ["WHO", "Diabetes", "Malaria"] },
  education: { icon: "📚", accent: "#7c3aed", accentBg: "#f5f3ff", accentBgDark: "#2e1065", tags: ["History", "Economics", "Geography"] },
  french:    { icon: "🇫🇷", accent: "#2563eb", accentBg: "#eff6ff", accentBgDark: "#172554", tags: ["CBSE 9–10", "IB DP", "Entre Jeunes"] },
  support:   { icon: "🎧", accent: "#0284c7", accentBg: "#f0f9ff", accentBgDark: "#082f49", tags: ["Billing", "SSO", "SLA"] },
}

export default function RootPage() {
  const router = useRouter()
  const [demos, setDemos] = useState<DemoMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    setIsDark(document.documentElement.getAttribute("data-theme") === "dark")
    // Re-sync on toggle
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.getAttribute("data-theme") === "dark")
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    fetchDemos()
      .then(d => {
        if (d.length === 1) {
          router.replace(`/${d[0].id}`)
        } else {
          setDemos(d)
          setLoading(false)
        }
      })
      .catch(() => router.replace("/law"))
  }, [router])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--bg)]">
        <div className="w-4 h-4 border border-[var(--border-hi)] border-t-[var(--text-3)] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col">
      {/* Nav */}
      <nav className="sticky top-0 z-20 flex items-center justify-between px-6 h-12 border-b border-[var(--border)] bg-[var(--bg)]"
        style={{ backdropFilter: "blur(12px)" }}>
        <span className="text-[13px] font-semibold text-[var(--text)]">Spectrum RAG</span>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => router.push("/law")}
            className="h-8 px-3 sm:px-4 text-[13px] font-medium rounded-lg bg-[var(--text)] text-[var(--bg)] hover:opacity-90 transition-opacity whitespace-nowrap"
          >
            <span className="hidden sm:inline">Open App </span>→
          </button>
        </div>
      </nav>

      {/* Hero */}
      <div className="flex flex-col items-center text-center px-4 pt-20 pb-14 relative">
        {/* Radial glow — only in dark mode */}
        {isDark && (
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] pointer-events-none"
            style={{
              background: "radial-gradient(ellipse at center, rgba(99,102,241,0.12) 0%, transparent 70%)",
            }}
          />
        )}
        <span className="relative text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-4)] mb-5">
          Grounded AI Platform
        </span>
        <h1 className="relative text-[1.25rem] sm:text-4xl md:text-5xl font-bold text-[var(--text)] leading-[1.2] tracking-tight mb-4 max-w-xl w-full">
          Six knowledge bases.<br />Zero hallucinations.
        </h1>
        <p className="relative text-[14px] sm:text-[15px] text-[var(--text-3)] max-w-sm mb-8 px-2">
          Select a domain to start asking grounded, cited questions.
        </p>
      </div>

      {/* Cards */}
      <div className="mx-auto w-full max-w-3xl px-4 pb-20 overflow-hidden">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-4)] mb-4">
          Choose your domain
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {demos.map(d => {
            const meta = DEMO_META[d.id] ?? { icon: "🤖", accent: "#6366f1", accentBg: "#eef2ff", accentBgDark: "#1e1b4b", tags: [] }
            const tagBg = isDark ? meta.accentBgDark : meta.accentBg
            return (
              <button
                key={d.id}
                onClick={() => router.push(`/${d.id}`)}
                className="group relative flex items-start gap-4 text-left bg-[var(--bg-card)] border border-[var(--border)] rounded-xl px-5 py-4 hover:border-[var(--border-hi)] hover:-translate-y-0.5 transition-all duration-150 overflow-hidden"
              >
                {/* Left accent strip */}
                <div
                  className="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-xl"
                  style={{ backgroundColor: meta.accent }}
                />

                {/* Icon */}
                <div
                  className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-base"
                  style={{ backgroundColor: tagBg }}
                >
                  {meta.icon}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-[var(--text)] leading-snug mb-0.5">
                    {d.title.split("—").pop()?.trim() ?? d.title}
                  </p>
                  <p className="text-[12px] text-[var(--text-2)] leading-snug mb-2.5">
                    {d.description}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {meta.tags.map(tag => (
                      <span
                        key={tag}
                        className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: tagBg,
                          color: isDark ? `${meta.accent}ee` : meta.accent,
                          filter: isDark ? "brightness(1.4)" : "none",
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Arrow */}
                <svg
                  className="shrink-0 w-4 h-4 text-[var(--text-4)] group-hover:text-[var(--text-3)] mt-0.5 transition-colors"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            )
          })}
        </div>

        {/* Footer */}
        <p className="text-center text-[11px] text-[var(--text-4)] mt-12">
          RAG · baai/bge-m3 · ParadeDB · OpenRouter
        </p>
      </div>
    </div>
  )
}
