"""
Content Formats Generator Service
Generates format-specific content (Reel, Carousel, Story, Repurpose) via Gemini with
process-local 1-hour hash cache and deterministic quality post-processing (humanize + lint).
"""

import asyncio
import hashlib
import logging
import time
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple

from database.supabase_client import get_supabase_admin_client
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
    current_month = date.today().replace(day=1).isoformat()
    res = (
        supabase.table("monthly_campaigns")
        .select("strategy_mode, status")
        .eq("account_id", account_id)
        .eq("month_date", current_month)
        .execute()
    )
    return res.data or []


async def resolve_strategy_mode(account_id: int) -> StrategyMode:
    """
    Resolves the strategy mode for an account (AD-2):
    1. Active/approved campaign of current month -> its strategy_mode.
    2. Otherwise -> 'personal_storyline'.
    """
    try:
        rows = await asyncio.to_thread(_fetch_month_campaign, account_id)
        if rows and rows[0].get("status") in ("approved", "active"):
            mode = rows[0].get("strategy_mode")
            if mode in ("commercial_campaign", "personal_storyline"):
                return mode  # type: ignore[return-value]
    except Exception as e:
        logger.warning(f"Error resolving strategy mode for account {account_id}: {e}")
    return "personal_storyline"


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
