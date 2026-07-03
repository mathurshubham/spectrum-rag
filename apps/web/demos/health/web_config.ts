import type { DemoConfig } from "@/lib/demoConfig"

const config: DemoConfig = {
  demoId: "health",
  title: "Vaidya — Health Information",
  shortTitle: "Vaidya",
  icon: "⚕",
  primaryColor: "emerald",
  disclaimerChip: "Not medical advice · Call 112 in emergency",
  subtitle: "WHO Fact Sheets — Diabetes · Hypertension · TB · Dengue · Malaria · Mental Health · Anaemia · COVID-19",
  about: "Vaidya is grounded in 8 WHO public health fact sheets covering diabetes, hypertension, tuberculosis, dengue, malaria, mental disorders, anaemia, and COVID-19. It provides general health information only — it will not diagnose conditions, advise on dosages, or prescribe medication. For emergencies (chest pain, difficulty breathing, severe bleeding, suicidal thoughts) it immediately directs you to call 112 or your local emergency number. All content is sourced from the World Health Organization and is not a substitute for consultation with a qualified healthcare professional.",
  inputPlaceholder: "Ask about symptoms, prevention, or health conditions…",
  suggestedQuestions: [
    { q: "What are the symptoms of diabetes?",                     icon: "🩸" },
    { q: "How can hypertension be prevented?",                     icon: "❤" },
    { q: "What are the symptoms of dengue?",                       icon: "🦟" },
    { q: "How is tuberculosis transmitted?",                        icon: "🫁" },
    { q: "What are common symptoms of anaemia?",                   icon: "💊" },
    { q: "How is malaria prevented?",                              icon: "🌿" },
  ],
  docColors: {
    DIABETES_WHO:     "bg-blue-50 text-blue-700 border-blue-200",
    HYPERTENSION_WHO: "bg-red-50 text-red-700 border-red-200",
    TUBERCULOSIS_WHO: "bg-amber-50 text-amber-700 border-amber-200",
    DENGUE_WHO:       "bg-orange-50 text-orange-700 border-orange-200",
    MALARIA_WHO:      "bg-green-50 text-green-700 border-green-200",
    MENTAL_HEALTH_WHO: "bg-violet-50 text-violet-700 border-violet-200",
    ANAEMIA_WHO:      "bg-pink-50 text-pink-700 border-pink-200",
    COVID19_WHO:      "bg-slate-50 text-slate-700 border-slate-200",
  },
  refusalMarkers: [
    "cannot answer", "not covered in the indexed", "not in the indexed",
    "not available in", "outside the scope", "please consult",
  ],
  guardMarkers: [
    "emergency", "call 112", "call 911",
    "seek immediate", "immediate medical",
  ],
  refusalBanner: "This is not covered in the indexed health information. Please consult a qualified healthcare professional.",
  guardBanner: "If this is an emergency, call 112 (India) or your local emergency number immediately.",
  datasets: [
    { label: "Golden" },
    { label: "TryEval Live",        version: "tryeval-live" },
    { label: "TryEval Calibration", version: "tryeval-calibration" },
  ],
}

export default config
