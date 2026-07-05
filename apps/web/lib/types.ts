export interface RetrievedChunk {
  id: number
  doc_id: string
  doc_title?: string   // server-provided; use as display label when present
  section_ref: string
  content: string
  metadata?: Record<string, unknown>
  score: number
  rerank_score: number | null
  retrieval_boost?: number | null
  boost_reasons?: string[]
}

export interface Citation {
  section_ref: string
  doc_title: string
}

export interface QueryConfig {
  demo: string
  mode: string
  top_k: number
  top_n: number
  rerank: boolean
  gen_model: string
  reranker_model?: string
  embed_model: string
  prompt_version: string
  visibility?: string[]
  chapter_filter?: string | null
  query_intent?: Record<string, unknown>
}

export interface Usage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface Latency {
  condense_ms: number
  retrieve_ms: number
  rerank_ms: number
  generate_ms: number
  total_ms: number
}

export interface QueryResponse {
  answer: string
  retrieved_chunks: RetrievedChunk[]
  citations: Citation[]
  config: QueryConfig
  usage: Usage
  latency: Latency
  trace_id: string
}

export interface Turn {
  role: "user" | "assistant"
  content: string
}

export interface ChatMessage extends Turn {
  id: string
  response?: QueryResponse
  isLoading?: boolean
  error?: string
}

export type GenProvider = "openrouter" | "openai"

export interface Settings {
  openrouterKey: string
  cfAccountId: string
  cfGatewayId: string
  genProvider: GenProvider
  openaiKey: string
  openaiModel: string
}
