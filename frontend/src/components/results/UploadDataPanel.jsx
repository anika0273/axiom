import { useRef, useState } from "react"
import Papa from "papaparse"
import { CheckCircle2, UploadCloud, XCircle } from "lucide-react"
import Button from "../ui/Button"
import Card from "../ui/Card"
import { API_BASE } from '../../config/api'
const CHUNK_SIZE = 5000
const MAX_BYTES = 52_428_800 // 50 MB

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}

function parseCSVAsync(file, options = {}) {
  return new Promise((resolve, reject) => {
    Papa.parse(file, { ...options, complete: resolve, error: reject })
  })
}

async function validateFile(file) {
  // 1. File size
  if (file.size > MAX_BYTES) {
    return {
      valid: false,
      errors: [
        "File is too large. Maximum size is 50MB. Consider uploading a sample of your data.",
      ],
      warnings: [],
    }
  }

  // 2. Parse preview
  let parsed
  try {
    parsed = await parseCSVAsync(file, {
      header: true,
      skipEmptyLines: true,
      preview: 1000,
    })
  } catch {
    return { valid: false, errors: ["Could not parse the file as CSV."], warnings: [] }
  }

  const rows = parsed.data ?? []
  const headers = parsed.meta?.fields ?? []
  const lowerHeaders = headers.map((h) => h.toLowerCase())

  // 3. Required columns
  const REQUIRED = ["subject_id", "variant", "outcome"]
  const missing = REQUIRED.filter((col) => !lowerHeaders.includes(col))
  if (missing.length > 0) {
    return {
      valid: false,
      errors: [
        `Missing required columns: ${missing.join(", ")}. Your CSV must include: subject_id, variant, outcome.`,
      ],
      warnings: [],
    }
  }

  // Resolve actual column names (preserving original casing)
  const variantCol  = headers.find((h) => h.toLowerCase() === "variant")
  const outcomeCol  = headers.find((h) => h.toLowerCase() === "outcome")
  const subjectCol  = headers.find((h) => h.toLowerCase() === "subject_id")

  // 4. Empty file
  if (rows.length === 0) {
    return {
      valid: false,
      errors: [
        "The CSV file is empty. Please upload a file with at least 20 rows (10 per variant).",
      ],
      warnings: [],
    }
  }

  // 5. Variant values
  const uniqueVariants = new Set(rows.map((r) => String(r[variantCol] ?? "").trim()))
  const badVariants = [...uniqueVariants].filter((v) => v !== "0" && v !== "1")
  if (badVariants.length > 0) {
    return {
      valid: false,
      errors: [
        `Invalid variant values found: ${badVariants.join(", ")}. The variant column must contain only 0 (control) or 1 (treatment).`,
      ],
      warnings: [],
    }
  }

  // 6. Outcome numeric
  const nonNumeric = rows.filter((r) => isNaN(parseFloat(r[outcomeCol])))
  if (nonNumeric.length / rows.length > 0.05) {
    return {
      valid: false,
      errors: [
        "The outcome column contains non-numeric values. Outcome must be a number (e.g. 1, 0, 45.50).",
      ],
      warnings: [],
    }
  }

  // 7. Minimum rows (warning only)
  const warnings = []
  const controlRows   = rows.filter((r) => String(r[variantCol] ?? "").trim() === "0")
  const treatmentRows = rows.filter((r) => String(r[variantCol] ?? "").trim() === "1")
  if (controlRows.length < 10) {
    warnings.push(
      `Only ${controlRows.length} control rows found in the preview. Make sure your full file has at least 10 rows per variant.`,
    )
  }
  if (treatmentRows.length < 10) {
    warnings.push(
      `Only ${treatmentRows.length} treatment rows found in the preview. Make sure your full file has at least 10 rows per variant.`,
    )
  }

  const extraColumns = headers.filter(
    (h) => !REQUIRED.includes(h.toLowerCase()),
  )

  return {
    valid: true,
    errors: [],
    warnings,
    summary: {
      totalRows: rows.length,
      controlRows: controlRows.length,
      treatmentRows: treatmentRows.length,
      columns: headers,
      extraColumns,
      sampleRow: rows[0] ?? null,
      subjectCol,
      variantCol,
      outcomeCol,
    },
  }
}

// ── sub-components ────────────────────────────────────────────────────────────

function ColNamePill({ name, color }) {
  return (
    <span
      style={{
        fontFamily: "DM Mono, monospace",
        fontSize: 11,
        color,
        background:
          color === "var(--color-accent-green)"
            ? "rgba(16,185,129,0.12)"
            : "rgba(59,130,246,0.12)",
        borderRadius: 4,
        padding: "1px 6px",
        marginRight: 4,
      }}
    >
      {name}
    </span>
  )
}

function ProgressBar({ value }) {
  return (
    <div
      style={{
        height: 4,
        background: "var(--color-bg-elevated)",
        borderRadius: 2,
        overflow: "hidden",
        marginTop: 8,
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${value}%`,
          background: "var(--color-accent-blue)",
          borderRadius: 2,
          transition: "width 0.3s ease",
        }}
      />
    </div>
  )
}

// ── main component ────────────────────────────────────────────────────────────

export default function UploadDataPanel({ experimentId, experiment, onUploadComplete }) {
  const [isOpen, setIsOpen] = useState(false)
  const [file, setFile] = useState(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [validationState, setValidationState] = useState("idle")
  const [validationErrors, setValidationErrors] = useState([])
  const [validationWarnings, setValidationWarnings] = useState([])
  const [validationSummary, setValidationSummary] = useState(null)
  const [uploadState, setUploadState] = useState("idle")
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedChunks, setUploadedChunks] = useState(0)
  const [totalChunks, setTotalChunks] = useState(0)
  const [uploadError, setUploadError] = useState(null)

  const fileInputRef = useRef(null)
  const isProportion = (experiment?.experiment_type ?? "proportion") === "proportion"

  function resetPanel() {
    setFile(null)
    setIsDragOver(false)
    setValidationState("idle")
    setValidationErrors([])
    setValidationWarnings([])
    setValidationSummary(null)
    setUploadState("idle")
    setUploadProgress(0)
    setUploadedChunks(0)
    setTotalChunks(0)
    setUploadError(null)
  }

  function handleOpen() {
    setIsOpen(true)
  }

  function handleCancel() {
    setIsOpen(false)
    resetPanel()
  }

  async function handleFile(selectedFile) {
    if (!selectedFile) return
    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null)
      setValidationState("error")
      setValidationErrors(["Only CSV files are accepted. Please select a .csv file."])
      return
    }
    setFile(selectedFile)
    setValidationState("validating")
    setValidationErrors([])
    setValidationWarnings([])
    setValidationSummary(null)

    const result = await validateFile(selectedFile)
    if (result.valid) {
      setValidationState("valid")
      setValidationSummary(result.summary)
      setValidationWarnings(result.warnings ?? [])
    } else {
      setValidationState("error")
      setValidationErrors(result.errors)
    }
  }

  function onInputChange(e) {
    handleFile(e.target.files?.[0] ?? null)
    // Reset input value so re-selecting same file re-triggers onChange
    e.target.value = ""
  }

  function onDragOver(e) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function onDragLeave(e) {
    e.preventDefault()
    setIsDragOver(false)
  }

  function onDrop(e) {
    e.preventDefault()
    setIsDragOver(false)
    handleFile(e.dataTransfer.files?.[0] ?? null)
  }

  async function handleUpload() {
    if (!file || validationState !== "valid") return
    setUploadState("uploading")
    setUploadProgress(0)
    setUploadError(null)

    try {
      // Full parse — no preview limit
      const parsed = await parseCSVAsync(file, { header: true, skipEmptyLines: true })
      const allRows = parsed.data ?? []
      const headers = parsed.meta?.fields ?? []

      // Split into chunks
      const chunks = []
      for (let i = 0; i < allRows.length; i += CHUNK_SIZE) {
        chunks.push(allRows.slice(i, i + CHUNK_SIZE))
      }
      setTotalChunks(chunks.length)

      // Upload each chunk
      for (let i = 0; i < chunks.length; i++) {
        const csvString = Papa.unparse({ fields: headers, data: chunks[i] })
        const blob = new Blob([csvString], { type: "text/csv" })
        const chunkFile = new File([blob], file.name, { type: "text/csv" })

        const formData = new FormData()
        formData.append("file", chunkFile)

        const res = await fetch(
          `${API_BASE}/api/v1/experiments/${experimentId}/upload-data`,
          { method: "POST", body: formData },
        )

        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(
            body?.detail ?? body?.error?.message ?? `Upload failed (${res.status})`,
          )
        }

        setUploadedChunks(i + 1)
        setUploadProgress(Math.round(((i + 1) / chunks.length) * 80))
      }

      // Analyze
      setUploadState("analyzing")
      setUploadProgress(85)

      const analyzeRes = await fetch(
        `${API_BASE}/api/v1/experiments/${experimentId}/analyze`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      )

      if (!analyzeRes.ok) {
        const body = await analyzeRes.json().catch(() => ({}))
        throw new Error(
          body?.error?.message ?? body?.detail ?? `Analysis failed (${analyzeRes.status})`,
        )
      }

      const analyzeBody = await analyzeRes.json()
      setUploadProgress(100)
      setUploadState("done")

      setTimeout(() => {
        onUploadComplete(analyzeBody.data)
      }, 1000)
    } catch (err) {
      setUploadState("error")
      setUploadError(err.message ?? "An unexpected error occurred.")
    }
  }

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        background: "var(--color-bg-card)",
        border: "1px solid var(--color-border-subtle)",
        borderLeft: "3px solid var(--color-accent-blue)",
        borderRadius: 10,
        overflow: "hidden",
        marginBottom: 20,
      }}
    >
      {/* Header row — always visible */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 20px",
          background: "var(--color-bg-elevated)",
        }}
      >
        <UploadCloud size={16} style={{ color: "var(--color-accent-blue)", flexShrink: 0 }} />
        <span style={{ fontSize: 13, color: "var(--color-text-secondary)", flexGrow: 1 }}>
          Upload Real Data
        </span>
        {!isOpen ? (
          <Button variant="secondary" size="sm" onClick={handleOpen}>
            Upload CSV →
          </Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        )}
      </div>

      {/* Expanded body */}
      {isOpen && (
        <div style={{ padding: "20px" }}>
          {/* SECTION 1 — Schema reminder */}
          <div
            style={{
              background: "var(--color-bg-elevated)",
              borderRadius: 6,
              padding: "12px 16px",
              marginBottom: 16,
            }}
          >
            <p
              style={{
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "var(--color-text-muted)",
                margin: "0 0 8px 0",
              }}
            >
              Required columns
            </p>
            {[
              { name: "subject_id", desc: "unique user identifier (e.g. user_123)" },
              { name: "variant",    desc: "0 for control, 1 for treatment" },
              {
                name: "outcome",
                desc: isProportion
                  ? "1 if converted, 0 if not"
                  : "numeric value (e.g. revenue, GMV)",
              },
            ].map((col) => (
              <div
                key={col.name}
                style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 4 }}
              >
                <span
                  style={{
                    fontFamily: "DM Mono, monospace",
                    fontSize: 12,
                    color: "var(--color-text-data)",
                    flexShrink: 0,
                  }}
                >
                  {col.name}
                </span>
                <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
                  — {col.desc}
                </span>
              </div>
            ))}
            <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: "10px 0 0" }}>
              Any additional numeric columns will be used as features for ML analysis.
            </p>
          </div>

          {/* SECTION 2 — Drop zone */}
          {uploadState === "idle" && (
            <>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                style={{
                  border: `2px dashed ${
                    isDragOver
                      ? "var(--color-accent-blue)"
                      : "var(--color-border-subtle)"
                  }`,
                  borderRadius: 8,
                  padding: "32px 24px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: isDragOver
                    ? "rgba(59,130,246,0.05)"
                    : "transparent",
                  transition: "border-color 0.15s, background 0.15s",
                  marginBottom: 16,
                }}
              >
                {file ? (
                  <>
                    <UploadCloud
                      size={28}
                      style={{ color: "var(--color-accent-blue)", margin: "0 auto 8px" }}
                    />
                    <p
                      style={{
                        fontSize: 13,
                        color: "var(--color-text-primary)",
                        margin: "0 0 4px",
                        fontWeight: 500,
                      }}
                    >
                      {file.name}
                    </p>
                    <p style={{ fontSize: 11, color: "var(--color-text-muted)", margin: 0 }}>
                      {fmtBytes(file.size)} · Click to change file
                    </p>
                  </>
                ) : (
                  <>
                    <UploadCloud
                      size={32}
                      style={{ color: "var(--color-text-muted)", margin: "0 auto 10px" }}
                    />
                    <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 6px" }}>
                      Drag and drop your CSV here, or click to browse
                    </p>
                    <p style={{ fontSize: 11, color: "var(--color-text-muted)", margin: 0 }}>
                      Max 50MB · CSV files only
                    </p>
                  </>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                style={{ display: "none" }}
                onChange={onInputChange}
              />
            </>
          )}

          {/* SECTION 3 — Validation result */}
          {validationState === "validating" && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 16px",
                background: "var(--color-bg-elevated)",
                borderRadius: 8,
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  border: "2px solid var(--color-accent-blue)",
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "spin 0.7s linear infinite",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                Checking your file...
              </span>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {validationState === "error" && (
            <div
              style={{
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.25)",
                borderRadius: 8,
                padding: "14px 16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
                <XCircle size={16} style={{ color: "var(--color-accent-red)", flexShrink: 0, marginTop: 1 }} />
                <div style={{ flexGrow: 1 }}>
                  {validationErrors.map((err, i) => (
                    <p
                      key={i}
                      style={{
                        fontSize: 13,
                        color: "var(--color-accent-red)",
                        margin: i < validationErrors.length - 1 ? "0 0 6px" : 0,
                      }}
                    >
                      {err}
                    </p>
                  ))}
                </div>
              </div>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: 0 }}>
                Fix these issues and select the file again.
              </p>
            </div>
          )}

          {validationState === "valid" && uploadState === "idle" && validationSummary && (
            <div
              style={{
                background: "rgba(16,185,129,0.07)",
                border: "1px solid rgba(16,185,129,0.25)",
                borderRadius: 8,
                padding: "14px 16px",
                marginBottom: 14,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <CheckCircle2 size={16} style={{ color: "var(--color-accent-green)", flexShrink: 0 }} />
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-accent-green)" }}>
                  File looks good. Ready to upload.
                </span>
              </div>

              {/* Summary */}
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.8 }}>
                <p style={{ margin: "0 0 4px" }}>
                  Previewed first 1,000 rows —{" "}
                  <strong style={{ color: "var(--color-text-primary)" }}>
                    {validationSummary.controlRows.toLocaleString()}
                  </strong>{" "}
                  control,{" "}
                  <strong style={{ color: "var(--color-text-primary)" }}>
                    {validationSummary.treatmentRows.toLocaleString()}
                  </strong>{" "}
                  treatment
                </p>

                <p style={{ margin: "0 0 4px", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 2 }}>
                  <span style={{ marginRight: 4 }}>Columns found:</span>
                  {["subject_id", "variant", "outcome"].map((c) => (
                    <ColNamePill key={c} name={c} color="var(--color-accent-green)" />
                  ))}
                  {validationSummary.extraColumns.map((c) => (
                    <ColNamePill key={c} name={c} color="var(--color-accent-blue)" />
                  ))}
                </p>

                {validationSummary.sampleRow && (
                  <p style={{ margin: "0 0 8px", fontFamily: "DM Mono, monospace", fontSize: 11, color: "var(--color-text-muted)" }}>
                    Sample row: subject_id=
                    {String(
                      validationSummary.sampleRow[validationSummary.subjectCol] ?? "?",
                    )}{" "}
                    variant=
                    {String(
                      validationSummary.sampleRow[validationSummary.variantCol] ?? "?",
                    )}{" "}
                    outcome=
                    {String(
                      validationSummary.sampleRow[validationSummary.outcomeCol] ?? "?",
                    )}
                  </p>
                )}

                {validationSummary.extraColumns.length > 0 ? (
                  <p
                    style={{
                      margin: 0,
                      fontSize: 12,
                      color: "var(--color-accent-blue)",
                    }}
                  >
                    ✓ {validationSummary.extraColumns.length} feature column
                    {validationSummary.extraColumns.length !== 1 ? "s" : ""} found — ML
                    analysis will use these for segment and treatment effect discovery.
                  </p>
                ) : (
                  <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)" }}>
                    No feature columns detected. Upload will work, but ML analysis (segment
                    discovery, treatment effect) will be limited. Consider adding optional
                    columns from the schema above.
                  </p>
                )}

                {validationWarnings.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {validationWarnings.map((w, i) => (
                      <p
                        key={i}
                        style={{ margin: "4px 0 0", fontSize: 12, color: "var(--color-accent-amber)" }}
                      >
                        ⚠ {w}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ marginTop: 14 }}>
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleUpload}
                  style={{ width: "100%" }}
                >
                  Upload and Analyze →
                </Button>
              </div>
            </div>
          )}

          {/* Upload progress */}
          {(uploadState === "uploading" || uploadState === "analyzing" || uploadState === "done") && (
            <div
              style={{
                background: "var(--color-bg-elevated)",
                borderRadius: 8,
                padding: "14px 16px",
              }}
            >
              <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>
                {uploadState === "uploading" &&
                  `Uploading... ${uploadProgress}%${
                    totalChunks > 1
                      ? ` (${uploadedChunks} of ${totalChunks} batches)`
                      : ""
                  }`}
                {uploadState === "analyzing" && "Running analysis..."}
                {uploadState === "done" && "Complete! Reloading results..."}
              </p>
              <ProgressBar value={uploadProgress} />
            </div>
          )}

          {/* Upload error */}
          {uploadState === "error" && uploadError && (
            <div
              style={{
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.25)",
                borderRadius: 8,
                padding: "14px 16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
                <XCircle size={16} style={{ color: "var(--color-accent-red)", flexShrink: 0, marginTop: 1 }} />
                <p style={{ fontSize: 13, color: "var(--color-accent-red)", margin: 0 }}>
                  {uploadError}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setUploadState("idle")
                  setUploadError(null)
                  setUploadProgress(0)
                }}
              >
                Try again
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
