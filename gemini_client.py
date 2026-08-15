import mimetypes
import time
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_API_KEY

GEMINI_MODEL = "gemini-flash-latest"
FILE_PROCESSING_POLL_INTERVAL_SECONDS = 2
FILE_PROCESSING_TIMEOUT_SECONDS = 60

BASE_ANALYSIS_INSTRUCTIONS = (
    "You are a veterinary behaviorist analyzing a short video of a pet. "
    "Watch the video and assess the pet's mood based on its body language, "
    "posture, movement, and any vocalizations."
)

PHOTOS_CLAUSE_TEMPLATE = (
    " You have also been given {n} supporting photo(s) of the pet — use them as "
    "additional visual evidence alongside the video."
)

DESCRIPTION_CLAUSE_TEMPLATE = (
    ' The owner also provided this context about recent behavior: "{description}". '
    "Treat this as additional behavioral context distinct from what you observe visually, "
    "and factor it into your mood assessment and suggestions."
)

RESPONSE_INSTRUCTIONS = (
    " Respond with a single primary mood word, a confidence score between 0 and 1, a short "
    "one-to-two sentence summary of what you observed, and a list of 2 to 4 concrete, "
    "actionable suggestions or next steps the owner can take in response to the pet's mood "
    "and behavior."
)

_client: genai.Client | None = None


class GeminiAnalysisError(Exception):
    """Raised when Gemini scan analysis fails for any reason."""


class ScanAnalysis(BaseModel):
    mood: str = Field(description="A single primary mood word, e.g. happy, anxious, playful, relaxed, stressed")
    confidence: float = Field(ge=0, le=1, description="Confidence in the mood classification, from 0 to 1")
    summary: str = Field(description="A short 1-2 sentence summary of the pet's observed behavior and mood")
    suggestions: List[str] = Field(
        description="2 to 4 concrete, actionable next steps or suggestions for the owner, "
                     "based on the observed mood and any provided context"
    )


def _build_prompt(num_photos: int, description: Optional[str]) -> str:
    prompt = BASE_ANALYSIS_INSTRUCTIONS
    if num_photos > 0:
        prompt += PHOTOS_CLAUSE_TEMPLATE.format(n=num_photos)
    if description:
        prompt += DESCRIPTION_CLAUSE_TEMPLATE.format(description=description)
    prompt += RESPONSE_INSTRUCTIONS
    return prompt


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def analyze_pet_scan(video_path: str, photo_paths: List[str], description: Optional[str]) -> ScanAnalysis:
    """Analyzes a pet's mood from a required video, plus optional supporting photos and an
    optional owner-supplied text description of the pet's behavior.

    The video goes through Gemini's Files API (upload + poll-for-ACTIVE + delete) since video
    files are large/slow to process. Photos, when present, are small enough to send inline via
    Part.from_bytes in the same request — callers are expected to enforce a per-photo size cap
    before calling this. Description text is folded straight into the prompt as additional
    context distinct from what's observed visually.
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        raise GeminiAnalysisError(str(e)) from e

    try:
        uploaded_file = client.files.upload(file=video_path)
    except Exception as e:
        raise GeminiAnalysisError(f"Failed to upload video to Gemini: {e}") from e

    try:
        deadline = time.monotonic() + FILE_PROCESSING_TIMEOUT_SECONDS
        while uploaded_file.state == types.FileState.PROCESSING:
            if time.monotonic() > deadline:
                raise GeminiAnalysisError("Timed out waiting for Gemini to process the video")
            time.sleep(FILE_PROCESSING_POLL_INTERVAL_SECONDS)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state != types.FileState.ACTIVE:
            raise GeminiAnalysisError(f"Gemini rejected the video (state: {uploaded_file.state})")

        photo_parts = []
        for path in photo_paths:
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError as e:
                raise GeminiAnalysisError(f"Failed to read photo {path}: {e}") from e
            mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
            photo_parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))

        prompt = _build_prompt(len(photo_paths), description)
        contents = [uploaded_file] + photo_parts + [prompt]

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ScanAnalysis,
                ),
            )
        except Exception as e:
            raise GeminiAnalysisError(f"Gemini analysis request failed: {e}") from e

        if not isinstance(response.parsed, ScanAnalysis):
            raise GeminiAnalysisError("Gemini returned an unparseable response")

        return response.parsed
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass
