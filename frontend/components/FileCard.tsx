"use client";

import { useState } from "react";

import type { AudioFile } from "@/lib/api";
import { type Step, StepTracker } from "./StepTracker";

const GNANI_STATUS_LABELS: Record<string, string> = {
    SUBMITTING: "Submitting to Gnani…",
    CREATED: "Starting job…",
    STARTING: "Starting job…",
    QUEUED: "Queued at Gnani…",
    IN_PROGRESS: "Converting speech to text…",
    COMPLETED: "Fetching transcript…",
};

export const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
};

const stepsFor = (file: AudioFile): Step[] => {
    const upload: Step = { label: "Upload", state: "done", detail: "Stored in Supabase" };
    const transcribe: Step = { label: "Transcribe", state: "pending", detail: "Gnani speech-to-text" };
    const summarize: Step = { label: "Summarize", state: "pending", detail: "Groq LLM" };

    switch (file.status) {
        case "uploaded":
            transcribe.state = "active";
            transcribe.detail = "Waiting to start…";
            break;
        case "transcribing":
            transcribe.state = "active";
            transcribe.detail = GNANI_STATUS_LABELS[file.gnani_status ?? ""] ?? "Transcribing…";
            break;
        case "transcribed":
            transcribe.state = "done";
            summarize.state = "active";
            summarize.detail = "Waiting to start…";
            break;
        case "summarizing":
            transcribe.state = "done";
            summarize.state = "active";
            summarize.detail = "Generating summary…";
            break;
        case "completed":
            transcribe.state = "done";
            summarize.state = "done";
            break;
        case "failed":
            if (file.transcript == null) {
                transcribe.state = "failed";
                transcribe.detail = "Failed";
            } else {
                transcribe.state = "done";
                summarize.state = "failed";
                summarize.detail = "Failed";
            }
            break;
    }
    if (transcribe.state === "done") transcribe.detail = "Transcript ready";
    if (summarize.state === "done") summarize.detail = "Summary ready";
    return [upload, transcribe, summarize];
};

const BADGES: Record<AudioFile["status"], { text: string; className: string }> = {
    uploaded: { text: "Uploaded", className: "bg-blue-50 text-blue-700" },
    transcribing: { text: "Transcribing", className: "bg-blue-50 text-blue-700" },
    transcribed: { text: "Transcribed", className: "bg-blue-50 text-blue-700" },
    summarizing: { text: "Summarizing", className: "bg-blue-50 text-blue-700" },
    completed: { text: "Completed", className: "bg-emerald-50 text-emerald-700" },
    failed: { text: "Failed", className: "bg-red-50 text-red-700" },
};

export const FileCard = ({ file, onRetry }: { file: AudioFile; onRetry: (id: string) => Promise<void> }) => {
    const [showTranscript, setShowTranscript] = useState(false);
    const [retrying, setRetrying] = useState(false);
    const badge = BADGES[file.status];

    const meta = [
        formatBytes(file.size_bytes),
        file.detected_language ?? file.language_code,
        file.duration_seconds != null ? formatDuration(file.duration_seconds) : null,
        new Date(file.created_at).toLocaleString(),
    ].filter(Boolean);

    return (
        <article className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <header className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <h3 className="truncate font-medium text-zinc-900" title={file.filename}>
                        {file.filename}
                    </h3>
                    <p className="text-xs text-zinc-500">{meta.join(" · ")}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className}`}>{badge.text}</span>
            </header>

            <StepTracker steps={stepsFor(file)} />

            {file.status === "failed" && (
                <div className="mt-4 flex items-start justify-between gap-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                    <p className="break-words">{file.error ?? "Something went wrong."}</p>
                    <button
                        type="button"
                        disabled={retrying}
                        onClick={async () => {
                            setRetrying(true);
                            try {
                                await onRetry(file.id);
                            } finally {
                                setRetrying(false);
                            }
                        }}
                        className="shrink-0 rounded-md bg-white px-3 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-100 disabled:opacity-50"
                    >
                        {retrying ? "Retrying…" : "Retry"}
                    </button>
                </div>
            )}

            {file.summary && (
                <section className="mt-5">
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Summary</h4>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-800">{file.summary}</p>
                </section>
            )}

            {file.transcript && (
                <section className="mt-4">
                    <button type="button" onClick={() => setShowTranscript((v) => !v)} className="text-xs font-semibold uppercase tracking-wide text-zinc-500 hover:text-zinc-800">
                        {showTranscript ? "▾" : "▸"} Transcript
                    </button>
                    {showTranscript && <p className="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 text-sm leading-relaxed text-zinc-700">{file.transcript}</p>}
                </section>
            )}
        </article>
    );
};

export const UploadingCard = ({ name, size, progress, loaded, error, onDismiss }: { name: string; size: number; progress: number; loaded: number; error?: string; onDismiss: () => void }) => {
    const percent = Math.round(progress * 100);
    const steps: Step[] = [
        {
            label: "Upload",
            state: error ? "failed" : "active",
            detail: error ? "Failed" : progress < 1 ? "To Supabase Storage" : "Finalizing…",
        },
        { label: "Transcribe", state: "pending", detail: "Gnani speech-to-text" },
        { label: "Summarize", state: "pending", detail: "Groq LLM" },
    ];
    return (
        <article className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <header className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <h3 className="truncate font-medium text-zinc-900">{name}</h3>
                    <p className="text-xs text-zinc-500">{formatBytes(size)}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${error ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-700"}`}>{error ? "Failed" : "Uploading"}</span>
            </header>
            <StepTracker steps={steps} />
            {!error && (
                <div className="mt-4">
                    <div className="mb-1 flex justify-between text-xs text-zinc-500">
                        <span>
                            {formatBytes(loaded)} of {formatBytes(size)}
                        </span>
                        <span className="font-medium tabular-nums text-zinc-700">{percent}%</span>
                    </div>
                    <div role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-zinc-100">
                        <div className="h-full rounded-full bg-blue-500 transition-[width] duration-200" style={{ width: `${percent}%` }} />
                    </div>
                </div>
            )}
            {error && (
                <div className="mt-4 flex items-start justify-between gap-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                    <p className="break-words">{error}</p>
                    <button type="button" onClick={onDismiss} className="shrink-0 rounded-md bg-white px-3 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-100">
                        Dismiss
                    </button>
                </div>
            )}
        </article>
    );
};
