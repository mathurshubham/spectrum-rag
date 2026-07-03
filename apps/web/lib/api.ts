import type {
  QueryResponse,
  RetrievedChunk,
  Citation,
  QueryConfig,
  Usage,
  Latency,
  Turn,
  Settings,
} from "./types"

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type RetrievalMode = "hybrid" | "vanilla" | "bm25" | "hyde"
export type LanguageMode = "fr" | "en" | "bilingual"
export type BoardFilter = "cbse" | "ib" | "all"

export async function postQuery(
  demo: string,
  q: string,
  history: Turn[],
  settings: Settings,
  mode: RetrievalMode = "hybrid",
  signal?: AbortSignal,
  languageMode?: LanguageMode,
  board?: BoardFilter,
): Promise<QueryResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-OpenRouter-Key": settings.openrouterKey,
  }

  const params = new URLSearchParams({ mode })
  if (settings.cfAccountId) params.set("cf_account_id", settings.cfAccountId)
  if (settings.cfGatewayId) params.set("cf_gateway_id", settings.cfGatewayId)
  if (board && board !== "all") params.set("board", board)

  const body: Record<string, unknown> = { q, history }
  if (languageMode) body.language_mode = languageMode

  const resp = await fetch(`${API_URL}/api/${demo}/query?${params}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API ${resp.status}: ${text}`)
  }

  return resp.json() as Promise<QueryResponse>
}

export interface StreamMeta {
  retrieved_chunks: RetrievedChunk[]
  citations: Citation[]
  config: QueryConfig
  trace_id: string
}

export interface StreamCallbacks {
  onMeta: (meta: StreamMeta) => void
  onDelta: (text: string) => void
  onDone: (final: { usage: Usage; latency: Latency }) => void
  onError?: (message: string) => void
}

export async function postQueryStream(
  demo: string,
  q: string,
  history: Turn[],
  settings: Settings,
  cb: StreamCallbacks,
  mode: RetrievalMode = "hybrid",
  signal?: AbortSignal,
  languageMode?: LanguageMode,
  board?: BoardFilter,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-OpenRouter-Key": settings.openrouterKey,
  }

  const params = new URLSearchParams({ mode })
  if (settings.cfAccountId) params.set("cf_account_id", settings.cfAccountId)
  if (settings.cfGatewayId) params.set("cf_gateway_id", settings.cfGatewayId)
  if (board && board !== "all") params.set("board", board)

  const body: Record<string, unknown> = { q, history }
  if (languageMode) body.language_mode = languageMode

  const resp = await fetch(`${API_URL}/api/${demo}/query/stream?${params}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  })

  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API ${resp.status}: ${text}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep).trim()
      buffer = buffer.slice(sep + 2)
      if (!raw.startsWith("data:")) continue
      const payload = raw.slice(5).trim()
      if (!payload) continue

      const evt = JSON.parse(payload)
      if (evt.type === "meta") {
        cb.onMeta(evt as StreamMeta)
      } else if (evt.type === "delta") {
        cb.onDelta(evt.text as string)
      } else if (evt.type === "done") {
        cb.onDone({ usage: evt.usage, latency: evt.latency })
      } else if (evt.type === "error") {
        cb.onError?.(evt.message as string)
      }
    }
  }
}

export interface DemoMeta {
  id: string
  title: string
  description: string
}

export async function fetchDemos(): Promise<DemoMeta[]> {
  const resp = await fetch(`${API_URL}/api/demos`)
  if (!resp.ok) return []
  const data = await resp.json()
  return data.demos ?? []
}

export interface CorpusDocument {
  doc_id: string
  doc_title: string
  chunk_count: number
  section_count: number
}

export interface CorpusInfo {
  demo_id: string
  documents: CorpusDocument[]
  total_chunks: number
}

export async function fetchCorpus(demo: string): Promise<CorpusInfo | null> {
  const resp = await fetch(`${API_URL}/api/${demo}/corpus`)
  if (!resp.ok) return null
  return resp.json()
}

export interface DatasetRow {
  eval_context: string
  input: string
  output?: string
  expected_answer?: string
  expected_citations?: string
  expected_assertions?: string
  [key: string]: string | undefined   // generic (TryEval) datasets carry other columns
}

export interface DatasetInfo {
  demo_id: string
  version?: string
  columns: string[]
  rows: DatasetRow[]
  categories: Record<string, number>
  total: number
}

export async function fetchDataset(demo: string, version?: string): Promise<DatasetInfo | null> {
  const params = version ? `?version=${encodeURIComponent(version)}` : ""
  const resp = await fetch(`${API_URL}/api/${demo}/dataset${params}`)
  if (!resp.ok) return null
  return resp.json()
}

// ── Teacher dashboard — chapter outline ───────────────────────────────────────
export interface ChapterSection {
  section_ref: string
  type: string | null
  skill: string | null
  preview: string
}
export interface Chapter {
  id: string
  doc_id: string
  doc_title: string
  board: string | null
  level: string | null
  sections: ChapterSection[]
}
export interface ChapterOutline {
  demo_id: string
  chapters: Chapter[]
}

export async function fetchChapters(demo: string, board?: string): Promise<ChapterOutline | null> {
  const params = board && board !== "all" ? `?board=${board}` : ""
  const resp = await fetch(`${API_URL}/api/${demo}/chapters${params}`)
  if (!resp.ok) return null
  return resp.json()
}

// ── Question generator ───────────────────────────────────────────────────────
export interface GenQuestionsReq {
  chapter?: string
  board?: string
  grade?: string                 // CBSE "9" | "10"
  count?: number
  difficulty?: string
  question_types?: string[]
  language_mode?: LanguageMode
  mode?: "exam_paper" | "practice_set"
  teacher_notes?: string         // free-text teacher customization
}

export interface GenQuestionsResp {
  questions_markdown: string
  chunks_used: { section_ref: string; doc_title: string }[]
  config: Record<string, unknown>
  error?: string
}

export async function generateQuestions(
  demo: string,
  req: GenQuestionsReq,
  settings: Settings,
): Promise<GenQuestionsResp | null> {
  const resp = await fetch(`${API_URL}/api/${demo}/generate-questions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-OpenRouter-Key": settings.openrouterKey,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) return null
  return resp.json()
}
