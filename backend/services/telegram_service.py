import asyncio
import json
import os
import re
import logging
import tempfile
from datetime import datetime, timezone
from typing import Optional
import httpx

from services.gemini_service import regenerate_slot_caption
from services.hermes.orchestrator import run_edit_session

from database.supabase_client import get_supabase_admin_client
from models.schemas import TelegramMessage, TelegramCallbackQuery
from utils.timezones import effective_timezone, local_to_utc, to_local, zone_label
from services.scheduler.post_scheduler import PostScheduler
import config
from services.post_media import (
    FEED_FORMATS, STORAGE_BUCKET, feed_crop_target, image_extension, image_size, prepare_image_for_instagram
)

# Lado mayor de la vista previa enviada a Telegram (es lo máximo que muestra)
TELEGRAM_PHOTO_MAX_SIDE = 2560
# Bot API: sendDocument sube archivos de hasta 50 MB
TELEGRAM_DOCUMENT_MAX_BYTES = 50 * 1024 * 1024

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Etiquetas en español para los eventos de progreso de run_edit_session — nombre de
# tool MCP -> gerundio corto mostrado en el mensaje editado progresivamente.
_PROGRESS_LABELS = {
    "drive_list_files": "Buscando imágenes en Drive",
    "supabase_update_post_image": "Actualizando la imagen",
    "supabase_update_post_schedule": "Actualizando la fecha/hora",
    "supabase_update_campaign_focus": "Actualizando el enfoque semanal",
    "supabase_update_campaign_milestones": "Actualizando los hitos",
    "supabase_update_campaign_details": "Actualizando el título/descripción",
}

# Margen defensivo entre ediciones de un mismo mensaje — Telegram no publica un
# límite oficial para editMessageText repetido, pero HERMES_EDIT_MAX_TURNS acota
# esto a un puñado de eventos por sesión de todos modos.
_PROGRESS_EDIT_MIN_INTERVAL = 0.7


class TelegramService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TelegramService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def _bot_url(self, method: str) -> str:
        token = config.TELEGRAM_BOT_TOKEN
        return f"{TELEGRAM_API_BASE}{token}/{method}"

    async def register_webhook(self, base_url: Optional[str]) -> None:
        if not base_url:
            logger.info("TELEGRAM_WEBHOOK_URL not set — skipping webhook registration")
            return
        token = config.TELEGRAM_BOT_TOKEN
        webhook_url = f"{base_url}/api/telegram/webhook/{token}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._bot_url("setWebhook"), json={"url": webhook_url})
            if resp.status_code == 200 and resp.json().get("ok"):
                sanitized_url = f"{base_url}/api/telegram/webhook/<REDACTED>" if token else webhook_url
                logger.info(f"Telegram webhook registered: {sanitized_url}")
            else:
                error_detail = resp.text.replace(token, "<REDACTED>") if token else resp.text
                logger.error(f"Failed to register Telegram webhook: {error_detail}")

    async def _chat_owns_account(self, account_id: str, chat_id: str) -> bool:
        if not account_id or not chat_id:
            return False
        try:
            supabase = get_supabase_admin_client()
            acc_res = supabase.table('instagram_accounts')\
                .select('telegram_chat_id').eq('id', account_id).execute()
            if not acc_res.data:
                return False
            db_chat_id = acc_res.data[0].get('telegram_chat_id')
            if db_chat_id is None:
                return False
            return str(db_chat_id) == str(chat_id)
        except Exception as e:
            logger.error(f"Error checking chat ownership of account {account_id}: {e}")
            return False

    async def _verify_post_owner(self, post_id: int, chat_id: str) -> bool:
        if not post_id or not chat_id:
            return False
        try:
            supabase = get_supabase_admin_client()
            post_res = supabase.table('posts')\
                .select('instagram_account_id').eq('id', post_id).execute()
            if not post_res.data:
                logger.warning(f"Post {post_id} not found when verifying owner")
                return False
            account_id = post_res.data[0].get('instagram_account_id')
            if not account_id:
                logger.warning(f"Post {post_id} has no instagram_account_id")
                return False
            
            is_owner = await self._chat_owns_account(account_id, chat_id)
            if not is_owner:
                logger.warning(f"Unauthorized access attempt: chat {chat_id} does not own post {post_id} (account {account_id})")
            return is_owner
        except Exception as e:
            logger.error(f"Error verifying post owner for post {post_id}: {e}")
            return False

    async def _verify_campaign_owner(self, campaign_id: str, chat_id: str) -> bool:
        if not campaign_id or not chat_id:
            return False
        try:
            supabase = get_supabase_admin_client()
            camp_res = supabase.table('monthly_campaigns')\
                .select('account_id').eq('id', campaign_id).execute()
            if not camp_res.data:
                logger.warning(f"Campaign {campaign_id} not found when verifying owner")
                return False
            account_id = camp_res.data[0].get('account_id')
            if not account_id:
                logger.warning(f"Campaign {campaign_id} has no account_id")
                return False

            is_owner = await self._chat_owns_account(account_id, chat_id)
            if not is_owner:
                logger.warning(f"Unauthorized access attempt: chat {chat_id} does not own campaign {campaign_id} (account {account_id})")
            return is_owner
        except Exception as e:
            logger.error(f"Error verifying campaign owner for campaign {campaign_id}: {e}")
            return False

    async def _verify_proposal_owner(self, proposal_id: str, chat_id: str) -> bool:
        if not proposal_id or not chat_id:
            return False
        try:
            supabase = get_supabase_admin_client()
            prop_res = supabase.table('content_proposals')\
                .select('account_id').eq('id', proposal_id).execute()
            if not prop_res.data:
                logger.warning(f"Proposal {proposal_id} not found when verifying owner")
                return False
            account_id = prop_res.data[0].get('account_id')
            if not account_id:
                logger.warning(f"Proposal {proposal_id} has no account_id")
                return False
            
            is_owner = await self._chat_owns_account(account_id, chat_id)
            if not is_owner:
                logger.warning(f"Unauthorized access attempt: chat {chat_id} does not own proposal {proposal_id} (account {account_id})")
            return is_owner
        except Exception as e:
            logger.error(f"Error verifying proposal owner for proposal {proposal_id}: {e}")
            return False

    async def send_approval_message(self, post_id: int, chat_id: str, post_data: dict) -> None:
        caption = post_data.get("content", "")
        media_url = post_data.get("media_url")

        inline_keyboard = {
            "inline_keyboard": [[
                {"text": "Approve ✅", "callback_data": f"approve:{post_id}"},
                {"text": "Reject ❌", "callback_data": f"reject:{post_id}"},
                {"text": "Edit 📝", "callback_data": f"edit:{post_id}"}
            ]]
        }

        async with httpx.AsyncClient() as client:
            sent = False
            if media_url:
                resp = await client.post(self._bot_url("sendPhoto"), json={
                    "chat_id": chat_id,
                    "photo": media_url,
                    "caption": caption,
                    "reply_markup": inline_keyboard
                })
                if resp.status_code == 200:
                    sent = True

            if not sent:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": caption or "New post for review:",
                    "reply_markup": inline_keyboard
                })

    async def handle_callback_query(self, callback_query: TelegramCallbackQuery) -> None:
        data = callback_query.data or ""
        chat_id = str(callback_query.from_user.id)
        message_id = callback_query.message.message_id if callback_query.message else None

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("answerCallbackQuery"), json={
                "callback_query_id": callback_query.id
            })

            if data.startswith("proposal:"):
                parts = data.split(":")
                if len(parts) >= 3:
                    proposal_id = parts[2]
                    if not await self._verify_proposal_owner(proposal_id, chat_id):
                        return
                await self._handle_proposal_callback(callback_query)
            elif data.startswith("slot_type:"):
                parts = data.split(":", 3)
                if len(parts) == 4:
                    if not await self._verify_proposal_owner(parts[1], chat_id):
                        return
                    await self._handle_slot_type(client, parts[1], int(parts[2]), parts[3], chat_id, message_id)
            elif data.startswith("slot:"):
                parts = data.split(":", 3)
                if len(parts) == 4:
                    if not await self._verify_proposal_owner(parts[1], chat_id):
                        return
                    await self._handle_slot_callback(client, parts[1], int(parts[2]), parts[3], chat_id, message_id)
            elif data.startswith("approve:"):
                post_id = int(data.split(":", 1)[1])
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_approve(client, post_id, chat_id, message_id)
            elif data.startswith("reject:"):
                post_id = int(data.split(":", 1)[1])
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_reject(client, post_id, chat_id, message_id)
            elif data.startswith("edit:"):
                post_id = int(data.split(":", 1)[1])
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_edit(client, post_id, chat_id)
            elif data.startswith("edit_text:"):
                post_id = int(data.split(":", 1)[1])
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_edit_text(client, post_id, chat_id)
            elif data.startswith("edit_date:"):
                post_id = int(data.split(":", 1)[1])
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_edit_date(client, post_id, chat_id)
            elif data.startswith("campaign:"):
                parts = data.split(":", 2)
                if len(parts) >= 3:
                    campaign_id = parts[2]
                    if not await self._verify_campaign_owner(campaign_id, chat_id):
                        return
                    await self._handle_campaign_callback(callback_query)

    async def _handle_approve(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        chat_id: str,
        message_id: Optional[int]
    ) -> None:
        supabase = get_supabase_admin_client()
        post_result = supabase.table('posts').select('id, scheduled_at').eq('id', post_id).execute()

        if not post_result.data:
            logger.error(f"Post {post_id} not found for approval")
            return

        scheduled_at_raw = post_result.data[0].get('scheduled_at')
        scheduled_time = datetime.now(timezone.utc)

        if scheduled_at_raw:
            parsed = datetime.fromisoformat(str(scheduled_at_raw).replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed > datetime.now(timezone.utc):
                scheduled_time = parsed

        await asyncio.to_thread(PostScheduler().schedule_post, post_id, scheduled_time)

        if message_id:
            await client.post(self._bot_url("editMessageText"), json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "✅ Approved — post scheduled."
            })

    async def _handle_reject(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        chat_id: str,
        message_id: Optional[int]
    ) -> None:
        supabase = get_supabase_admin_client()
        supabase.table('posts').update({"status": "failed"}).eq('id', post_id).execute()

        if message_id:
            await client.post(self._bot_url("editMessageText"), json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "❌ Rejected — post cancelled."
            })

    async def _handle_edit(self, client: httpx.AsyncClient, post_id: int, chat_id: str) -> None:
        await client.post(self._bot_url("sendMessage"), json={
            "chat_id": chat_id,
            "text": f"What would you like to edit for post #{post_id}?",
            "reply_markup": {"inline_keyboard": [[
                {"text": "Edit text ✏️", "callback_data": f"edit_text:{post_id}"},
                {"text": "Edit date 📅", "callback_data": f"edit_date:{post_id}"}
            ]]}
        })

    async def _handle_edit_text(self, client: httpx.AsyncClient, post_id: int, chat_id: str) -> None:
        await client.post(self._bot_url("sendMessage"), json={
            "chat_id": chat_id,
            "text": f"Send the new text for #post_{post_id}:",
            "reply_markup": {"force_reply": True, "selective": True}
        })

    async def _handle_edit_date(self, client: httpx.AsyncClient, post_id: int, chat_id: str) -> None:
        await client.post(self._bot_url("sendMessage"), json={
            "chat_id": chat_id,
            "text": f"Send the new date for #post_{post_id}_date:\nFormat: YYYY-MM-DD HH:MM (local time)",
            "reply_markup": {"force_reply": True, "selective": True}
        })

    async def handle_message(self, message: TelegramMessage) -> None:
        text = message.text or ""
        chat_id = str(message.chat.id)

        if text.startswith("/start "):
            token = text.split(" ", 1)[1].strip()
            await self._handle_link_account(chat_id, token)
            return

        if message.reply_to_message:
            reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            swap_match    = re.search(r'#slot_swap_([\w-]+)_(\d+)', reply_text)
            timeedit_match = re.search(r'#timeedit_([\w-]+)_(\d+)', reply_text)
            date_match    = re.search(r'#post_(\d+)_date', reply_text)
            text_match    = re.search(r'#post_(\d+)(?!_date)', reply_text)

            imgselect_match = re.search(r'#imgselect_([\w-]+)_(\d+)', reply_text)
            campaignchat_match = re.search(r'#campaignchat_([\w-]+)', reply_text)

            attachment = self._image_attachment(message)
            if swap_match and attachment:
                proposal_id = swap_match.group(1)
                slot_index = int(swap_match.group(2))
                if not await self._verify_proposal_owner(proposal_id, chat_id):
                    return
                await self._handle_photo_swap_reply(chat_id, proposal_id, slot_index, *attachment)
            elif campaignchat_match:
                campaign_id = campaignchat_match.group(1)
                if not await self._verify_campaign_owner(campaign_id, chat_id):
                    return
                await self._handle_campaign_chat_reply(chat_id, campaign_id, text)
            elif imgselect_match:
                proposal_id = imgselect_match.group(1)
                slot_index = int(imgselect_match.group(2))
                if not await self._verify_proposal_owner(proposal_id, chat_id):
                    return
                await self._handle_imgselect_reply(chat_id, proposal_id, slot_index, text)
            elif timeedit_match:
                proposal_id = timeedit_match.group(1)
                slot_index  = int(timeedit_match.group(2))
                if not await self._verify_proposal_owner(proposal_id, chat_id):
                    return
                await self._handle_timeedit_reply(chat_id, proposal_id, slot_index, text)
            elif date_match:
                post_id = int(date_match.group(1))
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_date_reply(chat_id, post_id, text)
            elif text_match:
                post_id = int(text_match.group(1))
                if not await self._verify_post_owner(post_id, chat_id):
                    return
                await self._handle_edit_reply(chat_id, post_id, text)

    async def _handle_link_account(self, chat_id: str, token: str) -> None:
        base_url = config.APP_BASE_URL
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{base_url}/api/telegram/link-account", json={
                "link_token": token,
                "telegram_chat_id": chat_id
            })
            confirmation = (
                "✅ Account linked successfully."
                if resp.status_code == 200
                else "❌ Invalid or expired token."
            )
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": confirmation
            })

    async def _run_edit_session_with_progress(
        self,
        chat_id: str,
        account_id: int,
        edit_type: str,
        context: dict,
        user_message: str
    ):
        """Wraps run_edit_session with a placeholder message that gets edited
        progressively as Hermes calls tools, so the user isn't staring at silence
        for the 15-30s the reasoning loop can take. Mirrors the on_progress pattern
        already used by the web chat's NDJSON stream, adapted to editMessageText."""
        placeholder_id: Optional[int] = None
        steps: list = []
        last_edit_at = 0.0
        last_sent_text: Optional[str] = None

        async with httpx.AsyncClient() as client:
            resp = await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": "🤖 Procesando…",
            })
            if resp.status_code == 200:
                placeholder_id = resp.json().get("result", {}).get("message_id")

        async def on_progress(event: dict) -> None:
            nonlocal last_edit_at, last_sent_text
            if placeholder_id is None:
                return
            label = _PROGRESS_LABELS.get(event.get("tool"), event.get("tool", ""))
            if event.get("type") == "tool_call":
                steps.append(f"🔎 {label}…")
            elif event.get("type") == "tool_result":
                icon = "✅" if event.get("ok") else "⚠️"
                if steps:
                    steps[-1] = f"{icon} {label}"
                else:
                    steps.append(f"{icon} {label}")
            else:
                return

            text = "\n".join(steps)
            if text == last_sent_text:
                return
            now = asyncio.get_event_loop().time()
            if now - last_edit_at < _PROGRESS_EDIT_MIN_INTERVAL:
                return
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._bot_url("editMessageText"), json={
                    "chat_id": chat_id,
                    "message_id": placeholder_id,
                    "text": text,
                })
                if resp.status_code == 200:
                    last_edit_at = now
                    last_sent_text = text

        result = await run_edit_session(
            account_id=account_id,
            edit_type=edit_type,
            context=context,
            user_message=user_message,
            on_progress=on_progress,
        )

        if placeholder_id is not None:
            final_text = "✅ Listo" if result.resolved else "⚠️ No pude completarlo"
            async with httpx.AsyncClient() as client:
                await client.post(self._bot_url("editMessageText"), json={
                    "chat_id": chat_id,
                    "message_id": placeholder_id,
                    "text": final_text,
                })

        return result

    async def _reply_edit_session_result(self, chat_id: str, result) -> None:
        icon = "✅" if result.resolved else "❌"
        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"{icon} {result.message}",
            })

    async def _handle_imgselect_reply(self, chat_id: str, proposal_id: str, slot_index: int, text: str) -> None:
        """Pasa la descripción de imagen del usuario a Hermes, que la resuelve contra la
        lista real de Drive y actualiza el post."""
        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('account_id').eq('id', proposal_id).execute()
        account_id = proposal_res.data[0].get('account_id') if proposal_res.data else None

        result = await self._run_edit_session_with_progress(
            chat_id=chat_id,
            account_id=account_id,
            edit_type="IMAGE_SELECT",
            context={"proposal_id": proposal_id, "slot_index": slot_index},
            user_message=text
        )
        await self._reply_edit_session_result(chat_id, result)

    async def _handle_timeedit_reply(self, chat_id: str, proposal_id: str, slot_index: int, text: str) -> None:
        """Pasa la fecha/hora en lenguaje natural del usuario a Hermes, que la interpreta
        y actualiza scheduled_at para el post del slot."""
        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('account_id').eq('id', proposal_id).execute()
        account_id = proposal_res.data[0].get('account_id') if proposal_res.data else None

        result = await self._run_edit_session_with_progress(
            chat_id=chat_id,
            account_id=account_id,
            edit_type="TIME",
            context={"proposal_id": proposal_id, "slot_index": slot_index},
            user_message=text
        )
        await self._reply_edit_session_result(chat_id, result)

    async def _handle_edit_reply(self, chat_id: str, post_id: int, new_content: str) -> None:
        supabase = get_supabase_admin_client()
        supabase.table('posts').update({"content": new_content, "status": "draft"}).eq('id', post_id).execute()

        post_result = supabase.table('posts').select('*').eq('id', post_id).execute()
        if post_result.data:
            await self.send_approval_message(post_id, chat_id, post_result.data[0])

    async def send_campaign_approval_card(self, chat_id, campaign: dict) -> None:
        """Sends a single Telegram message with the drafted campaign summary and
        Approve/Reject/Chat inline buttons, mirroring send_proposal_card's header."""
        campaign_id = campaign.get("id")
        title = campaign.get("title", "")
        description = campaign.get("description") or ""
        milestones = campaign.get("milestones") or []
        weekly_focus = campaign.get("weekly_focus") or {}

        lines = [f"🗓 *Propuesta de campaña — {title}*"]
        if description:
            lines.append(description)

        focus_lines = "\n".join(f"  Semana {k}: {v}" for k, v in sorted(weekly_focus.items()) if v)
        if focus_lines:
            lines.append(f"*Enfoque semanal:*\n{focus_lines}")

        if milestones:
            milestone_lines = "\n".join(f"  {m.get('date')}: {m.get('event')}" for m in milestones)
            lines.append(f"*Hitos:*\n{milestone_lines}")

        lines.append("Revísala y decide antes de que empiece el mes.")
        text = "\n\n".join(lines)

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Aprobar ✅", "callback_data": f"campaign:approve:{campaign_id}"},
                    {"text": "Rechazar ❌", "callback_data": f"campaign:reject:{campaign_id}"},
                    {"text": "Chat 💬", "callback_data": f"campaign:chat:{campaign_id}"},
                ]]}
            })

    async def _handle_campaign_callback(self, callback_query) -> None:
        data = callback_query.data or ""
        chat_id = str(callback_query.from_user.id)
        message_id = callback_query.message.message_id if callback_query.message else None

        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        action, campaign_id = parts[1], parts[2]

        supabase = get_supabase_admin_client()

        async with httpx.AsyncClient() as client:
            if action == "approve":
                supabase.table('monthly_campaigns').update({
                    "status": "approved",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }).eq('id', campaign_id).execute()

                if message_id:
                    await client.post(self._bot_url("editMessageText"), json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": "✅ Campaña aprobada."
                    })

            elif action == "reject":
                supabase.table('monthly_campaigns').update({
                    "status": "rejected",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }).eq('id', campaign_id).execute()

                if message_id:
                    await client.post(self._bot_url("editMessageText"), json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": "❌ Campaña rechazada — se generará un nuevo borrador."
                    })

            elif action == "chat":
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": f"¿Qué te gustaría ajustar de la campaña?\n#campaignchat_{campaign_id}",
                    "reply_markup": {"force_reply": True, "selective": True}
                })

    async def _handle_campaign_chat_reply(self, chat_id: str, campaign_id: str, text: str) -> None:
        """Passes the user's natural-language adjustment to Hermes (CAMPAIGN_CHAT edit
        type), replies with the result, and re-sends the force_reply prompt so the
        conversation stays open for further tweaks."""
        supabase = get_supabase_admin_client()
        campaign_res = supabase.table('monthly_campaigns').select('account_id').eq('id', campaign_id).execute()
        account_id = campaign_res.data[0].get('account_id') if campaign_res.data else None

        result = await self._run_edit_session_with_progress(
            chat_id=chat_id,
            account_id=account_id,
            edit_type="CAMPAIGN_CHAT",
            context={"campaign_id": campaign_id},
            user_message=text
        )
        await self._reply_edit_session_result(chat_id, result)

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"¿Algo más que ajustar?\n#campaignchat_{campaign_id}",
                "reply_markup": {"force_reply": True, "selective": True}
            })

    async def _handle_date_reply(self, chat_id: str, post_id: int, date_text: str) -> None:
        """Pasa la fecha en lenguaje natural del usuario a Hermes, que la interpreta y
        actualiza scheduled_at para el post."""
        supabase = get_supabase_admin_client()
        post_res = supabase.table('posts').select('instagram_account_id').eq('id', post_id).execute()
        account_id = post_res.data[0].get('instagram_account_id') if post_res.data else None

        result = await self._run_edit_session_with_progress(
            chat_id=chat_id,
            account_id=account_id,
            edit_type="DATE",
            context={"post_id": post_id},
            user_message=date_text
        )
        await self._reply_edit_session_result(chat_id, result)

    async def send_status_notification(
        self,
        chat_id: str,
        post_id: int,
        status: str,
        detail: Optional[str] = None
    ) -> None:
        if status == "published":
            text = f"✅ Post #{post_id} published successfully."
            if detail:
                text += f"\n🔗 {detail}"
        elif status == "deferred_quota":
            text = (
                f"⏳ Post #{post_id} postponed: Instagram's 24h publishing limit reached. "
                f"It will be retried every hour."
            )
        else:
            text = f"❌ Post #{post_id} failed to publish."
            if detail:
                text += f"\nDetail: {detail}"

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text
            })

    async def _download_drive_image(self, user_id: str, file_id: str) -> Optional[bytes]:
        """Downloads a Google Drive file as bytes. Runs the sync Drive API in a thread executor."""
        import io
        from googleapiclient.http import MediaIoBaseDownload

        def _sync() -> Optional[bytes]:
            try:
                from services.google_drive_connector import get_drive_connector
                drive = get_drive_connector(user_id)
                fh = io.BytesIO()
                dl = MediaIoBaseDownload(fh, drive.service.files().get_media(fileId=file_id))
                done = False
                while not done:
                    _, done = dl.next_chunk()
                return fh.getvalue()
            except Exception as e:
                logger.error(f"Drive image download failed for {file_id}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _sync)

    @staticmethod
    def _prepare_telegram_photo(image_bytes: bytes) -> Optional[bytes]:
        """Copia reducida solo para la vista previa de Telegram (sendPhoto: ≤ 10 MB y
        ancho + alto ≤ 10000). El original de Drive no se toca: es el que se publica."""
        import io
        from services.post_media import open_image

        try:
            img = open_image(image_bytes)
            img.thumbnail((TELEGRAM_PHOTO_MAX_SIDE, TELEGRAM_PHOTO_MAX_SIDE))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85)
            return out.getvalue()
        except Exception as e:
            logger.warning(f"No se pudo preparar la imagen para Telegram: {e}")
            return None

    async def send_proposal_card(self, chat_id: str, proposal_id: str, slots: list, user_id: str = None) -> None:
        supabase = get_supabase_admin_client()

        # 1. Header message with global approve/reject buttons
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": "📅 *Weekly content proposal* — review and approve each day:",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Approve all ✅", "callback_data": f"proposal:approve:{proposal_id}"},
                    {"text": "Reject ❌",      "callback_data": f"proposal:reject:{proposal_id}"}
                ]]}
            })
            if resp.status_code == 200:
                msg_id = resp.json().get("result", {}).get("message_id")
                if msg_id:
                    supabase.table('content_proposals').update(
                        {"telegram_message_id": str(msg_id)}
                    ).eq('id', proposal_id).execute()

            # 2. One message per slot (photo when available, text fallback)
            for i, s in enumerate(slots):
                day       = s.day if hasattr(s, 'day') else s['day']
                theme     = s.theme if hasattr(s, 'theme') else s['theme']
                caption   = s.caption if hasattr(s, 'caption') else s['caption']
                image_id  = (s.image_id if hasattr(s, 'image_id') else s.get('image_id'))
                post_type = ((s.post_type if hasattr(s, 'post_type') else s.get('post_type')) or 'post').upper()

                slot_text = f"*{day}* — {post_type}\n_{theme}_\n{caption[:150]}{'…' if len(caption) > 150 else ''}"
                slot_keyboard = {"inline_keyboard": [
                    [
                        {"text": "🔄 Regenerate",      "callback_data": f"slot:{proposal_id}:{i}:regen"},
                        {"text": "✂️ Skip",             "callback_data": f"slot:{proposal_id}:{i}:skip"},
                    ],
                    [
                        {"text": "🖼 Change image",    "callback_data": f"slot:{proposal_id}:{i}:change_image"},
                        {"text": "📎 Adjuntar foto",    "callback_data": f"slot:{proposal_id}:{i}:swap"},
                    ],
                    [
                        {"text": "🕐 Change date/time", "callback_data": f"slot:{proposal_id}:{i}:request_time"},
                    ],
                    [
                        {"text": "🎬 Type",            "callback_data": f"slot:{proposal_id}:{i}:change_type"},
                        {"text": "✅ Approve day",      "callback_data": f"slot:{proposal_id}:{i}:approve"},
                    ],
                ]}

                sent = False
                original = None
                if image_id and user_id:
                    original = image_bytes = await self._download_drive_image(user_id, image_id)
                    if image_bytes:
                        image_bytes = await asyncio.to_thread(self._prepare_telegram_photo, image_bytes)
                    if image_bytes:
                        resp2 = await client.post(
                            self._bot_url("sendPhoto"),
                            data={
                                "chat_id": chat_id,
                                "caption": slot_text,
                                "parse_mode": "Markdown",
                                "reply_markup": json.dumps(slot_keyboard),
                            },
                            files={"photo": ("slot.jpg", image_bytes, "image/jpeg")},
                        )
                        sent = resp2.status_code == 200
                        if not sent:
                            logger.warning(
                                f"Telegram rechazó la foto del slot {i} de la propuesta {proposal_id} "
                                f"(HTTP {resp2.status_code}): {resp2.text[:200]}"
                            )

                if not sent:
                    await client.post(self._bot_url("sendMessage"), json={
                        "chat_id": chat_id,
                        "text": slot_text,
                        "parse_mode": "Markdown",
                        "reply_markup": slot_keyboard,
                    })

                if original and post_type.lower() in FEED_FORMATS:
                    await self._request_feed_crop(client, chat_id, proposal_id, i, day, original)

    async def _request_feed_crop(
        self,
        client: httpx.AsyncClient,
        chat_id: str,
        proposal_id: str,
        slot_index: int,
        day: str,
        original: bytes
    ) -> None:
        """Si la foto no cabe en el feed (4:5 a 1.91:1), envía el original y pide al usuario
        el recorte exacto a máxima resolución; la respuesta la recoge _handle_photo_swap_reply."""
        try:
            width, height = image_size(original)
            target = feed_crop_target(width, height)
            ext = image_extension(original)
        except Exception as e:
            logger.warning(f"No se pudo comprobar la proporción del slot {slot_index} de {proposal_id}: {e}")
            return
        if not target:
            return

        ratio, crop_w, crop_h = target
        text = (
            f"✂️ La foto de {day} mide {width}x{height} px y no cabe en el feed de Instagram "
            f"(admite de 4:5 a 1.91:1).\n"
            f"Recórtala a {ratio}: {crop_w}x{crop_h} px para conservar la máxima resolución, "
            "y responde a este mensaje con la foto recortada enviada como archivo.\n"
            f"#slot_swap_{proposal_id}_{slot_index}"
        )
        reply_markup = {"force_reply": True, "selective": True}
        if len(original) <= TELEGRAM_DOCUMENT_MAX_BYTES:
            resp = await client.post(
                self._bot_url("sendDocument"),
                data={"chat_id": chat_id, "caption": text, "reply_markup": json.dumps(reply_markup)},
                files={"document": (f"original_{day}.{ext}", original, "application/octet-stream")},
            )
            if resp.status_code == 200:
                return
            logger.warning(f"Telegram rechazó el original del slot {slot_index} de {proposal_id} (HTTP {resp.status_code}): {resp.text[:200]}")
        # Sin el archivo adjunto: el usuario recorta la foto desde su carpeta de Drive
        await client.post(self._bot_url("sendMessage"), json={
            "chat_id": chat_id, "text": text, "reply_markup": reply_markup,
        })

    async def _handle_proposal_callback(self, callback_query) -> None:
        data = callback_query.data or ""
        chat_id = str(callback_query.from_user.id)
        message_id = callback_query.message.message_id if callback_query.message else None

        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        action, proposal_id = parts[1], parts[2]

        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
        if not proposal_res.data:
            logger.error(f"Proposal {proposal_id} not found")
            return

        proposal = proposal_res.data[0]
        slots = proposal.get('slots', [])

        async with httpx.AsyncClient() as client:
            if action == "approve":
                supabase.table('content_proposals').update({
                    "status": "approved",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }).eq('id', proposal_id).execute()

                post_ids = [s['post_id'] for s in slots if s.get('post_id')]
                failed = []
                if post_ids:
                    posts_res = supabase.table('posts').select('id, scheduled_at').in_('id', post_ids).execute()
                    for post in (posts_res.data or []):
                        supabase.table('posts').update({"status": "scheduled"}).eq('id', post['id']).execute()
                        scheduled_at_raw = post.get('scheduled_at')
                        scheduled_time = datetime.now(timezone.utc)
                        if scheduled_at_raw:
                            parsed = datetime.fromisoformat(str(scheduled_at_raw).replace('Z', '+00:00'))
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=timezone.utc)
                            if parsed > datetime.now(timezone.utc):
                                scheduled_time = parsed
                        try:
                            await asyncio.to_thread(PostScheduler().schedule_post, post['id'], scheduled_time)
                        except Exception as e:
                            logger.error(f"Could not schedule post {post['id']} from proposal {proposal_id}: {e}")
                            failed.append(f"• Post {post['id']}: {e}")

                if message_id:
                    await client.post(self._bot_url("editMessageText"), json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": f"✅ Calendar approved — {len(post_ids) - len(failed)} posts scheduled."
                    })
                if failed:
                    await client.post(self._bot_url("sendMessage"), json={
                        "chat_id": chat_id,
                        "text": "⚠️ Sin programar (no se publicarán hasta corregirlos):\n" + "\n".join(failed),
                    })

            elif action == "reject":
                supabase.table('content_proposals').update({
                    "status": "rejected",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }).eq('id', proposal_id).execute()

                post_ids = [s['post_id'] for s in slots if s.get('post_id')]
                if post_ids:
                    for pid in post_ids:
                        supabase.table('posts').delete().eq('id', pid).eq('status', 'draft').execute()

                if message_id:
                    await client.post(self._bot_url("editMessageText"), json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": "❌ Proposal rejected — drafts deleted."
                    })

    async def _handle_slot_callback(
        self,
        client: httpx.AsyncClient,
        proposal_id: str,
        slot_index: int,
        action: str,
        chat_id: str,
        message_id: Optional[int]
    ) -> None:
        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
        if not proposal_res.data:
            return
        proposal = proposal_res.data[0]
        slots = proposal.get('slots', [])
        if slot_index >= len(slots):
            return
        slot = slots[slot_index]
        post_id = slot.get('post_id')

        if action == "regen":
            if not post_id:
                return

            image_id = slot.get('image_id')
            description_context = ""
            if image_id:
                va_res = supabase.table('visual_analyses').select('gemini_description').eq('drive_file_id', image_id).execute()
                if va_res.data:
                    description_context = str(va_res.data[0].get('gemini_description', ''))
            theme = slot.get('theme', '')

            acc_res = supabase.table('instagram_accounts').select('default_language').eq('id', proposal['account_id']).execute()
            language = acc_res.data[0].get('default_language', 'es') if acc_res.data else 'es'

            try:
                new_caption = await regenerate_slot_caption(
                    theme=theme,
                    visual_context=description_context,
                    language=language
                )
            except Exception as e:
                logger.error(f"Gemini regen failed for slot {slot_index}: {e}")
                return
            supabase.table('posts').update({'content': new_caption}).eq('id', post_id).execute()
            slots[slot_index]['caption'] = new_caption
            supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
            if message_id:
                day = slot.get('day', '')
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": f"🔄 Caption for *{day}* regenerated:\n\n_{new_caption[:300]}_",
                    "parse_mode": "Markdown"
                })

        elif action == "skip":
            if post_id:
                supabase.table('posts').delete().eq('id', post_id).eq('status', 'draft').execute()
            slots[slot_index]['post_id'] = None
            supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
            day = slot.get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"✂️ Slot for *{day}* skipped.",
                "parse_mode": "Markdown"
            })

        elif action == "change_type":
            day = slot.get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"🎬 Change post type for *{day}*:",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "📱 Post",     "callback_data": f"slot_type:{proposal_id}:{slot_index}:post"},
                    {"text": "🎬 Reel",     "callback_data": f"slot_type:{proposal_id}:{slot_index}:reel"},
                    {"text": "📸 Carousel", "callback_data": f"slot_type:{proposal_id}:{slot_index}:carousel"},
                    {"text": "⭕ Story",    "callback_data": f"slot_type:{proposal_id}:{slot_index}:story"},
                ]]}
            })

        elif action == "request_time":
            day = slot.get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": (
                    f"🕐 New date and time for *{day}*\n\n"
                    f"Format: `DD/MM HH:MM` (e.g. `18/07 14:30`)\n\n"
                    f"#timeedit_{proposal_id}_{slot_index}"
                ),
                "parse_mode": "Markdown",
                "reply_markup": {"force_reply": True, "selective": True}
            })

        elif action == "change_image":
            day = slot.get('day', '')
            # Resolve user_id and folder_id from the proposal's account
            account_id = proposal.get('account_id')
            acc_res = supabase.table('instagram_accounts')\
                .select('user_id, drive_folder_id').eq('id', account_id).execute()
            if not acc_res.data:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id, "text": "❌ Account not found."
                })
                return
            acc = acc_res.data[0]
            uid = str(acc.get('user_id', ''))
            folder_id = acc.get('drive_folder_id')
            if not folder_id:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ No Drive folder configured for this account. Set it in Settings.",
                })
                return
            try:
                def _list_images():
                    from services.google_drive_connector import get_drive_connector
                    drive = get_drive_connector(uid)
                    return drive.list_files(folder_id=folder_id)
                files = await asyncio.get_event_loop().run_in_executor(None, _list_images)
                images = [f for f in files if f.get('mimeType', '').startswith('image/')][:15]
            except Exception as e:
                logger.error(f"Drive list images failed for Telegram change_image: {e}")
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id, "text": "❌ Could not fetch Drive images. Check your Drive connection."
                })
                return
            if not images:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id, "text": "📂 No images found in your Drive folder."
                })
                return
            lines = [f"{i+1}. {f['name']}" for i, f in enumerate(images)]
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": (
                    f"🖼 Available images for *{day}*:\n\n"
                    + "\n".join(lines)
                    + f"\n\nReply with the number of the image you want to use.\n"
                    + f"#imgselect_{proposal_id}_{slot_index}"
                ),
                "parse_mode": "Markdown",
                "reply_markup": {"force_reply": True, "selective": True}
            })

        elif action == "approve":
            if not post_id:
                return
            supabase.table('posts').update({"status": "scheduled"}).eq('id', post_id).execute()
            post_res = supabase.table('posts').select('scheduled_at').eq('id', post_id).execute()
            if post_res.data:
                raw_ts = post_res.data[0].get('scheduled_at')
                scheduled_time = datetime.now(timezone.utc)
                if raw_ts:
                    import re as _re
                    s2 = str(raw_ts).replace('Z', '+00:00')
                    s2 = _re.sub(r'\.(\d+)', lambda m: '.' + m.group(1)[:6].ljust(6, '0'), s2)
                    parsed = datetime.fromisoformat(s2)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    if parsed > datetime.now(timezone.utc):
                        scheduled_time = parsed
                try:
                    await asyncio.to_thread(PostScheduler().schedule_post, post_id, scheduled_time)
                except Exception as e:
                    logger.error(f"Could not schedule post {post_id} from proposal {proposal_id}: {e}")
                    await client.post(self._bot_url("sendMessage"), json={
                        "chat_id": chat_id,
                        "text": f"⚠️ {slot.get('day', '')} no se ha programado: {e}",
                    })
                    return
            day = slot.get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"✅ *{day}* approved and scheduled.",
                "parse_mode": "Markdown",
            })

        elif action == "swap":
            day = slot.get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": (
                    f"📸 Responde a este mensaje con la nueva foto para {day}. "
                    "Envíala como archivo para conservar la calidad original (máx. 20 MB).\n"
                    f"#slot_swap_{proposal_id}_{slot_index}"
                ),
                "reply_markup": {"force_reply": True, "selective": True}
            })

    async def _handle_slot_type(
        self,
        client: httpx.AsyncClient,
        proposal_id: str,
        slot_index: int,
        new_type: str,
        chat_id: str,
        message_id: Optional[int]
    ) -> None:
        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
        if not proposal_res.data:
            return
        slots = proposal_res.data[0].get('slots', [])
        if slot_index >= len(slots):
            return
        slot = slots[slot_index]
        post_id = slot.get('post_id')
        if post_id:
            supabase.table('posts').update({'post_type': new_type}).eq('id', post_id).execute()
        slots[slot_index]['post_type'] = new_type
        supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
        day = slot.get('day', '')
        await client.post(self._bot_url("sendMessage"), json={
            "chat_id": chat_id,
            "text": f"✅ Type for *{day}* changed to *{new_type}*.",
            "parse_mode": "Markdown"
        })

    @staticmethod
    def _image_attachment(message: TelegramMessage) -> Optional[tuple]:
        """(file_id, mime_type, comprimida) de la imagen adjunta: foto (Telegram la comprime
        a JPEG y reduce su resolución) o archivo de imagen (original, cualquier formato)."""
        if message.photo:
            largest = max(message.photo, key=lambda p: p.file_size or 0)
            return largest.file_id, "image/jpeg", True
        doc = message.document
        if doc and (doc.mime_type or "").startswith("image/"):
            return doc.file_id, doc.mime_type, False
        return None

    async def _handle_photo_swap_reply(
        self,
        chat_id: str,
        proposal_id: str,
        slot_index: int,
        file_id: str,
        mime_type: str,
        compressed: bool = False
    ) -> None:
        supabase = get_supabase_admin_client()
        proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
        if not proposal_res.data:
            return
        slots = proposal_res.data[0].get('slots', [])
        if slot_index >= len(slots):
            return
        slot = slots[slot_index]
        post_id = slot.get('post_id')
        if not post_id:
            return

        token = config.TELEGRAM_BOT_TOKEN
        async with httpx.AsyncClient() as client:
            try:
                # Get file path from Telegram (la Bot API solo descarga archivos de hasta 20 MB)
                file_resp = await client.get(self._bot_url(f"getFile?file_id={file_id}"))
                file_path = file_resp.json().get("result", {}).get("file_path", "") if file_resp.status_code == 200 else ""
                if not file_path:
                    raise ValueError(f"getFile HTTP {file_resp.status_code}")

                img_resp = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
                if img_resp.status_code != 200:
                    raise ValueError(f"download HTTP {img_resp.status_code}")
                width, height = image_size(img_resp.content)
            except Exception as e:
                logger.error(f"Photo swap failed for proposal {proposal_id} slot {slot_index}: {e}")
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ No se pudo usar esa imagen. Si pesa más de 20 MB, envíala más pequeña.",
                })
                return

            # El feed solo admite de 4:5 a 1.91:1: se pide de nuevo el recorte exacto
            target = feed_crop_target(width, height) if (slot.get('post_type') or 'post').lower() in FEED_FORMATS else None
            if target:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": (
                        f"✂️ La foto mide {width}x{height} px y sigue sin caber en el feed. "
                        f"Recórtala a {target[0]}: {target[1]}x{target[2]} px y responde a este mensaje "
                        "con la foto enviada como archivo.\n"
                        f"#slot_swap_{proposal_id}_{slot_index}"
                    ),
                    "reply_markup": {"force_reply": True, "selective": True},
                })
                return

            try:
                # Instagram solo publica JPEG ≤ 8 MB: original si ya cumple, si no a máxima resolución
                data = await asyncio.to_thread(prepare_image_for_instagram, img_resp.content, mime_type)
                storage_path = f"telegram/{proposal_id}_{slot_index}.jpg"
                storage = supabase.storage.from_(STORAGE_BUCKET)
                storage.upload(storage_path, data, {"content-type": "image/jpeg", "upsert": "true"})
                media_url = storage.get_public_url(storage_path)
            except Exception as e:
                logger.error(f"Photo swap upload failed for proposal {proposal_id} slot {slot_index}: {e}")
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ No se pudo guardar la imagen. Inténtalo de nuevo.",
                })
                return

            # La foto adjunta sustituye a la de Drive: el post se publicará con ella
            supabase.table('posts').update({'media_url': media_url, 'drive_file_id': None}).eq('id', post_id).execute()
            slots[slot_index]['image_id'] = None
            slots[slot_index]['media_url'] = media_url
            supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()

            note = (
                f" Telegram la comprimió a {width}x{height} px: para publicarla a máxima resolución "
                "envíala como archivo." if compressed else ""
            )
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"📸 Imagen del slot {slot.get('day', '')} actualizada.{note}",
            })

    async def send_daily_briefing(self, account_id: int, chat_id: str) -> None:
        supabase = get_supabase_admin_client()
        # "Hoy" y las horas en la zona efectiva de la cuenta, + la secundaria (AD-12)
        acc_res = supabase.table('instagram_accounts')\
            .select('primary_timezone, secondary_timezone, detected_timezone')\
            .eq('id', account_id)\
            .execute()
        account = acc_res.data[0] if acc_res.data else {}
        tz = effective_timezone(account)
        secondary_tz = account.get('secondary_timezone')
        local_today = to_local(datetime.now(timezone.utc), tz).date()
        today = local_today.isoformat()
        day_start = local_to_utc(datetime.combine(local_today, datetime.min.time()), tz)
        day_end = local_to_utc(datetime.combine(local_today, datetime.max.time()), tz)
        posts_res = supabase.table('posts')\
            .select('id, content, post_type, scheduled_at')\
            .eq('instagram_account_id', account_id)\
            .eq('status', 'scheduled')\
            .gte('scheduled_at', day_start.isoformat())\
            .lte('scheduled_at', day_end.isoformat())\
            .order('scheduled_at')\
            .execute()

        posts = posts_res.data or []
        if not posts:
            text = "📋 Sin publicaciones programadas para hoy."
        else:
            lines = []
            for p in posts:
                scheduled_at = p.get('scheduled_at', '')
                try:
                    dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    time_str = to_local(dt, tz).strftime('%H:%M')
                    if secondary_tz and secondary_tz != tz:
                        time_str += f" ({to_local(dt, secondary_tz).strftime('%H:%M')} {zone_label(secondary_tz)})"
                except Exception:
                    time_str = '??:??'
                ptype = p.get('post_type', 'post')
                caption_preview = (p.get('content', '') or '')[:60]
                lines.append(f"• *{time_str}* [{ptype}] — {caption_preview}{'…' if len(p.get('content','')) > 60 else ''}")
            text = f"📋 *Publicaciones de hoy ({today}):*\n\n" + "\n".join(lines)

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            })
