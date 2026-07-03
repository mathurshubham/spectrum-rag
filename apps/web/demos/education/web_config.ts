import type { DemoConfig } from "@/lib/demoConfig"

const config: DemoConfig = {
  demoId: "education",
  title: "Padhai — NCERT Class 10",
  shortTitle: "Padhai",
  icon: "📚",
  primaryColor: "violet",
  disclaimerChip: "Class 10 Social Science",
  subtitle: "History · Geography · Economics · Political Science — NCERT Class 10",
  about: "Padhai is grounded in 9 NCERT Class 10 Social Science chapters — three from History (The Rise of Nationalism in Europe, Nationalism in India, The Making of a Global World), two from Geography (Resources and Development; Forest and Wildlife Resources), two from Economics (Development; Sectors of the Indian Economy), and two from Political Science (Power Sharing; Federalism). It explains concepts in clear, age-appropriate language and cites the chapter section it draws from. It will not directly answer textbook exercise questions, and topics outside these specific chapters — including other subjects, other class levels, or general knowledge — are declined.",
  inputPlaceholder: "Ask about your Class 10 Social Science chapters…",
  suggestedQuestions: [
    { q: "Why did the non-cooperation movement start in India?",           icon: "🇮🇳" },
    { q: "What are renewable and non-renewable resources?",                icon: "🌿" },
    { q: "What is the difference between primary and tertiary sectors?",   icon: "📊" },
    { q: "What is power sharing and why is it important?",                 icon: "⚖" },
    { q: "What were the main causes of nationalism in Europe?",            icon: "🌍" },
    { q: "What is federalism?",                                            icon: "🏛" },
  ],
  docColors: {
    HIST_CH1_NATIONALISM_EUROPE: "bg-amber-50 text-amber-700 border-amber-200",
    HIST_CH2_NATIONALISM_INDIA:  "bg-orange-50 text-orange-700 border-orange-200",
    HIST_CH3_GLOBAL_WORLD:       "bg-red-50 text-red-700 border-red-200",
    GEO_CH1_RESOURCES:           "bg-green-50 text-green-700 border-green-200",
    GEO_CH2_FOREST_WILDLIFE:     "bg-emerald-50 text-emerald-700 border-emerald-200",
    ECON_CH1_DEVELOPMENT:        "bg-blue-50 text-blue-700 border-blue-200",
    ECON_CH2_SECTORS:            "bg-sky-50 text-sky-700 border-sky-200",
    CIVICS_CH1_POWER_SHARING:    "bg-violet-50 text-violet-700 border-violet-200",
    CIVICS_CH2_FEDERALISM:       "bg-purple-50 text-purple-700 border-purple-200",
  },
  refusalMarkers: [
    "cannot answer", "not in your indexed", "not in the indexed",
    "outside your ncert chapters", "not covered in the indexed",
    "check with your teacher", "not available in",
  ],
  guardMarkers: [],
  refusalBanner: "This is outside your indexed NCERT chapters. Check with your teacher or another reference.",
  guardBanner: "",
  datasets: [
    { label: "Golden" },
    { label: "TryEval Live",        version: "tryeval-live" },
    { label: "TryEval Calibration", version: "tryeval-calibration" },
  ],
}

export default config
