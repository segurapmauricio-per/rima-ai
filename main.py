from agents.landing.agent import landing_agent

# Brief de marca de ejemplo para testing
test_brief = {
    "business_name": "CoachPro",
    "service": "Mentoría para coaches que quieren escalar su negocio",
    "ideal_client": "Coaches con 1-3 años de experiencia facturando menos de $3K/mes",
    "problem": "No tienen un sistema predecible para conseguir clientes nuevos cada mes",
    "main_result": "Escalar a $10K/mes en 90 días con Instagram sin ads",
    "price": "$2,500 USD",
    "success_cases": "Cliente 1: pasó de $800 a $8K/mes en 60 días. Cliente 2: primeros $10K en 3 meses.",
    "guarantee": "Si no llegas a $10K en 90 días, devolvemos el 100%"
}

if __name__ == "__main__":
    print("Ejecutando Agente Landing...")
    result = landing_agent.run(test_brief)
    print(f"\nAgente: {result['agent']}")
    print(f"Marca: {result['brand']}")
    print(f"\n--- OUTPUT ---\n")
    print(result['output'])