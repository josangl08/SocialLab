import os
import json
import uuid
import logging
import tempfile
from datetime import datetime, date, timedelta, time, timezone
from typing import Optional

import google.generativeai as genai
import httpx

from database.supabase_client import get_supabase_admin_client
from models.schemas import AgentLog, VisualAnalysis, CalendarSlot, ContentProposal

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FREQUENCY_DAYS: dict = {
    "daily":               WEEKDAY_NAMES,
    "few_times_week":      ["Monday", "Tuesday", "Wednesday", "Thursday"],
    "once_or_twice_week":  ["Monday", "Thursday"],
    "weekly":              ["Monday"],
}


def run_agent(account_id: int) -> AgentLog:
    start = datetime.now(timezone.utc)
    supabase = get_supabase_admin_client()
    images_scanned = 0
    images_analyzed = 0
    posts_drafted = 0
    error_msg = None

    try:
        acc_res = supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
        if not acc_res.data:
            raise ValueError(f"Account {account_id} not found")
        account = acc_res.data[0]

        all_files, new_files = _scan_drive(account)
        images_scanned = len(all_files)

        if not new_files:
            logger.info(f"No new files for account {account_id}")
            duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            _write_agent_log(supabase, account_id, images_scanned, 0, 0, None, duration)
            supabase.table('instagram_accounts').update({
                'last_agent_sync': datetime.now(timezone.utc).isoformat()
            }).eq('id', account_id).execute()
            return AgentLog(account_id=str(account_id), images_scanned=images_scanned, duration_ms=duration)

        analyses = _analyze_images(str(account_id), new_files, account)
        images_analyzed = len(analyses)

        if not analyses:
            logger.warning(f"No images analyzed for account {account_id}")
            duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            _write_agent_log(supabase, account_id, images_scanned, 0, 0, None, duration)
            return AgentLog(account_id=str(account_id), images_scanned=images_scanned, duration_ms=duration)

        slots = _build_calendar(analyses, account)
        user_id = str(account.get('user_id', ''))
        best_times = account.get('best_times') or ['12:00']
        if isinstance(best_times, str):
            best_times = json.loads(best_times)
        proposal = _create_drafts(slots, account_id, user_id, best_times)
        posts_drafted = len(proposal.slots)

        chat_id = account.get('telegram_chat_id')
        if chat_id:
            _dispatch_proposal(proposal, str(chat_id))
        else:
            logger.warning(f"No telegram_chat_id for account {account_id} — proposal not sent via Telegram")

        supabase.table('instagram_accounts').update({
            'last_agent_sync': datetime.now(timezone.utc).isoformat()
        }).eq('id', account_id).execute()

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Agent error for account {account_id}: {e}")

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    _write_agent_log(supabase, account_id, images_scanned, images_analyzed, posts_drafted, error_msg, duration)

    return AgentLog(
        account_id=str(account_id),
        images_scanned=images_scanned,
        images_analyzed=images_analyzed,
        posts_drafted=posts_drafted,
        error=error_msg,
        duration_ms=duration
    )


def _scan_drive(account: dict) -> tuple:
    folder_id = account.get('drive_folder_id')
    if not folder_id:
        return [], []

    supabase = get_supabase_client()
    processed_res = (
        supabase.table('visual_analyses')
        .select('drive_file_id')
        .eq('account_id', account['id'])
        .execute()
    )
    processed_ids = {row['drive_file_id'] for row in (processed_res.data or [])}

    from services.google_drive_connector import get_drive_connector
    connector = get_drive_connector()
    all_files = connector.list_generic_resources(folder_id, set())
    new_files = [f for f in all_files if f['id'] not in processed_ids]
    return all_files, new_files


def _build_strategy_context(account: dict) -> str:
    account_type = account.get('account_type', 'personal')
    tone = account.get('default_tone', 'energetic')
    style_guide = account.get('style_guide') or ''
    target_audience = account.get('target_audience') or ''
    hashtag_strategy = account.get('hashtag_strategy', 'minimal')
    hashtag_range = {'minimal': '3-5', 'moderate': '3-5', 'maximum': '3-5'}.get(hashtag_strategy, '3-5')

    if account_type == 'professional':
        return (
            f"Voz de marca de tono {tone}, semiformal, emojis mínimos (0-1). "
            f"Empieza con el beneficio principal o propuesta de valor. "
            f"CTA de conversión al final ('Contáctanos', 'Reserva ahora', 'Link en bio'). "
            f"Incluye keywords SEO relevantes (Instagram indexado por Google desde 2025). "
            f"Usa {hashtag_range} hashtags industry-specific o branded. "
            f"Guía de estilo: {style_guide or 'profesional y directo'}."
        )
    else:
        return (
            f"Voz en primera persona, tono {tone}, emojis moderados. "
            f"Cuenta una historia auténtica o comparte un momento real. "
            f"Termina con una pregunta que invite a comentar ('¿Qué opinas?', '¡Cuéntame!'). "
            f"Incluye keywords naturales para discoverability. "
            f"Audiencia: {target_audience or 'comunidad general'}. "
            f"Usa {hashtag_range} hashtags de nicho + community + trending. "
            f"Guía de estilo: {style_guide or 'cercano e inspirador'}."
        )


def _analyze_images(account_id: str, files: list, account: dict = None) -> list:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not configured")
        return []

    genai.configure(api_key=api_key)
    supabase = get_supabase_client()

    from services.google_drive_connector import get_drive_connector
    connector = get_drive_connector()

    strategy_context = _build_strategy_context(account) if account else (
        "Voz natural, primera persona, tono inspirador, emojis moderados. "
        "Termina con una pregunta de engagement. Usa 3-5 hashtags relevantes."
    )

    vision_prompt = f"""Analiza detalladamente esta imagen. Retorna SOLO un objeto JSON con esta estructura exacta:
{{
  "objects": ["lista de objetos o personas principales"],
  "text_visible": "texto visible en la imagen o cadena vacía",
  "mood": "uno de: energetic, calm, professional, fun, inspiring, nostalgic",
  "theme": "tema principal en 2-3 palabras",
  "raw_description": "descripción detallada en 2-3 frases",
  "suggested_caption": "caption para Instagram siguiendo estas instrucciones: {strategy_context}"
}}"""

    analyses = []
    for f in files:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f"_{f['name']}", delete=False) as tmp:
                tmp_path = tmp.name

            if not connector.download_file(f['id'], tmp_path):
                logger.warning(f"Could not download Drive file {f['id']}")
                continue

            uploaded = genai.upload_file(tmp_path, mime_type=f.get('mimeType', 'image/jpeg'))
            os.unlink(tmp_path)
            tmp_path = None

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([uploaded, vision_prompt])

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            description = json.loads(text)

            suggested_caption = description.pop('suggested_caption', None)

            insert_res = supabase.table('visual_analyses').insert({
                'account_id': int(account_id),
                'drive_file_id': f['id'],
                'file_name': f['name'],
                'gemini_description': description,
                'suggested_caption': suggested_caption
            }).execute()

            if insert_res.data:
                analyses.append(VisualAnalysis(
                    drive_file_id=f['id'],
                    gemini_description=description,
                    suggested_caption=suggested_caption
                ))
        except Exception as e:
            logger.error(f"Error analyzing file {f.get('id')}: {e}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    return analyses


def _build_calendar(analyses: list, account: dict) -> list:
    freq = account.get('posting_frequency', 'few_times_week')
    available_days = list(FREQUENCY_DAYS.get(freq, FREQUENCY_DAYS['few_times_week']))

    # Build content type sequence from mix (personal=reel-heavy, professional=carousel-heavy)
    raw_mix = account.get('content_type_mix') or {}
    account_type = account.get('account_type', 'personal')
    if not any(v > 0 for v in raw_mix.values() if isinstance(v, int)):
        raw_mix = (
            {'reel': 3, 'carousel': 2, 'post': 1, 'story': 2}
            if account_type != 'professional'
            else {'carousel': 2, 'post': 2, 'reel': 1, 'story': 1}
        )

    type_sequence = []
    for ptype in ['reel', 'carousel', 'post', 'story']:
        type_sequence.extend([ptype] * int(raw_mix.get(ptype, 0)))
    if not type_sequence:
        type_sequence = ['post']

    slots = []
    for i, analysis in enumerate(analyses[:len(available_days)]):
        theme = analysis.gemini_description.get('theme', 'content')
        caption = analysis.suggested_caption or analysis.gemini_description.get('raw_description', '')
        slots.append(CalendarSlot(
            day=available_days[i],
            image_id=analysis.drive_file_id,
            theme=theme,
            caption=caption,
            post_type=type_sequence[i % len(type_sequence)]
        ))
    return slots


def _create_drafts(slots: list, account_id: int, user_id: str, best_times: list = None) -> ContentProposal:
    supabase = get_supabase_client()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    times = best_times if best_times else ['12:00']

    updated_slots = []
    for i, slot in enumerate(slots):
        day_offset = WEEKDAY_NAMES.index(slot.day) if slot.day in WEEKDAY_NAMES else 0
        raw_time = times[i % len(times)]
        h, m = map(int, raw_time.split(':'))
        scheduled_at = datetime.combine(
            week_start + timedelta(days=day_offset),
            time(h, m),
            tzinfo=timezone.utc
        )
        insert_res = supabase.table('posts').insert({
            'user_id': user_id,
            'content': slot.caption,
            'instagram_account_id': account_id,
            'status': 'draft',
            'is_ai_generated': True,
            'scheduled_at': scheduled_at.isoformat()
        }).execute()

        post_id = insert_res.data[0]['id'] if insert_res.data else None
        updated_slots.append(CalendarSlot(
            day=slot.day,
            post_id=post_id,
            image_id=slot.image_id,
            theme=slot.theme,
            caption=slot.caption,
            post_type=slot.post_type
        ))

    slots_json = [s.model_dump() for s in updated_slots]
    proposal_res = supabase.table('content_proposals').insert({
        'account_id': account_id,
        'week_start': week_start.isoformat(),
        'slots': slots_json,
        'status': 'pending_approval'
    }).execute()

    proposal_id = proposal_res.data[0]['id'] if proposal_res.data else str(uuid.uuid4())

    return ContentProposal(
        id=str(proposal_id),
        account_id=str(account_id),
        week_start=week_start.isoformat(),
        slots=updated_slots,
        status='pending_approval'
    )


def _dispatch_proposal(proposal: ContentProposal, chat_id: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return

    slots_lines = "\n".join(
        f"• {slot.day}: {slot.theme} — {slot.caption[:60]}{'...' if len(slot.caption) > 60 else ''}"
        for slot in proposal.slots
    )
    text = (
        f"📅 *Propuesta de contenido semanal*\n\n"
        f"Semana del {proposal.week_start}:\n\n"
        f"{slots_lines}\n\n"
        f"¿Apruebas este calendario?"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "Aprobar Calendario ✅", "callback_data": f"proposal:approve:{proposal.id}"},
            {"text": "Rechazar ❌", "callback_data": f"proposal:reject:{proposal.id}"}
        ]]
    }

    with httpx.Client() as client:
        try:
            client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard},
                timeout=10.0
            )
        except Exception as e:
            logger.error(f"Error dispatching proposal to Telegram: {e}")


def _write_agent_log(
    supabase,
    account_id: int,
    images_scanned: int,
    images_analyzed: int,
    posts_drafted: int,
    error: Optional[str],
    duration_ms: int
) -> None:
    try:
        supabase.table('agent_logs').insert({
            'account_id': account_id,
            'images_scanned': images_scanned,
            'images_analyzed': images_analyzed,
            'posts_drafted': posts_drafted,
            'error': error,
            'duration_ms': duration_ms
        }).execute()
    except Exception as e:
        logger.error(f"Failed to write agent log: {e}")
