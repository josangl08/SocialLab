import asyncio
import os
import re
import json
import uuid
import logging
import tempfile
from datetime import datetime, date, timedelta, time, timezone
from typing import Optional

from services.gemini_service import generate_gemini_content, clean_and_parse_json, analyze_image_vision

from database.supabase_client import get_supabase_admin_client
from models.schemas import AgentLog, VisualAnalysis, CalendarSlot, ContentProposal
from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FREQUENCY_DAYS: dict = {
    "daily":               WEEKDAY_NAMES,
    "few_times_week":      ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "once_or_twice_week":  ["Monday", "Thursday"],
    "weekly":              ["Monday"],
}

FREQ_RANGE: dict = {
    "daily":              (7, 7),
    "few_times_week":     (3, 5),
    "once_or_twice_week": (1, 2),
    "weekly":             (1, 1),
}


def _ai_schedule(analyses: list, account: dict, min_posts: int, max_posts: int, campaign_context: str = '') -> Optional[list]:
    """Ask Gemini to choose which days and post types to use. Returns list of CalendarSlot or None."""
    api_key = GOOGLE_API_KEY
    if not api_key:
        return None

    account_type = account.get('account_type', 'personal')
    audience = account.get('target_audience', 'audiencia general')
    tone = account.get('default_tone', 'auténtico')
    preferred_days = account.get('preferred_days') or []
    preferred_hint = f"Días preferidos por la cuenta: {', '.join(preferred_days)}." if preferred_days else ""

    posts_per_week = account.get('posts_per_week')
    posts_per_week_val = None
    if posts_per_week is not None:
        try:
            val = int(posts_per_week)
            if min_posts <= val <= max_posts:
                posts_per_week_val = val
        except (ValueError, TypeError):
            pass

    if posts_per_week_val is not None:
        target_str = f"exactamente {posts_per_week_val}"
        posts_per_week_hint = f"Publicaciones por semana objetivo: {posts_per_week_val}."
    else:
        target_str = f"entre {min_posts} y {max_posts}"
        posts_per_week_hint = ""

    scheduling_mode = account.get('scheduling_mode')
    if scheduling_mode == 'fixed':
        scheduling_hint = "Modo de programación: fijo (mantén una cadencia y días consistentes cada semana)."
        scheduling_inst = "- Mantén los días y el horario con una cadencia fija y consistente semana a semana."
    elif scheduling_mode == 'flexible':
        scheduling_hint = "Modo de programación: flexible (adapta los días según el contenido y el rendimiento esperado)."
        scheduling_inst = "- Adapta la distribución de días de forma flexible según el contenido y rendimiento esperado."
    else:
        scheduling_hint = ""
        scheduling_inst = ""

    raw_mix = account.get('content_type_mix') or {}
    if not any(isinstance(v, int) and v > 0 for v in raw_mix.values()):
        raw_mix = (
            {'reel': 3, 'carousel': 2, 'post': 1, 'story': 2}
            if account_type != 'professional'
            else {'carousel': 2, 'post': 2, 'reel': 1, 'story': 1}
        )
    mix_desc = ', '.join(f"{k}: {v}" for k, v in raw_mix.items() if isinstance(v, int) and v > 0)

    image_list = []
    for i, a in enumerate(analyses):
        desc = a.gemini_description
        theme = desc.get('theme', 'contenido visual') if isinstance(desc, dict) else str(desc)
        image_list.append(f"  {i}. {theme}")

    freq_text = {
        "daily": "todos los días (7 posts)",
        "few_times_week": f"{min_posts} a {max_posts} veces por semana",
        "once_or_twice_week": f"{min_posts} a {max_posts} veces por semana",
        "weekly": "una vez por semana",
    }.get(account.get('posting_frequency', 'few_times_week'), f"{min_posts} a {max_posts} veces por semana")

    profile_hints = []
    if preferred_hint:
        profile_hints.append(preferred_hint)
    if posts_per_week_hint:
        profile_hints.append(posts_per_week_hint)
    if scheduling_hint:
        profile_hints.append(scheduling_hint)
    if campaign_context:
        profile_hints.append(campaign_context)

    extra_profile = ("\n" + "\n".join(profile_hints)) if profile_hints else ""

    instructions = [
        f"- Elige {target_str} imágenes",
        "- Asigna un día distinto de la semana a cada una",
        "- Asigna el post_type más adecuado: reel, carousel, post, o story",
        "- Reels rinden mejor martes, miércoles o jueves",
        "- Carousels rinden mejor lunes o miércoles",
        "- Stories funcionan cualquier día",
        "- No repitas días"
    ]
    if scheduling_inst:
        instructions.append(scheduling_inst)
    instructions_text = "\n".join(instructions)

    prompt = f"""Eres un social media planner experto en Instagram. Crea un calendario semanal.

PERFIL DE CUENTA:
- Tipo: {account_type}
- Audiencia: {audience}
- Tono: {tone}
- Frecuencia: {freq_text}
- Mix preferido: {mix_desc}{extra_profile}

IMÁGENES DISPONIBLES ({len(analyses)} total):
{chr(10).join(image_list)}

INSTRUCCIONES:
{instructions_text}

Responde SOLO con JSON válido, sin explicaciones ni bloques markdown:
{{"slots": [{{"day": "Tuesday", "image_index": 0, "post_type": "reel"}}]}}"""

    try:
        async def _run_ai_schedule():
            raw = await generate_gemini_content(prompt)
            return await clean_and_parse_json(raw)

        data = asyncio.run(_run_ai_schedule())

        slots = []
        seen_days: set = set()
        for s in data.get('slots', []):
            day = s.get('day', '')
            idx = s.get('image_index', 0)
            post_type = s.get('post_type', 'post')
            if day not in WEEKDAY_NAMES or day in seen_days or idx >= len(analyses):
                continue
            seen_days.add(day)
            a = analyses[idx]
            desc = a.gemini_description
            theme = desc.get('theme', 'content') if isinstance(desc, dict) else str(desc)
            caption = a.suggested_caption or (desc.get('raw_description', '') if isinstance(desc, dict) else '')
            slots.append(CalendarSlot(
                day=day, image_id=a.drive_file_id,
                theme=theme, caption=caption, post_type=post_type,
            ))

        if slots:
            logger.info(f"[Agent] AI-scheduled {len(slots)} slots: {[s.day for s in slots]}")
            return slots
        raw_count = len(data.get('slots', []))
        logger.warning(f"[Agent] Gemini returned 0 valid slots (raw had {raw_count}), using fallback")
        return None
    except Exception as e:
        logger.warning(f"[Agent] AI calendar scheduling failed, using fallback: {e}")
        return None


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
        logger.info(f"[Agent] Started — account_id={account_id}, username={account.get('username', 'unknown')}")

        user_id = str(account.get('user_id', ''))
        week_start = _get_next_unplanned_week(account_id, supabase)
        campaign_res = supabase.table('monthly_campaigns').select('*') \
            .eq('account_id', account_id) \
            .eq('month_date', week_start.replace(day=1).isoformat()) \
            .execute()
        campaign_row = campaign_res.data[0] if campaign_res.data else None
        campaign_context = _build_campaign_context(campaign_row, week_start)

        all_files, new_files = _scan_drive(account, user_id)
        images_scanned = len(all_files)
        logger.info(f"[Agent] Drive scan complete — total_files={images_scanned}, new_files={len(new_files)}")

        if not all_files:
            logger.info(f"[Agent] Early exit — Drive folder is empty for account_id={account_id}")
            duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            _write_agent_log(supabase, account_id, images_scanned, 0, 0, None, duration)
            supabase.table('instagram_accounts').update({
                'last_agent_sync': datetime.now(timezone.utc).isoformat()
            }).eq('id', account_id).execute()
            return AgentLog(account_id=str(account_id), images_scanned=images_scanned, duration_ms=duration)

        # Load cached analyses for already-processed files
        new_file_ids = {f['id'] for f in new_files}
        already_analyzed_ids = {f['id'] for f in all_files} - new_file_ids
        cached_analyses: list = []
        if already_analyzed_ids:
            cached_res = supabase.table('visual_analyses').select(
                'drive_file_id, gemini_description, suggested_caption'
            ).eq('account_id', account_id).execute()
            cached_analyses = [
                VisualAnalysis(
                    drive_file_id=r['drive_file_id'],
                    gemini_description=r['gemini_description'],
                    suggested_caption=r['suggested_caption']
                )
                for r in (cached_res.data or [])
                if r['drive_file_id'] in already_analyzed_ids
            ]
            logger.info(f"[Agent] Loaded {len(cached_analyses)} cached analyses")

        new_analyses: list = []
        if new_files:
            logger.info(f"[Agent] Analyzing {len(new_files)} new images for account_id={account_id}...")
            new_analyses = _analyze_images(str(account_id), new_files, account, user_id, campaign_context)
            logger.info(f"[Agent] Image analysis complete — analyzed={len(new_analyses)} of {len(new_files)}")

        analyses = cached_analyses + new_analyses
        images_analyzed = len(analyses)

        if not analyses:
            logger.warning(f"No images analyzed for account {account_id}")
            duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            _write_agent_log(supabase, account_id, images_scanned, 0, 0, None, duration)
            return AgentLog(account_id=str(account_id), images_scanned=images_scanned, duration_ms=duration)

        # Exclude images already pending in other proposals for this account
        used_res = supabase.table('content_proposals')\
            .select('slots').eq('account_id', account_id).eq('status', 'pending_approval').execute()
        used_ids = {
            s.get('image_id')
            for row in (used_res.data or [])
            for s in (row.get('slots') or [])
            if s.get('image_id')
        }
        available_analyses = [a for a in analyses if a.drive_file_id not in used_ids] or analyses
        if len(available_analyses) < len(analyses):
            logger.info(f"[Agent] Excluded {len(analyses) - len(available_analyses)} already-pending images")

        slots = _build_calendar(available_analyses, account, campaign_context)
        logger.info(f"[Agent] Calendar slots built — count={len(slots)}")
        best_times = account.get('best_times') or ['12:00']
        if isinstance(best_times, str):
            best_times = json.loads(best_times)
        proposal = _create_drafts(slots, account_id, user_id, best_times, week_start)
        posts_drafted = len(proposal.slots)
        logger.info(f"[Agent] Proposal created — id={proposal.id}, week_start={proposal.week_start}, slots={posts_drafted}")

        logger.info(f"[Agent] Preparing Telegram dispatch for account_id={account_id}...")
        chat_id = account.get('telegram_chat_id')
        if chat_id:
            try:
                from services.telegram_service import TelegramService
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        TelegramService().send_proposal_card(str(chat_id), proposal.id, proposal.slots, user_id)
                    )
                finally:
                    loop.close()
                logger.info(f"[Agent] Telegram dispatch succeeded — chat_id={chat_id}")
            except Exception as te:
                logger.error(f"Telegram dispatch failed for account {account_id}: {te}")
        else:
            logger.warning(f"No telegram_chat_id for account {account_id} — proposal not sent via Telegram")

        supabase.table('instagram_accounts').update({
            'last_agent_sync': datetime.now(timezone.utc).isoformat()
        }).eq('id', account_id).execute()

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Agent error for account {account_id}: {e}")

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    logger.info(f"[Agent] Complete — account_id={account_id}, images_scanned={images_scanned}, posts_drafted={posts_drafted}, duration_ms={duration}")
    _write_agent_log(supabase, account_id, images_scanned, images_analyzed, posts_drafted, error_msg, duration)

    return AgentLog(
        account_id=str(account_id),
        images_scanned=images_scanned,
        images_analyzed=images_analyzed,
        posts_drafted=posts_drafted,
        error=error_msg,
        duration_ms=duration
    )


def _scan_drive(account: dict, user_id: str) -> tuple:
    folder_id = account.get('drive_folder_id')
    if not folder_id:
        return [], []

    supabase = get_supabase_admin_client()
    processed_res = (
        supabase.table('visual_analyses')
        .select('drive_file_id')
        .eq('account_id', account['id'])
        .execute()
    )
    processed_ids = {row['drive_file_id'] for row in (processed_res.data or [])}

    from services.google_drive_connector import get_drive_connector
    connector = get_drive_connector(user_id)
    all_files = connector.list_generic_resources(folder_id, set())
    new_files = [f for f in all_files if f['id'] not in processed_ids]
    return all_files, new_files


def _build_strategy_context(account: dict, campaign_context: str = '') -> str:
    account_type = account.get('account_type', 'personal')
    tone = account.get('default_tone', 'energetic')
    style_guide = account.get('style_guide') or ''
    target_audience = account.get('target_audience') or ''
    hashtag_strategy = account.get('hashtag_strategy', 'minimal')
    hashtag_range = {'minimal': '1-3', 'moderate': '4-7', 'maximum': '8-12'}.get(hashtag_strategy, '1-3')

    sector = account.get('sector') or ''
    purpose = account.get('purpose') or ''

    pillars_raw = account.get('content_pillars') or []
    if isinstance(pillars_raw, list):
        content_pillars = ', '.join(str(p) for p in pillars_raw if p)
    else:
        content_pillars = str(pillars_raw).strip()

    ref_raw = account.get('reference_accounts') or []
    if isinstance(ref_raw, list):
        reference_accounts = ', '.join(str(r) for r in ref_raw if r)
    else:
        reference_accounts = str(ref_raw).strip()

    if account_type == 'professional':
        base = (
            f"Voz de marca de tono {tone}, semiformal, emojis mínimos (0-1). "
            f"Empieza con el beneficio principal o propuesta de valor. "
            f"CTA de conversión al final ('Contáctanos', 'Reserva ahora', 'Link en bio'). "
            f"Incluye keywords SEO relevantes (Instagram indexado por Google desde 2025). "
            f"Usa {hashtag_range} hashtags industry-specific o branded. "
            f"Guía de estilo: {style_guide or 'profesional y directo'}."
        )
    else:
        base = (
            f"Voz en primera persona, tono {tone}, emojis moderados. "
            f"Cuenta una historia auténtica o comparte un momento real. "
            f"Termina con una pregunta que invite a comentar ('¿Qué opinas?', '¡Cuéntame!'). "
            f"Incluye keywords naturales para discoverability. "
            f"Audiencia: {target_audience or 'comunidad general'}. "
            f"Usa {hashtag_range} hashtags de nicho + community + trending. "
            f"Guía de estilo: {style_guide or 'cercano e inspirador'}."
        )

    extra_parts = []
    if sector:
        extra_parts.append(f"Sector: {sector}.")
    if purpose:
        extra_parts.append(f"Objetivo: {purpose}.")
    if content_pillars:
        extra_parts.append(f"Pilares de contenido: {content_pillars}.")
    if reference_accounts:
        extra_parts.append(f"Cuentas de referencia: {reference_accounts}.")

    if extra_parts:
        base = f"{base} {' '.join(extra_parts)}"

    return f"{base} {campaign_context}" if campaign_context else base


def _build_campaign_context(campaign: Optional[dict], week_start: date) -> str:
    """Turn a monthly_campaigns row into a prompt fragment describing this week's
    narrative/commercial focus and any milestone landing in this week. Returns ''
    when there's no campaign configured, so behavior is unchanged (see design.md
    §Architecture Decisions #3 — this is prompt context, not a new code branch)."""
    if not campaign:
        return ''

    week_of_month = min(((week_start.day - 1) // 7) + 1, 4)
    focus = (campaign.get('weekly_focus') or {}).get(str(week_of_month), '').strip()

    week_end = week_start + timedelta(days=6)
    milestones_in_range = [
        m for m in (campaign.get('milestones') or [])
        if m.get('date') and week_start.isoformat() <= m['date'] <= week_end.isoformat()
    ]

    if not focus and not milestones_in_range:
        return ''

    strategy_mode = campaign.get('strategy_mode', 'personal_storyline')
    title = campaign.get('title', '')

    if strategy_mode == 'commercial_campaign':
        parts = [f"ENFOQUE DE CAMPAÑA DEL MES: '{title}' (campaña comercial)."]
        if focus:
            parts.append(f"Foco de esta semana: {focus}. Alinea el lenguaje y las CTAs con este objetivo del embudo.")
    else:
        parts = [f"HILO NARRATIVO DEL MES: '{title}' (historia personal)."]
        if focus:
            parts.append(f"Esta semana el hilo se centra en: {focus}. Continúa la narrativa en primera persona.")

    if milestones_in_range:
        events = '; '.join(f"{m['date']}: {m['event']}" for m in milestones_in_range)
        parts.append(f"Hitos de esta semana ({events}) — asegúrate de que al menos un post los mencione explícitamente.")

    return ' '.join(parts)


def _analyze_images(account_id: str, files: list, account: dict = None, user_id: str = '', campaign_context: str = '') -> list:
    logger.info(f"_analyze_images: starting for account {account_id} with {len(files)} files")
    api_key = GOOGLE_API_KEY
    if not api_key:
        logger.error("GOOGLE_API_KEY not configured")
        return []

    supabase = get_supabase_admin_client()

    from services.google_drive_connector import get_drive_connector
    connector = get_drive_connector(user_id)

    strategy_context = _build_strategy_context(account, campaign_context) if account else (
        "Voz natural, primera persona, tono inspirador, emojis moderados. "
        "Termina con una pregunta de engagement. Usa 3-5 hashtags relevantes."
    )

    analyses = []
    for f in files:
        tmp_path = None
        try:
            logger.info(f"Processing file: {f['name']} ({f['id']})")
            with tempfile.NamedTemporaryFile(suffix=f"_{f['name']}", delete=False) as tmp:
                tmp_path = tmp.name

            if not connector.download_file(f['id'], tmp_path):
                logger.warning(f"Could not download Drive file {f['id']}")
                continue

            description = asyncio.run(analyze_image_vision(
                image_path=tmp_path,
                mime_type=f.get('mimeType', 'image/jpeg'),
                strategy_context=strategy_context
            ))
            os.unlink(tmp_path)
            tmp_path = None

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


def _build_calendar(analyses: list, account: dict, campaign_context: str = '') -> list:
    freq = account.get('posting_frequency', 'few_times_week')
    min_posts, max_posts = FREQ_RANGE.get(freq, (3, 5))

    # Try AI scheduling first
    ai_slots = _ai_schedule(analyses, account, min_posts, max_posts, campaign_context)
    if ai_slots:
        return ai_slots

    # Fallback: hardcoded day list + round-robin content type sequence
    available_days = list(FREQUENCY_DAYS.get(freq, FREQUENCY_DAYS['few_times_week']))

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
        desc = analysis.gemini_description
        theme = desc.get('theme', 'content') if isinstance(desc, dict) else str(desc)
        caption = analysis.suggested_caption or (desc.get('raw_description', '') if isinstance(desc, dict) else '')
        slots.append(CalendarSlot(
            day=available_days[i],
            image_id=analysis.drive_file_id,
            theme=theme,
            caption=caption,
            post_type=type_sequence[i % len(type_sequence)]
        ))
    return slots


def _get_next_unplanned_week(account_id: int, supabase) -> date:
    today = date.today()
    days_to_next_monday = 7 - today.weekday()  # Always ≥1: never current week
    candidate = today + timedelta(days=days_to_next_monday)
    existing = {
        r['week_start']
        for r in (supabase.table('content_proposals')
                 .select('week_start').eq('account_id', account_id).neq('status', 'rejected').execute().data or [])
    }
    while candidate.isoformat() in existing:
        candidate += timedelta(weeks=1)
    return candidate


def _create_drafts(slots: list, account_id: int, user_id: str, best_times: list = None, week_start: date = None) -> ContentProposal:
    supabase = get_supabase_admin_client()
    if week_start is None:
        week_start = _get_next_unplanned_week(account_id, supabase)
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
            'drive_file_id': slot.image_id,
            'post_type': slot.post_type,
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
