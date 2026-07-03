"use client"

import { useEffect, useState } from "react"
import { fetchDataset, type DatasetInfo, type DatasetRow } from "@/lib/api"
import type { DemoConfig, DatasetRef } from "@/lib/demoConfig"

interface Props {
  demo: string
  config: DemoConfig
  onClose: () => void
}

type OracleCol = "expected_answer" | "expected_citations" | "expected_assertions"

const ORACLE_LABELS: Record<OracleCol, string> = {
  expected_answer:     "Answer",
  expected_citations:  "Citations",
  expected_assertions: "Assertions",
}

const ORACLE_HINTS: Record<OracleCol, string> = {
  expected_answer:     "Ideal answer — for LLM-judge scoring",
  expected_citations:  "Section refs that must appear in citations[]",
  expected_assertions: "Machine-checkable pass/fail flags",
}

// Two palettes: light = pastel tints, dark = deep tints
const CATEGORY_LIGHT: Record<string, { bg: string; text: string; border: string }> = {
  retrieval:       { bg: "#dbeafe", text: "#1e40af", border: "#93c5fd" },
  refusal:         { bg: "#fef3c7", text: "#92400e", border: "#fcd34d" },
  guard:           { bg: "#ffedd5", text: "#9a3412", border: "#fdba74" },
  edge:            { bg: "#ede9fe", text: "#5b21b6", border: "#c4b5fd" },
  leak:            { bg: "#fee2e2", text: "#991b1b", border: "#fca5a5" },
  freshness:       { bg: "#ccfbf1", text: "#115e59", border: "#5eead4" },
  conflict:        { bg: "#ffe4e6", text: "#9f1239", border: "#fda4af" },
  confidentiality: { bg: "#f5f5f4", text: "#44403c", border: "#d6d3d1" },
  tone:            { bg: "#dcfce7", text: "#14532d", border: "#86efac" },
  escalation:      { bg: "#fce7f3", text: "#9d174d", border: "#f9a8d4" },
}

const CATEGORY_DARK: Record<string, { bg: string; text: string; border: string }> = {
  retrieval:       { bg: "#1e3a5f", text: "#93c5fd", border: "#1d4ed8" },
  refusal:         { bg: "#451a03", text: "#fcd34d", border: "#b45309" },
  guard:           { bg: "#431407", text: "#fb923c", border: "#c2410c" },
  edge:            { bg: "#2e1065", text: "#c4b5fd", border: "#7c3aed" },
  leak:            { bg: "#450a0a", text: "#fca5a5", border: "#dc2626" },
  freshness:       { bg: "#042f2e", text: "#5eead4", border: "#0d9488" },
  conflict:        { bg: "#4c0519", text: "#fda4af", border: "#e11d48" },
  confidentiality: { bg: "#1c1917", text: "#a8a29e", border: "#57534e" },
  tone:            { bg: "#052e16", text: "#86efac", border: "#16a34a" },
  escalation:      { bg: "#500724", text: "#f9a8d4", border: "#db2777" },
}

function categoryStyle(cat: string, isDark: boolean) {
  const map = isDark ? CATEGORY_DARK : CATEGORY_LIGHT
  return map[cat] ?? (isDark
    ? { bg: "#1c1c1c", text: "#a3a3a3", border: "#3f3f3f" }
    : { bg: "#f5f5f5", text: "#525252", border: "#d4d4d4" })
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n) + "…" : s
}

const BOM = "﻿"
// RFC-quote a field AND collapse embedded newlines to spaces. TryEval's importer splits on
// \n BEFORE tokenizing quotes, so a raw newline inside a field corrupts the row — this keeps
// every field on one physical line. Quotes are doubled ("") to match its escaping.
const esc = (v: string | undefined) =>
  '"' + (v ?? "").replace(/\r?\n/g, " ").replace(/"/g, '""') + '"'

// bom: prepend a UTF-8 BOM (nice for Excel). MUST be false for TryEval uploads — a BOM
// glues onto the first header ("﻿input" != "input") and breaks its required-column
// detection. Fields are RFC-quoted (wrapped + doubled quotes) so commas/quotes survive.
function saveCSV(csv: string, filename: string, bom: boolean) {
  const blob = new Blob([(bom ? BOM : "") + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function downloadCSV(rows: DatasetRow[], oracleCol: OracleCol, filename: string) {
  const header = ["eval_context", "input", "output", "expected_output"].map(esc).join(",")
  const body = rows.map(r => [r.eval_context, r.input, r.output, r[oracleCol]].map(esc).join(",")).join("\n")
  saveCSV(header + "\n" + body, filename, true)
}

// Generic (TryEval) datasets: raw columns/rows verbatim, no BOM, so the file is directly
// uploadable to TryEval (canonical headers input/eval_context/expected_output[/output]).
function downloadRaw(columns: string[], rows: DatasetRow[], filename: string) {
  const header = columns.map(esc).join(",")
  const body = rows.map(r => columns.map(c => esc(r[c])).join(",")).join("\n")
  saveCSV(header + "\n" + body, filename, false)
}

const DEFAULT_DATASETS: DatasetRef[] = [{ label: "Golden" }]

export function DatasetModal({ demo, config, onClose }: Props) {
  const datasets = config.datasets ?? DEFAULT_DATASETS
  const [selected, setSelected]           = useState(0)
  const [dataset, setDataset]             = useState<DatasetInfo | null>(null)
  const [loading, setLoading]             = useState(true)
  const [selectedCats, setSelectedCats]   = useState<Set<string>>(new Set())
  const [oracleCol, setOracleCol]         = useState<OracleCol>("expected_answer")
  const [isDark, setIsDark]               = useState(false)

  useEffect(() => {
    const check = () => setIsDark(document.documentElement.getAttribute("data-theme") === "dark")
    check()
    const obs = new MutationObserver(check)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    let live = true
    fetchDataset(demo, datasets[selected]?.version).then(d => {
      if (!live) return
      setDataset(d ?? null)
      if (d) setSelectedCats(new Set(Object.keys(d.categories)))
      setLoading(false)
    })
    return () => { live = false }
  }, [demo, selected])   // eslint-disable-line react-hooks/exhaustive-deps

  function pickDataset(i: number) {
    if (i === selected) return
    setLoading(true); setDataset(null); setSelected(i)   // reset in handler, not effect
  }

  // Golden schema carries the oracle columns; TryEval sets don't → render generically.
  const isGolden = !!dataset?.columns.includes("expected_answer")
  const filteredRows = dataset
    ? (isGolden ? dataset.rows.filter(r => selectedCats.has(r.eval_context)) : dataset.rows)
    : []
  const previewRows  = filteredRows.slice(0, 10)
  const downloadName = `${demo}${datasets[selected]?.version ? "-" + datasets[selected].version : ""}-dataset.csv`

  function toggleCat(cat: string) {
    setSelectedCats(prev => { const n = new Set(prev); n.has(cat) ? n.delete(cat) : n.add(cat); return n })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
        style={{ boxShadow: "0 25px 50px rgba(0,0,0,0.5)" }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] shrink-0">
          <div>
            <h2 className="text-[14px] font-semibold text-[var(--text)]">Eval Dataset</h2>
            <p className="text-[11px] text-[var(--text-3)] mt-0.5">{config.title}</p>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--bg-card)] transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {datasets.length > 1 && (
            <div className="flex items-center gap-2">
              <label className="text-[11px] font-semibold text-[var(--text-3)]">Dataset</label>
              <select
                value={selected}
                onChange={e => pickDataset(Number(e.target.value))}
                className="text-[12px] rounded-lg bg-[var(--bg-input)] border border-[var(--border)] px-2.5 py-1.5 text-[var(--text)] hover:border-[var(--border-hi)] cursor-pointer"
              >
                {datasets.map((d, i) => <option key={i} value={i}>{d.label}</option>)}
              </select>
            </div>
          )}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-5 h-5 border border-[var(--border-hi)] border-t-[var(--accent)] rounded-full animate-spin" />
            </div>
          ) : !dataset ? (
            <p className="text-[13px] text-[var(--text-3)] text-center py-8">No dataset found for this demo.</p>
          ) : (
            <>
              {isGolden && (
              <>
              {/* Category filter pills */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-[var(--text-3)] mr-1">{dataset.total} questions</span>
                {Object.entries(dataset.categories).map(([cat, n]) => {
                  const s = categoryStyle(cat, isDark)
                  const active = selectedCats.has(cat)
                  return (
                    <button key={cat} onClick={() => toggleCat(cat)}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all"
                      style={active
                        ? { background: s.bg, color: s.text, borderColor: s.border }
                        : { background: "transparent", color: "var(--text-4)", borderColor: "var(--border)", textDecoration: "line-through" }
                      }>
                      {cat} {n}
                    </button>
                  )
                })}
              </div>

              {/* Oracle selector */}
              <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-3.5">
                <p className="text-[10px] font-semibold text-[var(--text-4)] uppercase tracking-wide mb-3">
                  expected_output column in download
                </p>
                <div className="flex gap-4 flex-wrap">
                  {(Object.keys(ORACLE_LABELS) as OracleCol[]).map(col => (
                    <label key={col} className="flex items-start gap-2 cursor-pointer">
                      <input type="radio" name="oracle" checked={oracleCol === col}
                        onChange={() => setOracleCol(col)}
                        className="mt-0.5" style={{ accentColor: "var(--accent)" }} />
                      <span>
                        <span className="text-[12px] font-medium"
                          style={{ color: oracleCol === col ? "var(--accent-text, var(--accent))" : "var(--text-2)" }}>
                          {ORACLE_LABELS[col]}
                        </span>
                        <span className="block text-[10px] text-[var(--text-3)] mt-0.5">{ORACLE_HINTS[col]}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              </>
              )}

              {/* Preview table */}
              <div>
                <p className="text-[11px] text-[var(--text-4)] mb-2">
                  Showing {previewRows.length} of {filteredRows.length} rows
                  {filteredRows.length !== dataset.total && ` (${dataset.total} total)`}
                </p>
                <div className="rounded-lg border border-[var(--border)] overflow-hidden overflow-x-auto">
                  <table className="w-full text-[12px]">
                    {isGolden ? (
                      <>
                        <thead className="bg-[var(--bg-card)] border-b border-[var(--border)]">
                          <tr>
                            <th className="text-left px-3 py-2 text-[10px] font-semibold text-[var(--text-3)] uppercase tracking-wide w-28">Category</th>
                            <th className="text-left px-3 py-2 text-[10px] font-semibold text-[var(--text-3)] uppercase tracking-wide">Input</th>
                            <th className="text-left px-3 py-2 text-[10px] font-semibold text-[var(--text-3)] uppercase tracking-wide w-52">
                              expected_output
                              <span className="ml-1 text-[var(--accent)] normal-case font-normal opacity-70">({ORACLE_LABELS[oracleCol]})</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]">
                          {previewRows.map((row, i) => {
                            const s = categoryStyle(row.eval_context, isDark)
                            return (
                              <tr key={i} className="hover:bg-[var(--bg-card)] transition-colors">
                                <td className="px-3 py-2.5">
                                  <span className="inline-block text-[10px] px-2 py-0.5 rounded-full border font-medium"
                                    style={{ background: s.bg, color: s.text, borderColor: s.border }}>
                                    {row.eval_context}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-[var(--text-2)]">{truncate(row.input, 70)}</td>
                                <td className="px-3 py-2.5 text-[var(--text-3)] font-mono text-[11px]">{truncate(row[oracleCol] ?? "", 55)}</td>
                              </tr>
                            )
                          })}
                          {filteredRows.length === 0 && (
                            <tr>
                              <td colSpan={3} className="px-3 py-6 text-center text-[var(--text-3)] text-[12px]">
                                No rows match the selected categories.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </>
                    ) : (
                      <>
                        <thead className="bg-[var(--bg-card)] border-b border-[var(--border)]">
                          <tr>
                            {dataset.columns.map(c => (
                              <th key={c} className="text-left px-3 py-2 text-[10px] font-semibold text-[var(--text-3)] uppercase tracking-wide font-mono whitespace-nowrap">{c}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]">
                          {previewRows.map((row, i) => (
                            <tr key={i} className="hover:bg-[var(--bg-card)] transition-colors align-top">
                              {dataset.columns.map(c => (
                                <td key={c} className="px-3 py-2.5 text-[var(--text-2)]">{truncate(row[c] ?? "", 60)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </>
                    )}
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 border-t border-[var(--border)] bg-[var(--bg-card)] shrink-0 flex items-center justify-between gap-3">
          <a href="https://www.tryeval.com" target="_blank" rel="noopener noreferrer"
            className="text-[11px] text-[var(--accent)] hover:underline">
            Open TryEval →
          </a>
          <button
            onClick={() => {
              if (!dataset) return
              if (isGolden) downloadCSV(filteredRows, oracleCol, downloadName)
              else downloadRaw(dataset.columns, filteredRows, downloadName)
            }}
            disabled={!dataset || filteredRows.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium bg-[var(--accent)] text-white hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download CSV {filteredRows.length > 0 && `(${filteredRows.length})`}
          </button>
        </div>
      </div>
    </div>
  )
}
