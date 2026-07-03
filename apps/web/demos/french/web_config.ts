import type { DemoConfig } from "@/lib/demoConfig"

const config: DemoConfig = {
  demoId: "french",
  title: "Bonjour — Multi-board French Study",
  shortTitle: "Bonjour",
  icon: "🇫🇷",
  primaryColor: "blue",
  disclaimerChip: "CBSE 9–10 · IB DP",
  subtitle: "Entre Jeunes (CBSE 9 & 10) · IB DP French B (Oxford, themes 1–10)",
  about: "Bonjour is grounded in French textbooks across multiple boards. For CBSE classes 9 and 10 it indexes Entre Jeunes (A1–A2 level). For IB Diploma Programme French B (grades 11–12) it indexes the Oxford Course Book covering all five prescribed themes (Identités, Expériences, Ingéniosité humaine, Organisation sociale, Partage de la planète) at B1–B2 level. Answers are returned in French, English, or bilingual based on the toggle in the chat. The bot cites the exact lesson/section it draws from, refuses topics outside the indexed books, and never solves exercise problems — it explains the underlying concept and points to the section.",
  inputPlaceholder: "Posez votre question en français ou en anglais…",
  suggestedQuestions: [
    { q: "Comment se présenter en français ?",                             icon: "👋" },
    { q: "Quelle est la différence entre 'avoir' et 'être' ?",             icon: "📝" },
    { q: "Explain the passé composé tense with an example from the book", icon: "⏳" },
    { q: "Qu'est-ce que l'éco-citoyenneté ?",                              icon: "🌍" },
    { q: "Vocabulary related to family in CBSE Class 9",                   icon: "👨‍👩‍👧" },
    { q: "What are the main themes in the IB DP French B course?",        icon: "📖" },
  ],
  docColors: {
    CBSE_9_ENTREJEUNES:        "bg-blue-50 text-blue-700 border-blue-200",
    CBSE_10_ENTREJEUNES:       "bg-sky-50 text-sky-700 border-sky-200",
    IB_DP_OXFORD_IDENTITES:    "bg-rose-50 text-rose-700 border-rose-200",
    IB_DP_OXFORD_EXPERIENCES:  "bg-amber-50 text-amber-700 border-amber-200",
    IB_DP_OXFORD_INGENIOSITE:  "bg-violet-50 text-violet-700 border-violet-200",
    IB_DP_OXFORD_ORG_SOCIALE:  "bg-emerald-50 text-emerald-700 border-emerald-200",
    IB_DP_OXFORD_PARTAGE:      "bg-teal-50 text-teal-700 border-teal-200",
  },
  refusalMarkers: [
    "cannot answer", "i cannot answer", "je ne peux pas répondre",
    "not in your indexed", "not in the indexed",
    "outside your", "outside the indexed",
    "check with your teacher", "consultez votre professeur",
    "not available in",
  ],
  guardMarkers: [],
  refusalBanner: "This is outside your indexed French textbooks. Check with your teacher or another reference.",
  guardBanner: "",
  datasets: [
    { label: "Golden" },
    { label: "TryEval Live",        version: "tryeval-live" },
    { label: "TryEval Calibration", version: "tryeval-calibration" },
  ],
}

export default config
