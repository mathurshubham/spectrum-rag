export interface SuggestedQuestion {
  q: string
  icon: string
}

export interface DatasetRef {
  label: string
  version?: string   // omitted → default golden set (insurance-dataset.csv)
}

export interface DemoConfig {
  demoId: string
  title: string
  shortTitle: string
  icon: string
  primaryColor: string   // Tailwind color name e.g. "indigo", "teal", "emerald"
  disclaimerChip: string
  subtitle: string
  about: string          // 2-4 sentence description shown on empty state — what corpus, what it can do, key guardrails
  inputPlaceholder: string
  suggestedQuestions: SuggestedQuestion[]
  docColors: Record<string, string>   // doc_id → Tailwind classes
  refusalMarkers: string[]
  guardMarkers: string[]
  refusalBanner: string
  guardBanner: string
  datasets?: DatasetRef[]   // eval datasets selectable in the Dataset modal; defaults to Golden only
}

/** Resolve per-demo config. Import from demos/{demoId}/web_config.ts */
export async function loadDemoConfig(demoId: string): Promise<DemoConfig | null> {
  try {
    // Dynamic imports from the demos directory tree
    const mod = await import(`../demos/${demoId}/web_config`)
    return (mod.default ?? mod) as DemoConfig
  } catch {
    return null
  }
}
