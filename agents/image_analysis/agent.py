"""
Image Analysis Agent
Analiza cada imagen subida por el cliente con Gemini Vision.
Detecta: descripción, gestos, zonas libres para texto (con safe zones de Instagram),
colores dominantes, vibe y categoría sugerida.
"""
from core.gemini_client import gemini
from core.client_store import save_image_meta, ensure_client_dirs
import json
import os
import base64
from pathlib import Path
from datetime import datetime

# Instagram safe zones para Stories (1080x1920)
STORY_SAFE_ZONE = {
    "top_pct": 15,       # Primeros 15% ocupados por header de IG (perfil, botones)
    "bottom_pct": 20,    # Últimos 20% ocupados por barra de mensaje y controles
    "side_pct": 5,       # 5% en cada lado (bordes y rounded corners)
}

# Para carruseles (1080x1080 o 1080x1350)
CAROUSEL_SAFE_ZONE = {
    "top_pct": 5,
    "bottom_pct": 5,
    "side_pct": 5,
}

SYSTEM_PROMPT = """Eres un analizador de imágenes especializado en contenido de Instagram.
Analizás imágenes para determinar su mejor uso en historias y carruseles.

Tu tarea es:
1. Describir el contenido visual de la imagen
2. Detectar gestos o señales visuales que indiquen dirección (dedos apuntando, miradas, flechas)
3. Identificar zonas con espacio libre para superponer texto
4. Evaluar brillo/contraste de cada zona para recomendar color de texto
5. Identificar la paleta de colores dominantes
6. Sugerir la categoría de uso más apropiada
7. Evaluar el "vibe" o emoción que transmite

Responde SIEMPRE en JSON válido según el schema que se te pide."""


class ImageAnalysisAgent:
    def __init__(self):
        self.name = "image_analysis"
        self.client = self._get_gemini_client()

    def _get_gemini_client(self):
        """Get the underlying google genai client for multimodal requests."""
        from google import genai
        from dotenv import load_dotenv
        load_dotenv(override=True)
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "rima-ai-498117")
        return genai.Client(vertexai=True, project=project, location="us-central1")

    def analyze(self, image_path: str, brand: str, category: str = "historias") -> dict:
        """
        Analyze a single image file.
        category: 'historias' | 'carruseles' | 'branding'
        """
        path = Path(image_path)
        if not path.exists():
            return {"error": f"Imagen no encontrada: {image_path}"}

        # Detect dimensions from filename or default to story format
        is_story = category == "historias"
        width = 1080
        height = 1920 if is_story else 1080
        safe = STORY_SAFE_ZONE if is_story else CAROUSEL_SAFE_ZONE

        # Calculate safe zone pixels
        safe_zone_px = self._calc_safe_zone(width, height, safe)

        # Calculate text block zones within safe area
        text_blocks = self._calc_text_blocks(safe_zone_px, width, height)

        # Analyze with Gemini Vision
        vision_analysis = self._analyze_with_gemini(image_path, safe_zone_px, text_blocks, category)

        # Build final metadata
        meta = {
            "filename": path.name,
            "category": category,
            "dimensions": {"width": width, "height": height},
            "safe_zone_px": safe_zone_px,
            "text_blocks": vision_analysis.get("text_blocks", text_blocks),
            "best_text_zone": vision_analysis.get("best_text_zone", "center"),
            "gesture_direction": vision_analysis.get("gesture_direction"),
            "gesture_text_zone": vision_analysis.get("gesture_text_zone"),
            "description": vision_analysis.get("description", ""),
            "vibe": vision_analysis.get("vibe", ""),
            "suggested_category": vision_analysis.get("suggested_category", category),
            "dominant_colors": vision_analysis.get("dominant_colors", []),
            "tags": vision_analysis.get("tags", []),
            "is_face_present": vision_analysis.get("is_face_present", False),
            "production_quality": vision_analysis.get("production_quality", "media"),
        }

        # Save to client store
        save_image_meta(brand, path.name, category, meta)
        return meta

    def _calc_safe_zone(self, w: int, h: int, safe: dict) -> dict:
        return {
            "top_px": int(h * safe["top_pct"] / 100),
            "bottom_px": int(h * (1 - safe["bottom_pct"] / 100)),
            "left_px": int(w * safe["side_pct"] / 100),
            "right_px": int(w * (1 - safe["side_pct"] / 100)),
        }

    def _calc_text_blocks(self, safe: dict, w: int, h: int) -> list:
        """Divide the safe zone into 3 blocks: upper_third, center, lower_third."""
        safe_height = safe["bottom_px"] - safe["top_px"]
        third = safe_height // 3
        return [
            {
                "zone": "upper_third",
                "coords": {
                    "x1": safe["left_px"], "y1": safe["top_px"],
                    "x2": safe["right_px"], "y2": safe["top_px"] + third,
                },
                "background_brightness": "unknown",
                "recommended_text_color": "#FFFFFF",
                "available": True,
            },
            {
                "zone": "center",
                "coords": {
                    "x1": safe["left_px"], "y1": safe["top_px"] + third,
                    "x2": safe["right_px"], "y2": safe["top_px"] + 2 * third,
                },
                "background_brightness": "unknown",
                "recommended_text_color": "#FFFFFF",
                "available": True,
            },
            {
                "zone": "lower_third",
                "coords": {
                    "x1": safe["left_px"], "y1": safe["top_px"] + 2 * third,
                    "x2": safe["right_px"], "y2": safe["bottom_px"],
                },
                "background_brightness": "unknown",
                "recommended_text_color": "#FFFFFF",
                "available": True,
            },
        ]

    def _analyze_with_gemini(self, image_path: str, safe_zone: dict, text_blocks: list, category: str) -> dict:
        """Use Gemini Vision to analyze the image."""
        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            ext = Path(image_path).suffix.lower().lstrip(".")
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/jpeg")

            safe_desc = (
                f"Top {safe_zone['top_px']}px y bottom a partir de {safe_zone['bottom_px']}px "
                f"son zonas peligrosas (ocultas por la UI de Instagram)."
            )

            prompt = f"""Analiza esta imagen para uso en Instagram {category}.

Zona segura para texto: {safe_desc}
Las 3 zonas de texto disponibles son:
- upper_third: coords {text_blocks[0]['coords']}
- center: coords {text_blocks[1]['coords']}
- lower_third: coords {text_blocks[2]['coords']}

IMPORTANTE sobre gestos y señales visuales:
- Si hay una persona apuntando con el dedo, mirando hacia una dirección, o hay una flecha visual,
  indicá hacia qué zona de texto señala ese gesto (el texto debe ir donde apunta el gesto).

Responde SOLO con este JSON (sin texto adicional):
{{
  "description": "descripción detallada de lo que hay en la imagen",
  "is_face_present": true/false,
  "gesture_direction": "arriba|abajo|izquierda|derecha|ninguno",
  "gesture_text_zone": "upper_third|center|lower_third|null (zona donde poner el texto según el gesto)",
  "text_blocks": [
    {{
      "zone": "upper_third",
      "background_brightness": "claro|oscuro|mixto",
      "recommended_text_color": "#FFFFFF o #1A1A1A",
      "available": true/false,
      "obstruction": "ninguna|cara|objeto|movimiento"
    }},
    {{
      "zone": "center",
      "background_brightness": "claro|oscuro|mixto",
      "recommended_text_color": "#FFFFFF o #1A1A1A",
      "available": true/false,
      "obstruction": "ninguna|cara|objeto|movimiento"
    }},
    {{
      "zone": "lower_third",
      "background_brightness": "claro|oscuro|mixto",
      "recommended_text_color": "#FFFFFF o #1A1A1A",
      "available": true/false,
      "obstruction": "ninguna|cara|objeto|movimiento"
    }}
  ],
  "best_text_zone": "upper_third|center|lower_third (la mejor zona para texto principal)",
  "vibe": "descripción del mood o emoción que transmite (ej: profesional y cálida, energética, íntima)",
  "suggested_category": "historia de conexión|historia de ventas|carrusel informativo|thumbnail reel|branding",
  "dominant_colors": ["#hex1", "#hex2", "#hex3"],
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "production_quality": "alta|media|baja"
}}"""

            from google.genai import types as genai_types

            response = self.client.models.generate_content(
                model="google/gemini-2.5-flash",
                contents=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config={"system_instruction": SYSTEM_PROMPT},
            )

            text = response.text.strip()
            # Extract JSON if wrapped in markdown
            if "```" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            return json.loads(text)

        except Exception as e:
            return {
                "description": f"Error al analizar imagen: {e}",
                "gesture_direction": "ninguno",
                "gesture_text_zone": None,
                "text_blocks": text_blocks,
                "best_text_zone": "center",
                "vibe": "no analizada",
                "suggested_category": category,
                "dominant_colors": [],
                "tags": [],
                "is_face_present": False,
                "production_quality": "media",
            }

    def analyze_batch(self, brand: str, category: str = "historias") -> list:
        """Analyze all non-analyzed images in a category for a client."""
        from core.client_store import client_path
        img_dir = client_path(brand) / "images" / category
        if not img_dir.exists():
            return []

        results = []
        for img_file in img_dir.glob("*.{jpg,jpeg,png,webp}"):
            meta_file = img_dir / f"{img_file.name}.meta.json"
            if not meta_file.exists():
                result = self.analyze(str(img_file), brand, category)
                results.append(result)
        return results


image_analysis_agent = ImageAnalysisAgent()
