"use client";

import Image from "next/image";
import eagle from "../public/eagle.png";
import { useEffect, useState } from "react";

type RetrievedChunk = {
  chunk_id: string;
  text: string;
  company: string;
  fiscal_year: number;
  section: string;
  score: number;
};

type QueryResponse = {
  answer: string | null;
  persona: string | null;
  query_type: string | null;
  sources: string[];
  retrieved_chunks: RetrievedChunk[];
  cost_usd: number | null;
  latency_ms: number | null;
  langsmith_trace_id: string | null;
  status: string;
  ingested_entities: string[];
  ingestion_errors: string[];
  ingestion_details: { ticker: string; company: string; fiscal_year: number; filing_type: string; chunks: number }[];
  reasoning_trace: string[];
};

type UploadStatus = {
  document_id: string;
  status: "processing" | "ready" | "error";
  original_filename: string;
  company: string | null;
  ticker: string | null;
  fiscal_year: number | null;
  filing_type: string | null;
  sections_found: number | null;
  chunks_indexed: number | null;
  error_message: string | null;
};

type CorpusSummary = {
  companies: { ticker: string; company: string }[];
  filings_indexed: number;
  fiscal_year_min: number | null;
  fiscal_year_max: number | null;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const UPLOAD_POLL_INTERVAL_MS = 4000;
// Peste atat, query-ul aproape sigur a declansat ingestie live (un query normal
// dureaza ~10s): raspunsul e sincron, deci fara un semn explicit utilizatorul
// vede doar un spinner care nu se misca timp de minute.
const SLOW_QUERY_HINT_AFTER_SECONDS = 8;

const SUGGESTIONS = [
  "What are Apple's biggest risk factors this year?",
  "Compare R&D spending between Microsoft and Google",
  "What does Google's 10-K say about antitrust risk?",
];

// "Apple Inc." -> "Apple": generic corporate suffixes stripped for the sidebar
// pills, which show a friendly name, not the SEC registrant name.
const CORPORATE_SUFFIXES = new Set([
  "inc", "inc.", "corp", "corp.", "corporation", "co", "co.",
  "ltd", "ltd.", "holding", "holdings", "group", "plc", "llc",
]);
function shortCompanyName(company: string): string {
  const words = company.split(" ");
  while (words.length > 1 && CORPORATE_SUFFIXES.has(words[words.length - 1].toLowerCase())) {
    words.pop();
  }
  return words.join(" ");
}

function renderAnswerWithCitations(
  answer: string,
  chunks: RetrievedChunk[],
  onCiteClick: (chunkId: string) => void,
) {
  const parts = answer.split(/(\[[^\]]+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[([^\]]+)\]$/);
    if (match && chunks.some((c) => c.chunk_id === match[1])) {
      const chunkId = match[1];
      return (
        <button
          key={i}
          onClick={() => onCiteClick(chunkId)}
          className="mx-0.5 rounded bg-amber-100 px-1 text-xs font-medium text-amber-900 hover:bg-amber-200"
        >
          {part}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function DocumentPreviewCard({
  ticker,
  company,
  fiscalYear,
  filingType,
}: {
  ticker: string;
  company: string;
  fiscalYear: number;
  filingType: string;
}) {
  // Placeholder vizual de "pagina de document" (linii redactate) — nu exista
  // o miniatura reala a filing-ului de aratat, doar metadata reala de dedesubt.
  const lineWidths = ["85%", "60%", "92%", "70%", "45%"];
  return (
    <div className="rounded-lg border border-dashed border-sidebar-border p-2">
      <div className="label-caps mb-2">Found via dynamic ingestion</div>
      <div className="rounded bg-preview-card p-3">
        <div className="mb-2 h-2 w-2/3 rounded-sm bg-sidebar-muted/70" />
        {lineWidths.map((w, i) => (
          <div key={i} className="mb-1.5 h-1.5 rounded-sm bg-preview-line" style={{ width: w }} />
        ))}
      </div>
      <div className="mt-2 font-mono text-sm font-semibold">{ticker.toLowerCase()}.html</div>
      <div className="text-xs text-sidebar-muted">
        {company} · {filingType} · FY{fiscalYear}
      </div>
    </div>
  );
}

function ArrowUpIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M8 13V3M8 3L3.5 7.5M8 3L12.5 7.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [chunksOpen, setChunksOpen] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [highlightedChunk, setHighlightedChunk] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [corpus, setCorpus] = useState<CorpusSummary | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/corpus`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setCorpus)
      .catch(() => setCorpus(null)); // sidebar cade pe langa, restul UI-ului tot functioneaza
  }, []);

  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0);
      return;
    }
    const id = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => {
    if (highlightedChunk && chunksOpen) {
      document
        .getElementById(`chunk-${highlightedChunk}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightedChunk, chunksOpen]);

  useEffect(() => {
    if (!uploadStatus || uploadStatus.status !== "processing") return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/documents/${uploadStatus.document_id}/status`);
        if (!res.ok) throw new Error(`Backend responded with status ${res.status}`);
        const data: UploadStatus = await res.json();
        setUploadStatus(data);
      } catch {
        setUploadError("Could not reach the backend while checking upload status.");
      }
    }, UPLOAD_POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [uploadStatus]);

  async function handleFileUpload(file: File) {
    setUploadError(null);
    setUploadStatus(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_URL}/documents/upload`, { method: "POST", body: formData });
      if (!res.ok) throw new Error(`Backend responded with status ${res.status}`);
      const data: { document_id: string; status: string } = await res.json();
      setUploadStatus({
        document_id: data.document_id,
        status: "processing",
        original_filename: file.name,
        company: null,
        ticker: null,
        fiscal_year: null,
        filing_type: null,
        sections_found: null,
        chunks_indexed: null,
        error_message: null,
      });
    } catch (err) {
      const message =
        err instanceof TypeError
          ? "Could not reach the backend. Check that the API is running."
          : err instanceof Error
            ? err.message
            : "Unknown error while uploading the document.";
      setUploadError(message);
    }
  }

  async function submitQuery(overrideQuery?: string) {
    const questionText = overrideQuery ?? query;
    if (!questionText.trim() || loading) return;
    setQuery(questionText);
    setLoading(true);
    setError(null);
    setResult(null);
    setReasoningOpen(false);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_query: questionText }),
      });
      if (!res.ok) throw new Error(`Backend responded with status ${res.status}`);
      const data: QueryResponse = await res.json();
      setResult(data);
      setChunksOpen(false);
      setHighlightedChunk(null);
      // corpusul poate fi crescut de aceasta interogare (ingestie dinamica)
      if (data.ingested_entities.length > 0) {
        fetch(`${API_URL}/corpus`)
          .then((r) => (r.ok ? r.json() : null))
          .then(setCorpus)
          .catch(() => {});
      }
    } catch (err) {
      const message =
        err instanceof TypeError
          ? "Could not reach the backend. Check that the API is running."
          : err instanceof Error
            ? err.message
            : "Unknown error while querying the backend.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function handleCiteClick(chunkId: string) {
    setChunksOpen(true);
    setHighlightedChunk(chunkId);
  }

  async function copyTraceId() {
    if (!result?.langsmith_trace_id) return;
    await navigator.clipboard.writeText(result.langsmith_trace_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const showWelcome = !loading && !result && !error;

  return (
    <div className="flex h-screen overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="sidebar relative isolate flex w-80 shrink-0 flex-col gap-6 overflow-y-auto bg-sidebar p-6 text-white">
        <Image src={eagle} alt="" aria-hidden="true" className="eagle-watermark" unoptimized />
        <div>
          <h1 className="text-lg font-bold">Financial Report Analyzer</h1>
          <p className="mt-1 text-sm text-sidebar-muted">
            Persona-aware Q&amp;A over SEC 10-K / 10-Q filings
          </p>
        </div>

        <div>
          <div className="label-caps">Filings corpus</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(corpus?.companies ?? []).map((c) => (
              <span
                key={c.ticker}
                className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-medium text-zinc-900"
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
                {shortCompanyName(c.company)}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-sidebar-muted">
            {corpus
              ? `FY${corpus.fiscal_year_min}–FY${corpus.fiscal_year_max} · ${corpus.filings_indexed} filings indexed · live corpus`
              : "Loading corpus…"}
          </p>
        </div>

        <hr className="border-sidebar-border" />

        <div>
          <div className="label-caps">Upload a filing</div>
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              const file = e.dataTransfer.files?.[0];
              if (file) handleFileUpload(file);
            }}
            className={`mt-2 flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed px-4 py-5 text-center transition-colors ${
              dragActive ? "border-accent bg-sidebar-elevated" : "border-sidebar-border bg-sidebar-elevated"
            }`}
          >
            <input
              type="file"
              accept=".html,.htm"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
                e.target.value = "";
              }}
              className="hidden"
            />
            <span className="text-sm font-semibold">Drop or choose a 10-K/10-Q</span>
            <span className="text-xs text-sidebar-muted">.html or .htm files</span>
          </label>

          {uploadError && (
            <div className="mt-2 rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-xs text-red-200">
              {uploadError}
            </div>
          )}

          {uploadStatus && (
            <div className="mt-2 rounded-lg border border-sidebar-border px-3 py-2 text-xs">
              <div className="font-medium">{uploadStatus.original_filename}</div>
              {uploadStatus.status === "processing" && (
                <div className="mt-1 flex items-center gap-2 text-sidebar-muted">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
                  Processing — usually takes 1-3 minutes...
                </div>
              )}
              {uploadStatus.status === "ready" && (
                <div className="mt-1 text-green-400">
                  Ready — {uploadStatus.company} ({uploadStatus.ticker}) {uploadStatus.filing_type} FY
                  {uploadStatus.fiscal_year}, {uploadStatus.sections_found} sections,{" "}
                  {uploadStatus.chunks_indexed} chunks indexed.
                </div>
              )}
              {uploadStatus.status === "error" && (
                <div className="mt-1 text-red-400">Failed: {uploadStatus.error_message ?? "unknown error"}</div>
              )}
            </div>
          )}
        </div>

        {result && (result.ingestion_details?.length ?? 0) > 0 && (
          <div className="flex flex-col gap-2">
            {result.ingestion_details.map((d) => (
              <DocumentPreviewCard
                key={d.ticker}
                ticker={d.ticker}
                company={d.company}
                fiscalYear={d.fiscal_year}
                filingType={d.filing_type}
              />
            ))}
          </div>
        )}

        <p className="mt-auto text-xs text-sidebar-muted">
          Corpus grows via upload and dynamic ingestion from SEC EDGAR. Answers cite the exact filing
          chunks retrieved — not guaranteed complete or error-free.
        </p>
      </aside>

      {/* Main */}
      <main className="flex flex-1 flex-col overflow-hidden bg-white">
        <div className="flex-1 overflow-y-auto px-8 py-10">
          {showWelcome && (
            <div className="mx-auto mt-16 max-w-2xl text-center">
              <h2 className="text-3xl font-bold text-zinc-900">Ask about financial filings</h2>
              <p className="mt-3 text-zinc-500">
                Answers cite the exact filing chunks they&apos;re drawn from. Try one of these, or ask your
                own.
              </p>
              <div className="mt-6 flex flex-col items-center gap-3">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => submitQuery(s)}
                    className="rounded-full bg-suggestion-bg px-5 py-2.5 text-sm font-medium text-suggestion-text transition-colors hover:bg-suggestion-bg-hover"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mx-auto max-w-2xl">
            {loading && elapsedSeconds >= SLOW_QUERY_HINT_AFTER_SECONDS && (
              <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                This question may mention a company that isn&apos;t in the corpus yet — fetching and
                processing its filing from SEC EDGAR can take a few minutes. Elapsed: {elapsedSeconds}s
              </div>
            )}

            {error && (
              <div className="mb-4 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
                {error}
              </div>
            )}

            {result && (
              <div className="flex flex-col gap-3 rounded-2xl border border-zinc-200 p-5">
                {result.ingested_entities?.length > 0 && (
                  <div className="rounded-xl border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
                    Added to the corpus during this query:{" "}
                    <span className="font-medium">{result.ingested_entities.join(", ")}</span> — fetched
                    from SEC EDGAR because it wasn&apos;t indexed yet.
                  </div>
                )}

                {result.ingestion_errors?.length > 0 && (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <div className="font-medium">Could not add some companies to the corpus:</div>
                    <ul className="mt-1 list-disc pl-5">
                      {result.ingestion_errors.map((message, i) => (
                        <li key={i}>{message}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {(result.persona || result.query_type) && (
                  <div className="flex gap-2">
                    {result.persona && (
                      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700">
                        {result.persona}
                      </span>
                    )}
                    {result.query_type && (
                      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700">
                        {result.query_type}
                      </span>
                    )}
                  </div>
                )}

                {result.reasoning_trace?.length > 0 && (
                  <div>
                    <button
                      onClick={() => setReasoningOpen((o) => !o)}
                      className="label-caps flex items-center gap-1 text-zinc-500 hover:text-zinc-800"
                    >
                      {reasoningOpen ? "▾" : "▸"} How this answer was put together
                    </button>
                    {reasoningOpen && (
                      <ol className="mt-2 flex flex-col gap-1.5 border-l-2 border-zinc-200 pl-3 font-mono text-xs text-zinc-600">
                        {result.reasoning_trace.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}

                <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-900">
                  {result.answer
                    ? renderAnswerWithCitations(result.answer, result.retrieved_chunks, handleCiteClick)
                    : "No answer could be generated."}
                </p>

                <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-500">
                  {result.latency_ms != null && <span>Latency: {result.latency_ms} ms</span>}
                  {result.cost_usd != null && <span>Cost: ${result.cost_usd.toFixed(6)}</span>}
                  {result.langsmith_trace_id && (
                    <button onClick={copyTraceId} className="underline hover:no-underline">
                      {copied ? "Copied!" : `Trace ID: ${result.langsmith_trace_id}`}
                    </button>
                  )}
                </div>

                {result.retrieved_chunks.length > 0 && (
                  <div>
                    <button onClick={() => setChunksOpen((o) => !o)} className="text-xs font-medium underline">
                      {chunksOpen ? "Hide" : "Show"} retrieved chunks ({result.retrieved_chunks.length})
                    </button>
                    {chunksOpen && (
                      <div className="mt-2 flex flex-col gap-2">
                        {result.retrieved_chunks.map((chunk) => (
                          <div
                            key={chunk.chunk_id}
                            id={`chunk-${chunk.chunk_id}`}
                            className={`rounded-lg border p-2 text-xs ${
                              highlightedChunk === chunk.chunk_id
                                ? "border-amber-400 bg-amber-50"
                                : "border-zinc-200"
                            }`}
                          >
                            <div className="mb-1 font-medium text-zinc-500">
                              {chunk.chunk_id} · {chunk.company} {chunk.fiscal_year} · {chunk.section} ·
                              score {chunk.score.toFixed(2)}
                            </div>
                            <div className="whitespace-pre-wrap">{chunk.text}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitQuery();
          }}
          className="px-8 pb-8"
        >
          <div className="mx-auto flex max-w-2xl items-center gap-3 rounded-2xl bg-sidebar px-4 py-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about a company and fiscal year..."
              className="flex-1 bg-transparent text-sm text-white placeholder:text-sidebar-muted focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-sidebar transition-opacity disabled:opacity-40"
            >
              <ArrowUpIcon />
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
