"""
Tests for Community & Conversion Endpoints (Fase F).
Covers:
- Zero writes to Instagram Graph API (pure suggestions, read-only GET /comments)
- Fallback to source="unavailable" on Graph API 403 / permission error / missing media id
- 15-minute in-memory caching for live comments
- Manual comment triage (source="manual")
- Prospect comments generation (9 structured types)
- DM funnel generation (delivery message + 2 follow-ups)
- Authentication enforcement (401/403)
- Input validation (422)
"""

import json
import logging
import re

import pytest
import requests
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from auth.dependencies import get_current_user, get_user_supabase_client
from models.schemas import User
from tests.conftest import USER_ID, MockSupabaseClient
from services.content_formats import clear_comments_cache, clear_formats_cache


@pytest.fixture
def auth_client():
    """Client with authenticated user dependency override."""
    async def mock_get_current_user():
        return User(id=USER_ID, email="test@example.com")

    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = mock_get_current_user
    client = TestClient(app)
    yield client
    _restore_override(get_current_user, previous)


@pytest.fixture
def unauth_client():
    """Client without auth override (enforces auth)."""
    previous = app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    _restore_override(get_current_user, previous)


def _restore_override(dep, previous):
    if previous is None:
        app.dependency_overrides.pop(dep, None)
    else:
        app.dependency_overrides[dep] = previous


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure comment and Gemini caches are clean before and after each test."""
    clear_comments_cache()
    clear_formats_cache()
    yield
    clear_comments_cache()
    clear_formats_cache()


def _fake_label(text: str) -> str:
    t = text.lower()
    if "contratar" in t or "comprar" in t:
        return "lead"
    if "caro" in t:
        return "objection"
    if "?" in t:
        return "question"
    if len(t.strip()) < 4:
        return "noise"
    return "support"


def _fake_gemini_response(prompt: str) -> str:
    """Respuesta determinista de Gemini según el tipo de prompt."""
    if "Clasifica los comentarios" in prompt:
        block = prompt.split("COMENTARIOS:\n", 1)[1].split("\n\n", 1)[0]
        items = []
        for line in block.splitlines():
            m = re.match(r"(\d+)\. (.*)", line)
            if m:
                items.append({
                    "index": int(m.group(1)),
                    "label": _fake_label(m.group(2)),
                    "reply": "Gracias por comentar — te leo — siempre",
                })
        return json.dumps({"comments": items})
    if "comentarios con sustancia" in prompt:
        return json.dumps({"suggestions": [
            {"type": i, "text": f"Comentario de tipo {i}"} for i in range(1, 10)
        ]})
    if "palabra clave" in prompt:
        kw = re.search(r'palabra clave "([^"]+)"', prompt).group(1)
        return json.dumps({
            "delivery_dm": f"Gracias por comentar {kw}. Aquí tienes: [ENLACE]. ¿Qué te parece?",
            "follow_ups": ["¿Te sirvió?", "¿Cómo te fue aplicándolo?"],
        })
    raise AssertionError(f"Prompt inesperado: {prompt[:80]}")


@pytest.fixture(autouse=True)
def mock_gemini():
    """Ningún test de Fase F llama a Gemini de verdad."""
    async def fake(prompt, *args, **kwargs):
        return _fake_gemini_response(prompt)

    with patch(
        "services.content_formats.generate_gemini_content", new_callable=AsyncMock, side_effect=fake
    ) as m, patch(
        "services.content_formats.resolve_strategy_mode",
        new_callable=AsyncMock,
        return_value="commercial_campaign",
    ):
        yield m


# ── 1. Authentication ─────────────────────────────────────────────────────────

class TestConversionRoutesAuthentication:
    def test_get_comments_triage_requires_auth(self, unauth_client):
        resp = unauth_client.get("/content/comments/1/triage")
        assert resp.status_code in (401, 403)

    def test_post_comments_triage_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/comments/triage", json={"comments": ["hola"]})
        assert resp.status_code in (401, 403)

    def test_post_prospect_comments_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/prospect-comments", json={"target_post_text": "texto"})
        assert resp.status_code in (401, 403)

    def test_post_dm_funnel_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/dm-funnel", json={"keyword": "GUIA", "resource_description": "PDF"})
        assert resp.status_code in (401, 403)


# ── 2. Validation (422) ───────────────────────────────────────────────────────

class TestConversionRoutesValidation:
    def test_manual_triage_requires_comments_list(self, auth_client):
        resp = auth_client.post("/content/comments/triage", json={})
        assert resp.status_code == 422

    def test_prospect_comments_requires_target_text(self, auth_client):
        resp = auth_client.post("/content/prospect-comments", json={})
        assert resp.status_code == 422

    def test_dm_funnel_requires_keyword_and_resource(self, auth_client):
        # Missing resource_description
        resp = auth_client.post("/content/dm-funnel", json={"keyword": "GUIA"})
        assert resp.status_code == 422

        # Missing keyword
        resp = auth_client.post("/content/dm-funnel", json={"resource_description": "PDF"})
        assert resp.status_code == 422


# ── 3. Zero Writes to Graph API ──────────────────────────────────────────────

class TestZeroWritesToGraphApi:
    """Verifica que ningún endpoint de Fase F ejecute escrituras hacia Graph API."""

    def test_get_triage_never_writes_to_graph_api(self, auth_client):
        sample_post = {
            "id": 1,
            "instagram_account_id": 10,
            "instagram_post_id": "17890000000000",
            "status": "published",
        }
        sample_account = {
            "id": 10,
            "long_lived_access_token": "mock-token",
            "login_type": "facebook",
            "instagram_business_account_id": "17841400000",
        }
        mock_db = MockSupabaseClient({
            "posts": [sample_post],
            "instagram_accounts": [sample_account],
        })

        prev_db = app.dependency_overrides.get(get_user_supabase_client)
        app.dependency_overrides[get_user_supabase_client] = lambda: mock_db

        try:
            with patch("services.instagram_insights.requests.post") as mock_post, \
                 patch("services.instagram_insights.requests.put") as mock_put, \
                 patch("services.instagram_insights.requests.delete") as mock_delete, \
                 patch("services.instagram_insights.requests.patch") as mock_patch, \
                 patch("services.instagram_insights.requests.get") as mock_get:

                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "data": [{"id": "c1", "text": "Excelente post", "username": "user1"}]
                }
                mock_get.return_value.raise_for_status = MagicMock()

                resp = auth_client.get("/content/comments/1/triage")
                assert resp.status_code == 200
                assert resp.json()["source"] == "api"

                # Aserción clave: NINGUNA escritura HTTP hacia Graph API
                mock_post.assert_not_called()
                mock_put.assert_not_called()
                mock_delete.assert_not_called()
                mock_patch.assert_not_called()
        finally:
            _restore_override(get_user_supabase_client, prev_db)

    def test_manual_triage_and_funnel_endpoints_never_call_graph_api(self, auth_client):
        with patch("services.instagram_insights.requests.get") as mock_get, \
             patch("services.instagram_insights.requests.post") as mock_post:

            # 1. Manual triage
            r1 = auth_client.post("/content/comments/triage", json={"comments": ["Hola", "¿Precio?"]})
            assert r1.status_code == 200
            assert r1.json()["source"] == "manual"

            # 2. Prospect comments
            r2 = auth_client.post("/content/prospect-comments", json={"target_post_text": "Estrategias de Growth"})
            assert r2.status_code == 200
            assert len(r2.json()["suggestions"]) == 9

            # 3. DM funnel
            r3 = auth_client.post("/content/dm-funnel", json={"keyword": "SISTEMA", "resource_description": "Guía completa"})
            assert r3.status_code == 200
            assert "delivery_dm" in r3.json()

            # Sin interacción con Graph API
            mock_get.assert_not_called()
            mock_post.assert_not_called()


# ── 4. Fallback on 403 / Unavailable ──────────────────────────────────────────

class TestCommentsTriageFallback:
    def test_fallback_on_graph_api_403_forbidden(self, auth_client):
        """Si la Graph API devuelve 403 (permiso no concedido), el endpoint responde 200 con source='unavailable'."""
        sample_post = {
            "id": 2,
            "instagram_account_id": 10,
            "instagram_post_id": "17890000000001",
            "status": "published",
        }
        sample_account = {
            "id": 10,
            "long_lived_access_token": "mock-token",
            "login_type": "facebook",
            "instagram_business_account_id": "17841400000",
        }
        mock_db = MockSupabaseClient({
            "posts": [sample_post],
            "instagram_accounts": [sample_account],
        })

        prev_db = app.dependency_overrides.get(get_user_supabase_client)
        app.dependency_overrides[get_user_supabase_client] = lambda: mock_db

        try:
            with patch("services.instagram_insights.requests.get") as mock_get:
                # Simular error 403 Forbidden por falta de permisos
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    "403 Client Error: Forbidden for url", response=mock_response
                )

                resp = auth_client.get("/content/comments/2/triage")
                assert resp.status_code == 200
                data = resp.json()
                assert data["source"] == "unavailable"
                assert data["comments"] == []
        finally:
            _restore_override(get_user_supabase_client, prev_db)

    def test_post_without_instagram_post_id_returns_unavailable(self, auth_client):
        """Un post sin instagram_post_id (aún no publicado en IG) devuelve unavailable sin error."""
        sample_post = {
            "id": 3,
            "instagram_account_id": 10,
            "instagram_post_id": None,
            "status": "draft",
        }
        sample_account = {"id": 10}
        mock_db = MockSupabaseClient({
            "posts": [sample_post],
            "instagram_accounts": [sample_account],
        })

        prev_db = app.dependency_overrides.get(get_user_supabase_client)
        app.dependency_overrides[get_user_supabase_client] = lambda: mock_db

        try:
            resp = auth_client.get("/content/comments/3/triage")
            assert resp.status_code == 200
            assert resp.json()["source"] == "unavailable"
        finally:
            _restore_override(get_user_supabase_client, prev_db)


# ── 5. Caching (15 Minutos) ───────────────────────────────────────────────────

class TestCommentsTriageCaching:
    def test_comments_cached_for_15_minutes(self, auth_client):
        """Llamadas sucesivas al mismo post reutilizan la caché de 15 min sin consultar Graph API."""
        sample_post = {
            "id": 4,
            "instagram_account_id": 10,
            "instagram_post_id": "17890000000004",
            "status": "published",
        }
        sample_account = {
            "id": 10,
            "long_lived_access_token": "mock-token",
            "login_type": "facebook",
            "instagram_business_account_id": "17841400000",
        }
        mock_db = MockSupabaseClient({
            "posts": [sample_post],
            "instagram_accounts": [sample_account],
        })

        prev_db = app.dependency_overrides.get(get_user_supabase_client)
        app.dependency_overrides[get_user_supabase_client] = lambda: mock_db

        try:
            with patch("services.instagram_insights.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "data": [{"id": "c100", "text": "Pregunta de prueba?", "username": "tester"}]
                }
                mock_get.return_value.raise_for_status = MagicMock()

                # Primera llamada -> consulta Graph API
                r1 = auth_client.get("/content/comments/4/triage")
                assert r1.status_code == 200
                assert mock_get.call_count == 1

                # Segunda llamada -> hit en caché, no vuelve a consultar Graph API
                r2 = auth_client.get("/content/comments/4/triage")
                assert r2.status_code == 200
                assert mock_get.call_count == 1
                assert r1.json() == r2.json()
        finally:
            _restore_override(get_user_supabase_client, prev_db)


# ── 6. Triaje por Modo y Contenido ────────────────────────────────────────────

class TestCommentsTriageModesAndSuggestions:
    def test_manual_triage_commercial_labels(self, auth_client):
        payload = {
            "comments": [
                "¿Cuánto cuesta el servicio?",
                "Me gustaría contratar la consultoría",
                "Es muy caro para lo que ofrece",
                "¡Brutal post!",
                "ok",
            ],
            "strategy_mode": "commercial_campaign",
        }
        resp = auth_client.post("/content/comments/triage", json=payload)
        assert resp.status_code == 200
        items = resp.json()["comments"]
        assert len(items) == 5

        labels = [it["label"] for it in items]
        assert "question" in labels
        assert "lead" in labels
        assert "objection" in labels
        assert "support" in labels
        assert "noise" in labels

        for item in items:
            assert len(item["suggested_reply"]) > 0

    def test_manual_triage_personal_mode_excludes_commercial_labels(self, auth_client):
        """En modo personal no se usan etiquetas de Lead u Objeción."""
        payload = {
            "comments": [
                "¿Cuánto cuesta el servicio?",
                "Me gustaría comprarlo",
            ],
            "strategy_mode": "personal_storyline",
        }
        resp = auth_client.post("/content/comments/triage", json=payload)
        assert resp.status_code == 200
        items = resp.json()["comments"]
        labels = [it["label"] for it in items]
        assert "lead" not in labels
        assert "objection" not in labels


# ── 7. Prospect Comments y DM Funnel ──────────────────────────────────────────

class TestProspectCommentsAndDmFunnel:
    def test_prospect_comments_provides_9_types(self, auth_client):
        resp = auth_client.post(
            "/content/prospect-comments",
            json={"target_post_text": "Cómo escalar una agencia de marketing B2B"}
        )
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]
        assert len(suggestions) == 9

        types = [s["type"] for s in suggestions]
        assert types == list(range(1, 10))
        for s in suggestions:
            assert len(s["type_name"]) > 0
            assert len(s["text"]) > 0

    def test_dm_funnel_provides_delivery_and_two_follow_ups(self, auth_client):
        resp = auth_client.post(
            "/content/dm-funnel",
            json={"keyword": "PLANTILLA", "resource_description": "Plantilla financiera en Sheets"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "PLANTILLA" in data["delivery_dm"]
        assert len(data["follow_ups"]) == 2


# ── 8. Lógica de triaje y generadores ─────────────────────────────────────────

class TestConversionLogic:
    def test_personal_mode_remaps_commercial_labels_from_gemini(self, auth_client, mock_gemini):
        """Aunque Gemini devuelva lead/objection, en modo personal se convierten en question."""
        resp = auth_client.post("/content/comments/triage", json={
            "comments": ["Quiero contratarlo", "Es caro"],
            "strategy_mode": "personal_storyline",
        })
        assert resp.status_code == 200
        assert [c["label"] for c in resp.json()["comments"]] == ["question", "question"]

    def test_prompt_differs_by_strategy_mode(self, auth_client, mock_gemini):
        auth_client.post("/content/comments/triage", json={
            "comments": ["Hola"], "strategy_mode": "commercial_campaign"})
        auth_client.post("/content/comments/triage", json={
            "comments": ["Hola"], "strategy_mode": "personal_storyline"})
        commercial, personal = (c.args[0] for c in mock_gemini.call_args_list)
        assert "lead:" in commercial and "objection:" in commercial
        assert "lead:" not in personal and "Nada de DM comerciales" in personal

    def test_manual_triage_without_account_defaults_to_personal(self, auth_client, mock_gemini):
        resp = auth_client.post("/content/comments/triage", json={"comments": ["Quiero comprarlo"]})
        assert resp.json()["comments"][0]["label"] == "question"

    def test_suggested_replies_are_humanized(self, auth_client):
        resp = auth_client.post("/content/comments/triage", json={"comments": ["Genial"]})
        assert "—" not in resp.json()["comments"][0]["suggested_reply"]

    def test_triage_is_cached(self, auth_client, mock_gemini):
        payload = {"comments": ["Genial"], "strategy_mode": "commercial_campaign"}
        auth_client.post("/content/comments/triage", json=payload)
        auth_client.post("/content/comments/triage", json=payload)
        assert mock_gemini.call_count == 1

    def test_dm_funnel_invalid_gemini_output_returns_502(self, auth_client, mock_gemini):
        mock_gemini.side_effect = None
        mock_gemini.return_value = json.dumps({"delivery_dm": "Hola", "follow_ups": ["solo uno"]})
        resp = auth_client.post("/content/dm-funnel", json={"keyword": "GUIA", "resource_description": "PDF"})
        assert resp.status_code == 502

    def test_gemini_failure_returns_502(self, auth_client, mock_gemini):
        mock_gemini.side_effect = RuntimeError("quota")
        resp = auth_client.post("/content/prospect-comments", json={"target_post_text": "Texto"})
        assert resp.status_code == 502

    def test_403_does_not_log_access_token(self, auth_client, caplog):
        mock_db = MockSupabaseClient({
            "posts": [{"id": 5, "instagram_account_id": 10, "instagram_post_id": "1789"}],
            "instagram_accounts": [{"id": 10, "long_lived_access_token": "tok", "login_type": "facebook"}],
        })
        prev_db = app.dependency_overrides.get(get_user_supabase_client)
        app.dependency_overrides[get_user_supabase_client] = lambda: mock_db
        try:
            with patch("services.instagram_insights.decrypt_token", return_value="SECRET-TOKEN"), \
                 patch("services.instagram_insights.requests.get") as mock_get, \
                 caplog.at_level(logging.WARNING):
                mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    "403 Client Error for url: https://graph?access_token=SECRET-TOKEN",
                    response=MagicMock(status_code=403),
                )
                resp = auth_client.get("/content/comments/5/triage")
            assert resp.json()["source"] == "unavailable"
            assert "SECRET-TOKEN" not in caplog.text
            assert "HTTP 403" in caplog.text
        finally:
            _restore_override(get_user_supabase_client, prev_db)
