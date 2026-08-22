# Context Session: Hermes Monthly Strategy Auto

**Feature:** hermes-monthly-strategy-auto
**Created:** 2026-07-22
**Status:** ✅ Plan final (Explore → Team Selection → Plan → Advice → Clarificación completos)

## Objetivo

Generar automáticamente la estrategia mensual (`monthly_campaigns`) mediante Hermes, N-2 días
antes de que termine el mes en curso, para cada cuenta activa. La estrategia generada debe quedar
pendiente de aprobación (Telegram o app), y debe poderse modificar hablando con Hermes en lenguaje
natural desde ambos canales — comportamiento análogo al de la propuesta semanal ya construida
(`openspec/changes/archive/2026-07-22-hermes-mcp-integracion-fase-2/` y `-fase-3/`).

**Decisión ya tomada con el usuario:** el cajón de chat nuevo en el drawer de estrategia queda
**acotado a la estrategia mensual** — mismo patrón que `run_edit_session` (tools mínimas, sin
persistencia larga en `agent_memory`, resuelve una edición puntual y termina). No es un chat
abierto multi-turno. Esta restricción no se re-evalúa en Advice/Clarificación.

**Decisión ya tomada con el usuario:** este change se trata como feature grande (`/explore-plan`,
no `/opsx-propose`) porque introduce el primer punto de entrada frontend→Hermes (chat REST desde
`AgentStrategyDrawer.tsx`) — toda la arquitectura Hermes construida hasta ahora es backend-only
(cron semanal + webhook de Telegram).

---

## Estado Actual (Exploración completa)

### `monthly_campaigns` (migración 018)
```sql
CREATE TABLE monthly_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    month_date DATE NOT NULL,
    strategy_mode TEXT CHECK (strategy_mode IN ('commercial_campaign','personal_storyline')),
    title TEXT NOT NULL,
    description TEXT,
    milestones JSONB DEFAULT '[]'::jsonb,
    weekly_focus JSONB DEFAULT '{}'::jsonb,
    created_at/updated_at, UNIQUE(account_id, month_date)
);
```
**No tiene ninguna columna de estado/aprobación hoy.** Se escribe únicamente vía
`POST /api/agent/campaign` (upsert directo, sin revisión) desde el formulario manual del drawer —
`backend/routes/agent_routes.py:594-638`. Lectura: `GET /api/agent/campaign` (`:641-...`) y la tool
`supabase_get_campaign(instagram_account_id, week_start)` (`backend/mcp/supabase_server.py:122`,
extendida en `hermes-restaurar-contexto-agente`) que ya filtra por `week_start` para devolver
`{has_campaign, context_text, milestones_in_range}` a la sesión semanal de Hermes.

### Patrón de aprobación ya existente (`content_proposals`, para calcar)
- Modelo: `status: Literal["pending_approval","approved","rejected"]` (`models/schemas.py:157`).
- Endpoints: `POST /api/agent/proposals/{id}/approve` y `/reject` (`agent_routes.py:103-176`) —
  verifican ownership vía `instagram_accounts.user_id == current_user.id`, actualizan `status` +
  `resolved_at`.
- Telegram: `TelegramService.send_proposal_card` (`telegram_service.py:442`) — botones
  `proposal:approve:<id>` / `proposal:reject:<id>`, despachados en `_handle_proposal_callback`
  (`:511`). Verificación de ownership por chat vía `_verify_proposal_owner` (`:91`).
- Edición conversacional ya construida (Fase 3): ForceReply con tag `#timeedit_<id>_<idx>` /
  `#imgselect_<id>_<idx>` → regex en `handle_message` (`:274-320`) → `run_edit_session(edit_type=...)`.

### Cron jobs actuales (`backend/main.py:104-220`)
- `run_agent_for_all_accounts` — domingos 22:00, concurrencia acotada por `AGENT_CONCURRENCY_LIMIT`
  vía `asyncio.Semaphore` + `asyncio.gather` (patrón a reutilizar tal cual).
- `send_daily_briefings_for_all_accounts` — diario 09:00.
- Registrados en `startup_event()` sobre `PostScheduler().scheduler` (APScheduler), con
  `CronTrigger`, `replace_existing=True`, `max_instances=1`.

### Arquitectura Hermes/MCP ya construida (a reutilizar, no duplicar)
- `backend/services/hermes/orchestrator.py`: `run_session()` (sesión semanal, 13 tools, hasta
  `HERMES_MAX_TURNS=12`) y `run_edit_session(account_id, edit_type, context, user_message)`
  (sesión de edición acotada, `HERMES_EDIT_MAX_TURNS=3`, tool set por `edit_type` vía
  `_EDIT_TOOL_SETS`). `_dispatch_turn()` es el helper compartido de un turno de razonamiento.
- `backend/services/hermes/tool_bridge.py`: `ToolBridge` — descubre tools de instancias `FastMCP`,
  filtra `account_id`/`instagram_account_id` del schema que ve Gemini, lo inyecta en `dispatch()`
  desde la sesión (mitigación IDOR, no re-derivar, ya validada en 3 fases).
- `backend/services/hermes/prompts.py`: `get_system_prompt(account_id)` (sesión semanal) y
  `get_edit_prompt(edit_type, context)` (sesión de edición, con branch por `edit_type`).
- `backend/mcp/`: `drive_server.py`, `supabase_server.py` (14 tools), `vision_server.py`,
  `analytics_server.py` — un servidor por dominio, sin SQL libre, cada tool mapea a una operación
  fija.

### Frontend: `AgentStrategyDrawer.tsx` (833 líneas)
- Offcanvas de Bootstrap, un solo componente monolítico (sin subcomponentes propios salvo
  `HybridSelect`). Estado local con `useState` (sin Context). Estilo inline (`style={{...}}`) en
  vez de CSS por componente — **desviación ya existente** de `frontend.md` ("no inline style
  objects"), no introducida por este change; debo respetarla al extender el archivo (surgical
  change / match existing style, no lo "arreglo" de paso).
- Sección "Enfoque del Mes" (líneas 690-806): formulario manual puro — mes, modo, título,
  descripción, milestones, foco por semana — guarda vía `handleSave` → `POST /api/agent/campaign`.
  No hay ningún estado de aprobación ni chat hoy.
- Ya existe un patrón de "generar con IA" en el propio drawer: `handleGenerate()` (:345) llama a
  `POST /api/agent/generate-strategy` y rellena `cfg` — banner de éxito (`generatedBanner`),
  spinner (`generating`). Es la plantilla UX más cercana a reutilizar para "campaña generada por
  Hermes, pendiente de revisión", aunque ese endpoint es sincrónico de un solo turno (no Hermes).

---

## Propuesta de Arquitectura

### 1. Esquema: nueva migración `022_add_monthly_campaign_approval.sql`
Añadir a `monthly_campaigns`:
```sql
ALTER TABLE monthly_campaigns
  ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'
    CHECK (status IN ('pending_approval','approved','rejected')),
  ADD COLUMN generated_by TEXT NOT NULL DEFAULT 'user'
    CHECK (generated_by IN ('user','hermes')),
  ADD COLUMN resolved_at TIMESTAMPTZ;
```
**Decisión de diseño (documentar, no preguntar):** default `status='approved'`, `generated_by='user'`
para preservar el comportamiento actual sin migración de datos — las filas ya existentes (creadas a
mano) quedan aprobadas automáticamente. Solo las filas que Hermes cree nuevas nacen con
`status='pending_approval'`, `generated_by='hermes'`. El upsert manual del drawer (`handleSave`)
sigue escribiendo `status='approved'` explícitamente (edición directa del usuario no necesita
autoaprobarse-a-sí-misma).

### 2. `supabase_get_campaign` — filtrar por `status='approved'`
La sesión semanal de Hermes (`run_session`) no debe leer campañas `pending_approval`/`rejected` al
construir el contexto de la semana — evita que una campaña generada pero no revisada todavía
contamine captions reales. Cambio de una línea (`.eq('status', 'approved')`) en el `SELECT` de
`backend/mcp/supabase_server.py::supabase_get_campaign`. Sin cambio de firma ni de shape de salida.

### 3. Nueva sesión Hermes: `run_monthly_strategy_session(account_id) -> MonthlyStrategyResult`
**Revisión post-Advice (fastapi-backend-architect):** vive en un módulo nuevo
`backend/services/hermes/monthly_strategy.py`, no en `orchestrator.py` (que ya tiene 273 líneas
con `run_session` + `run_edit_session` + `_dispatch_turn` + `_correct_content_type_mix`). Importa
`_dispatch_turn` desde `orchestrator.py` (función pura, sin estado de orchestrator, se puede
importar sin circularidad). `_EDIT_TOOL_SETS["MONTHLY_STRATEGY"]` y el branch de
`get_edit_prompt` **sí** quedan en `orchestrator.py`/`prompts.py` — solo la sesión top-level nueva
se separa. Reutiliza `_dispatch_turn` y
`ToolBridge` (mismo patrón, no reescribir el bucle). Tool set: `supabase_get_account` (perfil),
`supabase_get_campaign` (con `include_pending=True` para leer el mes anterior como referencia de
continuidad — ver Pregunta Abierta #3), `analytics_get_empirical_scheduling_data` (opcional, para
que el foco de campaña considere qué tipo de contenido rinde mejor), y la tool nueva
`supabase_create_monthly_campaign` (ver punto 4). `HERMES_MONTHLY_MAX_TURNS` (env var, default 6 —
menor que el semanal porque el output es más compacto: un objeto, no N posts).

Prompt nuevo en `prompts.py`: `get_monthly_strategy_prompt(account_id)` — persona "estás generando
el enfoque narrativo/comercial del próximo mes", instruye a decidir `strategy_mode`, título,
descripción, hasta 4 hitos con fecha, y foco de cada semana, coherente con `sector`/`purpose`/
`content_pillars` del perfil de cuenta (mismo `_build_strategy_context` ya usado en el prompt
semanal — reutilizar, no duplicar).

### 4. Tool nueva: `supabase_create_monthly_campaign` en `backend/mcp/supabase_server.py`
```python
def supabase_create_monthly_campaign(
    instagram_account_id: int, month_date: str, strategy_mode: str,
    title: str, description: str, milestones: list[dict], weekly_focus: dict
) -> Dict[str, Any]:
    # INSERT con status='pending_approval', generated_by='hermes'
    # upsert on_conflict=(account_id, month_date) — si N-2 se ejecuta dos veces
    # por reintento de cron, no duplica fila
```
Mismo principio que las demás tools de escritura: una operación fija, sin SQL libre,
`account_id` inyectado por `ToolBridge` (nunca visible al modelo).

**Regla de idempotencia (post-Advice, cierra la interacción entre Preguntas Abiertas #1 y #5):**
la tool comprueba el estado de la fila existente para `(account_id, month_date)` antes de
escribir — nunca sobrescribe una fila `approved` (el usuario ya la validó, a mano o por Telegram/
chat) ni una `pending_approval` sin resolver (evita que un cron que corre varios días por la
guarda de rango regenere y pise la propuesta que el usuario todavía no ha revisado). Solo hace
upsert real si la fila no existe o está `rejected`. Regla única: *"Hermes nunca sobrescribe una
fila que no sea ya suya y sin resolver."* Ver Clarificación #1 y #2 para el resto de la política.

### 5. Cron nuevo: `run_monthly_strategy_for_all_accounts` en `main.py`
- Se registra en `startup_event()` junto a los otros dos, con `CronTrigger(hour=20, minute=0)` y
  una guarda interna (no un `CronTrigger` de día variable) — **confirmado por
  fastapi-backend-architect** como el idiom correcto de este proyecto (mismo patrón que
  `send_daily_briefings_for_all_accounts`, sin precedente de `day=` dinámico por mes).
- **Revisión post-Advice:** la guarda pasa de igualdad exacta (`date.today() ==
  last_day_of_month - 2`) a **rango** (`days_until_month_end <= 2`) — necesario para que un fallo
  del servidor justo el día N-2 no pierda la generación del mes entero. Combinado con la regla de
  idempotencia de abajo, el cron puede correr varios días seguidos sin generar duplicados ni
  spamear cuentas ya resueltas. Ver Clarificación #2 para la política exacta de reintento.
- Reutiliza el patrón exacto de `_run_agent_for_all_accounts_async` (semáforo +
  `asyncio.gather`, mismo `AGENT_CONCURRENCY_LIMIT`) pero llamando a
  `run_monthly_strategy_session`. **Añadido tras Advice:** aislamiento de fallos por cuenta (si
  una cuenta lanza excepción o falla el envío de Telegram, las demás siguen — mismo patrón que
  `run_agent_for_all_accounts`, con test espejo).
- Tras generar, si `telegram_chat_id` existe, dispara `TelegramService.send_campaign_approval_card`
  (nuevo método, análogo a `send_proposal_card`).

### 6. Telegram: tarjeta de aprobación + edición conversacional
- `send_campaign_approval_card(chat_id, campaign_id, campaign_data)` — mensaje con
  título/descripción/hitos/foco semanal, botones `campaign:approve:<id>`, `campaign:reject:<id>`,
  `campaign:chat:<id>` ("💬 Hablar con Hermes").
- `_handle_campaign_callback` (nuevo, junto a `_handle_proposal_callback`) despacha approve/reject
  (mismo patrón: `update status`, editar el texto de la tarjeta) y `chat` (envía `ForceReply` con
  tag `#campaignchat_<campaign_id>`).
- `handle_message`: nuevo regex `campaignchat_match = re.search(r'#campaignchat_([\w-]+)', reply_text)`
  → `_handle_campaign_chat_reply(chat_id, campaign_id, text)` → `run_edit_session(edit_type=
  "MONTHLY_STRATEGY", context={"campaign_id": campaign_id}, user_message=text)`.
- Ownership: nuevo `_verify_campaign_owner(campaign_id, chat_id)` — mismo patrón que
  `_verify_proposal_owner`.

### 7. Nuevo `edit_type="MONTHLY_STRATEGY"` en `run_edit_session`
Tool set acotado (añadir a `_EDIT_TOOL_SETS`): `supabase_update_campaign_focus(campaign_id,
week_number, focus_text)`, `supabase_update_campaign_milestones(campaign_id, milestones)`,
`supabase_update_campaign_details(campaign_id, title, description)` — 3 tools estrechas en vez de
un `update` genérico, seguiendo el mismo principio que las tools de Fase 3
(`supabase_update_post_schedule`/`supabase_update_post_image`: una tool por campo/concern, nunca
SQL/patch libre). `get_edit_prompt` gana un branch `MONTHLY_STRATEGY`.

### 8. Endpoint REST nuevo (primer punto de entrada frontend→Hermes)
`POST /api/agent/campaign/{campaign_id}/chat` en `agent_routes.py` — body `{message: str}`,
verifica ownership (mismo patrón que `/campaign` GET/POST: `instagram_accounts.user_id ==
current_user.id`, resuelto vía `account_id` de la fila de `monthly_campaigns`), llama
`asyncio.run(run_edit_session(...))` **síncrono** (bloquea 15-30s, igual que toda sesión Hermes
hasta ahora — no hay streaming construido todavía, ver Clarificación #4), devuelve
`{resolved: bool, message: str, campaign: MonthlyCampaign}` (la fila actualizada, para que el
frontend refresque sin un segundo round-trip).
`POST /api/agent/campaign/{campaign_id}/approve` y `/reject` — calcan `proposals/{id}/approve`
pero sin la parte de `PostScheduler` (aprobar una campaña no programa nada, solo cambia `status`).

**Confirmado por api-designer (Advice):**
- Respuestas **planas**, sin el envelope `{data, message, meta}` de `api.md` — ningún endpoint
  real de `agent_routes.py` lo usa hoy (ni `proposals/approve`, ni `campaign` GET/POST);
  introducirlo solo en 3 endpoints nuevos rompería la consistencia interna del archivo, no la
  mejoraría. Alinear todo el router con `api.md` sería un change aparte, fuera de alcance.
- `/chat` como naming se mantiene — es la misma categoría de excepción de verbo que `/approve`/
  `/reject`, ya aceptada en este router; no hay recurso "mensaje" persistente/listable que
  modelar como `/messages`.
- `resolved: false` sigue devolviendo **200** — es un resultado de negocio normal dentro del flujo
  conversacional (Hermes pide aclaración), no un error de cliente ni de servidor.

### 9. Frontend: cajón de chat en `AgentStrategyDrawer.tsx`
- Nuevo bloque condicional dentro de la sección "Enfoque del Mes" (línea ~690), visible solo si
  `campaign.status === 'pending_approval'` (campaña generada por Hermes esperando revisión) **o**
  si `campaign.id` existe y el usuario pulsa un botón "💬 Ajustar con Hermes" explícito (para poder
  reabrir el chat sobre una campaña ya aprobada). Requiere `campaign.id` — igual que Telegram, el
  chat opera sobre una fila ya persistida, no sobre el formulario en memoria sin guardar (decisión
  técnica, no requiere confirmación del usuario — se sigue de que las tools de edición operan
  sobre filas ya existentes, mismo patrón que Fase 3).
- Estado nuevo: `chatMessages: {role: 'user'|'hermes', text: string}[]`, `chatInput: string`,
  `chatSending: boolean`. Envía a `POST /campaign/{id}/chat`, añade la respuesta al hilo, y si
  `resolved`, refresca `campaign` con el objeto devuelto (mismo patrón que `handleGenerate`
  reemplaza `cfg`).
- Banner de estado: si `status === 'pending_approval'`, alerta con botones Aprobar/Rechazar
  (mismo estilo visual que `generatedBanner`/`saved` ya existentes) — reutiliza los mismos
  `alert py-2 px-3` con iconos `bi-*` que el resto del archivo, no introduce un patrón visual nuevo.

**Revisión post-Advice (react-frontend-architect + react-test-engineer):**
- **Extraer a `frontend/src/features/agent/CampaignChatBox.tsx`** — no por tamaño de archivo (833
  a ~950 líneas sería tolerable) sino porque el chat introduce una máquina de estados async
  genuinamente distinta (mensajes + request en vuelo + cancelación) mezclada con el estado de
  formulario simple del resto del drawer, lo que complica tanto el testing aislado como el blast
  radius de cambios futuros. **Sin CSS propio** — recibe los mismos objetos `style={{}}` que ya usa
  el padre (constantes compartidas tipo `inp`, pasadas por props), para no introducir
  `CampaignChatBox.css` como "arreglo de paso" de una convención ya aceptada en este archivo.
- **`useState` plano es suficiente** — 3 campos independientes sin transiciones cruzadas complejas
  no justifican `useReducer` (sin precedente fuerte en el repo para este caso).
- **Cancelación real necesaria:** en `onHide`, abortar la request en vuelo y descartar la
  respuesta si llega tarde (`AbortController`, guard `if (!signal.aborted)` antes de
  `setChatMessages`) — evita "setState tras unmount" y que una respuesta tardía de una cuenta
  sobreescriba `campaign` de otra si el usuario reabre el drawer rápido. Esto requiere un cambio
  pequeño y justificado en `frontend/src/api/client.ts`: añadir `signal?: AbortSignal` a
  `jsonRequest`/`post` (hoy solo `get` lo soporta) — mismo patrón ya usado ahí, no una abstracción
  nueva.
- **Loading UX:** no basta un spinner genérico para 15-30s — mensaje tipo "Hermes está pensando…
  puede tardar hasta 30s" (`spinner-grow` + texto), input y botón enviar deshabilitados durante
  `chatSending`.
- **Mock en tests:** el test existente (`AgentStrategyDrawer.test.tsx`) mockea `global.fetch`
  directamente (filtrando por `url.includes(...)`), no `apiClient.post` — el plan de test de
  `CampaignChatBox.test.tsx` debe seguir esa misma convención, no una nueva.

---

## Tests a cubrir (revisado post-Advice)

**Backend** (`python-test-engineer`):
- `test_mcp_supabase_server.py`: `supabase_create_monthly_campaign` — incluye **test explícito de
  idempotencia** (dos llamadas mismo `(account_id, month_date)` → una sola fila, regla "nunca
  sobrescribe approved/pending sin resolver"), `supabase_update_campaign_focus/milestones/details`,
  `supabase_get_campaign` filtrando por `status='approved'` **+ test de regresión** de que los
  demás callers existentes de esa tool (13 tools compartidas) no dependían de ver campañas no
  aprobadas.
- `test_hermes_orchestrator.py` / nuevo `test_hermes_monthly_strategy.py`: `run_monthly_strategy_session`
  (Gemini mockeado, `HERMES_MONTHLY_MAX_TURNS`, la tool de creación nace `pending_approval`) +
  **caso `max_turns_exceeded` que NO deja una fila a medias** si la sesión aborta antes de llamar
  a la tool de creación. Nuevo `edit_type="MONTHLY_STRATEGY"` en `run_edit_session` (mismo patrón
  que TIME/IMAGE_SELECT).
- `test_telegram_bot.py`: `_handle_campaign_callback` (approve/reject/chat),
  `_handle_campaign_chat_reply`, `_verify_campaign_owner`.
- `test_cron_jobs.py`: **sin `freezegun`** (no está en `requirements.txt`, y el repo no lo usa en
  ningún test hoy) — añadir `from datetime import date` a `main.py` y testear con
  `patch("main.date")` (`MagicMock().today.return_value` fijado por caso), parametrizado sobre
  meses de 28/29/30/31 días vía `calendar.monthrange`. Casos: día dentro del rango N-2→fin de mes
  actúa, fuera del rango no llama a Hermes en absoluto (ni gasta cuota), **aislamiento de fallos
  por cuenta** en el `asyncio.gather` (mismo patrón que `test_run_agent_for_all_accounts_concurrency_and_isolation`),
  y fallo de `send_campaign_approval_card`/`telegram_chat_id` nulo sin tumbar el resto del batch.
- `test_agent_routes.py` (o nuevo `test_campaign_routes.py`): endpoints
  `/campaign/{id}/chat|approve|reject` — ownership 403, 404, caso feliz, `resolved: false` → 200.

**Frontend** (`react-test-engineer`):
- `CampaignChatBox.test.tsx` (nuevo, junto al componente extraído): mock de `global.fetch`
  filtrando por `url.includes('/campaign/.../chat')` — **misma convención que
  `AgentStrategyDrawer.test.tsx` ya usa** (no `apiClient.post` directamente). Sin fake timers para
  la latencia — usar una promesa diferida (`resolveFetch` manual) para aserciones de estado
  "enviando" antes de resolver. Casos: mensaje vacío/whitespace deshabilita envío, doble envío
  rápido solo dispara un `fetch` (`chatSending` bloquea input+botón), `resolved:false` añade el
  mensaje de Hermes al hilo **sin** refrescar `campaign`, error de red resetea `chatSending` a
  `false` (no se queda bloqueado), append optimista del mensaje del usuario, `aria-live` en el
  hilo para accesibilidad (primer chat conversacional del frontend).
- `AgentStrategyDrawer.test.tsx`: render del banner `pending_approval`, aprobar/rechazar desde el
  drawer (banner desaparece tras resolver), chat deshabilitado si `campaign.id` no existe.

---

## Team Selection (Advice — no invocados aún)

Se va a pedir revisión en paralelo a:
- **fastapi-backend-architect** — validar el diseño del cron con guarda de fecha (vs. `CronTrigger`
  dinámico por mes), el nuevo estado `status`/`generated_by` en `monthly_campaigns`, y si
  `run_monthly_strategy_session` debería vivir en `orchestrator.py` o en un módulo separado dado
  que ya tiene 273 líneas con dos sesiones distintas.
- **react-frontend-architect** — validar la integración del chat dentro de `AgentStrategyDrawer.tsx`
  monolítico (833 líneas) vs. extraerlo a un subcomponente propio, y el manejo de estado de una
  request síncrona de 15-30s en la UI (loading state, cancelación, qué pasa si el usuario cierra el
  drawer a mitad).
- **python-test-engineer** — validar la estrategia de test del cron con guarda de fecha (mockear
  `date.today()` de forma robusta) y de la sesión Hermes nueva mockeando Gemini.
- **react-test-engineer** — validar el plan de test del cajón de chat nuevo (mocks de fetch/apiClient,
  aserciones de accesibilidad del hilo de chat).
- **api-designer** — validar los 3 endpoints nuevos (`/campaign/{id}/chat|approve|reject`) contra
  las convenciones REST de `api.md` (envelope de respuesta, códigos de estado, naming).

---

## Advice recibido (resumen — detalle completo en las secciones de arriba, ya integrado)

| Agente | Recomendación clave |
|---|---|
| fastapi-backend-architect | Guarda de cron por rango (no igualdad); idempotencia "nunca sobrescribe approved/pending sin resolver"; `run_monthly_strategy_session` en módulo propio |
| api-designer | Respuestas planas (no envelope); mantener `/chat`; 200 con `resolved:false` |
| react-frontend-architect | Extraer `CampaignChatBox.tsx` sin CSS propio; `AbortController` real; `useState` plano basta |
| react-test-engineer | Mockear `global.fetch` (no `apiClient`); sin fake timers; casos de doble-envío/error de red/aria-live |
| python-test-engineer | Sin `freezegun`; `patch("main.date")`; tests de idempotencia, max-turns, aislamiento de fallos |

## Preguntas para Clarificación (pendiente de respuesta del usuario)

1. **Conflicto manual vs. Hermes:** si el usuario edita el formulario manual del drawer mientras
   existe una campaña `pending_approval` generada por Hermes para ese mes, ¿qué debe pasar al
   guardar?
2. **Política de reintento del cron:** la guarda ahora es por rango (día N-2 hasta fin de mes, no
   un único día exacto) para sobrevivir a un servidor caído. ¿Qué hace el cron en los días
   siguientes a N-2 si la cuenta ya tiene una `pending_approval` sin resolver del primer intento?
3. **Continuidad narrativa entre meses:** ¿debe la sesión de Hermes leer la campaña `approved` del
   mes anterior (mismo `strategy_mode`, hitos, tono) para mantener coherencia, o cada mes se genera
   de forma completamente independiente?
4. **Alcance del streaming en esta feature:** el endpoint de chat bloquea 15-30s (ninguna parte de
   Hermes tiene streaming construido todavía — coincide con el hallazgo del análisis previo del
   backlog). ¿Se acepta eso con la UX mejorada que propusieron los agentes (mensaje "puede tardar
   hasta 30s" + cancelación al cerrar el drawer), o este change debe incluir algo de streaming real
   (polling o SSE) de una vez?

---

## Respuestas del usuario (Clarificación) — plan final

**1. Conflicto manual vs. Hermes — resuelto con una regla más precisa que las 3 opciones
propuestas:** la generación automática (mensual y semanal) solo debe dispararse si no hay ya algo
aprobado manualmente para ese mes/semana — la automatización nunca pisa una decisión manual ya
tomada. Mientras una propuesta esté `pending_approval`, **los tres canales de edición
(Telegram, chat del drawer, formulario manual) pueden modificar su contenido sin aprobarla
implícitamente** — editar el formulario manual y guardar actualiza los campos de la fila pero
**no** cambia `status`; solo una acción de aprobación explícita (botón del banner, botón de
Telegram, o el equivalente en el chat) la mueve a `approved`. Esto unifica los 3 canales bajo la
misma regla en vez de tratar "guardar el formulario" como un caso especial que auto-aprueba.
**Ajuste de diseño:** `handleSave` (`AgentStrategyDrawer.tsx`) y el endpoint `POST /campaign`
comprueban si ya existe una fila `pending_approval` para `(account_id, month_date)` — si existe,
el upsert actualiza título/descripción/milestones/weekly_focus/strategy_mode pero preserva
`status='pending_approval'` explícitamente (no lo sobrescribe con `'approved'` como hace hoy el
upsert por defecto). Si no existe fila pendiente, comportamiento actual sin cambios (guardar =
aprobado, como siempre ha sido para creación/edición manual).
**Nota de alcance:** el mismo principio aplicado a la parte "semanal" de la respuesta
(`content_proposals` nunca tiene hoy un concepto de "ya aprobado manualmente, no regenerar") es un
cambio de modelo de datos distinto y **no está en el alcance de este change** — `content_proposals`
se regenera cada semana por diseño actual. Se deja anotado como candidato a un change futuro si se
confirma que también hace falta ahí.

**2. Reintento del cron — "Reenviar recordatorio por Telegram":** mientras la cuenta tenga una
`pending_approval` sin resolver dentro de la ventana N-2→fin de mes, cada ejecución diaria del
cron (ya corre a las 20:00 todos los días, la guarda de rango ya lo garantiza) **reenvía la misma
tarjeta de aprobación** (edita/reenvía sobre el `campaign_id` existente, no genera contenido
nuevo ni llama a Hermes de nuevo — cero coste adicional de cuota Gemini). No hace falta columna de
tracking nueva: al estar acotado a una vez por invocación diaria del cron, la cadencia "una vez al
día" ya es inherente a cuándo corre el job.

**3. Continuidad narrativa — sí, leer el mes anterior:** `run_monthly_strategy_session` consulta
la campaña `approved` más reciente de la cuenta (típicamente el mes anterior) antes de generar,
y la pasa como contexto de continuidad al prompt (mismo `strategy_mode`, hilo narrativo, hitos
relacionados) — sin obligar a mantenerlo si el usuario cambió de dirección, es contexto para que
Hermes razone, no una restricción dura (mismo principio ya establecido: "esto es contexto, no una
decisión que tome Python").

**4. Streaming — incluido en el alcance de este change** (no diferido). Diseño:

- **Telegram:** no requiere infraestructura nueva — reutiliza el patrón ya existente de editar
  mensajes (`editMessageText`, ya usado para "✅ Aprobado — programado para...", etc.). Al iniciar
  `run_monthly_strategy_session` o una respuesta de chat vía `run_edit_session`, se envía primero
  un mensaje placeholder ("🤖 Generando la estrategia del mes…") y se edita progresivamente por
  cada paso relevante (mapeo `tool_name → texto humano`, ej. `supabase_get_campaign` → "Revisando
  el mes anterior…", `supabase_create_monthly_campaign` → "Guardando propuesta…"), terminando con
  la tarjeta de aprobación final (o la respuesta resuelta, en el caso del chat).
- **App (SSE-like sobre `fetch`, sin librerías nuevas):** el endpoint `POST
  /campaign/{id}/chat` pasa de devolver JSON plano a un `StreamingResponse` de FastAPI que emite
  líneas NDJSON (`{"type": "progress", "label": "..."}` por paso, terminando con `{"type":
  "result", "resolved": ..., "message": ..., "campaign": {...}}`). El frontend no usa
  `EventSource` (no soporta headers de auth con Bearer token, que es como ya funciona
  `apiClient`) — lee `response.body.getReader()` sobre el `fetch` normal ya autenticado, parseando
  NDJSON línea a línea. `CampaignChatBox` muestra las líneas de progreso según llegan y reemplaza
  por el mensaje final cuando llega `type: "result"`. El `AbortController` ya decidido en Advice
  sirve también aquí para cancelar el stream si se cierra el drawer.
- **Plomería compartida:** `_dispatch_turn` (helper ya compartido por `run_session`/
  `run_edit_session`, `orchestrator.py`) gana un parámetro opcional `on_progress: Optional[Callable]`,
  invocado antes/después de cada `bridge.dispatch(...)`. `run_monthly_strategy_session` y
  `run_edit_session` lo usan; `run_session` (flujo semanal) **no se toca en este change** — queda
  disponible para adoptarlo después sin coste, pero conectar streaming ahí (Telegram del domingo +
  UI semanal) es trabajo aparte, fuera de este change.
- **Efecto en el plan de tests:** añadir a `test_hermes_monthly_strategy.py`/
  `test_hermes_orchestrator.py` un test de que `on_progress` se invoca una vez por tool call con
  el nombre correcto; a `test_campaign_routes.py` un test que consuma el `StreamingResponse` y
  verifique el NDJSON; a `CampaignChatBox.test.tsx` un test que parsee un stream mockeado
  (`ReadableStream` con chunks) y muestre las líneas de progreso antes del mensaje final.
