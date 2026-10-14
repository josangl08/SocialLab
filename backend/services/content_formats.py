"""
Content Formats Generator Service
Generates format-specific content (Reel, Carousel, Story, Repurpose) via Gemini with
process-local 1-hour hash cache and deterministic quality post-processing (humanize + lint).
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from database.supabase_client import get_supabase_admin_client
from services.account_timezone import get_account_timezone
from utils.timezones import local_today
from models.schemas import (
    BeatsResponse,
    CarouselOut,
    CarouselSlide,
    QualityReport,
    ReelHookCandidate,
    ReelOut,
    RepurposeOut,
    StoryFrame,
    StoryOut,
    CommentTriageItem,
    ProspectCommentItem,
    DmFunnelResponse,
)
from services.content_quality import get_hook_formulas, humanize, lint_caption, score_hook, time_beats
from services.gemini_service import clean_and_parse_json, generate_gemini_content

logger = logging.getLogger(__name__)

StrategyMode = Literal["commercial_campaign", "personal_storyline"]

CACHE_TTL_SECONDS = 3600  # 1 hour TTL
_FORMATS_CACHE: Dict[str, Tuple[float, Any]] = {}


def clear_formats_cache() -> None:
    """Clears in-memory format generation cache."""
    _FORMATS_CACHE.clear()


def _get_cache_key(
    format_type: str, account_id: int, strategy_mode: str, normalized_input: str, language: str = "es"
) -> str:
    """Builds sha256 cache key based on type, account, strategy mode, language and input."""
    raw = f"{format_type}:{account_id}:{strategy_mode}:{language}:{normalized_input.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_from_cache(cache_key: str) -> Optional[Any]:
    """Retrieves an unexpired entry from memory cache."""
    entry = _FORMATS_CACHE.get(cache_key)
    if entry:
        timestamp, value = entry
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return value
        else:
            del _FORMATS_CACHE[cache_key]
    return None


def set_in_cache(cache_key: str, value: Any) -> None:
    """Stores a value in memory cache with current timestamp."""
    _FORMATS_CACHE[cache_key] = (time.time(), value)


def _fetch_month_campaign(account_id: int) -> List[Dict[str, Any]]:
    supabase = get_supabase_admin_client()
    current_month = local_today(get_account_timezone(account_id)).replace(day=1).isoformat()
    res = (
        supabase.table("monthly_campaigns")
        .select("strategy_mode, status")
        .eq("account_id", account_id)
        .eq("month_date", current_month)
        .execute()
    )
    return res.data or []


def get_strategy_mode(account_id: int) -> StrategyMode:
    """
    Resolves the strategy mode for an account (AD-2):
    1. Active/approved campaign of current month -> its strategy_mode.
    2. Otherwise -> 'personal_storyline'.
    """
    try:
        rows = _fetch_month_campaign(account_id)
        if rows and rows[0].get("status") in ("approved", "active"):
            mode = rows[0].get("strategy_mode")
            if mode in ("commercial_campaign", "personal_storyline"):
                return mode  # type: ignore[return-value]
    except Exception as e:
        logger.warning(f"Error resolving strategy mode for account {account_id}: {e}")
    return "personal_storyline"


async def resolve_strategy_mode(account_id: int) -> StrategyMode:
    """Async version of get_strategy_mode (the Supabase query runs in a thread)."""
    return await asyncio.to_thread(get_strategy_mode, account_id)


# --- Prompts Builder ---

_COMMON_RULES = (
    "REGLAS DE ESTILO:\n"
    "- Frases naturales y concretas; nada de clichés de IA (\"delve into\", \"game-changer\", \"sumérgete\", \"en el mundo actual\").\n"
    "- No uses em dashes (—) ni caracteres invisibles.\n"
    "- El gancho del caption cabe en los primeros 125 caracteres; máximo 5 hashtags al final."
)

_REEL_STRATEGY: Dict[str, str] = {
    "commercial_campaign": (
        "ESTRATEGIA COMERCIAL / CONVERSIÓN:\n"
        "- Objetivo: captar clientes potenciales, generar autoridad de marca y llamada clara a la acción.\n"
        "- Ganchos: directos, con pérdida cuantificada, paradojas de negocio o prueba de resultados.\n"
        "- Beats en este orden: Problema → Agitación → Solución → CTA, con foco en ROI o beneficios tangibles.\n"
        "- CTA: comercial directo (comenta una palabra clave, guarda para aplicar, enlace en bio)."
    ),
    "personal_storyline": (
        "ESTRATEGIA PERSONAL / STORYLINE:\n"
        "- Objetivo: conexión humana, empatía, vulnerabilidad y reflexiones auténticas sin venta directa.\n"
        "- Ganchos: bucle narrativo, confesión honesta, lección personal o verdad incómoda.\n"
        "- Beats en este orden: Anécdota → Giro → Aprendizaje → Cierre. Sin CTA de venta.\n"
        "- Cierre: conversacional y abierto (¿te ha pasado?, cuéntame tu experiencia)."
    ),
}

_CAROUSEL_STRATEGY: Dict[str, str] = {
    "commercial_campaign": (
        "ESTRATEGIA COMERCIAL:\n"
        "- Cover (portada): máximo 6 palabras, promesa contundente de transformación o error grave de negocio.\n"
        "- Stake: coste de no solucionarlo, urgencia o autoridad.\n"
        "- Ideas intermedias: pasos de implementación de alto valor, máximo 25 palabras por diapositiva.\n"
        "- Recap: resumen en lista con valor de referencia.\n"
        "- CTA: una sola acción orientada a leads."
    ),
    "personal_storyline": (
        "ESTRATEGIA PERSONAL / STORYLINE:\n"
        "- Cover (portada): máximo 6 palabras, ángulo íntimo, lección aprendida o historia vivida.\n"
        "- Stake: momento vulnerable o descubrimiento sincero.\n"
        "- Ideas intermedias: reflexiones y aprendizajes personales, máximo 25 palabras por diapositiva.\n"
        "- Recap: síntesis en lista de la perspectiva aprendida.\n"
        "- CTA: una sola invitación a reflexionar o comentar, sin venta."
    ),
}

_STORY_STRATEGY: Dict[str, str] = {
    "commercial_campaign": (
        "ESTRATEGIA COMERCIAL:\n"
        "- Secuencia orientada a cualificar audiencia y convertir.\n"
        "- Orden: calentar con encuesta ('poll') → caja de preguntas ('question') → llamada al DM ('dm_cta') o enlace ('link')."
    ),
    "personal_storyline": (
        "ESTRATEGIA PERSONAL:\n"
        "- Secuencia espontánea, conversacional y auténtica, sin venta.\n"
        "- Orden: calentar con encuesta ('poll') → caja de preguntas ('question') → invitación a seguir la charla por DM ('dm_cta') o 'none'."
    ),
}


def _hook_formulas_hint(strategy_mode: StrategyMode, limit: int = 8) -> str:
    """Formula ids/names recommended for the mode, so Gemini's formula_id matches the catalogue."""
    recommended = [f for f in get_hook_formulas(strategy_mode) if strategy_mode in f.get("best_for", [])]
    return "\n".join(f"- {f['id']}: {f['name']} ({f['template']})" for f in recommended[:limit])


def build_reel_prompt(topic: str, strategy_mode: StrategyMode, language: str = "es") -> str:
    return f"""Eres un creador experto de contenido para Instagram Reels.
Idioma: {language}.
Tema: "{topic}".

{_REEL_STRATEGY[strategy_mode]}

Fórmulas de gancho recomendadas (usa una distinta en cada gancho):
{_hook_formulas_hint(strategy_mode)}

- Cada beat se dice en 4 segundos o menos (máximo 11 palabras).
- El último beat retoma palabras del gancho para cerrar en loop.
{_COMMON_RULES}

Genera un guión estructurado para un Reel y responde ÚNICAMENTE con un JSON válido con la siguiente estructura:
{{
  "hooks": [
    {{"text": "Gancho 1 potente (frase corta inicial)", "formula_id": 1, "formula_name": "Nombre fórmula"}},
    {{"text": "Gancho 2 alternativo", "formula_id": 2, "formula_name": "Nombre fórmula"}},
    {{"text": "Gancho 3 alternativo", "formula_id": 3, "formula_name": "Nombre fórmula"}}
  ],
  "beats": [
    {{"label": "Nombre del beat", "text": "Frase hablada en cámara"}}
  ],
  "on_screen_text": [
    "Frase de texto clave que aparece en pantalla 1",
    "Frase de texto clave que aparece en pantalla 2"
  ],
  "caption": "Texto completo del caption para acompañar el reel."
}}"""


def build_carousel_prompt(topic: str, slides_count: int, strategy_mode: StrategyMode, language: str = "es") -> str:
    return f"""Eres un especialista en carruseles educativos y de alto engagement en Instagram.
Idioma: {language}.
Tema: "{topic}".
Número total de diapositivas requerido: {slides_count}.

{_CAROUSEL_STRATEGY[strategy_mode]}
{_COMMON_RULES}

Estructura obligatoria de diapositivas:
- Diapositiva 1: rol 'cover' (máximo 6 palabras)
- Diapositiva 2: rol 'stake'
- Diapositivas 3 a {slides_count - 2}: rol 'idea' (una idea por diapositiva, máximo 25 palabras)
- Diapositiva {slides_count - 1}: rol 'recap'
- Diapositiva {slides_count}: rol 'cta'

Responde ÚNICAMENTE con un JSON válido con la siguiente estructura:
{{
  "slides": [
    {{"index": 1, "role": "cover", "text": "Texto portada"}},
    {{"index": 2, "role": "stake", "text": "Texto problema o stake"}},
    ...
  ],
  "caption": "Caption completo para acompañar el carrusel."
}}"""


def build_story_prompt(topic: Optional[str], strategy_mode: StrategyMode, language: str = "es") -> str:
    topic_str = topic or "Día a día y conexión con la audiencia"
    return f"""Eres un creador de historias de Instagram de alta retención.
Idioma: {language}.
Tema: "{topic_str}".

{_STORY_STRATEGY[strategy_mode]}
{_COMMON_RULES}

Genera exactamente 3 o 4 frames de historias.
Responde ÚNICAMENTE con un JSON válido con esta estructura:
{{
  "frames": [
    {{
      "index": 1,
      "role": "warmup",
      "text": "Texto en pantalla o guión hablado de la historia",
      "sticker": "poll",
      "sticker_payload": {{"question": "¿Cuál prefieres?", "options": ["A", "B"]}}
    }},
    ...
  ]
}}"""


def build_repurpose_prompt(transcript: str, strategy_mode: StrategyMode, language: str = "es") -> str:
    return f"""Eres un estratega de reciclaje de contenidos (Content Repurposing) en Instagram.
Idioma: {language}.

A partir de la siguiente transcripción, genera exactamente 3 guiones de Reels y 2 carruseles (de 7 diapositivas cada uno) independientes entre sí, en una sola respuesta JSON.

REELS:
{_REEL_STRATEGY[strategy_mode]}

CARRUSELES (cover, stake, 3 ideas, recap, cta):
{_CAROUSEL_STRATEGY[strategy_mode]}
{_COMMON_RULES}

Transcripción:
\"\"\"{transcript}\"\"\"

Responde ÚNICAMENTE con un JSON válido con esta estructura:
{{
  "reels": [
    {{
      "hooks": [{{"text": "Gancho...", "formula_id": 1, "formula_name": "Fórmula"}}],
      "beats": [{{"label": "Beat", "text": "..."}}],
      "on_screen_text": ["Texto pantalla"],
      "caption": "Caption"
    }}
  ],
  "carousels": [
    {{
      "slides": [
        {{"index": 1, "role": "cover", "text": "Portada"}},
        {{"index": 2, "role": "stake", "text": "Problema"}},
        {{"index": 3, "role": "idea", "text": "Idea 1"}},
        {{"index": 4, "role": "idea", "text": "Idea 2"}},
        {{"index": 5, "role": "idea", "text": "Idea 3"}},
        {{"index": 6, "role": "recap", "text": "Resumen"}},
        {{"index": 7, "role": "cta", "text": "CTA"}}
      ],
      "caption": "Caption"
    }}
  ]
}}"""


# --- Post-procesadores deterministas ---

def _clean_text(text: str, language: str = "es") -> str:
    if not text:
        return ""
    cleaned, _ = humanize(text, language=language)
    return cleaned


def _post_process_reel(raw_reel: Dict[str, Any], strategy_mode: StrategyMode, language: str) -> ReelOut:
    raw_caption = raw_reel.get("caption", "")
    humanized_caption = _clean_text(raw_caption, language=language)
    report_dict = lint_caption(humanized_caption, language=language)
    report = QualityReport(**report_dict)

    raw_hooks = raw_reel.get("hooks", [])
    hooks: List[ReelHookCandidate] = []
    for h in raw_hooks:
        h_text = _clean_text(h.get("text", ""), language=language)
        scored = score_hook(h_text, strategy_mode=strategy_mode)
        hooks.append(
            ReelHookCandidate(
                text=h_text,
                score=scored.get("score", 0),
                formula_id=scored.get("formula_id") or h.get("formula_id"),
                formula_name=scored.get("formula_name") or h.get("formula_name"),
            )
        )

    raw_beats = raw_reel.get("beats", [])
    clean_beats_input = [
        {"label": b.get("label", ""), "text": _clean_text(b.get("text", ""), language=language)}
        for b in raw_beats
    ]
    timed_beats_dict = time_beats(clean_beats_input) if clean_beats_input else {"beats": [], "total_s": 0.0, "loops_to_hook": False}
    beats_out = BeatsResponse(**timed_beats_dict)

    raw_ost = raw_reel.get("on_screen_text", [])
    on_screen_text = [_clean_text(t, language=language) for t in raw_ost]

    return ReelOut(
        hooks=hooks,
        beats=beats_out,
        on_screen_text=on_screen_text,
        caption=humanized_caption,
        report=report,
    )


def _post_process_carousel(raw_carousel: Dict[str, Any], language: str) -> CarouselOut:
    raw_caption = raw_carousel.get("caption", "")
    humanized_caption = _clean_text(raw_caption, language=language)
    report_dict = lint_caption(humanized_caption, language=language)
    report = QualityReport(**report_dict)

    slides: List[CarouselSlide] = []
    warnings: List[str] = []
    raw_slides = raw_carousel.get("slides", [])

    for s in raw_slides:
        clean_text = _clean_text(s.get("text", ""), language=language)
        words = len(clean_text.split()) if clean_text.strip() else 0
        role = s.get("role", "idea")
        if role not in ("cover", "stake", "idea", "recap", "cta"):
            role = "idea"

        if role == "cover" and words > 6:
            warnings.append(f"La diapositiva de portada supera 6 palabras (actual: {words}).")
        elif role == "idea" and words > 25:
            warnings.append(f"La diapositiva {s.get('index', '')} supera 25 palabras (actual: {words}).")

        slides.append(
            CarouselSlide(
                index=s.get("index", len(slides) + 1),
                role=role,
                text=clean_text,
                word_count=words,
            )
        )

    return CarouselOut(
        slides=slides,
        caption=humanized_caption,
        report=report,
        warnings=warnings,
    )


# --- Generadores Principales ---

async def generate_reel(
    account_id: int,
    topic: str,
    strategy_mode: Optional[StrategyMode] = None,
    language: str = "es",
) -> ReelOut:
    """Generates a structured Reel with 3 scored hooks, timed beats, and quality report."""
    resolved_mode = strategy_mode or await resolve_strategy_mode(account_id)
    cache_key = _get_cache_key("reel", account_id, resolved_mode, topic, language)
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    prompt = build_reel_prompt(topic, resolved_mode, language)
    raw_response = await generate_gemini_content(prompt, json_mode=True)
    parsed = await clean_and_parse_json(raw_response)

    reel_out = _post_process_reel(parsed, resolved_mode, language)
    set_in_cache(cache_key, reel_out)
    return reel_out


async def generate_carousel(
    account_id: int,
    topic: str,
    slides: int = 7,
    strategy_mode: Optional[StrategyMode] = None,
    language: str = "es",
) -> CarouselOut:
    """Generates a structured Carousel (6-10 slides) with quality report and word warnings."""
    if slides < 6 or slides > 10:
        raise ValueError(f"slides must be between 6 and 10, got {slides}")

    resolved_mode = strategy_mode or await resolve_strategy_mode(account_id)
    cache_key = _get_cache_key("carousel", account_id, resolved_mode, f"{topic}:{slides}", language)
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    prompt = build_carousel_prompt(topic, slides, resolved_mode, language)
    raw_response = await generate_gemini_content(prompt, json_mode=True)
    parsed = await clean_and_parse_json(raw_response)

    carousel_out = _post_process_carousel(parsed, language)
    if len(carousel_out.slides) != slides:
        carousel_out.warnings.append(f"Se pidieron {slides} diapositivas y se generaron {len(carousel_out.slides)}.")
    set_in_cache(cache_key, carousel_out)
    return carousel_out


async def generate_story(
    account_id: int,
    topic: Optional[str] = None,
    strategy_mode: Optional[StrategyMode] = None,
    language: str = "es",
) -> StoryOut:
    """Generates 3-4 Story frames with interactive stickers."""
    resolved_mode = strategy_mode or await resolve_strategy_mode(account_id)
    input_str = topic or "daily_storyline"
    cache_key = _get_cache_key("story", account_id, resolved_mode, input_str, language)
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    prompt = build_story_prompt(topic, resolved_mode, language)
    raw_response = await generate_gemini_content(prompt, json_mode=True)
    parsed = await clean_and_parse_json(raw_response)

    frames: List[StoryFrame] = []
    for f in parsed.get("frames", [])[:4]:
        text = _clean_text(f.get("text", ""), language=language)
        sticker = f.get("sticker", "none")
        if sticker not in ("poll", "question", "link", "dm_cta", "none"):
            sticker = "none"
        frames.append(
            StoryFrame(
                index=f.get("index", len(frames) + 1),
                role=f.get("role", "story"),
                text=text,
                sticker=sticker,
                sticker_payload=f.get("sticker_payload"),
            )
        )

    story_out = StoryOut(frames=frames)
    set_in_cache(cache_key, story_out)
    return story_out


async def generate_repurpose(
    account_id: int,
    transcript: str,
    strategy_mode: Optional[StrategyMode] = None,
    language: str = "es",
) -> RepurposeOut:
    """Repurposes a transcript into 3 Reels and 2 Carousels in a single Gemini call."""
    if len(transcript) > 30000:
        raise ValueError(f"transcript exceeds maximum length of 30000 chars (got {len(transcript)})")

    resolved_mode = strategy_mode or await resolve_strategy_mode(account_id)
    cache_key = _get_cache_key("repurpose", account_id, resolved_mode, transcript, language)
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    prompt = build_repurpose_prompt(transcript, resolved_mode, language)
    raw_response = await generate_gemini_content(prompt, json_mode=True)
    parsed = await clean_and_parse_json(raw_response)

    reels = [_post_process_reel(r, resolved_mode, language) for r in parsed.get("reels", [])]
    carousels = [_post_process_carousel(c, language) for c in parsed.get("carousels", [])]

    repurpose_out = RepurposeOut(reels=reels, carousels=carousels)
    set_in_cache(cache_key, repurpose_out)
    return repurpose_out


# --- Reescritura de bio (auditoría de perfil) ---

_BIO_STRATEGY: Dict[str, str] = {
    "commercial_campaign": (
        "Cuenta comercial: a quién ayuda, qué resultado concreto consigue, una prueba de autoridad "
        "y una llamada a la acción hacia el enlace."
    ),
    "personal_storyline": (
        "Cuenta personal: quién es, de qué va su historia y qué encontrará quien le siga; "
        "tono cercano, sin lenguaje de venta."
    ),
}


def build_bio_prompt(
    current_bio: str, failed_tips: List[str], strategy_mode: StrategyMode, language: str = "es"
) -> str:
    tips = "\n".join(f"- {t}" for t in failed_tips) or "- (ninguno)"
    return f"""Reescribe la biografía de Instagram de esta cuenta. Idioma: {language}.
{_COMMON_RULES}
ESTRATEGIA: {_BIO_STRATEGY[strategy_mode]}
Máximo 150 caracteres, 3 o 4 líneas cortas separadas por saltos de línea.

BIO ACTUAL:
{current_bio or "(vacía)"}

PUNTOS DE LA AUDITORÍA QUE NO CUMPLE:
{tips}

Responde solo con JSON: {{"bio": "..."}}"""


async def generate_bio_rewrite(
    account_id: int,
    current_bio: str,
    failed_tips: List[str],
    strategy_mode: Optional[StrategyMode] = None,
    language: str = "es",
) -> str:
    """Bio sugerida acorde a la estrategia (Gemini, cacheada 1 h por bio + puntos fallidos)."""
    resolved_mode = strategy_mode or await resolve_strategy_mode(account_id)
    cache_key = _get_cache_key(
        "bio", account_id, resolved_mode, current_bio + "|" + "|".join(failed_tips), language
    )
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    prompt = build_bio_prompt(current_bio, failed_tips, resolved_mode, language)
    raw_response = await generate_gemini_content(prompt, json_mode=True)
    parsed = await clean_and_parse_json(raw_response)
    bio = _clean_text(str(parsed.get("bio", "")).strip(), language=language)
    if not bio:
        raise ValueError("Gemini no devolvió una bio")
    set_in_cache(cache_key, bio)
    return bio


# --- Triaje de comentarios y comunidad (Fase F) ---

COMMENTS_CACHE_TTL_SECONDS = 900  # 15 minutes TTL (AD-8)
_COMMENTS_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def clear_comments_cache() -> None:
    """Limpia la caché en memoria de comentarios leídos de Graph API."""
    _COMMENTS_CACHE.clear()


def get_comments_from_cache(media_id: str) -> Optional[List[Dict[str, Any]]]:
    """Obtiene comentarios en caché si no han expirado (15 min)."""
    entry = _COMMENTS_CACHE.get(media_id)
    if entry:
        timestamp, comments = entry
        if time.time() - timestamp < COMMENTS_CACHE_TTL_SECONDS:
            return comments
        else:
            del _COMMENTS_CACHE[media_id]
    return None


def set_comments_in_cache(media_id: str, comments: List[Dict[str, Any]]) -> None:
    """Almacena comentarios en caché con timestamp actual."""
    _COMMENTS_CACHE[media_id] = (time.time(), comments)


_TRIAGE_LABELS: Dict[str, Tuple[str, ...]] = {
    "commercial_campaign": ("lead", "question", "objection", "support", "noise"),
    "personal_storyline": ("question", "support", "noise"),
}

_TRIAGE_STRATEGY: Dict[str, str] = {
    "commercial_campaign": (
        "Cuenta comercial. Etiquetas:\n"
        "- lead: muestra intención de compra o pide precio, información o contratar.\n"
        "- question: pregunta sobre el contenido.\n"
        "- objection: duda o pega sobre precio, utilidad o confianza.\n"
        "- support: elogio, agradecimiento o apoyo.\n"
        "- noise: emojis sueltos, spam o texto sin contenido.\n"
        "Respuestas: al lead, invítale a hablar por DM sin presionar; a la objeción, reconócela y aclárala "
        "con un dato; a la pregunta, respóndela de forma breve."
    ),
    "personal_storyline": (
        "Cuenta personal, sin venta. Etiquetas (solo estas):\n"
        "- question: pregunta o curiosidad (también si pregunta por precios o comprar).\n"
        "- support: elogio, apoyo o experiencia compartida.\n"
        "- noise: emojis sueltos, spam o texto sin contenido.\n"
        "Respuestas: cercanas y conversacionales, que inviten a seguir hablando (una pregunta de vuelta, "
        "una anécdota breve). Nada de DM comerciales ni llamadas a la venta."
    ),
}


def build_triage_prompt(comments: List[str], strategy_mode: StrategyMode, language: str = "es") -> str:
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(comments, start=1))
    return f"""Clasifica los comentarios de una publicación de Instagram y sugiere una respuesta para cada uno.
Idioma de las respuestas: {language}.

{_TRIAGE_STRATEGY[strategy_mode]}
{_COMMON_RULES}
Respuestas de 1 o 2 frases, sin hashtags.

COMENTARIOS:
{numbered}

Responde ÚNICAMENTE con un JSON válido, un elemento por comentario y en el mismo orden:
{{"comments": [{{"index": 1, "label": "question", "reply": "..."}}]}}"""


async def triage_comments(
    raw_comments: List[Dict[str, Any]],
    strategy_mode: StrategyMode = "personal_storyline",
    language: str = "es",
    account_id: int = 0,
) -> List[CommentTriageItem]:
    """
    Etiqueta cada comentario y sugiere una respuesta (una sola llamada Gemini, caché 1 h).
    - commercial_campaign: lead / question / objection / support / noise
    - personal_storyline: question / support / noise (lead y objection pasan a question)
    """
    if not raw_comments:
        return []
    texts = [str(c.get("text") or "") for c in raw_comments]
    cache_key = _get_cache_key("triage", account_id, strategy_mode, "\n".join(texts), language)
    parsed = get_from_cache(cache_key)
    if parsed is None:
        raw_response = await generate_gemini_content(
            build_triage_prompt(texts, strategy_mode, language), json_mode=True
        )
        parsed = await clean_and_parse_json(raw_response)
        set_in_cache(cache_key, parsed)

    by_index = {
        item.get("index"): item for item in parsed.get("comments", []) if isinstance(item, dict)
    }
    allowed = _TRIAGE_LABELS[strategy_mode]
    results: List[CommentTriageItem] = []
    for i, c in enumerate(raw_comments, start=1):
        item = by_index.get(i, {})
        label = item.get("label")
        if label not in allowed:
            label = "question" if label in ("lead", "objection") else "noise"
        results.append(CommentTriageItem(
            id=c.get("id") or str(i),
            text=texts[i - 1],
            username=c.get("username"),
            label=label,
            suggested_reply=_clean_text(str(item.get("reply") or ""), language=language),
        ))
    return results


PROSPECT_COMMENT_TYPES: List[str] = [
    "Dato complementario",
    "Experiencia propia",
    "Matiz respetuoso",
    "Pregunta reflexiva",
    "Síntesis clave",
    "Analogía",
    "Pregunta de seguimiento",
    "Caso práctico",
    "Agradecimiento concreto",
]


def build_prospect_prompt(target_post_text: str, strategy_mode: StrategyMode, language: str = "es") -> str:
    types = "\n".join(f"{i}. {name}" for i, name in enumerate(PROSPECT_COMMENT_TYPES, start=1))
    tone = (
        "Tono de profesional del sector que aporta criterio; sin autopromoción ni enlaces."
        if strategy_mode == "commercial_campaign"
        else "Tono cercano de creador que conecta con otro; sin venta ni autopromoción."
    )
    return f"""Escribe comentarios con sustancia para dejar en la publicación de otra cuenta del sector.
Idioma: {language}. {tone}
{_COMMON_RULES}
Cada comentario: 1 a 3 frases, específico de esta publicación (nada genérico como "gran post"), sin hashtags.

Un comentario por cada tipo:
{types}

PUBLICACIÓN:
\"\"\"{target_post_text}\"\"\"

Responde ÚNICAMENTE con un JSON válido:
{{"suggestions": [{{"type": 1, "text": "..."}}]}}"""


async def generate_prospect_comments(
    target_post_text: str,
    strategy_mode: StrategyMode = "personal_storyline",
    language: str = "es",
    account_id: int = 0,
) -> List[ProspectCommentItem]:
    """Un comentario de prospección por cada uno de los 9 tipos (Gemini, caché 1 h)."""
    cache_key = _get_cache_key("prospect", account_id, strategy_mode, target_post_text, language)
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    raw_response = await generate_gemini_content(
        build_prospect_prompt(target_post_text, strategy_mode, language), json_mode=True
    )
    parsed = await clean_and_parse_json(raw_response)
    by_type = {
        s.get("type"): s for s in parsed.get("suggestions", []) if isinstance(s, dict)
    }
    suggestions = [
        ProspectCommentItem(
            type=i,
            type_name=name,
            text=_clean_text(str(by_type[i].get("text") or ""), language=language),
        )
        for i, name in enumerate(PROSPECT_COMMENT_TYPES, start=1)
        if i in by_type and by_type[i].get("text")
    ]
    set_in_cache(cache_key, suggestions)
    return suggestions


def build_dm_funnel_prompt(keyword: str, resource_description: str, language: str = "es") -> str:
    return f"""Una publicación de Instagram pide comentar la palabra clave "{keyword}" para recibir este recurso:
{resource_description}

Escribe los mensajes directos que la cuenta enviará a quien comente. Idioma: {language}.
{_COMMON_RULES}
- delivery_dm: agradece el comentario mencionando la palabra clave "{keyword}", entrega el recurso (usa el marcador [ENLACE]) y termina con una pregunta abierta.
- follow_ups: exactamente 2 seguimientos cortos (a las 24 h y a los 3 días) que pregunten si le sirvió y ofrezcan ayuda, sin presionar.

Responde ÚNICAMENTE con un JSON válido:
{{"delivery_dm": "...", "follow_ups": ["...", "..."]}}"""


async def generate_dm_funnel(
    keyword: str,
    resource_description: str,
    language: str = "es",
    account_id: int = 0,
) -> DmFunnelResponse:
    """DM de entrega del recurso + 2 seguimientos (Gemini, caché 1 h). Solo cuentas comerciales en la UI."""
    cache_key = _get_cache_key(
        "dm_funnel", account_id, "commercial_campaign", f"{keyword}|{resource_description}", language
    )
    cached = get_from_cache(cache_key)
    if cached is not None:
        return cached

    raw_response = await generate_gemini_content(
        build_dm_funnel_prompt(keyword, resource_description, language), json_mode=True
    )
    parsed = await clean_and_parse_json(raw_response)
    funnel = DmFunnelResponse(
        delivery_dm=_clean_text(str(parsed.get("delivery_dm") or ""), language=language),
        follow_ups=[_clean_text(str(f), language=language) for f in parsed.get("follow_ups", [])[:2]],
    )
    set_in_cache(cache_key, funnel)
    return funnel
