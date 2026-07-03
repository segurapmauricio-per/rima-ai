"""Datos de vista previa del popup de descubrimiento de referentes (sin Apify/Gemini)."""

PREVIEW_SUGGESTIONS = [
    {
        "username": "coach.latam.demo",
        "full_name": "Coach LATAM Demo",
        "nombre_nicho": "Coach LATAM Demo · fitness",
        "motivo": "Contenido educativo de ventas en español, cuenta mediana modelable.",
        "profile_pic_url": "https://i.pravatar.cc/80?u=coachlatam1",
        "profile_url": "https://www.instagram.com/coach.latam.demo/",
        "followers": 42000,
    },
    {
        "username": "nutri.emprende",
        "full_name": "Nutri Emprende",
        "nombre_nicho": "Nutri Emprende · salud",
        "motivo": "Reels con estructura clara de hook + CTA, buen ratio de comentarios.",
        "profile_pic_url": "https://i.pravatar.cc/80?u=nutriemp2",
        "profile_url": "https://www.instagram.com/nutri.emprende/",
        "followers": 28500,
    },
    {
        "username": "ventas.con.impacto",
        "full_name": "Ventas con Impacto",
        "nombre_nicho": "Ventas con Impacto · negocios",
        "motivo": "Nicho adyacente con posts de autoridad y prueba social.",
        "profile_pic_url": "https://i.pravatar.cc/80?u=ventasimpacto3",
        "profile_url": "https://www.instagram.com/ventas.con.impacto/",
        "followers": 51000,
    },
]


def get_preview_suggestions() -> list[dict]:
    return [dict(s) for s in PREVIEW_SUGGESTIONS]
