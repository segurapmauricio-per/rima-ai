from google import genai
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv(override=True)

# Vertex AI con Application Default Credentials (gcloud auth application-default login)
# Usa scope cloud-platform â€” compatible con proyectos de organizaciÃ³n Google Cloud
_project = os.getenv("GOOGLE_CLOUD_PROJECT", "rima-ai-498117")
client = genai.Client(
    vertexai=True,
    project=_project,
    location="us-central1"
)


class GeminiClient:
    def __init__(self, model="google/gemini-2.5-flash"):
        self.model_name = model

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        contents = prompt
        config = {}
        if system_prompt:
            config["system_instruction"] = system_prompt

        response = client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config if config else None
        )
        text = response.text
        self._log(prompt, text)
        return text

    def generate_json(self, prompt: str, system_prompt: str = None) -> str:
        """Respuesta forzada a JSON — para arrays/objetos estructurados."""
        config = {"response_mime_type": "application/json"}
        if system_prompt:
            config["system_instruction"] = system_prompt

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        text = response.text
        self._log(prompt, text)
        return text

    def transcribe_video(self, video_bytes: bytes, mime_type: str = "video/mp4") -> str:
        """Transcribe diálogo hablado de un reel (Vertex multimodal)."""
        from google.genai import types

        if not video_bytes:
            return ""
        prompt = (
            "Transcribe ONLY the spoken words in this Instagram reel. "
            "Use the original language of the speaker. "
            "Ignore music and sound effects. "
            "Return plain text only — no markdown, no timestamps. "
            "If there is no speech, return an empty string."
        )
        response = client.models.generate_content(
            model=self.model_name,
            contents=types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt),
                ],
            ),
        )
        text = (response.text or "").strip()
        self._log("[transcribe_video]", text[:200])
        return text

    def _log(self, prompt: str, response: str):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "prompt_preview": prompt[:100],
            "response_preview": response[:100]
        }
        os.makedirs("logs", exist_ok=True)
        with open("logs/agent_calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")


gemini = GeminiClient()

