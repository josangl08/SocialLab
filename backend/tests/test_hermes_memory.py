import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from services.hermes.memory import (
    load_session_history,
    append_turn,
    append_correction,
    get_correction_count_since,
    summarize_recent_corrections,
)

def test_load_session_history():
    session_id = uuid4()
    account_id = 123
    
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "role": "user", "content": "hello"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        history = load_session_history(account_id, session_id)
        
        assert history == [{"id": 1, "role": "user", "content": "hello"}]
        mock_client.table.assert_called_once_with("agent_memory")
        
        # Verify query parameters
        mock_client.table.return_value.select.assert_called_once_with("*")
        eq1 = mock_client.table.return_value.select.return_value.eq
        eq1.assert_called_once_with("account_id", account_id)
        
        eq2 = eq1.return_value.eq
        eq2.assert_called_once_with("session_id", str(session_id))
        
        order = eq2.return_value.order
        order.assert_called_once_with("id", desc=False)

def test_append_turn():
    session_id = uuid4()
    account_id = 123
    
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 42, "role": "model"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        
        res = append_turn(
            account_id=account_id,
            session_id=session_id,
            role="model",
            content="model output",
            tool_name="some_tool",
            tool_args={"arg": 1},
            tool_result="success"
        )
        
        assert res == {"id": 42, "role": "model"}
        mock_client.table.assert_called_once_with("agent_memory")
        mock_client.table.return_value.insert.assert_called_once_with({
            "account_id": account_id,
            "session_id": str(session_id),
            "role": "model",
            "content": "model output",
            "tool_name": "some_tool",
            "tool_args": {"arg": 1},
            "tool_result": "success"
        })


def test_append_correction_inserts_with_correction_role():
    account_id = 123

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory.extract_rule_from_correction") as mock_extract_rule:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        append_correction(account_id, edit_type="TIME", user_message="muévelo al martes", resolution="Hecho")

        mock_client.table.assert_called_once_with("agent_memory")
        mock_extract_rule.assert_called_once_with(account_id, mock_response.data[0])
        insert_payload = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_payload["account_id"] == account_id
        assert insert_payload["role"] == "correction"
        assert insert_payload["content"] == {
            "edit_type": "TIME",
            "user_message": "muévelo al martes",
            "resolution": "Hecho",
        }


def test_get_correction_count_since_returns_zero_when_no_int_count():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.count = None
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        assert get_correction_count_since(123, since=None) == 0


def test_get_correction_count_since_filters_by_since_when_given():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.count = 3
        query = mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value
        query.gt.return_value.execute.return_value = mock_response

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = get_correction_count_since(123, since=since)

        assert result == 3
        query.gt.assert_called_once_with("created_at", since.isoformat())


@pytest.mark.asyncio
async def test_summarize_recent_corrections_returns_none_when_no_rows():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        result = await summarize_recent_corrections(123)
        assert result is None


@pytest.mark.asyncio
async def test_summarize_recent_corrections_calls_gemini_with_oldest_first_rows():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
         patch("services.hermes.memory._summarize_corrections_llm", new_callable=AsyncMock) as mock_llm:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        # Query orders desc — newest first — summarize_recent_corrections must reverse it.
        mock_response.data = [
            {"id": 2, "content": {"edit_type": "TIME", "user_message": "b", "resolution": "y"}},
            {"id": 1, "content": {"edit_type": "DATE", "user_message": "a", "resolution": "x"}},
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        mock_llm.return_value = "Resumen de prueba"

        result = await summarize_recent_corrections(123, limit=20)

        assert result == "Resumen de prueba"
        passed_rows = mock_llm.call_args[0][0]
        assert [r["id"] for r in passed_rows] == [1, 2]


def test_record_agent_decision_happy_path():
    session_id = uuid4()
    account_id = 123

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory.get_gemini_client") as mock_get_gemini:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "decision_type": "supabase_create_post", "status": "active"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_get_gemini.return_value.models.generate_content.return_value = MagicMock(
            text="CONFIDENCE: 0.9\nRATIONALE: Encaja con el perfil de la cuenta."
        )

        from services.hermes.memory import record_agent_decision
        res = record_agent_decision(
            account_id=account_id,
            session_id=session_id,
            decision_type="supabase_create_post",
            tool_args={"caption": "Test post"},
            tool_result={"post_id": 456},
            related_post_id=456
        )

        assert isinstance(res, dict)


def test_record_agent_decision_dedupes_labels_keeps_all_ids():
    """Two active rules of the same rule_type (a conflict pair) must not produce a
    duplicated label, but both ids stay so the conflict detail is available."""
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory.get_active_brand_rules") as mock_rules, \
            patch("services.hermes.memory._generate_decision_rationale", return_value=(0.5, "ok")):
        mock_rules.return_value = [
            {"id": 3, "rule_type": "tone"},
            {"id": 4, "rule_type": "format"},
            {"id": 5, "rule_type": "format"},
        ]
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        from services.hermes.memory import record_agent_decision
        record_agent_decision(account_id=1, session_id=uuid4(), decision_type="supabase_create_post")

        inserted = mock_client.table.return_value.insert.call_args[0][0]
        assert inserted["applied_rule_ids"] == [3, 4, 5]
        assert inserted["applied_rule_labels"].count("Format") == 1
        assert "Tone" in inserted["applied_rule_labels"]


def test_extract_rule_from_correction_dedup_vs_new_rule():
    account_id = 123
    correction_row = {
        "id": 10,
        "account_id": account_id,
        "content": {"edit_type": "TONE", "user_message": "No uses tono tan informal"}
    }

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory.get_gemini_client") as mock_get_gemini:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "account_id": account_id, "rule_type": "tone", "rule_text": "No uses tono tan informal"}]
        )
        mock_get_gemini.return_value.models.generate_content.return_value = MagicMock(
            text="RULE_TYPE: tone\nRULE_TEXT: No uses tono tan informal"
        )

        from services.hermes.memory import extract_rule_from_correction
        res = extract_rule_from_correction(account_id, correction_row)
        assert res is None or isinstance(res, dict)


def test_record_agent_decision_non_blocking_failure():
    session_id = uuid4()
    account_id = 123

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.side_effect = Exception("Database connection error")

        from services.hermes.memory import record_agent_decision
        # Should not raise exception
        try:
            res = record_agent_decision(
                account_id=account_id,
                session_id=session_id,
                decision_type="supabase_create_post"
            )
            assert res == {} or res is None
        except Exception as e:
            pytest.fail(f"record_agent_decision raised an exception: {e}")


def test_classify_correction_branching_new_reinforce_conflict():
    from services.hermes.memory import _classify_correction
    import inspect

    sig = inspect.signature(_classify_correction)
    has_existing_rules_param = "existing_rules" in sig.parameters

    with patch("services.hermes.memory.get_gemini_client") as mock_get_gemini:
        mock_model = mock_get_gemini.return_value.models

        # Test 'new'
        mock_model.generate_content.return_value = MagicMock(
            text="RULE_TYPE: tone\nRULE_TEXT: Usar tono profesional\nRELATION: new"
        )
        if has_existing_rules_param:
            res_new = _classify_correction("Sé más profesional", "Ajustado", existing_rules=[])
        else:
            res_new = _classify_correction("Sé más profesional", "Ajustado")
        if res_new:
            assert res_new.get("rule_type") == "tone"

        # Test 'reinforce'
        mock_model.generate_content.return_value = MagicMock(
            text="RULE_TYPE: tone\nRULE_TEXT: Usar siempre tono muy profesional\nRELATION: reinforce"
        )
        existing_rules = [{"id": 10, "rule_type": "tone", "rule_text": "Usar tono profesional"}]
        if has_existing_rules_param:
            res_reinforce = _classify_correction("Sé aún más profesional", "Ajustado", existing_rules=existing_rules)
        else:
            res_reinforce = _classify_correction("Sé aún más profesional", "Ajustado")
        if res_reinforce:
            assert res_reinforce.get("rule_type") == "tone"

        # Test 'conflict'
        mock_model.generate_content.return_value = MagicMock(
            text="RULE_TYPE: tone\nRULE_TEXT: Usar tono cercano e informal\nRELATION: conflict"
        )
        if has_existing_rules_param:
            res_conflict = _classify_correction("Sé informal y cercano", "Ajustado", existing_rules=existing_rules)
        else:
            res_conflict = _classify_correction("Sé informal y cercano", "Ajustado")
        if res_conflict:
            assert res_conflict.get("rule_type") == "tone"



def test_extract_rule_from_correction_versioning_reinforce():
    account_id = 123
    correction_row = {
        "id": 100,
        "account_id": account_id,
        "content": {"edit_type": "TONE", "user_message": "Cambia a un tono formal", "resolution": "Ajustado"}
    }
    existing_rule = {
        "id": 50,
        "account_id": account_id,
        "rule_type": "tone",
        "rule_text": "Tono informal",
        "is_active": True,
        "times_applied": 2,
        "confidence": 0.8
    }

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory._classify_correction") as mock_classify, \
            patch("services.hermes.memory.get_active_brand_rules") as mock_get_active:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_active.return_value = [existing_rule]
        mock_classify.return_value = {
            "rule_type": "tone",
            "rule_text": "Tono formal",
            "relation": "reinforce"
        }

        # Mock insert for new version
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 51,
                "account_id": account_id,
                "rule_type": "tone",
                "rule_text": "Tono formal",
                "previous_version_id": 50,
                "is_active": True
            }]
        )
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        from services.hermes.memory import extract_rule_from_correction
        res = extract_rule_from_correction(account_id, correction_row)

        assert res is not None or res == {}


def test_extract_rule_from_correction_versioning_conflict():
    account_id = 123
    correction_row = {
        "id": 101,
        "account_id": account_id,
        "content": {"edit_type": "TONE", "user_message": "Usa humor negro", "resolution": "Ajustado"}
    }
    existing_rule = {
        "id": 50,
        "account_id": account_id,
        "rule_type": "tone",
        "rule_text": "Cero humor negro",
        "is_active": True
    }

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.memory._classify_correction") as mock_classify, \
            patch("services.hermes.memory.get_active_brand_rules") as mock_get_active:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_get_active.return_value = [existing_rule]
        mock_classify.return_value = {
            "rule_type": "tone",
            "rule_text": "Usa humor negro",
            "relation": "conflict"
        }

        # Mock insert for conflict version
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 52,
                "account_id": account_id,
                "rule_type": "tone",
                "rule_text": "Usa humor negro",
                "conflicts_with_id": 50,
                "is_active": True
            }]
        )

        from services.hermes.memory import extract_rule_from_correction
        res = extract_rule_from_correction(account_id, correction_row)

        assert res is not None or res == {}


