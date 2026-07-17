# Backlog de Mejoras — Punto de partida para `/opsx-explore`

Este documento consolida `AUDITORIA_SOCIALLAB.md` y `OPTIMIZACIONES_PROCESOS_Y_TOKENS.md` en items accionables. No re-audita ni añade hallazgos nuevos — cada item cita la evidencia ya verificada en esos dos documentos, troceada para que un agente pueda arrancar `/opsx-explore <name>` directamente sobre ella, sin tener que releer ambos documentos completos primero.

Cada item incluye: nombre sugerido de change, problema con evidencia `archivo:línea`, por qué importa, archivos afectados, dirección propuesta, dependencias y esfuerzo estimado. Todos usan `/opsx-propose`, salvo el item 17 (Hermes/MCP), que por su escala requiere `/explore-plan`.

---

## Seguridad

### 1. `jwt-propagation-rls`

**Problema:** El cliente `supabase` (anon key) es un singleton creado una sola vez al importar el módulo; nunca se propaga el JWT del usuario autenticado hacia él (no hay `set_session` ni `postgrest.auth` en todo el backend). Resultado: `auth.uid()` es `NULL` en cualquier query hecha con ese cliente. Además, `posts`, `content_proposals`, `agent_logs` y `visual_analyses` **nunca reciben `ENABLE ROW LEVEL SECURITY`** en ninguna de las 18 migraciones — no hay política que saltarse aunque se quisiera.

**Por qué importa:** Las políticas RLS existentes (`instagram_accounts`, `templates`, etc.) actúan como candado total, no como aislamiento por usuario — fuerzan a usar `admin_supabase` en todas partes. Migrar a "usar el cliente con JWT" no resuelve nada si antes no se arregla la propagación del JWT.

**Archivos afectados:** cliente Supabase (inicialización, singleton anon), todas las rutas que hoy usan `admin_supabase` por necesidad en vez de por elección, migraciones (nueva migración para `posts`/`content_proposals`/`agent_logs`/`visual_analyses`).

**Dirección propuesta:** (1) Propagar el JWT del request autenticado al cliente Supabase por request (no singleton global). (2) Añadir migración con `ENABLE ROW LEVEL SECURITY` + políticas para las 4 tablas sin protección. Hacer esto en ese orden — RLS sin JWT propagado no cambia nada.

**Dependencias:** Bloqueante para el item 2 (IDOR) si se quiere resolver con RLS en vez de con un chequeo manual — aunque el item 2 puede resolverse de forma independiente y más rápida con un chequeo explícito de ownership.

**Esfuerzo:** L.

---

### 2. `idor-create-post`

**Problema:** `backend/routes/posts_routes.py:72-78`, en `create_post`. El parámetro `instagram_account_id` (controlado por el cliente) se consulta con `admin_supabase` filtrando **solo por `id`**, sin verificar que pertenezca al usuario autenticado.

**Por qué importa:** Un usuario puede pasar el `instagram_account_id` de otra cuenta y el backend leerá su `telegram_chat_id` y disparará un mensaje de aprobación al chat de Telegram de otro usuario.

**Archivos afectados:** `backend/routes/posts_routes.py:72-78`.

**Dirección propuesta:** Añadir verificación explícita de que `instagram_account_id` pertenece al `user_id` del JWT antes de continuar (filtrar por `id` + `user_id`, o validar contra la lista de cuentas del usuario autenticado).

**Dependencias:** Ninguna — puede resolverse antes o independientemente del item 1.

**Esfuerzo:** S.

---

### 3. `cifrado-tokens-ig-drive`

**Problema:** Tokens de Instagram y Google Drive almacenados en texto plano en `instagram_accounts`/`drive_tokens` (columnas `TEXT`, sin cifrado). El de Drive está protegido por RLS "solo service role"; el de Instagram no tiene ninguna protección adicional.

**Por qué importa:** Cualquier acceso a la base de datos (dump, backup expuesto, acceso admin comprometido) expone directamente credenciales de las cuentas de Instagram/Drive de los usuarios.

**Archivos afectados:** `instagram_accounts`, `drive_tokens` (esquema), servicios que leen/escriben esos tokens (`google_drive_connector.py`, servicio de Instagram OAuth).

**Dirección propuesta:** Cifrar los tokens en reposo (p. ej. `pgcrypto` en Supabase, o cifrado a nivel de aplicación antes de insertar/leer).

**Dependencias:** Ninguna.

**Esfuerzo:** M.

---

### 4. `oauth-state-nonce`

**Problema:** El `state` de OAuth = `user_id` en claro, sin nonce firmado, tanto en el flujo de Instagram como en el de Drive.

**Por qué importa:** Debilidad de diseño CSRF clásica en el flujo OAuth — un `state` predecible facilita ataques de fijación/CSRF sobre el callback.

**Archivos afectados:** `backend/routes/instagram_routes.py` (login/callback), flujo equivalente de Drive OAuth.

**Dirección propuesta:** Generar un nonce firmado (o token de un solo uso con expiración corta) como `state`, validado en el callback antes de asociar la cuenta.

**Dependencias:** Ninguna.

**Esfuerzo:** S.

---

### 5. `telegram-webhook-token-ownership`

**Problema:** Dos hallazgos distintos en el mismo subsistema: (a) `telegram_service.py:44` loguea la URL completa del webhook, que incluye el bot token que lo protege; (b) los handlers de aprobar/rechazar/editar del webhook actúan sobre `post_id`/`proposal_id` sin comprobar que el `chat_id` que llama esté vinculado a la cuenta dueña de ese post.

**Por qué importa:** (a) filtra una credencial sensible en logs. (b) un chat que ya interactuó con el bot podría, en teoría, tocar posts de otra cuenta si conoce o adivina el ID.

**Archivos afectados:** `telegram_service.py:44` (logging), handlers de callback del webhook en `telegram_routes.py`/`telegram_service.py`.

**Dirección propuesta:** Quitar el token de la URL logueada (loguear solo la ruta, no la query string completa). Añadir verificación `chat_id` ↔ cuenta dueña del `post_id`/`proposal_id` antes de ejecutar cualquier acción del callback.

**Dependencias:** Ninguna.

**Esfuerzo:** S.

---

## Rendimiento / arquitectura backend

### 6. `event-loop-async-endpoints`

**Problema:** `supabase-py` en este proyecto es 100% síncrono (`create_client`, no `acreate_client`). **24 de 37 endpoints** en `agent_routes.py`, `instagram_routes.py`, `posts_routes.py` y `telegram_routes.py` son `async def` que ejecutan `.execute()` síncrono directamente en su cuerpo — patrón dominante, no caso aislado (`agent_routes.py` tiene 14/15). `reorder_proposal_slot` encadena hasta 8 `.execute()` en una sola request.

**Por qué importa:** Cada llamada síncrona a Supabase dentro de una ruta `async def` bloquea el event loop de FastAPI/uvicorn, degradando la concurrencia de todo el backend bajo carga.

**Archivos afectados:** `agent_routes.py`, `instagram_routes.py`, `posts_routes.py`, `telegram_routes.py`.

**Dirección propuesta:** Declarar esas rutas como `def` normal (FastAPI las ejecuta en threadpool automáticamente) o envolver las llamadas síncronas con `asyncio.to_thread`.

**Dependencias:** Ninguna, pero es un cambio transversal — considerar dividirlo por archivo (4 sub-changes) en vez de uno solo si se quiere revisar en PRs pequeños.

**Esfuerzo:** L (por volumen, no por dificultad técnica).

---

### 7. `cron-paralelizacion-agente`

**Problema:** `main.py:99-123`, `run_agent_for_all_accounts()` usa un `for` plano sin paralelismo. Cada cuenta espera a que termine la anterior.

**Por qué importa:** El tiempo total de la ejecución semanal/cron escala linealmente con el número de cuentas — no escala a multi-cuenta real.

**Archivos afectados:** `main.py:99-123`.

**Dirección propuesta:** Paralelizar con `asyncio.gather` (respetando los límites de tasa de Gemini/Instagram — no lanzar todas las cuentas a la vez sin control, ver rate limiting mencionado en la sección de vigilancia).

**Dependencias:** Relacionado con el item 16 (paralelizar `_analyze_images`) — mismo tipo de cambio, evaluar si conviene abordarlos juntos.

**Esfuerzo:** M.

---

### 8. `db-indices-faltantes`

**Problema:** `content_proposals.account_id`/`.status`, `visual_analyses.account_id` y `agent_logs.account_id` no tienen ningún índice pese a filtrarse constantemente — mientras que tablas de migraciones anteriores (`templates`, `post_performance`, analytics) sí los tienen. Omisión localizada en la migración 014.

**Por qué importa:** Cambio de bajo riesgo y alto impacto en rendimiento de queries que ya se ejecutan constantemente.

**Archivos afectados:** nueva migración SQL sobre `content_proposals`, `visual_analyses`, `agent_logs`.

**Dirección propuesta:** Añadir índices sobre las columnas mencionadas.

**Dependencias:** Ninguna.

**Esfuerzo:** S.

---

## Duplicación / limpieza

### 9. `consolidar-sistemas-ia-duplicados`

**Problema:** 4 sistemas paralelos de generación de contenido con IA que no comparten código: (a) análisis de imagen con Gemini Vision reimplementado casi idéntico en `agent_service.py` y `ai_routes.py`; (b) regeneración de caption de un slot triplicada entre `agent_routes.py` (español) y `telegram_service.py` (inglés — hay *drift* de idioma entre las dos copias); (c) un tercer flujo completo de captions "manual" (`caption_generator.py`/`content_generation.py`, para datos de PROJECT 1) que nunca se cruza con el del agente autónomo. El patrón "strip markdown fences + json.loads" está copiado literalmente en 5 sitios. Además, `CaptionGeneratorService` (la clase) es código muerto en producción — solo se ejercita en su propio bloque `__main__`.

**Por qué importa:** Cualquier fix o mejora de prompt tiene que aplicarse en múltiples sitios manualmente, y ya hay divergencia real de comportamiento (idioma) entre dos copias del mismo flujo.

**Archivos afectados:** `agent_service.py`, `ai_routes.py`, `agent_routes.py`, `telegram_service.py`, `caption_generator.py`, `content_generation.py`.

**Dirección propuesta:** Extraer un módulo único de utilidades de generación IA (parseo de respuesta JSON, prompt building por caso de uso) consumido por los cuatro puntos de entrada, arreglando el drift de idioma en el proceso. Evaluar si `CaptionGeneratorService` se elimina por no usarse en producción.

**Dependencias:** Ninguna directa, pero es un cambio grande — buen candidato para dividir en sub-changes (análisis de imagen / regeneración de caption / limpieza de código muerto).

**Esfuerzo:** L.

---

### 10. `frontend-api-layer-centralizada`

**Problema:** 0 cliente HTTP compartido en frontend, 64 llamadas a `fetch()` sueltas en 21 archivos, **72 ocurrencias de `http://localhost:8000` hardcodeado** en 22 archivos (no usa `import.meta.env`). El boilerplate de headers de auth está copiado ~20 veces. Tampoco existe una carpeta `types/` compartida: `Post` está definida de forma distinta e incompatible en varios componentes; 46 usos de `: any` + 17 de `as any`.

**Por qué importa:** El frontend no funciona fuera de `localhost` sin tocar código a mano — bloquea cualquier despliegue a un entorno real.

**Archivos afectados:** los 21 archivos con `fetch()` directo (buscar `http://localhost:8000` para localizarlos todos).

**Dirección propuesta:** Crear un cliente API centralizado que lea la base URL de `import.meta.env`, migrar los 64 `fetch()` a usarlo, y de paso crear `types/` compartido para `Post` y tipos afines.

**Dependencias:** Ninguna.

**Esfuerzo:** L.

---

### 11. `tablas-huerfanas-decision`

**Problema:** `content_generation_queue` y `content_generation_history` reciben `INSERT` pero nunca se actualizan ni se procesan — no hay worker ni cron que las consuma. El endpoint que expone su estado siempre mostrará contadores en cero. El flujo real de generación es síncrono dentro del propio request HTTP y ni siquiera usa la cola.

**Por qué importa:** Es una decisión de producto, no solo técnica — mantener tablas y endpoints que nunca hacen nada es deuda muerta que confunde a quien lea el código.

**Archivos afectados:** las dos tablas, el endpoint que expone su estado, `content_generation.py`.

**Dirección propuesta:** Decidir entre (a) implementar el worker que falta si el async processing es deseado, o (b) eliminar las tablas y el endpoint si el flujo síncrono actual es intencional y suficiente. Requiere decisión del usuario antes de `/opsx-propose` — no es solo técnico.

**Dependencias:** Ninguna.

**Esfuerzo:** S si se elige eliminar, L si se elige implementar el worker.

---

### 12. `auth-config-unificacion`

**Problema:** Tres hallazgos relacionados: (a) doble implementación de auth con contratos distintos — `backend/auth/dependencies.py:13` (devuelve `User` Pydantic) y `backend/auth/jwt_handler.py:13` (devuelve `dict`) son dos guardianes `get_current_user()` independientes; 8 archivos de rutas usan uno, 4 usan el otro; (b) `JWT_SECRET` está en `.env.example:31` pero no se usa en ningún `.py` del backend — toda validación delega en `supabase.auth.get_user(token)`; (c) sin `config.py` centralizado — variables de entorno leídas de forma dispersa con `os.getenv` en ~10 archivos; solo `SUPABASE_URL`/`SUPABASE_KEY` fallan rápido al arrancar, el resto falla tarde y en silencio.

**Por qué importa:** Riesgo de que las dos implementaciones de auth diverjan silenciosamente si se añade lógica (revocación, roles) a solo una. La falta de fail-fast en config hace que errores de configuración de Instagram/Telegram/Gemini/Drive se descubran solo cuando un usuario ejerce esa función, no al arrancar.

**Archivos afectados:** `backend/auth/dependencies.py`, `backend/auth/jwt_handler.py`, `.env.example`, los ~10 archivos con `os.getenv` disperso.

**Dirección propuesta:** Unificar en una sola implementación de `get_current_user()` (migrar los 4 archivos que usan la otra), eliminar `JWT_SECRET` muerto o empezar a usarlo si se decide validar localmente, crear `config.py` centralizado que falle rápido al arrancar si falta cualquier variable requerida.

**Dependencias:** Ninguna, pero tocar auth requiere testing de regresión completo (regla dura del proyecto: "Never modify auth middleware without full auth regression testing").

**Esfuerzo:** M.

---

### 13. `cosmeticos-menores`

**Problema (bundle de 4 fixes triviales, no relacionados entre sí más que por tamaño):**
- La línea de stack resumen en `CLAUDE.md` dice "Tailwind CSS" — el proyecto usa Bootstrap 5 + CSS por componente (inconsistencia interna, contradice la sección "Hard Constraints" del mismo archivo).
- El comentario del backoff exponencial en `post_scheduler.py:162-163` dice "3er intento: 30min" pero la fórmula (`5 * 2^retry_count`) da 20 min.
- `PostDetailModal.tsx` duplicado por nombre en `components/posts/` y `components/analytics/panels/` — mismo nombre, contenido y tipos completamente distintos.
- `MonthlyCampaignSection.test.tsx` está mal nombrado — en realidad testea `AgentStrategyDrawer.tsx`, resto de una refactorización sin limpiar.

**Por qué importa:** Bajo impacto individual, pero cada uno genera confusión a quien lea el código sin contexto.

**Archivos afectados:** `CLAUDE.md`, `post_scheduler.py:162-163`, ambos `PostDetailModal.tsx`, `MonthlyCampaignSection.test.tsx`.

**Dirección propuesta:** Corregir la línea de stack en CLAUDE.md, corregir el comentario del backoff, renombrar uno de los dos `PostDetailModal.tsx` (o el componente) para desambiguar, renombrar el archivo de test a su nombre real.

**Dependencias:** Ninguna. Candidato a resolverse en un solo change chico dado que son 4 fixes de una línea cada uno.

**Esfuerzo:** S.

---

## Inteligencia del agente

### 14. `agente-campos-fantasma`

**Problema:** De los 16 campos del drawer de estrategia (`STRATEGY_FIELDS`, `agent_routes.py:176-181`), **7 se guardan pero nunca se leen en `agent_service.py`**: `sector`, `purpose`, `content_pillars`, `reference_accounts`, `posts_per_week`, `scheduling_mode`. `hashtag_strategy` sí se lee pero es un no-op — sus tres valores (`minimal/moderate/maximum`) mapean todos al mismo rango `'3-5'` (`agent_service.py:294-295`). Además, `ai_strategy` se referencia en `_ai_schedule` (línea 46) pero **no existe en ninguna migración de `instagram_accounts`** — código muerto, siempre evalúa a `''`.

**Por qué importa:** El wizard `generate_strategy` rellena estos campos con gran detalle, generando una falsa sensación de personalización que luego no tiene efecto real en el output del agente.

**Archivos afectados:** `agent_routes.py:176-181`, `agent_service.py` (289-316, 294-295, 46), `AgentStrategyDrawer.tsx`.

**Dirección propuesta:** Decisión de producto por campo: conectar cada campo fantasma al pipeline real en `agent_service.py` (usarlo en el prompt de `_build_strategy_context`/`_ai_schedule`), o eliminarlo de la UI si no se va a implementar pronto. Eliminar `ai_strategy` (código muerto) en cualquier caso.

**Dependencias:** Relacionado con item 15 — ambos tocan `_build_strategy_context`/`_ai_schedule`, buen candidato a resolverse en la misma iteración de diseño aunque sean changes separados.

**Esfuerzo:** M (depende de cuántos campos se decida conectar vs. eliminar).

---

### 15. `agente-best-times-datos-reales`

**Problema:** La hora del día se decide por round-robin sobre `best_times` en `_create_drafts` (línea 503) — configurado a mano o sugerido una vez por un endpoint de IA (`suggest-times`) basado en heurísticas de sector/audiencia, **no en el histórico real de engagement de la cuenta**, pese a que el sistema ya recolecta `daily_account_metrics`/`audience_demographics` cada hora. Además, `_ai_schedule` usa heurísticas hardcodeadas en el prompt ("reels rinden mejor martes/miércoles/jueves") en vez de datos reales, y no valida que el resultado de Gemini respete `content_type_mix` — es solo una sugerencia textual al modelo.

**Por qué importa:** Es el mayor apalancamiento identificado para diferenciar cuentas personales (sección 6.5 de la auditoría): usar datos ya recolectados de `instagram_insights` para informar `best_times`/mix real, en vez de heurísticas genéricas.

**Archivos afectados:** `agent_service.py` (`_ai_schedule:35-132`, `_create_drafts:503`), endpoint `suggest-times`.

**Dirección propuesta:** Cruzar `daily_account_metrics`/`instagram_insights` reales de la cuenta al calcular `best_times` y al armar el prompt de `_ai_schedule`, en vez de heurísticas fijas. Añadir validación posterior de que el resultado de Gemini respeta `content_type_mix` configurado.

**Dependencias:** Relacionado con item 14.

**Esfuerzo:** M.

---

## Eficiencia de imágenes/IA

### 16. `imagenes-analisis-eficiente`

**Problema (combina hallazgos de ambos documentos fuente):** `_analyze_images` procesa imágenes una a una con llamadas HTTP síncronas en loop, sin paralelismo — el costo/latencia escala linealmente con el número de imágenes nuevas en Drive. El escaneo ocurre en batch la noche de la ejecución semanal, no cuando la imagen se sube. No hay límites de tokens (`max_output_tokens`) ni streaming en ninguna llamada a Gemini. Solo `ai_routes.py:78-99` maneja explícitamente `ResourceExhausted` (429) con fallback a otro modelo — en ningún otro sitio del backend se captura ese error específico ni hay reintentos con backoff para Gemini. `content_generation.py:201-212` tiene fuga de archivos temporales (`NamedTemporaryFile` sin `try/finally`).

**Por qué importa:** Combina latencia evitable (batch dominical de minutos vs. análisis incremental de segundos) con robustez ante rate limits de Gemini (100 req/h, sin contador ni caché actual — ver también nota de vigilancia).

**Archivos afectados:** `agent_service.py` (`_scan_drive`, `_analyze_images:358-435`), `ai_routes.py:78-99`, `content_generation.py:201-212`.

**Dirección propuesta (de `OPTIMIZACIONES_PROCESOS_Y_TOKENS.md`, sección 8):**
- Análisis reactivo: webhook de Google Drive Push Notifications que dispare el análisis en cuanto se sube una imagen nueva, en vez de escanear todo en batch — la ejecución semanal solo lee de `visual_analyses` ya poblada.
- Procesamiento in-memory: descargar la imagen desde Drive como `io.BytesIO` y pasarla a Gemini sin escribir archivos temporales en disco.
- Paralelizar las llamadas de análisis que sí queden (`asyncio.gather` en vez de loop secuencial).
- Segregación de modelos: Gemini 2.5 Flash estrictamente para visión/OCR (costo bajo, latencia baja), reservar modelos más caros solo para el paso de planificación/redacción.
- Manejar `ResourceExhausted` de forma consistente en todos los puntos que llaman a Gemini, no solo en `ai_routes.py`. Envolver el temp file de `content_generation.py` en `try/finally`.

**Dependencias:** El webhook reactivo depende de tener un endpoint público accesible (Drive Push Notifications requiere una URL HTTPS que Google pueda alcanzar) — relevante si el despliegue sigue en localhost (ver item 10).

**Esfuerzo:** L (el webhook reactivo es la pieza más grande; in-memory/paralelismo/segregación de modelos son S-M cada una y pueden ir en changes separados si se prefiere iterar).

---

## Apuesta arquitectónica grande — usar `/explore-plan`, no `/opsx-propose`

### 17. `hermes-mcp-integracion`

**Problema/motivación:** El pipeline actual es secuencial y rígido (`agent_service.py` hace scan → analyze → schedule → create drafts en un flujo fijo), y `telegram_service.py` depende de un parseador manual de regex/callbacks (`approve:`, `reject:`, `edit_text:`, `timeedit_:`) en vez de lenguaje natural.

**Por qué es distinto al resto de este backlog:** No es un fix puntual — es un cambio de arquitectura que sustituye servicios centrales (`agent_service.py`, `telegram_service.py`), estimado en 14-17 días hábiles en 3 fases. Por eso **no debe entrar en el flujo `/opsx-propose`** (pensado para cambios incrementales) sino en `/explore-plan` (6 agentes de planificación en paralelo, para features grandes con arquitectura propia).

**Arquitectura propuesta:** Modelo Hermes Agent (orquestador con memoria persistente + librería de skills) conectado vía Model Context Protocol (MCP, inspirado en Wayland) a tres servidores MCP: Supabase, Google Drive, Instagram Graph API. Ver diagrama Mermaid completo en `OPTIMIZACIONES_PROCESOS_Y_TOKENS.md` sección 1.

**Código a depreciar/simplificar:** `agent_service.py` (escaneo, análisis secuencial, construcción de slots — absorbido por el bucle de razonamiento de Hermes + herramientas MCP), `telegram_service.py` (elimina el parseador manual — el bot pasa a ser puente de texto natural hacia el agente).

**Código nuevo:** `backend/mcp/` (servidores MCP para Drive/Supabase/Instagram), `backend/services/hermes_orchestrator.py` (daemon Hermes + memoria persistente), cambios en `telegram_routes.py`/`agent_routes.py` para redirigir payloads al orquestador.

**Fases (de `OPTIMIZACIONES_PROCESOS_Y_TOKENS.md` sección 4):**
1. Capa MCP (4-5 días) — wrappers de Supabase/Drive/Instagram como herramientas MCP.
2. Motor Hermes (6-7 días) — daemon, prompt de sistema, memoria, sustituir `agent_service.py`.
3. Telegram natural (4-5 días) — webhook conectado a la sesión de Hermes, parseo conversacional.

**Optimizaciones empaquetadas dentro de este item** (solo aplican si se adopta esta arquitectura — de ahí que vivan aquí y no como items separados):
- **Tokens:** prompt caching nativo de Gemini (system prompt, esquema de BD, firmas JSON de herramientas MCP cacheados 1h, hasta 90% de ahorro en tokens de entrada); compresión de contexto (ventana de 5-8 mensajes + resumen de turnos antiguos); poda dinámica de herramientas (tool pruning — no enviar todas las herramientas MCP en cada llamada, solo las relevantes al intent detectado).
- **Latencia/fluidez:** enrutamiento híbrido (comandos estructurados como aprobar/rechazar se ejecutan directo en DB sin pasar por Hermes; solo lenguaje natural pasa por el bucle de razonamiento); streaming de estado en Telegram/React (mensajes editados progresivamente: "Escaneando Drive... [OK]", "Generando captions... [OK]") para mitigar los 15-30s de latencia esperados del bucle ReAct.

**Pros/contras ya documentados:** steerability extrema y flexibilidad de modelo (MCP desacopla de Gemini específicamente) vs. latencia mayor por turno, complejidad operativa de mantener un daemon persistente, y consumo de tokens más alto por ejecución que los prompts directos actuales — mitigado por el punto anterior pero no eliminado.

**Dependencias:** Es el item más grande del backlog; probablemente conviene resolver primero los items de seguridad (1-5) y el event loop (6) antes de construir una arquitectura nueva sobre las mismas bases inestables.

**Esfuerzo:** XL (14-17 días hábiles estimados).

---

## Backlog de baja prioridad / vigilancia (sin plantilla completa)

Hallazgos que la propia auditoría marcó como bajo riesgo real o dependientes de contexto externo — no ameritan un change dedicado todavía, pero vale la pena vigilarlos:

- **Event loop local en `agent_service.py` (líneas 233-239):** usa `asyncio.new_event_loop()` + `run_until_complete()` + `close()`. Nunca corre en el hilo del event loop principal de uvicorn (se invoca desde `BackgroundTasks`/threadpool de APScheduler), así que el riesgo directo es menor de lo que parece a primera vista. Sí es un code smell — `asyncio.run()` sería más correcto — y el `except Exception` genérico podría silenciar un `RuntimeError` real si algún cliente (Telegram/httpx) cachea el loop entre invocaciones del mismo hilo reutilizado.
- **Template selector (`template_selector.py:_check_player_rules`):** usa métricas planas (`min_goals`, `min_assists`, posición). El sistema de análisis por aspectos/percentiles que se sospechaba como contraparte no existe en este repo — el `metadata.json` que consume viene de un proyecto externo ("PROJECT 1"). Cualquier desajuste real solo se puede evaluar auditando ese otro repositorio.
- **Rate limiting de Gemini/Instagram:** no existe contador, caché ni throttling real pese a que el proyecto documenta límites (Gemini 100 req/h, Instagram 200 llamadas/h) — solo topes de tamaño de lote y reintentos con backoff ante fallos de red. Sin incidentes reportados todavía, pero es cuestión de tiempo con más cuentas activas. Relevante si se paraleliza el cron (item 7) sin control de concurrencia.
- **Condición de carrera potencial:** `_get_next_unplanned_week` y la exclusión de imágenes ya usadas no están protegidas por lock/transacción — ejecuciones concurrentes de `run_agent` para la misma cuenta podrían crear propuestas duplicadas para la misma semana. Relevante también si se paraleliza el cron (item 7).
- **Backend testing:** los tests mockean Supabase por completo (`conftest.py`) — no hay test de integración contra Postgres real, así que no detectarían problemas de esquema/índices/RLS que sí se están corrigiendo en items 1 y 8.
- **Frontend testing:** ~36% de componentes con test (12/33), Playwright solo cubre auth y dashboard — nada de posts, calendario, planner, analytics ni cuentas.
- **`posts` sin `CREATE TABLE` en ninguna migración:** fue creada fuera de control de versiones (probablemente a mano en el dashboard de Supabase). Impide reconstruir el esquema completo solo desde el repo. Si se toca la tabla en el item 1 (RLS), documentar su schema real en una migración correctiva de paso.
