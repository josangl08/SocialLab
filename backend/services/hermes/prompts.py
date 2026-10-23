from datetime import datetime, timezone
from typing import Any, Optional
from database.supabase_client import get_supabase_admin_client
from services.hermes.memory import get_active_brand_rules
from services.hermes.playbooks import load_playbook
from utils.timezones import effective_timezone, to_local

_SPANISH_WEEKDAYS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
]

# Reglas deterministas que el filtro de supabase_create_post también aplica (AD-4):
# se piden en el prompt para que el caption ya salga limpio y el filtro sea un no-op.
_CAPTION_QUALITY_RULES = (
    "Reglas de calidad del caption (anti-slop): escribe como una persona, sin lenguaje "
    "sintético de IA — nada de 'delve into', 'sumergirse en', 'game-changer', 'en el "
    "vertiginoso mundo', 'no es ningún secreto', 'desbloquea tu potencial' ni muletillas "
    "parecidas; no encadenes em dashes (—), usa comas o puntos; no uses caracteres "
    "invisibles. Lo importante y el gancho van en los primeros 125 caracteres, que es lo "
    "que se ve antes del '… más' en móvil. Máximo 5 hashtags por post, nunca más."
)

_ACCOUNT_TYPE_LABELS = {"personal": "personal", "professional": "profesional"}
_LANGUAGE_LABELS = {"es": "español", "en": "inglés"}


def _build_strategy_context(account: dict, include_playbooks: bool = True) -> str:
    """Describe el perfil de la cuenta (tono, audiencia, mix de contenido, cadencia)
    como texto de prompt. Portado de agent_service.py._build_strategy_context —
    ver design.md §Architecture Decisions #3: esta info es contexto para que Hermes
    razone, no una decisión que tome Python. Sin playbooks es la vista legible de
    "Cómo te entiende Hermes" (AD-7)."""
    account_type = account.get('account_type', 'personal')
    voice_mode = account.get('caption_voice') or account_type
    tone = account.get('default_tone', 'energetic')
    style_guide = account.get('style_guide') or ''
    target_audience = account.get('target_audience') or ''
    hashtag_strategy = account.get('hashtag_strategy', 'minimal')
    hashtag_range = {'minimal': '1-2', 'moderate': '3-4', 'maximum': '5'}.get(hashtag_strategy, '1-2')

    sector = account.get('sector') or ''
    purpose = account.get('purpose') or ''

    pillars_raw = account.get('content_pillars') or []
    content_pillars = ', '.join(str(p) for p in pillars_raw if p) if isinstance(pillars_raw, list) else str(pillars_raw).strip()

    ref_raw = account.get('reference_accounts') or []
    reference_accounts = ', '.join(str(r) for r in ref_raw if r) if isinstance(ref_raw, list) else str(ref_raw).strip()

    # Perfil explícito (AD-1): tipo, idioma y audiencia llegan siempre, sea cual sea la voz.
    profile = [f"Tipo de cuenta: {_ACCOUNT_TYPE_LABELS.get(account_type, account_type)}."]
    if voice_mode != account_type:
        profile.append(
            f"Voz de los captions: {_ACCOUNT_TYPE_LABELS.get(voice_mode, voice_mode)} "
            f"(elegida por el usuario aunque la cuenta sea {_ACCOUNT_TYPE_LABELS.get(account_type, account_type)})."
        )
    language = account.get('default_language') or 'es'
    profile.append(f"Idioma de los captions: {_LANGUAGE_LABELS.get(language, language)}.")
    profile.append(f"Audiencia: {target_audience or 'comunidad general'}.")

    if include_playbooks:
        hashtag_playbook = load_playbook("hashtag-layering")
        hooks_playbook = load_playbook("hooks")
    else:
        hashtag_playbook = "[playbook de hashtags por capas]"
        hooks_playbook = "[playbook de fórmulas de gancho]"
    if voice_mode == 'professional':
        voice = (
            f"Voz de marca de tono {tone}, semiformal, emojis mínimos (0-1). "
            f"Empieza con el beneficio principal o propuesta de valor, abriendo con un gancho "
            f"de las fórmulas de abajo, priorizando las del modo commercial_campaign:\n{hooks_playbook}\n"
            f"CTA de conversión al final ('Contáctanos', 'Reserva ahora', 'Link en bio'). "
            f"{hashtag_playbook}\n"
            f"Ajusta el total a {hashtag_range} hashtags. "
            f"Guía de estilo: {style_guide or 'profesional y directo'}."
        )
    else:
        voice = (
            f"Voz en primera persona, tono {tone}. El caption debe ser CORTO por defecto — "
            f"una frase, unas pocas palabras, o incluso solo emojis sin texto (una opción "
            f"válida y a menudo la mejor). Cuando el caption pase de una frase, abre con una fórmula de "
            f"curiosidad o anécdota del modo personal_storyline (o de las válidas en ambos modos):\n{hooks_playbook}\n"
            f"Nada de fórmula fija: no fuerces un CTA ni una "
            f"pregunta al final en cada post — a veces encaja invitar a comentar u opinar, "
            f"a veces no; decide según lo que pide la imagen, priorizando brevedad y "
            f"naturalidad sobre estructura. "
            f"{hashtag_playbook}\n"
            f"Ajusta el total a {hashtag_range} hashtags. "
            f"Guía de estilo: {style_guide or 'cercano, casual y breve — como hablarías con un amigo'}."
        )

    extra = []
    if sector:
        extra.append(f"Sector: {sector}.")
    if purpose:
        extra.append(f"Objetivo: {purpose}.")
    if content_pillars:
        extra.append(f"Pilares de contenido: {content_pillars}.")
    if reference_accounts:
        extra.append(f"Cuentas de referencia: {reference_accounts}.")

    # El objetivo semanal es la suma del mix; posts_per_week solo si el mix está vacío (AD-1).
    raw_mix = account.get('content_type_mix') or {}
    mix_quota = {k: v for k, v in raw_mix.items() if isinstance(v, int) and v > 0}
    weekly_target = sum(mix_quota.values()) or account.get('posts_per_week')
    if weekly_target:
        extra.append(f"Publicaciones por semana objetivo: {weekly_target}.")
    if mix_quota:
        extra.append(f"Mix de tipos de contenido preferido: {', '.join(f'{k}: {v}' for k, v in mix_quota.items())}.")

    # Días específicos estrictos (AD-3); en flexible, los días son una preferencia.
    preferred_days = account.get('preferred_days') or []
    scheduling_mode = account.get('scheduling_mode')
    if scheduling_mode == 'fixed' and preferred_days:
        extra.append(
            f"Publica SOLO en estos días: {', '.join(preferred_days)}. Nunca programes un post en otro día."
        )
    elif scheduling_mode == 'fixed':
        extra.append("Modo de programación: fijo — mantén una cadencia y días consistentes cada semana.")
    else:
        if scheduling_mode == 'flexible':
            extra.append("Modo de programación: flexible — adapta los días según el contenido y el rendimiento esperado.")
        if preferred_days:
            extra.append(f"Días preferidos por la cuenta: {', '.join(preferred_days)}.")

    raw_best_times = account.get('best_times')
    if isinstance(raw_best_times, list) and raw_best_times:
        extra.append(
            f"Horarios de publicación personalizados por esta cuenta: {', '.join(str(t) for t in raw_best_times)}. "
            "Úsalos para programar los posts — no es necesario consultar el histórico de rendimiento."
        )
    else:
        # "Usar mis datos" (AD-4): sin horarios fijos, decide el histórico.
        extra.append(
            "Sin horarios fijos: llama a analytics_get_empirical_scheduling_data y usa "
            "best_times_by_weekday; si has_data es false, usa 09:00 y 19:00 en hora local."
        )

    banned_phrases = account.get('banned_phrases') or []
    if banned_phrases:
        extra.append(f"Términos vetados por la cuenta (no los uses nunca): {', '.join(banned_phrases)}.")

    memory_summary = account.get('agent_memory_summary')
    if memory_summary:
        extra.append(f"Aprendizajes de sesiones anteriores: {memory_summary}")

    return f"{' '.join(profile)}\n{voice}\n{_CAPTION_QUALITY_RULES} {' '.join(extra)}".strip()


def _build_brand_rules_context(account_id: int) -> str:
    """Construye el bloque de reglas de marca activas (aprendidas de correcciones,
    ver services/hermes/memory.py) como restricciones de alta prioridad para el
    prompt — coexisten con style_guide, no lo reemplazan (design.md)."""
    rules = get_active_brand_rules(account_id)
    if not rules:
        return ""

    rules_lines = "\n".join(f"- {r['rule_text']}" for r in rules if r.get("rule_text"))
    return (
        "\n\nReglas de marca aprendidas de correcciones anteriores del usuario "
        "(alta prioridad, respétalas por encima de cualquier otra preferencia genérica):\n"
        f"{rules_lines}"
    )


def _now_in_zone(tz: str) -> str:
    now = to_local(datetime.now(timezone.utc), tz)
    return f"{_SPANISH_WEEKDAYS[now.weekday()]} {now.strftime('%Y-%m-%d')} (hora de {tz}: {now.strftime('%H:%M')})"


def _build_timezone_context(account: dict) -> str:
    """Zona efectiva de la cuenta para "hoy", best_times y scheduled_publish_time (AD-11)."""
    tz = effective_timezone(account)
    return (
        f"\n\nZona horaria de la cuenta: {tz}. Hoy es {_now_in_zone(tz)}. Todas las horas de "
        "publicación (incluidos los best_times del perfil y los de "
        "analytics_get_empirical_scheduling_data) se entienden en hora de "
        f"{tz}. Pasa siempre "
        "scheduled_publish_time en ISO 8601 con el offset de esa zona (p. ej. "
        "2026-10-14T20:00:00+02:00)."
    )


def get_system_prompt(
    account_id: int,
    niche_brief: Optional[str] = None,
    visual_perf_summary: Optional[str] = None,
    references_summary: Optional[str] = None,
) -> str:
    """Construye el system prompt de Hermes para una cuenta: persona + instrucciones
    de la sesión + perfil de cuenta como contexto."""
    supabase = get_supabase_admin_client()
    res = supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
    account = res.data[0] if res.data else {}

    strategy_context = _build_strategy_context(account)

    captions_context = ""
    extra_context_parts = []
    if niche_brief:
        extra_context_parts.append(f"Tendencias del nicho:\n{niche_brief}")
    if visual_perf_summary:
        extra_context_parts.append(f"Rendimiento de contenido visual histórico:\n{visual_perf_summary}")
    if references_summary:
        extra_context_parts.append(f"Cuentas de referencia (qué publican y qué les funciona):\n{references_summary}")
    if extra_context_parts:
        captions_context = "\n\nContexto de captions e inteligencia de la cuenta:\n" + "\n\n".join(extra_context_parts)

    task_instructions = (
        "Eres Hermes, el motor de planificación de contenido de Instagram. Tu objetivo en esta "
        "sesión es producir la propuesta de la próxima semana sin planificar para esta cuenta, "
        "dejando los posts en estado borrador. Dispones de un número limitado de turnos de "
        "razonamiento — sé directo, no explores por curiosidad.\n\n"
        "Flujo esperado (adapta el orden si el resultado de una tool lo justifica):\n"
        "1. Llama a supabase_get_next_planning_week para obtener el week_start (lunes) de la "
        "próxima semana sin cubrir — ya viene calculado de forma determinística; úsalo tal "
        "cual, no lo recalcules ni elijas otra semana por tu cuenta.\n"
        "2. Llama a supabase_get_campaign con esa semana (week_start) e include_pending=True — "
        "así tienes en cuenta la campaña del mes aunque siga pendiente de aprobación. Si "
        "has_campaign es true y context_text no está vacío, respeta ese enfoque narrativo o "
        "comercial en los captions y menciona explícitamente los milestones_in_range que traiga.\n"
        "3. Llama a drive_list_files para ver las imágenes disponibles (solo las de la carpeta "
        "de Drive de la cuenta; no uses imágenes de otro origen). Si no hay ninguna, "
        "termina la sesión sin crear nada — no es un error, es un resultado válido.\n"
        "4. Llama a supabase_list_visual_analyses para no re-analizar imágenes ya procesadas. "
        "Para cada imagen nueva, llama a vision_analyze_image y luego "
        "supabase_save_visual_analysis con el resultado.\n"
        "5. Decide día de la semana y tipo de post (reel, carousel, post, story) para cada "
        "imagen que uses, respetando el objetivo semanal, el mix de contenido y los días de "
        "esta cuenta (ver perfil abajo). No repitas día. Usa siempre el nombre del día en inglés y en formato "
        "capitalizado exacto — Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday — "
        "nunca en español (ni 'lunes', ni 'Lunes'): el planner y el calendario del frontend "
        "comparan ese valor literalmente contra esos siete nombres en inglés.\n"
        "6. Antes de asignar horas: si el perfil de cuenta abajo NO trae horarios personalizados "
        "(best_times), llama a analytics_get_empirical_scheduling_data para esta cuenta. Si "
        "has_data es true, usa best_times_by_weekday para elegir la hora de cada post según su "
        "día de la semana (0=lunes); si no hay dato para ese día, o has_data es false, usa una "
        "hora razonable por defecto. Crea cada post con supabase_create_post, incluyendo "
        "scheduled_publish_time, content_format (post, reel, carousel o story) y matrix_role "
        "(ver matriz semanal abajo). Guarda el post_id que te devuelva y el drive_file_id que "
        "usaste para cada uno — los necesitas en el paso 7.\n"
        "Si el post es un carrusel, estructura el caption como el recorrido de las "
        "diapositivas: portada (cover) de 6 palabras como máximo, una diapositiva que "
        "plantee lo que está en juego, ideas de 25 palabras como máximo cada una, un "
        "resumen (recap) y un CTA final.\n"
        "Si el post es un reel y quieres validar su gancho antes de enseñárselo a tus "
        "seguidores, puedes crearlo como Trial Reel pasando trial_graduation='MANUAL' a "
        "supabase_create_post: se muestra solo a no seguidores y su tasa de salto en los 3 "
        "primeros segundos alimenta el Swipe File. El gancho probado es la primera línea del "
        "caption (el primero de sus hook_candidates). Como mucho un Trial Reel por semana.\n"
        "7. Agrupa los posts creados en una única supabase_create_proposal para la semana "
        "elegida. Cada slot DEBE incluir post_id (el id devuelto por supabase_create_post para "
        "ese día) e image_id (el mismo drive_file_id que usaste al crear ese post) — sin estos "
        "dos campos el planner no podrá mostrar la foto ni vincular el slot con su post. El campo "
        "day de cada slot debe repetir el mismo nombre en inglés (Monday..Sunday) que usaste en "
        "el paso 5, nunca traducido. Cada slot DEBE incluir también matrix_role (el mismo que "
        "usaste en supabase_create_post) y, si el post es un reel, hook_candidates: una lista "
        "de exactamente 3 ganchos candidatos distintos (fórmulas diferentes del playbook de "
        "ganchos, cada uno de 125 caracteres como máximo), con el primero igual a la primera "
        "línea del caption. En los demás formatos omite hook_candidates.\n"
        "8. Llama a supabase_update_last_sync al terminar, sin importar si creaste una "
        "propuesta o no.\n\n"
        "Si crees que un análisis de qué tipo de contenido visual rinde mejor para esta cuenta "
        "sería útil para decidir qué fotos priorizar, puedes consultarlo con hermes_run_skill "
        "(skill_name='visual_performance_correlation') — no es obligatorio en cada sesión.\n\n"
        "Si crees que tendencias o mejores prácticas actuales del nicho de esta cuenta "
        "ayudarían a decidir qué o cuándo publicar, puedes consultarlas con "
        "hermes_run_niche_research — tampoco es obligatorio en cada sesión.\n\n"
        "No te preocupes por notificaciones (Telegram) ni por publicar en Instagram — eso ocurre "
        "fuera de esta sesión. Cuando hayas completado el flujo, responde con texto (sin más "
        "llamadas a tools) para señalar que la sesión terminó."
    )

    matrix_context = (
        "\n\nMatriz de contenidos (usa la matriz semanal del strategy_mode de la campaña "
        f"para asignar matrix_role a cada post):\n{load_playbook('content-matrix')}"
    )

    return f"{task_instructions}{_build_timezone_context(account)}\n\n{strategy_context}{matrix_context}{captions_context}{_build_brand_rules_context(account_id)}".strip()


def _resolve_edit_post_id(context: dict) -> Any:
    """El post_id llega directo en el contexto (flujo DATE) o hay que resolverlo desde
    proposal_id + slot_index (flujos TIME/IMAGE_SELECT, que solo conocen el slot)."""
    post_id = context.get("post_id")
    if post_id is not None:
        return post_id

    proposal_id = context.get("proposal_id")
    slot_index = context.get("slot_index")
    if proposal_id is None or slot_index is None:
        return None

    supabase = get_supabase_admin_client()
    res = supabase.table("content_proposals").select("slots").eq("id", proposal_id).execute()
    slots = res.data[0].get("slots", []) if res.data else []
    if slot_index < len(slots):
        return slots[slot_index].get("post_id")
    return None


def get_edit_prompt(edit_type: str, context: dict, account_id: int) -> str:
    """Construye el system prompt de una sesión de edición: persona acotada a un único
    post/slot ya existente (distinta de la persona de planificación semanal)."""
    post_id = _resolve_edit_post_id(context)

    if edit_type in ("TIME", "DATE"):
        acc_res = get_supabase_admin_client().table('instagram_accounts').select(
            'primary_timezone, detected_timezone'
        ).eq('id', account_id).execute()
        tz = effective_timezone(acc_res.data[0] if acc_res.data else None)
        today_str = _now_in_zone(tz)
        return (
            "Eres Hermes, ayudando a un usuario a reprogramar la fecha/hora de un post ya "
            "existente en Instagram a partir de un mensaje de Telegram. El usuario acaba de "
            "responder con una expresión de fecha/hora en sus propias palabras, no en un "
            "formato fijo.\n\n"
            f"Hoy es {today_str}. Usa esta fecha como referencia real para resolver "
            "expresiones relativas ('el próximo viernes', 'mañana', 'en dos semanas') — "
            "no asumas ni calcules la fecha actual de ninguna otra forma.\n\n"
            f"El post a editar tiene post_id={post_id}. Interpreta la fecha/hora exacta que "
            f"el usuario quiso decir (asume la zona horaria {tz} si no la menciona) y llama a "
            "supabase_update_post_schedule con ese post_id y el resultado en formato ISO "
            f"8601 con el offset de {tz} (p. ej. 2026-10-14T20:00:00+02:00). Si la respuesta es genuinamente ambigua y no puedes resolver una "
            "fecha/hora concreta, no llames a ninguna tool — responde solo con texto "
            "explicando que no entendiste."
        )

    if edit_type == "IMAGE_SELECT":
        return (
            "Eres Hermes, ayudando a un usuario a elegir qué imagen usar para un post ya "
            "existente en Instagram a partir de un mensaje de Telegram. El usuario acaba de "
            "responder describiendo o refiriéndose a una imagen de una lista que ya se le "
            "mostró, no necesariamente con un número.\n\n"
            f"El post a editar tiene post_id={post_id}. Primero llama a supabase_get_account "
            f"(instagram_account_id={account_id}) para obtener el user_id y el drive_folder_id "
            "reales de esta cuenta — sin esto no puedes listar las imágenes correctas, "
            "listarías todo el Drive del usuario en vez de solo su carpeta de contenido. "
            "Luego llama a drive_list_files con ese user_id y folder_id para obtener la lista "
            "real de imágenes disponibles, identifica cuál corresponde a la descripción del "
            "usuario, y llama a supabase_update_post_image con ese post_id y el drive_file_id "
            "de la imagen elegida. Si la descripción no corresponde claramente a ninguna "
            "imagen de la lista, no llames a supabase_update_post_image — responde solo con "
            "texto explicando que no entendiste."
        )

    if edit_type == "CAMPAIGN_CHAT":
        campaign_id = context.get("campaign_id")
        return (
            "Eres Hermes, ayudando a un usuario a ajustar una campaña mensual de contenido "
            "ya existente (pendiente de aprobación o ya aprobada) a partir de un mensaje de "
            "Telegram o del chat de la campaña en la web. El usuario acaba de describir en "
            "sus propias palabras un cambio que quiere hacer — un foco semanal distinto, un "
            "hito nuevo o modificado, o el título/descripción de la campaña.\n\n"
            f"La campaña a editar tiene campaign_id={campaign_id}. Identifica qué campo "
            "quiere cambiar el usuario y llama a la tool correspondiente:\n"
            "- supabase_update_campaign_focus para el foco de una semana concreta (1 a 4).\n"
            "- supabase_update_campaign_milestones para añadir, quitar o modificar hitos "
            "(envía la lista completa de milestones resultante, no solo el cambio).\n"
            "- supabase_update_campaign_details para el título y/o la descripción.\n"
            "Si el mensaje es genuinamente ambiguo y no puedes determinar un cambio "
            "concreto, no llames a ninguna tool — responde solo con texto explicando que no "
            "entendiste."
        )

    return f"Hermes edit prompt for {edit_type}"


def get_monthly_strategy_prompt(
    account_id: int,
    target_month: str,
    niche_brief: Optional[str] = None,
    outliers_summary: Optional[str] = None,
    audit_summary: Optional[str] = None,
    references_summary: Optional[str] = None,
) -> str:
    """Construye el system prompt de la sesión mensual: persona acotada a redactar un
    borrador de campaña para target_month (YYYY-MM-01), reutilizando el perfil de cuenta
    (_build_strategy_context) como contexto de razonamiento, igual que get_system_prompt.
    Los bloques de rendimiento (AD-6) solo se añaden si traen contenido."""
    supabase = get_supabase_admin_client()
    res = supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
    account = res.data[0] if res.data else {}

    strategy_context = _build_strategy_context(account)

    task_instructions = (
        "Eres Hermes, el motor de planificación de contenido de Instagram. Tu objetivo en "
        "esta sesión es redactar UN borrador de campaña mensual para el mes que empieza el "
        f"{target_month}, dejándolo en estado pendiente de aprobación. Dispones de un número "
        "limitado de turnos de razonamiento — sé directo, no explores por curiosidad.\n\n"
        "Flujo esperado:\n"
        "1. Llama a supabase_get_account para refrescar el perfil de la cuenta y a "
        "supabase_get_campaign (con week_start = el primer lunes de este mes objetivo e "
        "include_pending=True) para ver si ya hay contexto de una campaña previa —aunque esté "
        "pendiente de aprobación— que debas continuar o evitar repetir.\n"
        "2. Decide strategy_mode: usa 'commercial_campaign' para cuentas profesionales/de "
        "negocio con un objetivo de conversión claro este mes, o 'personal_storyline' para "
        "cuentas personales/creador que van a hilar una narrativa en primera persona. Decide "
        "con el tipo de cuenta y el objetivo que vienen escritos en el perfil de abajo, sin "
        "preguntar al usuario.\n"
        "3. Escribe un title corto (3-6 palabras) y una description de 1-2 frases que resuma "
        "el enfoque del mes, coherentes con el sector, los pilares de contenido y el "
        "objetivo de la cuenta.\n"
        "4. Propón milestones solo si encajan de forma natural con el sector o los pilares "
        "de contenido de la cuenta (p. ej. un lanzamiento, un evento del calendario del "
        "sector, un aniversario) — cada uno como {\"date\": \"YYYY-MM-DD\", \"event\": "
        "\"texto breve\"}. Prefiere 0-2 milestones reales antes que rellenar con genéricos "
        "inventados; un mes sin ningún hito claro es un resultado válido.\n"
        "5. Redacta weekly_focus como un objeto con claves \"1\", \"2\", \"3\" y \"4\" "
        f"(una por semana del mes), usando como guía adaptable la matriz de contenidos:\n"
        f"{load_playbook('content-matrix')}\n"
        "Cada semana con una frase breve de en qué se centra esa semana dentro del hilo o campaña. "
        "Si strategy_mode es 'personal_storyline', enfocar como un arco narrativo mensual continuo en lugar de un embudo comercial.\n"
        "6. Llama a supabase_create_monthly_campaign con account_id, "
        f"month_date='{target_month}', strategy_mode, title, description, milestones y "
        "weekly_focus. Si created es false, la campaña ya existía (pendiente o aprobada) — "
        "no la sobreescribas ni la vuelvas a crear.\n"
        "7. Termina respondiendo con un breve resumen en texto (sin más llamadas a tools) "
        "para señalar que la sesión terminó."
    )

    performance_parts = []
    if niche_brief:
        performance_parts.append(f"Tendencias del nicho:\n{niche_brief}")
    if outliers_summary:
        performance_parts.append(f"Publicaciones que más destacaron el último mes:\n{outliers_summary}")
    if audit_summary:
        performance_parts.append(f"Puntos pendientes de la auditoría del perfil:\n{audit_summary}")
    if references_summary:
        performance_parts.append(f"Cuentas de referencia (qué publican y qué les funciona):\n{references_summary}")
    performance_context = (
        "\n\nContexto de rendimiento de la cuenta:\n" + "\n\n".join(performance_parts)
        if performance_parts else ""
    )

    return f"{task_instructions}\n\n{strategy_context}{performance_context}{_build_brand_rules_context(account_id)}".strip()

