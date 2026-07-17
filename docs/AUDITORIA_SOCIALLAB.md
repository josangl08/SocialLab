# Análisis comparativo de SocialLab — mi auditoría vs. la del otro agente

## Contexto

El usuario pidió un análisis exhaustivo de propósito, funcionamiento e implementación de SocialLab, y compartió el resultado de un análisis previo hecho por otro agente para contrastarlo. Este documento no es un plan de implementación — es el resultado de verificar, con 3 agentes de exploración en paralelo (backend/scheduler, seguridad/RLS, frontend/template selector), cada afirmación del otro análisis contra el código real, línea por línea, más los hallazgos nuevos que surgieron en el camino. El objetivo es tener una base fáctica común antes de decidir qué corregir y en qué orden.

**Veredicto general**: el análisis del otro agente es sólido en el flujo funcional y acierta en 4 de sus 5 hallazgos técnicos (A, B, D parcialmente, y el problema real detrás de C). Se equivoca en un dato de stack (Tailwind vs Bootstrap) y en el punto E, cuya premisa (sistema de aspectos deportivos) no existe en este repositorio. Mi auditoría añade una vulnerabilidad IDOR concreta no detectada, y un hallazgo más grave sobre RLS que el propio punto D del otro análisis.

---

## 1. Propósito y funcionamiento — CONFIRMADO, con más detalle

El resumen del otro análisis es correcto. `run_agent(account_id)` en `backend/services/agent_service.py:135-265` hace, en orden:

1. Carga la cuenta → calcula la próxima semana sin planificar (`_get_next_unplanned_week`)
2. Construye contexto de campaña mensual (`_build_campaign_context`)
3. Escanea Google Drive buscando archivos nuevos (`_scan_drive`)
4. Analiza imágenes nuevas con Gemini 2.5 Flash (`_analyze_images`) → guarda en `visual_analyses`
5. Planifica el calendario semanal con Gemini 2.0 Flash (`_ai_schedule`, con fallback determinista round-robin si falla)
6. Crea posts en `draft` + una `content_proposals` en `pending_approval` (`_create_drafts`)
7. Envía la tarjeta de propuesta a Telegram
8. Registra siempre un `agent_logs`, incluso si hubo excepción

El flujo de aprobación por Telegram y la publicación vía `PostScheduler`/`InstagramPublisher` con reintentos también se confirman tal como los describió el otro agente.

---

## 2. Punto por punto: qué se confirma, qué se corrige, qué es nuevo

### A. Bloqueo del Event Loop — CONFIRMADO, y más extendido de lo descrito

`supabase-py` en este proyecto es 100% síncrono (`create_client`, no `acreate_client`). Conteo real: **24 de 37 endpoints** en `agent_routes.py`, `instagram_routes.py`, `posts_routes.py` y `telegram_routes.py` son `async def` que ejecutan `.execute()` síncrono directamente en su cuerpo — no es un caso aislado, es el patrón dominante en las rutas más usadas (`agent_routes.py` tiene 14/15). `reorder_proposal_slot` encadena hasta 8 `.execute()` en una sola request. La solución propuesta por el otro análisis (declarar las rutas como `def` normal o usar `asyncio.to_thread`) es correcta.

### B. Cron secuencial — CONFIRMADO exactamente

`main.py:99-123`, `run_agent_for_all_accounts()` usa un `for` plano sin paralelismo. Cada cuenta espera a la anterior. Confirmado byte a byte.

### C. Event loop local en `agent_service.py` — el código es real, pero el riesgo estaba sobrestimado

El código (`asyncio.new_event_loop()` + `run_until_complete()` + `close()`, líneas 233-239) existe tal cual se describió y es el único lugar del backend con este patrón. Pero mi verificación matiza el impacto: `run_agent()` **nunca corre en el hilo del event loop principal de uvicorn** — se invoca desde `BackgroundTasks` (que Starlette ejecuta en threadpool) o desde el `ThreadPoolExecutor` de APScheduler. En ambos casos corre en un hilo aislado sin loop propio, así que el conflicto directo con el loop de FastAPI que sugiere el otro análisis no aplica tal como está planteado.

El riesgo real es más sutil: nunca se llama `asyncio.set_event_loop(loop)`, así que el loop cerrado no queda "pegado" al hilo — pero el `except Exception as te` genérico (línea 241) silenciaría cualquier `RuntimeError` sin dejar rastro, y si alguna librería interna de `TelegramService`/`httpx` cachea el loop entre invocaciones del mismo hilo reutilizado del pool, sí hay una vía de fallo. Es un code smell real (usar `asyncio.run()` sería más correcto y explícito), pero la severidad es menor de lo que sugiere el otro análisis.

### D. RLS bypass — CONFIRMADO y es más grave de lo descrito

Esto es lo más importante que añade mi auditoría. El otro análisis se queda corto:

- **Tablas sin ninguna política RLS**: `content_proposals`, `agent_logs`, `visual_analyses`, y **`posts` nunca recibe `ENABLE ROW LEVEL SECURITY` en ninguna de las 18 migraciones**. No es solo que se use `admin_supabase` en vez de RLS — para estas tablas no hay RLS que saltarse aunque se quisiera usar el cliente normal.
- **Hallazgo más crítico**: el cliente `supabase` "normal" (anon key) es un singleton creado una sola vez al importar el módulo, y **nunca se propaga el JWT del usuario autenticado hacia él** (confirmado: no hay `set_session` ni `postgrest.auth` en todo el backend). Esto significa que aunque existan políticas RLS activas (`instagram_accounts`, `templates`, etc.), `auth.uid()` es `NULL` en cualquier query hecha con ese cliente — las políticas actúan como un candado total (bloquean todo acceso vía anon, forzando a usar `admin_supabase`), no como aislamiento por usuario. **Migrar a "usar el cliente con JWT" como sugiere el otro análisis no resolvería nada por sí solo** — primero habría que arreglar la propagación del JWT hacia el cliente Supabase en cada request.
- **Vulnerabilidad IDOR nueva, no detectada por el otro análisis**: `backend/routes/posts_routes.py:72-78`, en `create_post`. El parámetro `instagram_account_id` (controlado por el cliente) se consulta con `admin_supabase` filtrando **solo por `id`**, sin verificar que pertenezca al usuario autenticado. Un usuario puede pasar el `instagram_account_id` de otra cuenta y el backend leerá su `telegram_chat_id` y disparará un mensaje de aprobación al chat de Telegram de otro usuario.

### E. Template selector vs. sistema de aspectos deportivos — la premisa del otro análisis es incorrecta

`template_selector.py:_check_player_rules` sí usa métricas planas (`min_goals`, `min_assists`, posición) — eso se confirma. Pero **el sistema de análisis por aspectos/percentiles/radar/clustering que el otro análisis da por hecho no existe en absoluto dentro de `SocialLab/backend`** (búsqueda exhaustiva sin resultados). El propio `template_selector.py:3` referencia que el `metadata.json` que consume viene de "PROJECT 1" — un proyecto externo. Así que no hay "desajuste conceptual entre dos sistemas del mismo repo": lo que hay es un selector simple que consume metadata plana de una fuente externa. Si el sistema de aspectos existe, vive en ese otro repositorio, fuera del alcance de esta auditoría — habría que revisarlo por separado para saber si de verdad hay un desajuste al integrar ambos.

---

## 3. Hallazgos nuevos no mencionados en el otro análisis

1. **Error de stack en el otro análisis**: describe el frontend como "React 18, Vite, TypeScript, **Tailwind CSS**". Es incorrecto — el proyecto usa **Bootstrap 5** (`bootstrap ^5.3.7`, `react-bootstrap ^2.10.10`) + CSS por componente, sin rastro de Tailwind en `package.json`, código ni configuración. Coincide con lo que dice tu propio CLAUDE.md en las secciones "Hard Constraints" (aunque curiosamente la línea del stack resumen en tu mismo CLAUDE.md también dice "Tailwind CSS" por error — es una inconsistencia interna en tu propio documento que vale la pena corregir).
2. **Sin rate limiting real para Gemini ni Instagram**: pese a que las reglas del proyecto mencionan límites (Gemini 100 req/h, Instagram 200 llamadas/h), no existe ningún contador, caché o throttling — solo topes fijos de tamaño de lote y reintentos con backoff ante fallos de red, que no son lo mismo que prevenir alcanzar el límite.
3. **Inconsistencia menor**: el comentario del backoff exponencial en `post_scheduler.py:162-163` dice "3er intento: 30min" pero la fórmula (`5 * 2^retry_count`) da 20 min.
4. **Posible condición de carrera**: `_get_next_unplanned_week` y la exclusión de imágenes ya usadas no están protegidas por lock/transacción — ejecuciones concurrentes de `run_agent` para la misma cuenta podrían crear propuestas duplicadas para la misma semana.

---

## 4. Análisis independiente propio (áreas no cubiertas por el otro análisis)

Investigado con 3 agentes adicionales sobre: autenticación/OAuth/webhooks, servicios de IA/generación de contenido, y arquitectura frontend/tests/esquema de BD. Todo con evidencia archivo:línea verificada por los agentes.

### 4.1 Seguridad — hallazgos nuevos

- **Doble implementación de auth con contratos distintos**: `backend/auth/dependencies.py:13` (devuelve `User` Pydantic) y `backend/auth/jwt_handler.py:13` (devuelve `dict`) son dos guardianes `get_current_user()` independientes; 8 archivos de rutas usan uno, 4 usan el otro. Riesgo de que diverjan silenciosamente si se añade lógica (revocación, roles) a solo uno.
- **`JWT_SECRET` es configuración muerta**: está en `.env.example:31` pero no se usa en ningún `.py` del backend — toda validación de token delega en `supabase.auth.get_user(token)` contra el servidor de Supabase.
- **Tokens de Instagram y Google Drive almacenados en texto plano** en `instagram_accounts`/`drive_tokens` (columnas `TEXT`, sin cifrado). El de Drive al menos está protegido por RLS "solo service role"; el de Instagram no tiene ninguna protección adicional.
- **Sin renovación proactiva del token de Instagram** (dura 60 días) — solo se detecta que expiró cuando una operación falla y se pide reconectar manualmente. Drive sí refresca correctamente de forma lazy (`drive_oauth_service.py:75-83`).
- **`state` de OAuth = `user_id` en claro, sin nonce firmado**, en Instagram y Drive — debilidad de diseño CSRF clásica en el flujo OAuth.
- **Bot token de Telegram filtrado en logs**: `telegram_service.py:44` loguea la URL completa del webhook, que incluye el token que lo protege.
- **Webhook de Telegram no verifica propiedad chat↔post**: los handlers de aprobar/rechazar/editar actúan sobre `post_id`/`proposal_id` sin comprobar que el `chat_id` que llama esté vinculado a la cuenta dueña de ese post. Un chat que ya interactuó con el bot podría, en teoría, tocar posts de otra cuenta si conoce/adivina el ID.
- **Sin `config.py` centralizado**: variables de entorno leídas de forma dispersa con `os.getenv` en ~10 archivos; solo `SUPABASE_URL`/`SUPABASE_KEY` fallan rápido al arrancar — el resto (Instagram, Telegram, Gemini, Drive) falla tarde y en silencio cuando un usuario ejerce esa función.
- **CORS y redirects hardcodeados a localhost** (`main.py:226`, `instagram_routes.py:169`) — no configurables por entorno, indicando que el despliegue a producción requeriría tocar código a mano.

### 4.2 Duplicación y arquitectura — hallazgos nuevos

- **4 sistemas paralelos de generación de contenido con IA que no comparten código**: el análisis de imagen con Gemini Vision está reimplementado casi idéntico en `agent_service.py` y `ai_routes.py`; la regeneración de caption de un slot está triplicada entre `agent_routes.py` (español) y `telegram_service.py` (inglés — hay *drift* de idioma entre las dos copias); y existe un tercer flujo completo de captions "manual" (`caption_generator.py`/`content_generation.py`, para datos de PROJECT 1) que no se cruza nunca con el del agente autónomo. El patrón "strip markdown fences + json.loads" está copiado literalmente en 5 sitios distintos.
- **`CaptionGeneratorService` (la clase) es código muerto en producción**: solo se ejercita en su propio bloque `__main__`; en producción solo se usa una función standalone dentro del mismo archivo.
- **Dos tablas completamente huérfanas**: `content_generation_queue` y `content_generation_history` reciben `INSERT` pero nunca se actualizan ni se procesan — no hay worker ni cron que las consuma. El endpoint que expone su estado siempre mostrará contadores en cero. El flujo real de generación es síncrono dentro del propio request HTTP y ni siquiera usa la cola.
- **Frontend sin capa de API centralizada**: 0 cliente HTTP compartido, 64 llamadas a `fetch()` sueltas en 21 archivos, **72 ocurrencias de `http://localhost:8000` hardcodeado** en 22 archivos (no usa `import.meta.env`, así que no funcionaría en otro entorno sin tocar código). El boilerplate de headers de auth está copiado ~20 veces.
- **Sin carpeta `types/` compartida**: interfaces como `Post` están definidas de forma distinta e incompatible en varios componentes. 46 usos de `: any` + 17 de `as any`.
- **`PostDetailModal.tsx` duplicado por nombre** en `components/posts/` y `components/analytics/panels/` — mismo nombre, contenido y tipos completamente distintos.

### 4.3 Manejo de errores y rendimiento — hallazgos nuevos

- **Manejo de errores de Gemini inconsistente**: mezcla de fallos silenciosos (`agent_service.py`, `caption_generator.py`, `telegram_service.py` — el usuario nunca se entera de que la IA falló) con propagación explícita como HTTP 500 (`ai_routes.py`, `agent_routes.py`). Solo `ai_routes.py:78-99` maneja explícitamente `ResourceExhausted` (429) con fallback a otro modelo; en ningún otro sitio del backend se captura ese error específico, ni hay reintentos con backoff para llamadas a Gemini.
- **Sin límites de tokens ni streaming en ninguna llamada a Gemini** (`generation_config`/`max_output_tokens` no aparece en el backend).
- **Análisis de imágenes secuencial, sin paralelismo**: `_analyze_images` procesa una imagen a la vez con llamadas HTTP síncronas en loop — el costo/latencia escala linealmente con el número de imágenes nuevas en Drive.
- **Fuga de archivos temporales en `content_generation.py:201-212`**: crea un `NamedTemporaryFile` y hace `unlink` fuera de un `try/finally` — si falla la descarga entre medio, el archivo queda huérfano en disco. Los otros dos sitios que crean temp files (`ai_routes.py`, `agent_service.py`) sí usan `finally` correctamente.
- **Índices de base de datos faltantes, localizados en las tablas más nuevas**: `content_proposals.account_id`/`.status`, `visual_analyses.account_id` y `agent_logs.account_id` no tienen ningún índice pese a filtrarse constantemente — mientras que tablas creadas en migraciones anteriores (`templates`, `post_performance`, analytics) sí los tienen. Es una omisión localizada en la migración 014, no un patrón general.
- **La tabla `posts` no tiene `CREATE TABLE` en ninguna de las 18 migraciones** — fue creada fuera de control de versiones (probablemente a mano en el dashboard de Supabase), lo que impide reconstruir el esquema completo solo desde el repo y es la razón por la que tampoco aparece con RLS en las migraciones.

### 4.4 Testing — hallazgos nuevos

- **Backend**: 13 archivos de test para 27 módulos de rutas/servicios (~1:2), pero **los tests mockean Supabase por completo** (`conftest.py`) — no hay ningún test de integración contra un Postgres real, así que no detectarían problemas de esquema, índices o RLS.
- **Frontend**: ~36% de componentes con test (12/33), Playwright solo cubre auth y dashboard (2 specs) — nada de posts, calendario, planner, analytics ni cuentas.
- Un archivo de test (`MonthlyCampaignSection.test.tsx`) está mal nombrado — en realidad testea `AgentStrategyDrawer.tsx`, resto de una refactorización sin limpiar.

---

## 5. Próximos pasos propuestos (para decidir juntos, no para ejecutar ya)

Prioridad sugerida combinando el análisis del otro agente y el mío, por impacto real:

1. **Seguridad crítica**: propagación de JWT al cliente Supabase + RLS en `posts`/`content_proposals`/`agent_logs`/`visual_analyses`, el IDOR en `create_post`, cifrado de tokens de Instagram/Drive, y el `state` OAuth sin nonce firmado.
2. **Webhook de Telegram**: dejar de loguear el token, y añadir verificación de propiedad chat↔post en los handlers.
3. **Bloqueo del event loop**: convertir endpoints síncronos-sobre-async a `def` o `asyncio.to_thread`.
4. **Cron secuencial del agente**: paralelizar `run_agent_for_all_accounts`.
5. **Consolidar los 4 sistemas de generación de IA** en uno solo (elimina duplicación, arregla el drift de idioma entre `agent_routes.py` y `telegram_service.py`).
6. **Capa de API centralizada en frontend**: elimina las 72 URLs hardcodeadas y el boilerplate repetido; sería también la base para arreglar el problema de que el frontend no funciona fuera de `localhost`.
7. **Índices faltantes** en `content_proposals`, `visual_analyses`, `agent_logs` — cambio de bajo riesgo y alto impacto en rendimiento.
8. **Decidir qué hacer con las tablas huérfanas** (`content_generation_queue`/`history`): ¿implementar el worker que faltaba, o eliminarlas si el flujo síncrono actual es intencional y suficiente?
9. **Cosméticos/menores**: línea "Tailwind CSS" en tu CLAUDE.md, comentario de backoff en `post_scheduler.py`, unificar las dos implementaciones de `get_current_user`, eliminar `JWT_SECRET` muerto o usarlo, `config.py` centralizado con fail-fast real.
10. Menor prioridad: `asyncio.new_event_loop()` local (bajo riesgo real), template selector (E, depende de un repo externo no auditado), rate limiting de Gemini/Instagram (no hay incidentes reportados todavía pero es cuestión de tiempo con más cuentas activas).

No voy a tocar código todavía — esto es la síntesis para que decidamos qué abordar primero y con qué alcance.

---

## 6. Cómo decide el agente su rol de "Community Manager" — evaluación para cuentas personales

Investigado con 2 agentes adicionales leyendo completo `agent_service.py`, `agent_routes.py`, `AgentStrategyDrawer.tsx`, `google_drive_connector.py` y las migraciones de estrategia (014, 015, 018).

### 6.1 El pipeline de decisión, paso a paso

1. **Selección de imágenes** (`_scan_drive`, `agent_service.py:268-286`): query a Drive API **sin `orderBy`** — orden no garantizado por fecha. Único filtro: excluir imágenes ya presentes en `visual_analyses`. Sin scoring de calidad, mood o relevancia de campaña.
2. **Análisis visual** (`_analyze_images`, `agent_service.py:358-435`): Gemini Vision genera `objects/mood/theme/suggested_caption` por imagen, uno por uno (sin batch ni paralelismo — ver punto 4.3). El prompt de tono viene de `_build_strategy_context` (`289-316`), que sí usa `account_type`/`default_tone`/`target_audience`/`style_guide` configurados por el usuario.
3. **Planificación semanal** (`_ai_schedule`, `agent_service.py:35-132`): un único prompt le da a Gemini la lista de imágenes (solo su `theme`, sin fecha ni score) + configuración de cuenta, y le pide elegir día/tipo de post por slot. **Heurísticas hardcodeadas en el prompt** ("reels rinden mejor martes/miércoles/jueves", "carousels lunes/miércoles") — no salen de datos reales de la cuenta. **No hay validación posterior de que el resultado respete `content_type_mix`** — es solo una sugerencia textual al modelo.
4. **Fallback determinista** (si Gemini falla, `_build_calendar:438-477`): toma `analyses[:len(available_days)]` — los primeros N de la lista tal cual llegó — y sí reparte los tipos de post exactamente según `content_type_mix`, pero a ciegas del contenido visual.
5. **Hashtags**: nunca de una lista curada ni de datos de tendencias — siempre inventados libremente por Gemini dentro del `suggested_caption`, guiado solo por una instrucción de rango numérico.
6. **Hora del día**: round-robin sobre `best_times` en `_create_drafts` (línea 503) — configurada a mano o sugerida una vez por un endpoint de IA (`suggest-times`) basado en heurísticas de sector/audiencia, **no en el histórico real de engagement de la cuenta** (pese a que el sistema sí recolecta `daily_account_metrics`/`audience_demographics` cada hora — nunca se cruzan con esta decisión).
7. **Aprobación**: todo se crea como `posts.status='draft'` dentro de una `content_proposals.status='pending_approval'`. Nunca se publica sin aprobación humana explícita (web o Telegram).

### 6.2 Campos "fantasma" — configurado pero sin efecto real

De los 16 campos del drawer de estrategia (`STRATEGY_FIELDS`, `agent_routes.py:176-181`), **7 se guardan pero nunca se leen en `agent_service.py`**: `sector`, `purpose`, `content_pillars`, `reference_accounts`, `posts_per_week`, `scheduling_mode`. Y `hashtag_strategy` sí se lee pero es un no-op — sus tres valores (`minimal/moderate/maximum`) mapean todos al mismo rango `'3-5'` (`agent_service.py:294-295`). El wizard `generate_strategy` (endpoint de sugerencia por IA) rellena estos mismos campos con gran detalle, reforzando la sensación de personalización que luego no tiene efecto.

También hay un campo `ai_strategy` referenciado en `_ai_schedule` (línea 46) que **no existe en ninguna migración de `instagram_accounts`** — código muerto, siempre evalúa a `''`.

### 6.3 Campos que sí importan

`account_type`, `default_tone`, `target_audience`, `style_guide`, `posting_frequency`, `best_times`, `content_type_mix`, `preferred_days` — estos se leen y afectan el resultado real. `monthly_campaigns` es opcional (fallback silencioso a `''` si no existe) pero sí añade contexto narrativo/de hitos cuando se configura.

### 6.4 Aptitud para cuentas personales

**Sí está diseñado para esto, no es un añadido secundario**: `account_type: 'personal'` es el default en base de datos y en el frontend, hay un selector dedicado "Personal vs Profesional" con defaults distintos (`PERSONAL_STRATEGY_DEFAULTS` vs `PROFESSIONAL_STRATEGY_DEFAULTS`, `AgentStrategyDrawer.tsx:80-96`), y el pipeline deportivo de PROJECT1 (`template_selector.py`) está completamente desacoplado — `agent_service.py` no lo importa ni lo invoca nunca. El único requisito "de negocio" es que Meta exige cuenta Business/Creator para usar la Graph API — una limitación de la plataforma, no de SocialLab.

**Pero la diferenciación real entre personal y profesional es delgada**: en la práctica son solo dos ramas de plantilla de texto en `_build_strategy_context` y dos diccionarios de mezcla de formatos por defecto. No existe:
- Continuidad narrativa entre ejecuciones semanales (más allá del campo opcional `monthly_campaigns.strategy_mode='personal_storyline'`, que solo añade una frase al prompt).
- Aprendizaje de qué formatos/horarios funcionan mejor con los datos reales de `instagram_insights` que el sistema ya recolecta.
- Mecanismo que evite repetir temas/moods semana tras semana (no hay memoria de qué se publicó antes más allá de no reusar la misma imagen).
- Cualquier señal de "momento vital" o relevancia temporal en la selección de imágenes — es esencialmente orden de llegada a Drive.

### 6.5 Implicaciones para priorizar mejoras

Esto añade una categoría nueva a la lista de próximos pasos (sección 5): **antes de invertir en pulir la config UI**, vale la pena decidir si esos 7 campos fantasma se conectan al pipeline real o se eliminan de la UI (ahora mismo generan una falsa sensación de control). Y si el objetivo del producto es diferenciarse en "cuentas personales", el mayor apalancamiento no está en más campos de configuración sino en: (a) usar los datos de `instagram_insights` ya recolectados para informar `best_times`/mix real en vez de heurísticas genéricas hardcodeadas en el prompt, y (b) alguna forma de memoria/continuidad entre semanas para evitar que el agente se sienta "genérico" en una cuenta personal.
