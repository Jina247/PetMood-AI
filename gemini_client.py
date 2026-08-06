import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_API_KEY

GEMINI_MODEL = "gemini-flash-latest"
FILE_PROCESSING_POLL_INTERVAL_SECONDS = 2
FILE_PROCESSING_TIMEOUT_SECONDS = 60

ANALYSIS_PROMPT = (
    "You are a veterinary behaviorist analyzing a short video of a pet. "
    "Watch the video and assess the pet's mood based on its body language, "
    "posture, movement, and any vocalizations. Respond with a single primary "
    "mood word, a confidence score between 0 and 1, and a short one-to-two "
    "sentence summary of what you observed."
)

_client: genai.Client | None = None


class GeminiAnalysisError(Exception):
    """Raised when Gemini video analysis fails for any reason."""


class MoodAnalysis(BaseModel):
    mood: str = Field(description="A single primary mood word, e.g. happy, anxious, playful, relaxed, stressed")
    confidence: float = Field(ge=0, le=1, description="Confidence in the mood classification, from 0 to 1")
    summary: str = Field(description="A short 1-2 sentence summary of the pet's observed behavior and mood")


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def analyze_pet_video(video_path: str) -> MoodAnalysis:
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

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[uploaded_file, ANALYSIS_PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MoodAnalysis,
                ),
            )
        except Exception as e:
            raise GeminiAnalysisError(f"Gemini analysis request failed: {e}") from e

        if not isinstance(response.parsed, MoodAnalysis):
            raise GeminiAnalysisError("Gemini returned an unparseable response")

        return response.parsed
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass
