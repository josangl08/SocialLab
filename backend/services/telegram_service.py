import os
import re
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import httpx

from database.supabase_client import get_supabase_client
from models.schemas import TelegramMessage, TelegramCallbackQuery
from services.scheduler.post_scheduler import PostScheduler

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TelegramService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def _bot_url(self, method: str) -> str:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        return f"{TELEGRAM_API_BASE}{token}/{method}"

    async def register_webhook(self, base_url: Optional[str]) -> None:
        if not base_url:
            logger.info("TELEGRAM_WEBHOOK_URL not set — skipping webhook registration")
            return
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        webhook_url = f"{base_url}/api/telegram/webhook/{token}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._bot_url("setWebhook"), json={"url": webhook_url})
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info(f"Telegram webhook registered: {webhook_url}")
            else:
                logger.error(f"Failed to register Telegram webhook: {resp.text}")

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
                await self._handle_proposal_callback(callback_query)
            elif data.startswith("approve:"):
                post_id = int(data.split(":", 1)[1])
                await self._handle_approve(client, post_id, chat_id, message_id)
            elif data.startswith("reject:"):
                post_id = int(data.split(":", 1)[1])
                await self._handle_reject(client, post_id, chat_id, message_id)
            elif data.startswith("edit:"):
                post_id = int(data.split(":", 1)[1])
                await self._handle_edit(client, post_id, chat_id)
            elif data.startswith("edit_text:"):
                post_id = int(data.split(":", 1)[1])
                await self._handle_edit_text(client, post_id, chat_id)
            elif data.startswith("edit_date:"):
                post_id = int(data.split(":", 1)[1])
                await self._handle_edit_date(client, post_id, chat_id)

    async def _handle_approve(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        chat_id: str,
        message_id: Optional[int]
    ) -> None:
        supabase = get_supabase_client()
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

        PostScheduler().schedule_post(post_id, scheduled_time)

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
        supabase = get_supabase_client()
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
            reply_text = message.reply_to_message.text or ""
            date_match = re.search(r'#post_(\d+)_date', reply_text)
            text_match = re.search(r'#post_(\d+)(?!_date)', reply_text)
            if date_match:
                post_id = int(date_match.group(1))
                await self._handle_date_reply(chat_id, post_id, text)
            elif text_match:
                post_id = int(text_match.group(1))
                await self._handle_edit_reply(chat_id, post_id, text)

    async def _handle_link_account(self, chat_id: str, token: str) -> None:
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
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

    async def _handle_edit_reply(self, chat_id: str, post_id: int, new_content: str) -> None:
        supabase = get_supabase_client()
        supabase.table('posts').update({"content": new_content, "status": "draft"}).eq('id', post_id).execute()

        post_result = supabase.table('posts').select('*').eq('id', post_id).execute()
        if post_result.data:
            await self.send_approval_message(post_id, chat_id, post_result.data[0])

    async def _handle_date_reply(self, chat_id: str, post_id: int, date_text: str) -> None:
        try:
            tz = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Madrid"))
            scheduled_at = datetime.strptime(date_text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except (ValueError, KeyError):
            async with httpx.AsyncClient() as client:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ Wrong format. Use: YYYY-MM-DD HH:MM (e.g. 2026-06-15 14:30)"
                })
            return

        supabase = get_supabase_client()
        supabase.table('posts').update({
            "scheduled_at": scheduled_at.isoformat(),
            "status": "draft"
        }).eq('id', post_id).execute()

        post_result = supabase.table('posts').select('*').eq('id', post_id).execute()
        if post_result.data:
            await self.send_approval_message(post_id, chat_id, post_result.data[0])

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
        else:
            text = f"❌ Post #{post_id} failed to publish."
            if detail:
                text += f"\nDetail: {detail}"

        async with httpx.AsyncClient() as client:
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text
            })

    async def send_proposal_card(self, chat_id: str, proposal_id: str, slots: list) -> None:
        lines = "\n".join(
            f"• {s.day if hasattr(s, 'day') else s['day']}: "
            f"{s.theme if hasattr(s, 'theme') else s['theme']} — "
            f"{(s.caption if hasattr(s, 'caption') else s['caption'])[:60]}"
            for s in slots
        )
        text = f"📅 *Propuesta de contenido semanal*\n\n{lines}\n\n¿Apruebas este calendario?"

        keyboard = {
            "inline_keyboard": [[
                {"text": "Aprobar Calendario ✅", "callback_data": f"proposal:approve:{proposal_id}"},
                {"text": "Rechazar ❌", "callback_data": f"proposal:reject:{proposal_id}"}
            ]]
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            })
            if resp.status_code == 200:
                msg_id = resp.json().get("result", {}).get("message_id")
                if msg_id:
                    supabase = get_supabase_client()
                    supabase.table('content_proposals').update({
                        "telegram_message_id": str(msg_id)
                    }).eq('id', proposal_id).execute()

    async def _handle_proposal_callback(self, callback_query) -> None:
        data = callback_query.data or ""
        chat_id = str(callback_query.from_user.id)
        message_id = callback_query.message.message_id if callback_query.message else None

        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        action, proposal_id = parts[1], parts[2]

        supabase = get_supabase_client()
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
                        PostScheduler().schedule_post(post['id'], scheduled_time)

                if message_id:
                    await client.post(self._bot_url("editMessageText"), json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": f"✅ Calendario aprobado — {len(post_ids)} posts programados."
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
                        "text": "❌ Propuesta rechazada — borradores eliminados."
                    })
