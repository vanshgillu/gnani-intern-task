export type FileStatus = "uploaded" | "transcribing" | "transcribed" | "summarizing" | "completed" | "failed";

export interface AudioFile {
    id: string;
    filename: string;
    size_bytes: number;
    language_code: string;
    status: FileStatus;
    gnani_status: string | null;
    transcript: string | null;
    detected_language: string | null;
    duration_seconds: number | null;
    summary: string | null;
    error: string | null;
    created_at: string;
    updated_at: string;
}

export interface GuestUser {
    id: string;
    is_new: boolean;
}

export interface Language {
    code: string;
    name: string;
}

export const ACTIVE_STATUSES: FileStatus[] = ["uploaded", "transcribing", "transcribed", "summarizing"];

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const res = await fetch(path, { credentials: "same-origin", ...init });
    if (!res.ok) throw new Error(await errorMessage(res.status, await res.text()));
    return res.json() as Promise<T>;
};

const errorMessage = async (status: number, body: string): Promise<string> => {
    try {
        const json = JSON.parse(body);
        if (typeof json.detail === "string") return json.detail;
        if (typeof json.message === "string") return json.message;
    } catch {
        // not JSON
    }
    return `Request failed (${status})`;
};

export const guestLogin = () => request<GuestUser>("/api/auth/guest", { method: "POST" });

export const listFiles = () => request<AudioFile[]>("/api/files");

export const listLanguages = () => request<Language[]>("/api/languages");

export const retryFile = (id: string) => request<AudioFile>(`/api/files/${id}/retry`, { method: "POST" });

export interface UploadProgress {
    loaded: number;
    total: number;
}

// xhr instead of fetch for upload progress
const putToStorage = (url: string, file: File, onProgress: (p: UploadProgress) => void): Promise<void> => {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", url);
        xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) onProgress({ loaded: e.loaded, total: e.total });
        };
        xhr.onload = async () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error(`Storage upload failed: ${await errorMessage(xhr.status, xhr.responseText)}`));
        };
        xhr.onerror = () => reject(new Error("Network error while uploading to storage"));
        xhr.send(file);
    });
};

export const uploadFile = async (file: File, languageCode: string, onProgress: (p: UploadProgress) => void): Promise<AudioFile> => {
    const { file_id, upload_url } = await request<{ file_id: string; upload_url: string }>("/api/files/upload-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, size_bytes: file.size, language_code: languageCode }),
    });
    await putToStorage(upload_url, file, onProgress);
    return request<AudioFile>("/api/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id, filename: file.name, language_code: languageCode }),
    });
};
