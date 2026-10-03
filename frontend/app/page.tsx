"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { FileCard, UploadingCard } from "@/components/FileCard";
import { ACTIVE_STATUSES, type AudioFile, type GuestUser, type Language, guestLogin, listFiles, listLanguages, retryFile, uploadFile } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
const ACCEPT = ".wav,.mp3,.mp4,.flac,.ogg,.opus,.m4a,.aac,.webm,.amr,audio/*";
const AUTO_DETECT = "en-IN,hi-IN";

interface PendingUpload {
    key: string;
    name: string;
    size: number;
    progress: number;
    loaded: number;
    error?: string;
}

const Home = () => {
    const [user, setUser] = useState<GuestUser | null>(null);
    const [authError, setAuthError] = useState<string | null>(null);
    const [files, setFiles] = useState<AudioFile[]>([]);
    const [uploads, setUploads] = useState<PendingUpload[]>([]);
    const [languages, setLanguages] = useState<Language[]>([]);
    const [language, setLanguage] = useState("en-IN");
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const refresh = useCallback(async () => {
        try {
            setFiles(await listFiles());
        } catch {
            // next poll will retry
        }
    }, []);

    useEffect(() => {
        guestLogin()
            .then(async (u) => {
                setUser(u);
                await refresh();
            })
            .catch((e: Error) => setAuthError(e.message));
        listLanguages()
            .then(setLanguages)
            .catch(() => {});
    }, [refresh]);

    const hasActive = files.some((f) => ACTIVE_STATUSES.includes(f.status));
    useEffect(() => {
        if (!hasActive) return;
        const id = setInterval(refresh, POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [hasActive, refresh]);

    const updateUpload = (key: string, patch: Partial<PendingUpload>) => setUploads((list) => list.map((u) => (u.key === key ? { ...u, ...patch } : u)));

    const startUploads = (selected: FileList | null) => {
        if (!selected) return;
        for (const file of Array.from(selected)) {
            const key = crypto.randomUUID();
            setUploads((list) => [{ key, name: file.name, size: file.size, progress: 0, loaded: 0 }, ...list]);
            uploadFile(file, language, ({ loaded, total }) => updateUpload(key, { progress: loaded / total, loaded }))
                .then((created) => {
                    setFiles((list) => [created, ...list.filter((f) => f.id !== created.id)]);
                    setUploads((list) => list.filter((u) => u.key !== key));
                })
                .catch((e: Error) => updateUpload(key, { error: e.message }));
        }
    };

    const onRetry = async (id: string) => {
        try {
            const updated = await retryFile(id);
            setFiles((list) => list.map((f) => (f.id === id ? updated : f)));
        } catch (e) {
            alert((e as Error).message);
        }
    };

    return (
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10">
            <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-semibold text-zinc-900">Audio Summarizer</h1>
                    <p className="text-sm text-zinc-500">Upload audio → Gnani transcribes it → Groq summarizes it.</p>
                </div>
                {user ? (
                    <div className="flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-sm">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        <span className="text-zinc-700">Guest</span>
                        <code className="text-xs text-zinc-400" title={user.id}>
                            {user.id.slice(0, 8)}
                        </code>
                    </div>
                ) : (
                    <span className="text-sm text-zinc-400">{authError ? "Login failed" : "Signing in…"}</span>
                )}
            </header>

            {authError && <p className="mb-6 rounded-lg bg-red-50 p-3 text-sm text-red-700">Could not log in as guest: {authError}. Is the backend running?</p>}

            <section
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    if (user) startUploads(e.dataTransfer.files);
                }}
                className={`mb-8 rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${dragging ? "border-blue-400 bg-blue-50" : "border-zinc-300 bg-white"}`}
            >
                <p className="mb-1 font-medium text-zinc-800">Drop audio files here</p>
                <p className="mb-5 text-sm text-zinc-500">WAV, MP3, M4A, FLAC, OGG, WebM and more</p>
                <div className="flex flex-wrap items-center justify-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-zinc-600">
                        Language
                        <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-800">
                            {languages.length === 0 && <option value="en-IN">English</option>}
                            {languages.map((l) => (
                                <option key={l.code} value={l.code}>
                                    {l.name}
                                </option>
                            ))}
                            <option value={AUTO_DETECT}>Auto-detect (English / Hindi)</option>
                        </select>
                    </label>
                    <button
                        type="button"
                        disabled={!user}
                        onClick={() => inputRef.current?.click()}
                        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40"
                    >
                        Choose files
                    </button>
                    <input
                        ref={inputRef}
                        type="file"
                        accept={ACCEPT}
                        multiple
                        hidden
                        onChange={(e) => {
                            startUploads(e.target.files);
                            e.target.value = "";
                        }}
                    />
                </div>
            </section>

            <section className="space-y-4">
                {uploads.map((u) => (
                    <UploadingCard
                        key={u.key}
                        name={u.name}
                        size={u.size}
                        progress={u.progress}
                        loaded={u.loaded}
                        error={u.error}
                        onDismiss={() => setUploads((list) => list.filter((x) => x.key !== u.key))}
                    />
                ))}
                {files.map((f) => (
                    <FileCard key={f.id} file={f} onRetry={onRetry} />
                ))}
                {user && files.length === 0 && uploads.length === 0 && <p className="py-8 text-center text-sm text-zinc-400">No files yet. Upload one to get started.</p>}
            </section>
        </main>
    );
};

export default Home;
