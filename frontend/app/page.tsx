"use client";

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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const UPLOAD_POLL_INTERVAL_MS = 4000;

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
          className="mx-0.5 rounded bg-blue-100 px-1 text-xs font-medium text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200"
        >
          {part}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [chunksOpen, setChunksOpen] = useState(false);
  const [highlightedChunk, setHighlightedChunk] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  async function submitQuery() {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_query: query }),
      });
      if (!res.ok) throw new Error(`Backend responded with status ${res.status}`);
      const data: QueryResponse = await res.json();
      setResult(data);
      setChunksOpen(false);
      setHighlightedChunk(null);
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

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-4 py-8 font-sans">
      <h1 className="text-xl font-semibold">Financial Report Analyzer</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submitQuery();
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about Apple, Microsoft, or Google 10-K filings..."
          className="flex-1 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {loading ? "..." : "Send"}
        </button>
      </form>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2 rounded border border-dashed border-zinc-300 p-3 text-sm dark:border-zinc-700">
        <div className="flex items-center gap-2">
          <span className="font-medium">Upload a 10-K/10-Q (.html):</span>
          <input
            type="file"
            accept=".html,.htm"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileUpload(file);
              e.target.value = "";
            }}
            className="text-xs"
          />
        </div>

        {uploadError && (
          <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {uploadError}
          </div>
        )}

        {uploadStatus && (
          <div className="rounded border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800">
            <div className="font-medium">{uploadStatus.original_filename}</div>
            {uploadStatus.status === "processing" && (
              <div className="mt-1 flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                Processing — parsing, contextualizing and embedding usually takes 1-3 minutes...
              </div>
            )}
            {uploadStatus.status === "ready" && (
              <div className="mt-1 text-green-700 dark:text-green-400">
                Ready — detected {uploadStatus.company} ({uploadStatus.ticker}) {uploadStatus.filing_type}{" "}
                FY{uploadStatus.fiscal_year}, {uploadStatus.sections_found} sections,{" "}
                {uploadStatus.chunks_indexed} chunks indexed. You can now ask questions about it.
              </div>
            )}
            {uploadStatus.status === "error" && (
              <div className="mt-1 text-red-700 dark:text-red-400">
                Failed: {uploadStatus.error_message ?? "unknown error"}
              </div>
            )}
          </div>
        )}
      </div>

      {result && (
        <div className="flex flex-col gap-3 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          {(result.persona || result.query_type) && (
            <div className="flex gap-2">
              {result.persona && (
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium dark:bg-zinc-800">
                  {result.persona}
                </span>
              )}
              {result.query_type && (
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium dark:bg-zinc-800">
                  {result.query_type}
                </span>
              )}
            </div>
          )}

          <p className="whitespace-pre-wrap text-sm leading-6">
            {result.answer
              ? renderAnswerWithCitations(result.answer, result.retrieved_chunks, handleCiteClick)
              : "No answer could be generated."}
          </p>

          <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
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
                      className={`rounded border p-2 text-xs ${
                        highlightedChunk === chunk.chunk_id
                          ? "border-blue-400 bg-blue-50 dark:bg-blue-950"
                          : "border-zinc-200 dark:border-zinc-800"
                      }`}
                    >
                      <div className="mb-1 font-medium text-zinc-500 dark:text-zinc-400">
                        {chunk.chunk_id} · {chunk.company} {chunk.fiscal_year} · {chunk.section} · score{" "}
                        {chunk.score.toFixed(2)}
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
  );
}
