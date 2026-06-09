from agents.content.agent import content_agent

brief = {
    'business_name': 'FitBody Studio',
    'service': 'Entrenamiento personalizado para mujeres que quieren bajar de peso sin dietas extremas',
    'ideal_client': 'Mujeres de 28-45 anos, profesionales ocupadas, sin resultados duraderos',
    'problem': 'No tienen tiempo, han probado dietas que no funcionan',
    'main_result': 'Bajar 6-10 kg en 12 semanas',
    'price': '150.000 CLP/mes'
}

print("Generando calendario con Gemini 2.5 Flash...")
result = content_agent.run(brief)
cal = result['calendar']
print(f"Total slots generados: {len(cal)}")
print()

for slot in cal[:5]:  # mostrar primeras 5 semanas/dias
    semana = slot.get('semana', '?')
    dia = slot.get('dia', '?')
    tipo = slot.get('tipo', '?')
    ideas = slot.get('ideas', [])
    print(f"--- Semana {semana} | {dia} | [{tipo}] ---")
    for i, idea in enumerate(ideas):
        titulo = idea.get('titulo', '')
        hook = idea.get('hook', '')
        cta = idea.get('cta', '')
        print(f"  Idea {i+1}: {titulo}")
        print(f"  Hook: {hook}")
        print(f"  CTA:  {cta}")
        print()
