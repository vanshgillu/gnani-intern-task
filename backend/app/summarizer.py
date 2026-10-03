from openai import AsyncOpenAI

from app.config import get_settings

# ~6k tokens, stays under groq free tier limits
CHUNK_CHARS = 24_000

SYSTEM_PROMPT = (
    "You summarize transcripts of audio recordings. The transcript comes from "
    "automatic speech recognition, so it has no punctuation and may contain "
    "recognition errors. Write the summary in English, regardless of the "
    "transcript's language. Start with a one-sentence overview, then list the "
    "key points as concise bullet points. Do not invent details that are not "
    "in the transcript."
)


def _client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url)


async def _complete(client: AsyncOpenAI, system: str, user: str) -> str:
    resp = await client.chat.completions.create(
        model=get_settings().groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _chunks(text: str) -> list[str]:
    words = text.split()
    chunks, current, size = [], [], 0
    for word in words:
        if size + len(word) + 1 > CHUNK_CHARS and current:
            chunks.append(" ".join(current))
            current, size = [], 0
        current.append(word)
        size += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


async def summarize(transcript: str) -> str:
    client = _client()
    chunks = _chunks(transcript)
    if len(chunks) <= 1:
        return await _complete(client, SYSTEM_PROMPT, f"Transcript:\n\n{transcript}")

    partials = []
    for i, chunk in enumerate(chunks, 1):
        partials.append(
            await _complete(
                client,
                SYSTEM_PROMPT,
                f"This is part {i} of {len(chunks)} of a longer transcript.\n\n{chunk}",
            )
        )
    combined = "\n\n".join(f"Part {i}:\n{p}" for i, p in enumerate(partials, 1))
    return await _complete(
        client,
        SYSTEM_PROMPT,
        "Below are summaries of consecutive parts of one recording. Merge them "
        f"into a single summary of the whole recording.\n\n{combined}",
    )
