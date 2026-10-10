"""
Tests for Content Formats Generation Service (Fase C)
Covers:
- Gemini mocked (no external calls)
- In-memory 1-hour hash cache hit behavior
- Distinct prompt building by strategy_mode (commercial_campaign vs personal_storyline)
- Deterministic humanization and QualityReport post-processing
- Input validations (slides range 6-10, transcript length <= 30000)
- Strategy mode resolution from monthly_campaigns
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from models.schemas import (
    CarouselOut,
    CarouselRequest,
    ReelOut,
    RepurposeOut,
    RepurposeRequest,
    StoryOut,
)
from services.content_formats import (
    CACHE_TTL_SECONDS,
    _get_cache_key,
    build_carousel_prompt,
    build_reel_prompt,
    build_repurpose_prompt,
    build_story_prompt,
    clear_formats_cache,
    generate_carousel,
    generate_reel,
    generate_repurpose,
    generate_story,
    get_from_cache,
    resolve_strategy_mode,
    set_in_cache,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure format generator cache is empty before and after each test."""
    clear_formats_cache()
    yield
    clear_formats_cache()


# --- Cache Tests ---

def test_cache_key_generation():
    key1 = _get_cache_key("reel", 1, "commercial_campaign", "Automatiza tu Instagram")
    key2 = _get_cache_key("reel", 1, "commercial_campaign", "automatiza tu instagram ")
    key3 = _get_cache_key("reel", 1, "personal_storyline", "Automatiza tu Instagram")

    # Normalized input should match
    assert key1 == key2
    # Different strategy modes should produce different hashes
    assert key1 != key3
    assert len(key1) == 64  # SHA256 hex length


def test_cache_set_get_and_expiration():
    key = "test_key_123"
    base_time = 1000000.0
    with patch("services.content_formats.time.time", return_value=base_time):
        set_in_cache(key, {"dummy": "value"})
        assert get_from_cache(key) == {"dummy": "value"}

    # Mock time expiry after TTL
    with patch("services.content_formats.time.time", return_value=base_time + CACHE_TTL_SECONDS + 1):
        assert get_from_cache(key) is None


@pytest.mark.asyncio
async def test_generate_reel_cache_hit():
    mock_payload = {
        "hooks": [
            {"text": "El gran error al crear contenido", "formula_id": 1, "formula_name": "Error común"}
        ],
        "beats": [
            {"label": "Gancho", "text": "El gran error al crear contenido"},
            {"label": "Cierre", "text": "Sigue para más"}
        ],
        "on_screen_text": ["Aprende esto"],
        "caption": "Caption para el reel con consejos útiles #marketing #tips"
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        # Primer llamado -> llama a Gemini
        reel1 = await generate_reel(account_id=1, topic="Estrategia Instagram", strategy_mode="commercial_campaign")
        assert isinstance(reel1, ReelOut)
        assert mock_gemini.call_count == 1

        # Segundo llamado con mismos parámetros -> cache hit, NO llama a Gemini
        reel2 = await generate_reel(account_id=1, topic="Estrategia Instagram", strategy_mode="commercial_campaign")
        assert isinstance(reel2, ReelOut)
        assert mock_gemini.call_count == 1
        assert reel1.caption == reel2.caption

        # Tercer llamado con topic diferente -> cache miss, llama a Gemini
        await generate_reel(account_id=1, topic="Otro tema diferente", strategy_mode="commercial_campaign")
        assert mock_gemini.call_count == 2


# --- Prompts by Strategy Mode Tests ---

def test_prompts_differ_by_strategy_mode():
    topic = "Gestión del tiempo"

    # Reel prompts
    reel_comm = build_reel_prompt(topic, "commercial_campaign")
    reel_pers = build_reel_prompt(topic, "personal_storyline")
    assert reel_comm != reel_pers
    assert "ESTRATEGIA COMERCIAL" in reel_comm
    assert "ESTRATEGIA PERSONAL" in reel_pers
    assert "ROI" in reel_comm or "conversión" in reel_comm.lower()
    assert "vulnerabilidad" in reel_pers.lower() or "empatía" in reel_pers.lower()

    # Carousel prompts
    car_comm = build_carousel_prompt(topic, 7, "commercial_campaign")
    car_pers = build_carousel_prompt(topic, 7, "personal_storyline")
    assert car_comm != car_pers
    assert "ESTRATEGIA COMERCIAL" in car_comm
    assert "ESTRATEGIA PERSONAL" in car_pers

    # Story prompts
    story_comm = build_story_prompt(topic, "commercial_campaign")
    story_pers = build_story_prompt(topic, "personal_storyline")
    assert story_comm != story_pers
    assert "ESTRATEGIA COMERCIAL" in story_comm
    assert "ESTRATEGIA PERSONAL" in story_pers


@pytest.mark.asyncio
async def test_generate_reel_passes_mode_specific_prompt():
    mock_payload = {
        "hooks": [{"text": "Gancho", "formula_id": 1}],
        "beats": [{"label": "Beat", "text": "Texto beat"}],
        "on_screen_text": [],
        "caption": "Caption"
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        await generate_reel(account_id=1, topic="Lanzamiento", strategy_mode="commercial_campaign")
        prompt_used = mock_gemini.call_args[0][0]
        assert "ESTRATEGIA COMERCIAL" in prompt_used

        clear_formats_cache()

        await generate_reel(account_id=1, topic="Lanzamiento", strategy_mode="personal_storyline")
        prompt_used_personal = mock_gemini.call_args[0][0]
        assert "ESTRATEGIA PERSONAL" in prompt_used_personal


# --- Humanized Post-Processing & QualityReport Tests ---

@pytest.mark.asyncio
async def test_reel_post_processing_humanizes_and_builds_quality_report():
    # Payload con término de slop ("delve into") y em dashes duplicados
    mock_payload = {
        "hooks": [
            {"text": "Let's delve into why 80% fail", "formula_id": 2}
        ],
        "beats": [
            {"label": "Gancho", "text": "Let's delve into this secret"},
            {"label": "Cierre", "text": "Secret details here"}
        ],
        "on_screen_text": ["Do not delve into myths"],
        "caption": "We will delve into marketing——and find success. #uno #dos #tres"
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        reel = await generate_reel(account_id=2, topic="Marketing", strategy_mode="commercial_campaign", language="en")

        # Verifica que el humanizador reemplazó "delve into"
        assert "delve into" not in reel.caption.lower()
        assert "delve into" not in reel.hooks[0].text.lower()
        assert "delve into" not in reel.on_screen_text[0].lower()

        # Verifica QualityReport adjunto
        assert reel.report is not None
        assert reel.report.hashtag_count == 3
        assert reel.report.slop.invisible_chars == 0

        # Verifica hook score calculado
        assert reel.hooks[0].score > 0

        # Verifica beat timer calculado
        assert len(reel.beats.beats) == 2
        assert reel.beats.total_s > 0


@pytest.mark.asyncio
async def test_carousel_post_processing_calculates_words_and_warnings():
    mock_payload = {
        "slides": [
            {
                "index": 1,
                "role": "cover",
                "text": "Esta es una portada con más de seis palabras para testear el aviso"  # 13 words (> 6)
            },
            {
                "index": 2,
                "role": "stake",
                "text": "El problema principal radica en no tener claridad."
            },
            {
                "index": 3,
                "role": "idea",
                "text": "Esta es una idea exageradamente larga que incluye tantas palabras que superará los veinticinco vocablos permitidos con absoluta seguridad según el contador."  # 24 words
            },
            {
                "index": 4,
                "role": "idea",
                "text": "Idea corta y al punto."
            },
            {
                "index": 5,
                "role": "idea",
                "text": "Otra idea concisa."
            },
            {
                "index": 6,
                "role": "recap",
                "text": "Resumen final."
            },
            {
                "index": 7,
                "role": "cta",
                "text": "Guarda este post."
            }
        ],
        "caption": "Caption para carrusel #carrusel #consejos"
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        carousel = await generate_carousel(account_id=1, topic="Productividad", slides=7)
        assert isinstance(carousel, CarouselOut)
        assert len(carousel.slides) == 7
        assert carousel.slides[0].word_count == 13

        # Advertencia de portada > 6 palabras
        assert any("portada supera 6 palabras" in w for w in carousel.warnings)
        assert carousel.report is not None
        assert carousel.report.hashtag_count == 2


@pytest.mark.asyncio
async def test_story_generation():
    mock_payload = {
        "frames": [
            {
                "index": 1,
                "role": "intro",
                "text": "¿Sabías esto sobre tu alcance?",
                "sticker": "poll",
                "sticker_payload": {"question": "¿Lo sabías?", "options": ["Sí", "No"]}
            },
            {
                "index": 2,
                "role": "solution",
                "text": "Aquí tienes la clave.",
                "sticker": "none"
            },
            {
                "index": 3,
                "role": "cta",
                "text": "Mándame un DM con la palabra CLAVE.",
                "sticker": "dm_cta"
            }
        ]
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        story = await generate_story(account_id=3, topic="Alcance orgánico")
        assert isinstance(story, StoryOut)
        assert len(story.frames) == 3
        assert story.frames[0].sticker == "poll"
        assert story.frames[2].sticker == "dm_cta"


@pytest.mark.asyncio
async def test_repurpose_generation_3_reels_2_carousels():
    mock_payload = {
        "reels": [
            {
                "hooks": [{"text": "Reel hook 1", "score": 80}],
                "beats": [{"label": "Intro", "text": "Texto"}],
                "on_screen_text": ["OST"],
                "caption": "Caption reel 1 #reel"
            },
            {
                "hooks": [{"text": "Reel hook 2", "score": 75}],
                "beats": [{"label": "Intro", "text": "Texto"}],
                "on_screen_text": ["OST"],
                "caption": "Caption reel 2 #reel"
            },
            {
                "hooks": [{"text": "Reel hook 3", "score": 70}],
                "beats": [{"label": "Intro", "text": "Texto"}],
                "on_screen_text": ["OST"],
                "caption": "Caption reel 3 #reel"
            }
        ],
        "carousels": [
            {
                "slides": [{"index": 1, "role": "cover", "text": "Portada 1"}],
                "caption": "Caption carrusel 1 #carrusel"
            },
            {
                "slides": [{"index": 1, "role": "cover", "text": "Portada 2"}],
                "caption": "Caption carrusel 2 #carrusel"
            }
        ]
    }

    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(mock_payload)

        transcript = "Transcripción corta de prueba sobre hábitos de creadores de contenido."
        repurpose = await generate_repurpose(account_id=1, transcript=transcript)

        assert isinstance(repurpose, RepurposeOut)
        assert len(repurpose.reels) == 3
        assert len(repurpose.carousels) == 2
        assert repurpose.reels[0].report is not None
        assert repurpose.carousels[0].report is not None


# --- Validation Tests ---

@pytest.mark.asyncio
async def test_carousel_slides_validation():
    with pytest.raises(ValueError, match="between 6 and 10"):
        await generate_carousel(account_id=1, topic="Test", slides=5)

    with pytest.raises(ValueError, match="between 6 and 10"):
        await generate_carousel(account_id=1, topic="Test", slides=11)

    # Schema Pydantic level validation
    with pytest.raises(ValidationError):
        CarouselRequest(account_id=1, topic="Test", slides=5)

    with pytest.raises(ValidationError):
        CarouselRequest(account_id=1, topic="Test", slides=11)


@pytest.mark.asyncio
async def test_repurpose_transcript_validation():
    long_transcript = "x" * 30001
    with pytest.raises(ValueError, match="30000"):
        await generate_repurpose(account_id=1, transcript=long_transcript)

    # Schema Pydantic level validation
    with pytest.raises(ValidationError):
        RepurposeRequest(account_id=1, transcript=long_transcript)


# --- Strategy Mode Resolution Tests ---

@pytest.mark.asyncio
async def test_resolve_strategy_mode_from_approved_campaign():
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq1 = MagicMock()
    mock_eq2 = MagicMock()

    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq1
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.execute.return_value = MagicMock(
        data=[{"strategy_mode": "commercial_campaign", "status": "approved"}]
    )

    with patch("services.content_formats.get_supabase_admin_client", return_value=mock_supabase):
        mode = await resolve_strategy_mode(account_id=42)
        assert mode == "commercial_campaign"


@pytest.mark.asyncio
async def test_resolve_strategy_mode_defaults_to_personal_when_no_active_campaign():
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq1 = MagicMock()
    mock_eq2 = MagicMock()

    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq1
    mock_eq1.eq.return_value = mock_eq2
    # No records found
    mock_eq2.execute.return_value = MagicMock(data=[])

    with patch("services.content_formats.get_supabase_admin_client", return_value=mock_supabase):
        mode = await resolve_strategy_mode(account_id=42)
        assert mode == "personal_storyline"


# --- Revisión (Claude) ---

def test_cache_key_includes_language():
    assert _get_cache_key("reel", 1, "personal_storyline", "Tema", "es") != _get_cache_key(
        "reel", 1, "personal_storyline", "Tema", "en"
    )


@pytest.mark.asyncio
async def test_repurpose_cache_distinguishes_transcripts_with_same_prefix():
    payload = {"reels": [], "carousels": []}
    prefix = "a" * 600
    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(payload)
        await generate_repurpose(account_id=1, transcript=prefix + " final uno", strategy_mode="personal_storyline")
        await generate_repurpose(account_id=1, transcript=prefix + " final dos", strategy_mode="personal_storyline")
        assert mock_gemini.call_count == 2


@pytest.mark.asyncio
async def test_generators_request_json_mode():
    payload = {"frames": [{"index": 1, "role": "warmup", "text": "Hola", "sticker": "poll"}]}
    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(payload)
        await generate_story(account_id=1, topic="Tema", strategy_mode="personal_storyline")
        assert mock_gemini.call_args.kwargs.get("json_mode") is True


def test_repurpose_and_reel_prompts_follow_mode_structure():
    rep_comm = build_repurpose_prompt("texto", "commercial_campaign")
    rep_pers = build_repurpose_prompt("texto", "personal_storyline")
    assert "ESTRATEGIA COMERCIAL" in rep_comm and "ESTRATEGIA PERSONAL" not in rep_comm
    assert "ESTRATEGIA PERSONAL" in rep_pers and "ESTRATEGIA COMERCIAL" not in rep_pers

    reel_comm = build_reel_prompt("Tema", "commercial_campaign")
    assert "Problema → Agitación → Solución → CTA" in reel_comm
    assert "Sin CTA de venta" in build_reel_prompt("Tema", "personal_storyline")


def test_story_prompt_orders_poll_question_dm():
    prompt = build_story_prompt(None, "commercial_campaign")
    assert prompt.index("'poll'") < prompt.index("'question'") < prompt.index("'dm_cta'")


@pytest.mark.asyncio
async def test_story_frames_capped_at_four():
    frames = [{"index": i, "role": "r", "text": f"Frame {i}", "sticker": "none"} for i in range(1, 7)]
    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps({"frames": frames})
        story = await generate_story(account_id=1, topic="Tema", strategy_mode="personal_storyline")
        assert len(story.frames) == 4


@pytest.mark.asyncio
async def test_carousel_warns_when_slide_count_differs():
    payload = {"slides": [{"index": 1, "role": "cover", "text": "Portada"}], "caption": "Caption"}
    with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = json.dumps(payload)
        carousel = await generate_carousel(account_id=1, topic="Tema", slides=6, strategy_mode="personal_storyline")
        assert any("Se pidieron 6" in w for w in carousel.warnings)


# --- Rutas /content/formats/* ---

from fastapi.testclient import TestClient

from auth.dependencies import get_current_user, get_user_supabase_client
from main import app
from models.schemas import User
from tests.conftest import USER_ID, MockSupabaseClient


@pytest.fixture
def formats_client():
    """Usuario autenticado que ve la cuenta 1 por RLS."""
    async def _user():
        return User(id=USER_ID, email="test@example.com")

    previous_user = app.dependency_overrides.get(get_current_user)
    previous_db = app.dependency_overrides.get(get_user_supabase_client)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_user_supabase_client] = lambda: MockSupabaseClient(
        {"instagram_accounts": [{"id": 1}]}
    )
    yield TestClient(app)
    for dep, prev in ((get_current_user, previous_user), (get_user_supabase_client, previous_db)):
        if prev is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = prev


_REEL_PAYLOAD = {
    "hooks": [{"text": "Perdí 3 clientes por no hacer esto", "formula_id": 1}],
    "beats": [{"label": "Problema", "text": "Perdí 3 clientes"}],
    "on_screen_text": ["3 clientes"],
    "caption": "Perdí 3 clientes por no hacer esto #negocio",
}


class TestFormatsRoutes:
    def test_reel_returns_scored_output(self, formats_client):
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = json.dumps(_REEL_PAYLOAD)
            resp = formats_client.post(
                "/content/formats/reel",
                json={"account_id": 1, "topic": "Clientes", "strategy_mode": "commercial_campaign"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["hooks"][0]["score"] > 0
        assert body["report"]["hashtag_count"] == 1

    def test_carousel_rejects_slides_out_of_range(self, formats_client):
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            for slides in (5, 11):
                resp = formats_client.post(
                    "/content/formats/carousel", json={"account_id": 1, "topic": "T", "slides": slides}
                )
                assert resp.status_code == 422
            mock_gemini.assert_not_called()

    def test_repurpose_rejects_long_transcript(self, formats_client):
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            resp = formats_client.post(
                "/content/formats/repurpose", json={"account_id": 1, "transcript": "x" * 30001}
            )
            assert resp.status_code == 422
            mock_gemini.assert_not_called()

    def test_foreign_account_is_404_without_gemini(self, formats_client):
        # RLS no devuelve la cuenta ajena
        app.dependency_overrides[get_user_supabase_client] = lambda: MockSupabaseClient({"instagram_accounts": []})
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            resp = formats_client.post("/content/formats/story", json={"account_id": 99})
            assert resp.status_code == 404
            mock_gemini.assert_not_called()

    def test_invalid_gemini_json_is_502(self, formats_client):
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = "no es json"
            resp = formats_client.post(
                "/content/formats/story", json={"account_id": 1, "strategy_mode": "personal_storyline"}
            )
        assert resp.status_code == 502

    def test_gemini_json_not_matching_schema_is_502(self, formats_client):
        # JSON válido pero un frame sin índice numérico: error de la IA, no del usuario
        bad = {"frames": [{"index": None, "role": "warmup", "text": "Hola", "sticker": "poll"}]}
        with patch("services.content_formats.generate_gemini_content", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = json.dumps(bad)
            resp = formats_client.post(
                "/content/formats/story", json={"account_id": 1, "topic": "Sin índice", "strategy_mode": "personal_storyline"}
            )
        assert resp.status_code == 502

    def test_requires_auth(self):
        previous = app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = TestClient(app).post("/content/formats/reel", json={"account_id": 1, "topic": "T"})
            assert resp.status_code in (401, 403)
        finally:
            if previous is not None:
                app.dependency_overrides[get_current_user] = previous
