import type { DemoConfig } from "@/lib/demoConfig"

const config: DemoConfig = {
  demoId: "law",
  title: "Vidhi — Indian Legal RAG",
  shortTitle: "Vidhi",
  icon: "⚖",
  primaryColor: "indigo",
  disclaimerChip: "Not legal advice",
  subtitle: "BNS · BNSS · BSA · Constitution · Contract Act · CP 2019 · DPDP",
  about: "Vidhi is grounded in 7 central Indian statutes — the Bharatiya Nyaya Sanhita 2023 (criminal law), BNSS 2023 (criminal procedure), BSA 2023 (evidence), the Constitution of India, the Contract Act 1872, the Consumer Protection Act 2019, and the DPDP Act 2023. It also carries a repeal-mapping reference so queries about older laws (IPC, CrPC, Indian Evidence Act) are automatically cross-referenced to their current equivalents. Every answer cites the exact section it draws from, and the bot refuses to answer when the relevant provision is not in the indexed corpus.",
  inputPlaceholder: "Ask about Indian law…",
  suggestedQuestions: [
    { q: "What is the punishment for murder under BNS 2023?",       icon: "⚖" },
    { q: "What are the fundamental rights under the Constitution?",  icon: "📜" },
    { q: "What constitutes a valid contract under the Contract Act?", icon: "📋" },
    { q: "What are consumer rights under the CP Act 2019?",          icon: "🛒" },
    { q: "What does IPC Section 302 say?",                           icon: "🔍" },
    { q: "What is personal data under the DPDP Act 2023?",           icon: "🔒" },
  ],
  docColors: {
    BNS_2023:                 "bg-red-50 text-red-700 border-red-200",
    BNSS_2023:                "bg-orange-50 text-orange-700 border-orange-200",
    BSA_2023:                 "bg-yellow-50 text-yellow-700 border-yellow-200",
    CONSTITUTION:             "bg-blue-50 text-blue-700 border-blue-200",
    CONSUMER_PROTECTION_2019: "bg-green-50 text-green-700 border-green-200",
    CONTRACT_ACT_1872:        "bg-purple-50 text-purple-700 border-purple-200",
    DPDP_2023:                "bg-pink-50 text-pink-700 border-pink-200",
    LAW_MAPPINGS:             "bg-slate-50 text-slate-700 border-slate-200",
  },
  refusalMarkers: [
    "cannot answer", "i cannot answer", "not in the available",
    "please consult", "does not contain", "cannot be cited",
    "not part of", "not indexed", "outside the statutes", "not available in",
  ],
  guardMarkers: [
    "repealed statute", "repealed law", "ipc", "crpc",
    "indian evidence act", "consumer protection act 1986",
  ],
  refusalBanner: "Insufficient context — this question falls outside the indexed corpus.",
  guardBanner: "References repealed law — current statute shown below.",
  datasets: [
    { label: "Golden" },
    { label: "TryEval Live",        version: "tryeval-live" },
    { label: "TryEval Calibration", version: "tryeval-calibration" },
  ],
}

export default config
