from google import genai
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiClient:
    def __init__(self, model="gemini-2.0-flash"):
        self.model_name = model

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = client.models.generate_content(
            model=self.model_name,
            contents=full_prompt
        )
        self._log(prompt, response.text)
        return response.text

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