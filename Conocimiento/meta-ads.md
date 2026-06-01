# Módulo: meta-ads

---
### Fuente: campanas-meta-ads-100k.md
**Tipo:** MAPA + DOC
**Relevancia:** alta

## Setup obligatorio antes de tocar Ads Manager

**Checklist:**
- [ ] Cuenta en Meta Business Manager creada y verificada (`business.facebook.com`)
- [ ] Cuenta publicitaria activa con método de pago cargado
- [ ] Pixel instalado y disparando eventos
- [ ] Cuenta de Instagram conectada al BM
- [ ] Lista de clientes en CSV lista para subir (mínimo 100 contactos, ideal 500+)

**Instalar Pixel:** Meta BM → Eventos → Administrador de Eventos → Agregar nueva fuente de datos → Pixel de Meta.

**Configurar evento de conversión:** Evento de URL que se active cuando alguien llega a la página de confirmación de la agenda (ej: `midominio.com/gracias`).

---

## Distribución de presupuesto

| Budget diario | TOFU (70%) | MOFU (20%) | BOFU (10%) |
|---------------|-----------|------------|------------|
| $10/día | $7 | $2 | $1 |
| $30/día | $21 | $6 | $3 |
| $50/día | $35 | $10 | $5 |
| $100/día | $70 | $20 | $10 |

---

## Campaña 1 — TOFU (70% del budget)

**Nombre sugerido:** `TOFU | [mes]`
**Objetivo:** Tráfico → destino: Perfil de Instagram

Crear **3 conjuntos separados** (uno por tipo de audiencia). Desactivar presupuesto a nivel de campaña, ponerlo a nivel de conjunto.

**Los 3 tipos de audiencia para TOFU:**
1. **Broad:** solo países + edad, sin intereses
2. **Segmentado:** países + edad + intereses específicos del nicho
3. **Lookalike:** subís lista de clientes en CSV → Meta busca personas similares

**PRO TIP:** Arrancá los 3 conjuntos el mismo día y dejá correr mínimo 7 días antes de tocar algo. Cada edición reinicia el aprendizaje.

**Creatividades para TOFU:**
- Usá reels que ya funcionaron orgánicamente
- Hook: los primeros 2 segundos son todo — polémico, contraintuitivo, o que nombre un dolor específico
- Sin look de publicidad: tiene que verse como contenido orgánico normal
- Sin logos grandes, música corporativa ni textos que griten "soy un anuncio"

**Optimización semanal TOFU:**
- Semana 1-2: no toques nada. Solo mirá el CPM. Si es >$15, la audiencia puede ser muy chica
- Semana 3: el conjunto con menor costo por seguidor es el ganador. Duplicá su presupuesto. Pausá los que están $2+ más caros
- Mes 2+: rotá creativos cada 10-14 días

---

## Campaña 2 — MOFU (20% del budget)

**Nombre:** `MOFU | Agenda | [mes]`
**Objetivo:** Clientes potenciales (o Conversiones si tenés el evento configurado)

**Configuración paso a paso:**
1. Crear audiencia personalizada: Públicos → Crear público personalizado → Cuenta de Instagram → "Personas que siguen tu cuenta" → guardar como `Seguidores IG - MOFU`
2. Nueva campaña con objetivo Clientes potenciales
3. Solo usar `Seguidores IG - MOFU`. Sin segmentación adicional
4. Placement: solo Instagram (feed + stories + reels)

**PRO TIP:** Si la cuenta tiene menos de 500 seguidores, la audiencia de MOFU es demasiado chica. Invertí todo en TOFU primero.

**Los 4 ángulos que mejor convierten en MOFU:**
1. **Problema:** nombrás exactamente la frustración.
   > *"Estás invirtiendo horas en llamadas de descubrimiento y la mayoría ni aparece. Esto es lo que cambia eso."*
2. **Objeción:** atacás la razón por la que no agendan.
   > *"Antes de decir que no tenés tiempo para escalar tu mentoría, mirá esto."*
3. **Resultado:** transformación real de un cliente, punto A al punto B, con números concretos.
   > *"Este cliente pasó de $2K a $15K por mes en 90 días. Esto es lo que hicimos."*
4. **Autoridad:** demostración de expertise.
   > *"Llevamos más de 40 mentores a su primer $10K. Este es el sistema que usan todos."*

**CTA:** "Agendá tu llamada gratuita" con link directo al calendario. Cada paso extra = -30% de conversiones.

---

## Campaña 3 — BOFU (10% del budget)

**Quién entra en la audiencia de BOFU:**
- Agendó llamada pero no compró
- Mandó un DM en los últimos 14 días
- Visitó tu landing de agenda 2+ veces
- Agendó pero no se presentó

**Configuración:**
- "Visitó la landing": sitio web + página específica + últimos 30 días
- "Mandó un DM": Cuenta de Instagram → Personas que enviaron un mensaje
- Clientes que no cerraron: CSV con sus datos
- **Combinar todos los públicos BOFU en un solo conjunto**
- **Excluir:** clientes actuales

**PRO TIP:** Los mejores creativos para BOFU son testimonios en video de clientes reales. Si no tenés, usá capturas de conversaciones de WhatsApp o mensajes de resultados.

---

## Errores que queman plata

- Correr ads desde el botón azul de Instagram: tiene menos opciones de optimización. Siempre usar Meta Ads Manager
- Tocar la campaña antes de los 7 días: cada edición reinicia el aprendizaje
- Mezclar audiencias calientes y frías en el mismo conjunto
- No excluir a clientes actuales en MOFU y BOFU
- Escalar el budget de golpe (de $10/día a $100/día reinicia el aprendizaje)
- No tener el perfil optimizado antes de correr TOFU

---

## Cuándo y cómo escalar

- **Regla de los 7 días:** nunca subas el presupuesto antes de que pasen 7 días desde el último cambio
- **Incremento máximo del 20%:** de $30/día → $36, no a $60
- **Cuándo escalar:** costo por resultado dentro del KPI objetivo durante 5+ días consecutivos
- **Cómo escalar TOFU:** identificá el conjunto ganador → duplicalo → aumentá el budget del duplicado → pausá el original

---
### Fuente: configuraci-n-de-campa-as-de-ads-de-350k-m.md
**Tipo:** MAPA
**Relevancia:** alta

## Follow Me Ads — Configuración paso a paso (tráfico a perfil)

**Botón azul de Instagram = Corolla. Ads Manager = Ferrari.** Siempre usar Ads Manager.

**Rango de inversión inicial:** $10/día ($300/mes). Con $3000/mes se pueden ganar 50K seguidores nuevos por mes.

### Pasos de configuración

1. Ir a: `adsmanager.facebook.com/adsmanager/manager/campaigns`
2. Crear campaña → Tipo: **Tráfico** → Configuración manual
3. Nombre campaña: `FM - Segmentación abierta`
4. Ad set: seleccionar Instagram → cuenta de Instagram objetivo
5. **Audiencia:** Segmentación abierta. Solo elegir países.
   - Incluir: Argentina, México, Chile, Colombia, Uruguay, España, EEUU (comunidad hispana)
   - Excluir: países con bajo poder adquisitivo según experiencia propia
   - **No agregar intereses en esta segmentación** — dejar que el algoritmo decida
6. Anuncios: usar posteos existentes (no crear nuevos). Elegir 4-5 videos.
7. Quick Duplicate del adset para crear segunda segmentación: **Lookalike** de base de clientes.

### Criterio para elegir qué videos usar como anuncios

- Videos que orgánicamente tuvieron buenas vistas (más que el promedio del perfil)
- Videos que NO se vayan del nicho (no videos virales random)
- Videos con buen hook, bien estructurados

### Las 2 segmentaciones a probar

1. **Segmentación abierta** — solo países, sin intereses. Le da libertad al algoritmo.
2. **Lookalike de clientes** — subir CSV de base de datos de clientes → Instagram busca personas similares. Mayor calidad de seguidores.

**Máximo 4-5 anuncios por adset.** Meta testea todos y concentra el gasto en los mejores.

---
### Fuente: consultor-a-exclusiva-de-mastermind-ramiro-2.md
**Tipo:** DOC + MAPA
**Relevancia:** alta

## Follow Me Ads — Criterio de evaluación por creativo

**Presupuesto de testeo por creativo:** $20-50 USD. Si al gastar $30 el costo por seguidor es inaceptable → pausar de inmediato.

**Señal de creativo ganador:** CPF inferior a $1 USD el primer día de gasto.
**Señal de creativo perdedor:** CPF de $5+ USD el primer día.

**Dinámica de rotación:**
- 1 video = 1 ad set. No mezclar videos en el mismo ad set.
- Revisar al día siguiente → apagar los perdedores, prender nuevos.
- El creativo ganador: dejarlo correr hasta que la frecuencia llegue a 1.6-1.7 (señal de que se quemó la audiencia).

**Para nichos muy específicos** (clínicas, abogados, realtors): esperar CTR, no conteo de comentarios. El nicho nunca va a ser viral orgánicamente — todo el crecimiento viene de Follow Me Ads.

---
### Fuente: consultor-a-exclusiva-de-mastermind-ramiro-1.md
**Tipo:** DOC + MAPA
**Relevancia:** alta

## BOFU — Segmentación de retargeting según temperatura

| Temperatura | Audiencia | Tipo de contenido |
|-------------|-----------|------------------|
| Muy caliente | Personas que enviaron mensaje en últimos 30 días | Testimonios, oferta directa, objeciones |
| Tibia | Seguidores o visitantes de perfil últimos 180 días | Problemas, contenido de awareness |

**Regla:** Mientras más directa la oferta, más pequeña y caliente debe ser la audiencia. Para generar awareness en el MOFU → seguidores o visitantes es suficiente.

---

## Webinar como táctica de pipeline de emergencia

**Cuándo usarlo:** Primera semana después de un mes récord (pipeline clearout) o cuando faltan agendas.

**Estructura:**
- Landing page → "Reserva tu acceso"
- Landing redirige a grupo de WhatsApp
- Correr ads a la landing 2 semanas antes del evento
- Evento: 40 minutos de valor + 20 minutos de pitch

**Métricas a proyectar:**
- X% de los que entran al grupo se presentan al webinar
- X% de los presentes escuchan hasta la oferta
- X% de los que escuchan la oferta agendan llamada
- X% de los que agendan convierten

**Para quién:** Tanto a audiencia fría (nuevo mercado) como a audiencia tibia (seguidores + leads calientes).

---
### Fuente: consultor-a-exclusiva-de-mastermind-mat-as-2.md
**Tipo:** DOC + MAPA
**Relevancia:** alta

## Follow Me Ads — Metodología de testing de 21 anuncios

**Setup:** Subir 4-5 videos por semana → usar todos como anuncios en 1 adset. En 1 semana, tener 21+ anuncios testeados.

**KPI principal:** Costo por seguidor (no costo por visita al perfil).
- B2B (nichos de negocio, coaches) en LatAm: $0.50-$2.00 USD por seguidor
- B2C: $0.25-$0.50 USD por seguidor

**Criterio de corte (después de 7 días):**
- Anuncios dentro del KPI → mantener
- Anuncios fuera del KPI ($2+ más caros) → pausar
- El adset ganador: duplicar su presupuesto

**Creativos para Follow Me Ads:** El creativo se "quema" rápido (la audiencia lo ve varias veces). Rotar cada 10-14 días. BSL (landing page) tiene la ventaja de que un solo creativo puede durar mucho más tiempo.

---

## BSL — Métricas clave de landing page

**Métricas a medir:**
- Visitantes únicos (no total de visitas)
- Tasa de agenda: 1% sobre visitantes únicos es un buen resultado para landing page (no esperar 3-4%)
- Reproducción del BCL/VSL (instalar mapa de calor para ver % de reproducción)
- Average session duration + bounce rate

**A/B testing de encabezado:**
- El encabezado (headline) es lo que más determina si la gente se cae.
- Testear distintos encabezados.
- Al escalar: personalizar el encabezado de la landing según el creativo que lo trajo.
  > Ejemplo: Creativo dice "Dejá de depender de agencias para tu estudio de abogado" → Landing dice "¿Cómo dejar de depender de agencias en tu estudio de abogado?"

---

## UTMs para tracking de creativos (BSL)

**Flujo completo:**
1. En Meta Ads Manager → Parámetros del anuncio: agregar nombre del ad, campaña, conjunto.
2. Los UTMs viajan: Meta → Landing (Framer/Webflow) → Calendly.
3. Configurar que el UTM se mantenga a través de toda la cadena.
4. Calendly exporta los datos con UTM a Google Sheets.

**Uso en equipo:** El closer ve la hoja → sabe de qué creativo vino el lead antes de la llamada.

**KPI por creativo:** Leads agendados / agendas → conversión → CAC por anuncio. El creativo ganador se explota (más presupuesto) y cuando se quema, se graban varios similares.

---

## Cálculo de CAC inverso para validar escala

**Lógica:**
1. Definir tasa de cierre: si 1 de cada 6 llamadas cierra → necesito 6 llamadas por venta.
2. Definir tasa de agenda: si 1 de cada 50 mensajes agenda → necesito 300 mensajes por venta.
3. Costo por mensaje (CPL): si cada mensaje sale $1.80 → CAC = $540.
4. Comparar CAC con AOB (Average Order Basket):
   - Si AOB = $4,200 y CAC = $540 → FQCAC de 7.7x → escalar.

**Principio de escala:** Un ROAS alto (50:1) es insostenible a escala, pero en nominales genera más plata. Preferible hacer $1M/mes invirtiendo $300k que $50k/mes invirtiendo $5k, si los márgenes lo permiten.

**Cuándo escalar aunque el ROAS baje:** Siempre que el CAC siga por debajo del AOB con margen suficiente. El FQCAC de equilibrio real suele estar entre 7-15x en negocios de alto ticket.

---

## BCL vs Funnel Orgánico (cuándo usar cada uno)

| Criterio | BSL (Landing + Ads) | Orgánico + Follow Me Ads |
|---------|--------------------|-----------------------|
| Velocidad de resultados | Rápido (semanas) | Lento (meses) |
| Calidad de leads | Variable (depende del creativo) | Alta (leads que siguieron) |
| Sostenibilidad | No (requiere gasto constante) | Sí (activo compuesto) |
| Cuándo usar | Primeros $10-30k/mes | A partir de $30k/mes |

**Recomendación:** Construir ambos en paralelo. BSL para flujo de caja inmediato. Orgánico para escala a largo plazo.

---

---
### Fuente: loom-estructura-landing-ganadora.md
**Tipo:** MAPA + DOC
**Relevancia:** alta

## Estructura de Landing Page (Link en Bio)

**Resultado:** 16,000 USD en 21 dias sin esfuerzo adicional (gente que entra desde el link, se agenda y compra).

### Estructura de la pagina

`
1. PROMESA (titular + descripcion breve)
2. VSL (video 10-15 min)
3. CASOS DE EXITO / TESTIMONIOS (entrevistas o grabaciones)
4. CTA: Agenda una sesion (boton + calendario integrado)
5. Preguntas frecuentes
`

---

## Estructura del VSL (Video Sales Letter)

Duracion ideal: 10-15 minutos. No requiere produccion profesional (un Loom sirve).

`
1. PROMESA
   Que resultado concreto le vas a dar al cliente en X tiempo.

2. POR QUE DEBERIAN ESCUCHARTE
   Prueba social: tus resultados personales, casos de exito, metricas.
   Ejemplo: "Funde un negocio que hizo 1.8M en su primer ano, tengo 100+ casos de exito."

3. PASO A PASO SIMPLE
   Explicacion clara del metodo que usas para ayudar a clientes a lograr el resultado.
   No extenderse mas de lo necesario. Simple y concreto.

4. MAS PRUEBA SOCIAL
   Volver a mencionar casos de exito, esta vez mostrando que el mismo paso a paso
   fue lo que usaron tus clientes para lograr el resultado.
   "Este paso a paso fue lo que utilizaron Pepito, Juancito, etc."

5. LAS DOS OPCIONES
   "Con todo lo que te acabo de mostrar, tenes dos opciones:"
   - Hacerlo solo: mostrar cuanto tiempo / dinero / sufrimiento cuesta hacerlo solo.
   - Hacerlo acompanado: mostrar lo simple que es con acompanamiento + la promesa especifica.

6. CTA: Agenda una llamada
`

---

### Referencia de landing en produccion

sellyourknowledge.io y sellyourknowledge.io/Ramiro — usar como referencia de estructura real.

---
### Fuente: loom-follow-me-ads.md
**Tipo:** DOC + MAPA
**Relevancia:** alta

## Follow Me Ads — Logica de ejecucion

### A que videos correrles publicidad

**Error comun:** Boostar los videos mas virales.

| Modelo de negocio | A que videos boostar | CPF esperado |
|-------------------|---------------------|-------------|
| B2B / high-ticket / nicho especifico | Videos de nicho tecnicos (no virales) | USD 0.03-0.08 por visita a perfil |
| B2C / producto masivo / infoproducto barato | Videos mas virales | USD 0.01-0.04 por visita a perfil |

**Logica:** Los videos virales le gustan a todo el mundo → traen a todo el mundo. Si vends a un nicho especifico, los seguidores genericos no sirven. El costo por perfil es mas alto con videos de nicho, pero la audiencia es calificada.

**Ejemplo Ramiro (B2B):** Boosteo el reel "como pasar de 1,000 a 3,000 USD por tu servicio." Costo: USD 0.06 por visita. Presupuesto USD 800 → 13,000 visitas a perfil → leads calificados.

---

### Setup de campana

**Presupuesto inicial:** USD 5-10/dia.

**Conjuntos de anuncios:** 2 conjuntos para testear:
- Conjunto 1: segmentacion con intereses del nicho
- Conjunto 2: segmentacion abierta (sin intereses, solo paises)

**Paises recomendados (mercado hispano):**
- Incluir: Chile, Uruguay, Paraguay, Peru, Colombia, Mexico, EEUU
- Excluir: Argentina, Bolivia, Ecuador, Brasil

**Regla:** Usar Ads Manager (NO el boton azul de Instagram). El boton azul no permite segmentacion ni optimizacion real.

---

### Metricas reales de FM Ads (cuenta Ramiro, B2B)

- CPF niche: USD 0.06 por visita a perfil
- Presupuesto mes: USD 800
- Visitas generadas: 13,000+
- Clasificacion del trafico: leads interesados en temas de negocio especificos

---
### Fuente: loom-vsl-funnel.md
**Tipo:** MAPA + DOC
**Relevancia:** alta

## VSL Funnel — Estructura completa

### Estructura del embudo

`
ANUNCIO (Meta Ads)
        |
LANDING PAGE
- Promesa irresistible + garantia
- VSL (5-8 minutos)
- Calendario (Go High Level o Calendly)
- Testimonios
- Segundo calendario (opcional)
        |
PROCESO PRE-CALL
        |
LLAMADA + CIERRE
`

### Estructura del creativo (anuncio)

`
1. HOOK — llamar la atencion creativamente
2. CALLOUT — hablarle directamente al avatar ("si sos hombre de 30+ en corporativo...")
3. PROBLEMA — el dolor principal del avatar
4. SOLUCION — el metodo/sistema que resuelve el problema
5. PRUEBA SOCIAL — resultados propios o de clientes
6. ACCION — "haz clic en el enlace de este anuncio"
`

**El callout es el que segmenta:** el anuncio tiene que hablarle tan directamente al avatar que la gente que no es el avatar lo ignora y la que si lo es para a verlo.

---

### Metricas de referencia (VSL Funnel)

| Metrica | Valor saludable |
|---------|----------------|
| Costo por llamada calificada | USD 35-50 (con inversion minima USD 900 en Calendly) |
| Costo con inversion minima USD 1,800 | USD 50-70 por llamada |
| Show rate | >60% |
| Presupuesto para testear | USD 50/dia minimo = USD 3,000 en 2 meses |

---

### Orden de prioridades para que funcione

1. **Segmentacion:** Paises correctos para costos razonables sin leads de mala calidad
2. **Creativos:** Si no son buenos, nadie llega a la landing
3. **Landing:** Promesa + garantia atractiva, VSL bien explicado
4. **VSL:** Paso a paso del sistema claro y atractivo
5. **Proceso pre-call:** Determina el show rate (sin pre-call, la gente no se presenta)

---

### Recomendaciones tecnicas

- **Bots en CRM:** Desactivar Advantage Placements y elegir posicionamientos manualmente.
- **No lanzar si no hay presupuesto:** Menos de USD 3,000 para testear = no lanzar funnel de ads.
- **El Calendly filtra el costo:** A mayor inversion minima requerida en Calendly → mayor costo por llamada, pero mayor calificacion.

---
### Fuente: yt-202k-26dias-sin-ads.md
**Tipo:** DOC
**Relevancia:** alta

## Organico vs Ads — Por que el contenido supera a los anuncios pagados

**Metricas SYK (mes de referencia):**
- Cash Collected: USD 205K
- Inversion en ads: USD 5K
- ROI sobre inversion publicitaria: **40x**
- Margen de ganancia: 75% = USD 150K+ de profit neto
- % del revenue destinado a ads: 2.5%

**BCL Funnel (ads) vs Organico — Comparacion:**

| Variable | BCL Funnel / Ads | Organico |
|----------|-----------------|---------|
| ROI | ~3x (caso real: 1,2M revenue, 300-350K en ads) | 40x |
| Margen de ganancia | ~50% o menos | 75%+ |
| Rotacion de creativos | 30/mes (mismo esfuerzo que crear contenido) | No aplica |
| Tasa de cierre | Baja (trafico frio) | 40-60% (leads calientes, te conocen) |
| Equipo | Grande | Lean: 3 payroll + 2 setters + 2 closers |
| Complejidad | Alta (optimizar campanas, rotar creativos) | Baja |

**4 desventajas de los ads:**
1. Costo alto: necesitas USD 3-5K/mes para hacer USD 20K en ventas
2. Rotacion alta de creativos (~30/mes) = mismo esfuerzo que crear contenido organico
3. Margenes garchados: el gasto en ads se come el margen
4. Trafico frio: competis contra 70,000 ofertas, tasa de cierre baja

**Umbrales para el organico:**
- 1,000-5,000 seguidores = suficiente para USD 30-50K/mes
- 7 piezas de contenido/semana = 2-4 horas de grabacion
- Agregar Follow Me Ads con poco presupuesto para amplificar

**Casos de clientes:**
- Gero (coach fitness, 4.000 seguidores): USD 22K primer mes. Solo. USD 500 en FM Ads + ads a mensajes. Profit: ~USD 21.500.
- Joseph (nutricionista): USD 5K en ads -> USD 105K en ventas.

**Regla:** Antes de invertir en ads, construi la audiencia organica. El contenido organico con minima inversion en FM Ads supera al BCL Funnel en ROI y margen.

---
### Fuente: yt-estrategias-300k-mes.md
**Tipo:** DOC
**Relevancia:** alta

## Cuándo empezar a correr ads + métricas de seguimiento

**Cuándo empezar ads:** Cuando tenés un ángulo ganador validado en orgánico (un reel que trajo leads calificados, agendas o al menos conversaciones calificadas). No antes.

**Métricas para mantener un anuncio activo:**
- Costo por visita al perfil: <$0.05-0.06
- Frecuencia: <1.8-2
- Hook rate: >27%
- CTR: >2% (idealmente 2.5-4%)

**Si falla alguna métrica:** El anuncio está quemado. Crear nuevos creativos del mismo ángulo (el ángulo no se quema, el creativo sí).

**Trazabilidad inversa:** Para identificar qué contenido pautar, hacer ingeniería inversa desde los clientes que compraron → ver qué contenido los trajo → ese es el ángulo a amplificar con ads.

---
### Fuente: yt-sistemas-contenido-10k-dia.md
**Tipo:** DOC
**Relevancia:** media

## Follow Me Ads — Criterio para elegir que videos amplificar

**Criterio:** No correrle ads a los videos mas virales. Correrle ads a los videos que generaron mayor CANTIDAD y CALIDAD de conversaciones.

Señal de calidad: comentarios de cuentas verificadas o con perfil de dueño de negocio, alto numero de comentarios que derivaron en DMs.

**Configuracion recomendada:**
- Maximo 5 creativos por conjunto de anuncios (Meta gasta solo en 2-3 si hay mas)
- Minimo 3 conjuntos de anuncios para testear segmentaciones distintas:
  1. Segmentacion abierta por paises (sin intereses, Meta decide a quien mostrar)
  2. Lookalike de base de datos de clientes actuales
  3. Segmentacion por paises + intereses especificos

**Paises recomendados (hispanohablantes con poder adquisitivo):** EEUU, Espana, Mexico, Chile, Uruguay, Peru. Excluir: Venezuela, Bolivia, Paraguay (segun historial de calidad de leads).
