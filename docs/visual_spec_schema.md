# Spec Visual JSON — esquema unificado (Sprint KIE, Jun 2026)

Un único esquema JSON describe una pieza visual, sea que venga de **análisis**
(imagen real del cliente analizada con Gemini Vision) o de **generación**
(imagen/video nuevo vía KIE AI). Implementación: `core/visual_spec.py`
(determinístico, sin LLM).

## Esquema

```json
{
  "tipo_pieza": "imagen | video",
  "origen": "analisis | generacion",
  "formato": "1080x1080 | 1080x1920 | 1920x1080",
  "ratio": "1:1 | 9:16 | 16:9",
  "descripcion": "qué hay / qué debería haber en la pieza",
  "vibe": "mood o emoción que transmite",
  "paleta_colores": ["#0F1E5E", "#111111"],
  "elementos_clave": ["tag1", "tag2"],
  "zona_texto": {
    "zone": "upper_third | center | lower_third",
    "coords": {"x1": 0, "y1": 0, "x2": 0, "y2": 0},
    "recommended_text_color": "#FFFFFF | #1A1A1A"
  },
  "estilo_fotografico": "fotografía realista, limpia y profesional...",
  "texto_overlay": "texto que se superpondrá (NO va dentro de la imagen generada)",
  "duracion_seg": null,
  "escenas": null
}
```

- `duracion_seg` y `escenas` quedan reservados para video (Veo3.1, pendiente de
  implementación — la API existe pero el costo no está documentado y no se
  integra en este sprint).
- `texto_overlay` documenta el texto del slide; el prompt de generación pide
  explícitamente NO incrustar texto (el overlay lo pone el render del dashboard).

## Funciones (`core/visual_spec.py`)

| Función | Uso |
|---|---|
| `spec_vacia()` | Spec con defaults |
| `validar_spec(spec) -> list` | Lista de errores, `[]` si es válida |
| `spec_desde_analisis(analisis_json, archivo_url=None)` | Mapea el `analisis_json` de la tabla `imagenes` al esquema (origen `analisis`) |
| `spec_desde_slide(slide, tipo, slot_context, paleta_marca)` | Spec de generación para un slide `kie_pending` (origen `generacion`) |
| `spec_a_prompt(spec) -> str` | Prompt de generación KIE armado por template |

## Mapeo desde `analisis_json` (image_analysis)

| analisis_json | spec visual |
|---|---|
| `description` | `descripcion` |
| `vibe` | `vibe` |
| `dominant_colors` | `paleta_colores` |
| `tags` | `elementos_clave` |
| `best_text_zone` / `gesture_text_zone` + `text_blocks` | `zona_texto` |
| `production_quality`, `is_face_present` | `estilo_fotografico` |
| `dimensions` | `formato` + `ratio` |

`agents/image_analysis/agent.py` expone `to_visual_spec(meta)` y agrega
`visual_spec` al resultado de `analyze()` (aditivo — el `analisis_json`
existente no cambia de shape; imágenes ya analizadas se mapean on-the-fly).

## Uso en generación (visual_composer → kie_client)

Los slides `kie_pending` de `produccion_json.slides` llevan:

```json
{
  "image_source": "kie_pending",
  "spec_visual": { ...esquema de arriba, origen "generacion"... },
  "prompt_sugerido": "resultado de spec_a_prompt(spec_visual)",
  "ratio": "1:1 | 9:16"
}
```

La `paleta_colores` de marca se deriva determinísticamente de los
`dominant_colors` de las imágenes de branding del cliente
(`get_imagenes_para(cliente_id, "branding")`).
