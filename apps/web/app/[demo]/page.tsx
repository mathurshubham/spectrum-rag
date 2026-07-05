"use client"

import { use, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import type { ChatMessage, Settings, Turn, QueryResponse } from "@/lib/types"
import { postQueryStream, type RetrievalMode, type LanguageMode, type BoardFilter } from "@/lib/api"
import type { DemoConfig } from "@/lib/demoConfig"
import { MessageBubble } from "../components/MessageBubble"
import { ChunksPanel } from "../components/ChunksPanel"
import { SettingsPanel } from "../components/SettingsPanel"
import { TryEvalExportModal } from "../components/TryEvalExportModal"
import { CorpusModal } from "../components/CorpusModal"
import { DatasetModal } from "../components/DatasetModal"
import { TeacherToolsModal } from "../components/TeacherToolsModal"
import { DemoPicker } from "../components/DemoPicker"
import { ThemeToggle } from "../components/ThemeToggle"

import lawConfig       from "../../demos/law/web_config"
import insuranceConfig from "../../demos/insurance/web_config"
import healthConfig    from "../../demos/health/web_config"
import educationConfig from "../../demos/education/web_config"
import supportConfig   from "../../demos/support/web_config"
import frenchConfig    from "../../demos/french/web_config"

const DEMO_CONFIGS: Record<string, DemoConfig> = {
  law: lawConfig, insurance: insuranceConfig,
  health: healthConfig, education: educationConfig, support: supportConfig,
  french: frenchConfig,
}

const DEMO_ACCENT: Record<string, string> = {
  law: "#4f46e5", insurance: "#0d9488", health: "#059669",
  education: "#7c3aed", support: "#0284c7", french: "#2563eb",
}

const LANGUAGE_MODES = [
  { id: "fr",        label: "FR",       desc: "Réponse en français" },
  { id: "en",        label: "EN",       desc: "Answer in English" },
  { id: "bilingual", label: "FR + EN",  desc: "Bilingual answer" },
] as const

const BOARDS = [
  { id: "all",  label: "All",  desc: "Search all indexed boards" },
  { id: "cbse", label: "CBSE", desc: "Class 9–10 (Entre Jeunes, A1–A2)" },
  { id: "ib",   label: "IB",   desc: "DP French B (grades 11–12, B1–B2)" },
] as const

// Demos that surface the language + board toggles. Others ignore the fields.
const LANGUAGE_TOGGLE_DEMOS = new Set(["french"])
const BOARD_TOGGLE_DEMOS = new Set(["french"])
const LANGUAGE_KEY = "rag-demo-language-mode"
const BOARD_KEY = "rag-demo-board"

function newId() { return Math.random().toString(36).slice(2) }

const SETTINGS_KEY = "rag-demo-settings"
const _EMPTY: Settings = {
  openrouterKey: "", cfAccountId: "", cfGatewayId: "",
  genProvider: "openrouter", openaiKey: "", openaiModel: "gpt-4o",
}

function loadSettings(): Settings {
  if (typeof window === "undefined") return _EMPTY
  // Merge with defaults so settings saved before new fields existed don't come back undefined.
  try { return { ..._EMPTY, ...(JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "null") ?? {}) } } catch { return _EMPTY }
}
function saveSettings(s: Settings) {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)) } catch {}
}

const MODES = [
  { id: "hybrid",  label: "Hybrid",   desc: "Dense + BM25 → RRF" },
  { id: "bm25",    label: "BM25",     desc: "Full-text only" },
  { id: "vanilla", label: "RAG only", desc: "Dense vector" },
  { id: "hyde",    label: "HyDE",     desc: "Hypothetical doc → embed" },
] as const

export default function DemoPage({ params }: { params: Promise<{ demo: string }> }) {
  const { demo } = use(params)
  const router = useRouter()
  const config = DEMO_CONFIGS[demo] ?? lawConfig
  const accent = DEMO_ACCENT[demo] ?? "#6366f1"

  const [messages, setMessages]         = useState<ChatMessage[]>([])
  const [input, setInput]               = useState("")
  const [loading, setLoading]           = useState(false)
  const [settings, setSettings]         = useState<Settings>(_EMPTY)
  const [activeSources, setActiveSources] = useState<string | null>(null)
  const [mode, setMode]                 = useState<RetrievalMode>("hybrid")
  const [languageMode, setLanguageMode] = useState<LanguageMode>("bilingual")
  const [boardFilter, setBoardFilter]   = useState<BoardFilter>("all")
  const showLanguageToggle = LANGUAGE_TOGGLE_DEMOS.has(demo)
  const showBoardToggle    = BOARD_TOGGLE_DEMOS.has(demo)
  const [showSettings, setShowSettings] = useState(false)
  const [showTryEval, setShowTryEval]   = useState(false)
  const [showCorpus, setShowCorpus]     = useState(false)
  const [showMobileMenu, setShowMobileMenu] = useState(false)
  const [showDataset, setShowDataset]   = useState(false)
  const [showTeacher, setShowTeacher]   = useState(false)
  const showTeacherTools = demo === "french"
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const abortRef  = useRef<AbortController | null>(null)

  useEffect(() => { setSettings(loadSettings()) }, [])
  useEffect(() => {
    if (!showLanguageToggle) return
    try {
      const v = localStorage.getItem(LANGUAGE_KEY) as LanguageMode | null
      if (v === "fr" || v === "en" || v === "bilingual") setLanguageMode(v)
    } catch {}
  }, [showLanguageToggle])
  useEffect(() => {
    if (!showLanguageToggle) return
    try { localStorage.setItem(LANGUAGE_KEY, languageMode) } catch {}
  }, [languageMode, showLanguageToggle])
  useEffect(() => {
    if (!showBoardToggle) return
    try {
      const v = localStorage.getItem(BOARD_KEY) as BoardFilter | null
      if (v === "cbse" || v === "ib" || v === "all") setBoardFilter(v)
    } catch {}
  }, [showBoardToggle])
  useEffect(() => {
    if (!showBoardToggle) return
    try { localStorage.setItem(BOARD_KEY, boardFilter) } catch {}
  }, [boardFilter, showBoardToggle])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  const activeResponse = activeSources
    ? messages.find(m => m.id === activeSources)?.response ?? null
    : null

  const buildHistory = (): Turn[] =>
    messages.filter(m => !m.isLoading && !m.error).map(m => ({ role: m.role, content: m.content }))

  async function send(q: string) {
    if (!q.trim() || loading) return

    const userId = newId(), assistId = newId()
    setMessages(prev => [
      ...prev,
      { id: userId,   role: "user",      content: q },
      { id: assistId, role: "assistant", content: "", isLoading: true },
    ])
    setInput(""); setLoading(true)
    inputRef.current?.focus()

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let acc = ""
    try {
      await postQueryStream(
        demo, q, buildHistory(), settings,
        {
          onMeta: (meta) => {
            const resp = {
              answer: "",
              retrieved_chunks: meta.retrieved_chunks,
              citations: meta.citations,
              config: meta.config,
              trace_id: meta.trace_id,
              usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
              latency: { condense_ms: 0, retrieve_ms: 0, rerank_ms: 0, generate_ms: 0, total_ms: 0 },
            } as QueryResponse
            setMessages(prev => prev.map(m =>
              m.id === assistId ? { ...m, isLoading: false, response: resp } : m
            ))
            setActiveSources(assistId)
          },
          onDelta: (text) => {
            acc += text
            setMessages(prev => prev.map(m =>
              m.id === assistId
                ? { ...m, content: acc, response: m.response ? { ...m.response, answer: acc } : m.response }
                : m
            ))
          },
          onDone: ({ usage, latency }) => {
            setMessages(prev => prev.map(m =>
              m.id === assistId && m.response
                ? { ...m, response: { ...m.response, usage, latency } }
                : m
            ))
          },
          onError: (msg) => {
            setMessages(prev => prev.map(m =>
              m.id === assistId ? { ...m, isLoading: false, error: msg } : m
            ))
          },
        },
        mode, ctrl.signal,
        showLanguageToggle ? languageMode : undefined,
        showBoardToggle ? boardFilter : undefined,
      )
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return
      const msg = err instanceof Error ? err.message : String(err)
      setMessages(prev => prev.map(m =>
        m.id === assistId ? { ...m, isLoading: false, error: msg, content: "" } : m
      ))
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const empty = messages.length === 0

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg)]">

      {/* ── Header ── */}
      <header className="flex items-center justify-between px-3 sm:px-4 h-12 border-b border-[var(--border)] shrink-0 z-20 bg-[var(--bg)]">

        {/* Left: back + switcher */}
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => router.push("/")}
            title="Back to dashboard"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--bg-card)] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="w-px h-4 bg-[var(--border)] mx-1" />

          <DemoPicker currentDemo={demo} config={config} />
        </div>

        {/* Right: tools + theme + settings */}
        <div className="flex items-center">
          {/* Mobile ⋯ menu — visible only on mobile */}
          <div className="sm:hidden relative">
            <button
              onClick={() => setShowMobileMenu(o => !o)}
              title="Tools"
              className={`flex items-center gap-1.5 h-8 px-2.5 text-[12px] font-medium rounded-lg border transition-all ${
                showMobileMenu
                  ? "bg-[var(--bg-card)] border-[var(--border-hi)] text-[var(--text)]"
                  : "border-[var(--border)] text-[var(--text-2)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)] hover:text-[var(--text)]"
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h.01M12 12h.01M19 12h.01" />
              </svg>
              <span>Tools</span>
            </button>
            {showMobileMenu && (
              <div
                className="absolute right-0 top-full mt-1.5 w-44 bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl shadow-xl overflow-hidden z-50"
                style={{ boxShadow: "0 10px 30px rgba(0,0,0,0.3)" }}
              >
                {[
                  { label: "Corpus",   hint: "Indexed documents",     action: () => { setShowCorpus(true);    setShowMobileMenu(false) } },
                  { label: "Dataset",  hint: "Eval golden set",        action: () => { setShowDataset(true);   setShowMobileMenu(false) } },
                  ...(showTeacherTools ? [
                  { label: "Teacher",  hint: "Question generator",     action: () => { setShowTeacher(true);  setShowMobileMenu(false) } },
                  ] : []),
                  { label: "TryEval",  hint: "Export endpoint config", action: () => { setShowTryEval(true);  setShowMobileMenu(false) } },
                  { label: "Settings", hint: "API keys",               action: () => { setShowSettings(true); setShowMobileMenu(false) } },
                ].map(item => (
                  <button key={item.label} onClick={item.action}
                    className="w-full text-left px-4 py-3 hover:bg-[var(--bg-card)] transition-colors border-b border-[var(--border)] last:border-0">
                    <p className="text-[13px] font-medium text-[var(--text)]">{item.label}</p>
                    <p className="text-[11px] text-[var(--text-3)] mt-0.5">{item.hint}</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Labeled tool buttons — hidden on mobile */}
          <div className="hidden sm:flex items-center gap-1.5">
            {/* Corpus */}
            <button onClick={() => setShowCorpus(true)}
              className="flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[var(--text-2)] border border-[var(--border)] rounded-lg hover:text-[var(--text)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)] transition-all">
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              Corpus
            </button>

            {/* Dataset */}
            <button onClick={() => setShowDataset(true)}
              className="flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[var(--text-2)] border border-[var(--border)] rounded-lg hover:text-[var(--text)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)] transition-all">
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18M10 3v18M14 3v18" />
              </svg>
              Dataset
            </button>

            {/* Teacher tools — french only */}
            {showTeacherTools && (
              <button onClick={() => setShowTeacher(true)}
                className="flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[var(--text-2)] border border-[var(--border)] rounded-lg hover:text-[var(--text)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)] transition-all">
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-4.247 2.123a1.125 1.125 0 01-1.006 0L8.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l4.247-2.123a1.125 1.125 0 011.006 0l4.247 2.123c.318.158.69.158 1.006 0z" />
                </svg>
                Teacher
              </button>
            )}

            {/* TryEval */}
            <button onClick={() => setShowTryEval(true)}
              className="flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[var(--text-2)] border border-[var(--border)] rounded-lg hover:text-[var(--text)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)] transition-all">
              <div className="w-3.5 h-3.5 rounded-sm bg-[var(--accent)] flex items-center justify-center text-white text-[8px] font-bold shrink-0">T</div>
              TryEval
            </button>
          </div>

          <div className="w-px h-4 bg-[var(--border)] mx-1.5 hidden sm:block" />
          <ThemeToggle />
          <div className="w-px h-4 bg-[var(--border)] mx-1.5 hidden sm:block" />

          {/* Settings — desktop only; mobile uses Tools dropdown */}
          <button onClick={() => setShowSettings(true)}
            className={`h-8 px-3 hidden sm:flex items-center gap-1.5 text-[12px] font-medium rounded-lg border transition-all ${
              settings.openrouterKey
                ? "text-[var(--text-2)] border-[var(--border)] hover:text-[var(--text)] hover:border-[var(--border-hi)] hover:bg-[var(--bg-card)]"
                : "text-red-500 border-red-500/30 hover:bg-red-500/10"
            }`}>
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {settings.openrouterKey ? "Settings" : "Add key"}
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-6">
            {empty ? (
              /* ── Empty state ── */
              <div className="max-w-[600px] mx-auto flex flex-col items-center text-center pt-8 overflow-hidden">
                {/* Identity pill */}
                <span
                  className="inline-flex items-center gap-1.5 text-[11px] font-medium rounded-full px-3 py-1 mb-5 border"
                  style={{
                    borderColor: `${accent}40`,
                    background: `${accent}12`,
                    color: accent,
                  }}
                >
                  <span>{config.icon}</span>
                  <span>{config.shortTitle}</span>
                </span>

                {/* Headline */}
                <h1 className="text-lg sm:text-2xl font-bold text-[var(--text)] leading-tight tracking-tight mb-2 w-full break-words px-1">
                  {config.inputPlaceholder.replace("…", "").replace("...", "")}
                </h1>
                <p className="text-[13px] text-[var(--text-3)] mb-8 max-w-sm w-full px-1">
                  Every answer cites its source. Refuses when not in corpus.
                </p>

                {/* Suggestion cards — left accent strip style from Stitch */}
                <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2 text-left mb-5">
                  {config.suggestedQuestions.map(({ q, icon }) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="group relative grid items-start bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-3 py-3 hover:border-[var(--border-hi)] hover:bg-[var(--bg-surface)] transition-all duration-150 text-left w-full overflow-hidden"
                      style={{ gridTemplateColumns: "20px 1fr", gap: "10px" }}
                    >
                      {/* Accent left strip */}
                      <div
                        className="absolute left-0 top-0 bottom-0 w-0.5"
                        style={{ backgroundColor: accent }}
                      />
                      <span className="text-sm mt-0.5 ml-1">{icon}</span>
                      <p className="text-[13px] text-[var(--text-2)] group-hover:text-[var(--text)] leading-snug transition-colors" style={{ overflowWrap: "break-word", wordBreak: "break-word", minWidth: 0 }}>
                        {q}
                      </p>
                    </button>
                  ))}
                </div>

                {/* About corpus */}
                {config.about && (
                  <div
                    className="w-full text-left rounded-r-lg px-4 py-3"
                    style={{
                      borderLeft: `2px solid ${accent}`,
                      background: `${accent}08`,
                    }}
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-[0.08em] mb-1.5"
                      style={{ color: accent }}>
                      What this covers
                    </p>
                    <p className="text-[12px] text-[var(--text-2)] leading-relaxed break-words">{config.about}</p>
                  </div>
                )}
              </div>
            ) : (
              /* ── Chat ── */
              <div className="max-w-[640px] mx-auto space-y-5">
                {messages.map(m => (
                  <MessageBubble
                    key={m.id}
                    message={m}
                    config={config}
                    accent={accent}
                    onShowSources={id => setActiveSources(prev => prev === id ? null : id)}
                    activeSources={activeSources}
                  />
                ))}
                <div ref={bottomRef} />
              </div>
            )}
          </main>

          {/* ── Input bar ── */}
          <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--bg)] shrink-0">
            <div className="max-w-[640px] mx-auto">

              {/* Mode segmented pill control */}
              <div className="flex items-center gap-2 mb-2">
                <div className="flex items-center gap-0.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-full p-0.5">
                  {MODES.map(m => (
                    <button
                      key={m.id}
                      title={m.desc}
                      onClick={() => setMode(m.id)}
                      className={`px-3 py-1 text-[11px] font-medium rounded-full transition-all duration-150 ${
                        mode === m.id
                          ? "bg-[var(--text)] text-[var(--bg)] shadow-sm"
                          : "text-[var(--text-3)] hover:text-[var(--text-2)]"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
                <span className="text-[10px] text-[var(--text-4)] hidden sm:inline">
                  {MODES.find(m => m.id === mode)?.desc}
                </span>
                {showBoardToggle && (
                  <div
                    className="flex items-center gap-0.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-full p-0.5 ml-auto"
                    title="Board filter — restrict retrieval to one board"
                  >
                    {BOARDS.map(b => (
                      <button
                        key={b.id}
                        title={b.desc}
                        onClick={() => setBoardFilter(b.id)}
                        className={`px-3 py-1 text-[11px] font-medium rounded-full transition-all duration-150 ${
                          boardFilter === b.id
                            ? "bg-[var(--text)] text-[var(--bg)] shadow-sm"
                            : "text-[var(--text-3)] hover:text-[var(--text-2)]"
                        }`}
                      >
                        {b.label}
                      </button>
                    ))}
                  </div>
                )}
                {showLanguageToggle && (
                  <div
                    className={`flex items-center gap-0.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-full p-0.5 ${showBoardToggle ? "" : "ml-auto"}`}
                    title="Answer language"
                  >
                    {LANGUAGE_MODES.map(l => (
                      <button
                        key={l.id}
                        title={l.desc}
                        onClick={() => setLanguageMode(l.id)}
                        className={`px-3 py-1 text-[11px] font-medium rounded-full transition-all duration-150 ${
                          languageMode === l.id
                            ? "bg-[var(--text)] text-[var(--bg)] shadow-sm"
                            : "text-[var(--text-3)] hover:text-[var(--text-2)]"
                        }`}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Input box */}
              <div className="flex items-end gap-2 bg-[var(--bg-input)] border border-[var(--border)] rounded-xl px-4 py-3 transition-all focus-within:border-[var(--border-hi)]">
                <textarea
                  ref={inputRef}
                  className="flex-1 resize-none text-[14px] text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none bg-transparent min-h-[22px] max-h-32"
                  placeholder={config.inputPlaceholder}
                  rows={1}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={loading}
                />
                <button
                  onClick={() => {
                    if (loading && abortRef.current) { abortRef.current.abort(); return }
                    send(input)
                  }}
                  disabled={!input.trim() && !loading}
                  className="w-7 h-7 shrink-0 rounded-full flex items-center justify-center transition-all disabled:opacity-30"
                  style={{ backgroundColor: accent }}
                  aria-label={loading ? "Stop" : "Send"}
                >
                  {loading ? (
                    <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                    </svg>
                  )}
                </button>
              </div>

              <p className="text-center text-[10px] text-[var(--text-4)] mt-1.5">
                Enter ↵ to send · Shift+Enter for newline
              </p>
            </div>
          </div>
        </div>

        {/* ── Sources panel (desktop) ── */}
        {activeResponse && (
          <div className="hidden md:flex w-80 lg:w-96 shrink-0 border-l border-[var(--border)] flex-col overflow-hidden bg-[var(--bg)]">
            <ChunksPanel
              chunks={activeResponse.retrieved_chunks}
              config={config}
              accent={accent}
              onClose={() => setActiveSources(null)}
            />
          </div>
        )}
      </div>

      {/* Modals */}
      {showSettings  && <SettingsPanel settings={settings} onSave={s => { setSettings(s); saveSettings(s) }} onClose={() => setShowSettings(false)} />}
      {showTryEval   && <TryEvalExportModal demo={demo} config={config} settings={settings} mode={mode} onClose={() => setShowTryEval(false)} />}
      {showCorpus    && <CorpusModal demo={demo} config={config} onClose={() => setShowCorpus(false)} />}
      {showTeacher   && <TeacherToolsModal demo={demo} board={boardFilter} settings={settings} onClose={() => setShowTeacher(false)} />}
      {showDataset   && <DatasetModal demo={demo} config={config} onClose={() => setShowDataset(false)} />}
    </div>
  )
}
