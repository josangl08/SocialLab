import asyncio
import json
import os
import re
import logging
import tempfile
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import httpx

import google.generativeai as genai

from database.supabase_client import get_supabase_admin_client
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
            reply_text = message.reply_to_message.text or ""
            swap_match    = re.search(r'#slot_swap_(\w+)_(\d+)', reply_text)
            timeedit_match = re.search(r'#timeedit_([\w-]+)_(\d+)', reply_text)
            date_match    = re.search(r'#post_(\d+)_date', reply_text)
            text_match    = re.search(r'#post_(\d+)(?!_date)', reply_text)

            imgselect_match = re.search(r'#imgselect_([\w-]+)_(\d+)', reply_text)

            if swap_match and message.photo:
                proposal_id = swap_match.group(1)
                slot_index = int(swap_match.group(2))
                if not await self._verify_proposal_owner(proposal_id, chat_id):
                    return
                await self._handle_photo_swap_reply(chat_id, proposal_id, slot_index, message.photo)
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

    async def _handle_imgselect_reply(self, chat_id: str, proposal_id: str, slot_index: int, text: str) -> None:
        """Parses a 1-based image number from user reply and updates the slot's Drive image."""
        async with httpx.AsyncClient() as client:
            try:
                choice = int(text.strip())
            except ValueError:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ Please reply with a number from the list.",
                })
                return

            supabase = get_supabase_admin_client()
            proposal_res = supabase.table('content_proposals').select('slots, account_id').eq('id', proposal_id).execute()
            if not proposal_res.data:
                return
            proposal = proposal_res.data[0]
            slots = proposal.get('slots', [])
            if slot_index >= len(slots):
                return

            account_id = proposal.get('account_id')
            acc_res = supabase.table('instagram_accounts')\
                .select('user_id, drive_folder_id').eq('id', account_id).execute()
            if not acc_res.data:
                return
            acc = acc_res.data[0]
            uid = str(acc.get('user_id', ''))
            folder_id = acc.get('drive_folder_id')
            if not folder_id:
                return

            try:
                def _list():
                    from services.google_drive_connector import get_drive_connector
                    drive = get_drive_connector(uid)
                    return drive.list_files(folder_id=folder_id)
                files = await asyncio.get_event_loop().run_in_executor(None, _list)
                images = [f for f in files if f.get('mimeType', '').startswith('image/')][:15]
            except Exception as e:
                logger.error(f"Drive list failed in imgselect_reply: {e}")
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id, "text": "❌ Could not fetch Drive images."
                })
                return

            if choice < 1 or choice > len(images):
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": f"❌ Invalid choice. Pick a number between 1 and {len(images)}.",
                })
                return

            selected = images[choice - 1]
            file_id = selected['id']
            file_name = selected['name']

            post_id = slots[slot_index].get('post_id')
            if post_id:
                supabase.table('posts').update({'drive_file_id': file_id}).eq('id', post_id).execute()
            slots[slot_index]['image_id'] = file_id
            supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()

            day = slots[slot_index].get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"✅ Image for *{day}* changed to *{file_name}*.",
                "parse_mode": "Markdown",
            })

    async def _handle_timeedit_reply(self, chat_id: str, proposal_id: str, slot_index: int, text: str) -> None:
        """Parses 'DD/MM HH:MM' from user reply and updates scheduled_at for the slot's post."""
        m = re.match(r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})', text.strip())
        async with httpx.AsyncClient() as client:
            if not m:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ Invalid format. Use: `DD/MM HH:MM` (e.g. `18/07 14:30`)",
                    "parse_mode": "Markdown",
                })
                return
            day_num, month_num = int(m.group(1)), int(m.group(2))
            hour, minute = int(m.group(3)), int(m.group(4))
            year = datetime.now(timezone.utc).year
            try:
                scheduled_time = datetime(year, month_num, day_num, hour, minute, tzinfo=timezone.utc)
            except ValueError:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": "❌ Invalid date. Check the day and month.",
                    "parse_mode": "Markdown",
                })
                return

            supabase = get_supabase_admin_client()
            proposal_res = supabase.table('content_proposals').select('slots').eq('id', proposal_id).execute()
            if not proposal_res.data:
                return
            slots = proposal_res.data[0].get('slots', [])
            if slot_index >= len(slots):
                return
            post_id = slots[slot_index].get('post_id')
            if not post_id:
                return

            supabase.table('posts').update({'scheduled_at': scheduled_time.isoformat()}).eq('id', post_id).execute()
            post_res = supabase.table('posts').select('media_url').eq('id', post_id).execute()
            if post_res.data and post_res.data[0].get('media_url'):
                try:
                    PostScheduler().schedule_post(post_id, scheduled_time)
                except Exception as e:
                    logger.warning(f"No se pudo crear APScheduler job para post {post_id}: {e}")

            day_name = slots[slot_index].get('day', '')
            await client.post(self._bot_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": f"✅ *{day_name}* scheduled for {day_num:02d}/{month_num:02d} at {hour:02d}:{minute:02d}",
                "parse_mode": "Markdown",
            })

    async def _handle_edit_reply(self, chat_id: str, post_id: int, new_content: str) -> None:
        supabase = get_supabase_admin_client()
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

        supabase = get_supabase_admin_client()
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
                        {"text": "🕐 Change date/time", "callback_data": f"slot:{proposal_id}:{i}:request_time"},
                    ],
                    [
                        {"text": "🎬 Type",            "callback_data": f"slot:{proposal_id}:{i}:change_type"},
                        {"text": "✅ Approve day",      "callback_data": f"slot:{proposal_id}:{i}:approve"},
                    ],
                ]}

                sent = False
                if image_id and user_id:
                    image_bytes = await self._download_drive_image(user_id, image_id)
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
                    await client.post(self._bot_url("sendMessage"), json={
                        "chat_id": chat_id,
                        "text": slot_text,
                        "parse_mode": "Markdown",
                        "reply_markup": slot_keyboard,
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
                        "text": f"✅ Calendar approved — {len(post_ids)} posts scheduled."
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
            api_key = os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                return
            genai.configure(api_key=api_key)
            image_id = slot.get('image_id')
            description_context = ""
            if image_id:
                va_res = supabase.table('visual_analyses').select('gemini_description').eq('drive_file_id', image_id).execute()
                if va_res.data:
                    description_context = str(va_res.data[0].get('gemini_description', ''))
            theme = slot.get('theme', '')
            prompt = (
                f"Generate a new creative Instagram caption about the theme: '{theme}'. "
                f"Visual context: {description_context or 'inspiring image'}. "
                f"Tone: authentic and inspiring. End with an engagement question. "
                f"Include 3-5 relevant hashtags. Only the caption, no explanations."
            )
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt)
                new_caption = response.text.strip()
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
                PostScheduler().schedule_post(post_id, scheduled_time)
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
                "text": f"📸 Send the new photo for *{day}* as a reply to this message.\n#slot_swap_{proposal_id}_{slot_index}",
                "parse_mode": "Markdown",
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

    async def _handle_photo_swap_reply(
        self,
        chat_id: str,
        proposal_id: str,
        slot_index: int,
        photos: list
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

        # Get largest photo
        largest = max(photos, key=lambda p: p.file_size or 0) if photos else None
        if not largest:
            return

        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        async with httpx.AsyncClient() as client:
            # Get file path from Telegram
            file_resp = await client.get(self._bot_url(f"getFile?file_id={largest.file_id}"))
            if file_resp.status_code != 200:
                return
            file_path = file_resp.json().get("result", {}).get("file_path", "")
            if not file_path:
                return

            # Download the file
            download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            img_resp = await client.get(download_url)
            if img_resp.status_code != 200:
                return

        # Upload to Supabase Storage
        try:
            from database.supabase_client import get_supabase_admin_client
            admin = get_supabase_admin_client()
            ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "jpg"
            storage_path = f"telegram/{proposal_id}_{slot_index}.{ext}"
            admin.storage.from_('posts').upload(
                storage_path,
                img_resp.content,
                {"content-type": f"image/{ext}"}
            )
            public_url_res = admin.storage.from_('posts').get_public_url(storage_path)
            media_url = public_url_res if isinstance(public_url_res, str) else public_url_res.get('publicUrl', '')
            if media_url:
                supabase.table('posts').update({'media_url': media_url}).eq('id', post_id).execute()
                slots[slot_index]['image_id'] = storage_path
                supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()

            async with httpx.AsyncClient() as client:
                await client.post(self._bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": f"📸 Imagen del slot *{slot.get('day', '')}* actualizada.",
                    "parse_mode": "Markdown"
                })
        except Exception as e:
            logger.error(f"Photo swap failed for proposal {proposal_id} slot {slot_index}: {e}")

    async def send_daily_briefing(self, account_id: int, chat_id: str) -> None:
        supabase = get_supabase_admin_client()
        today = date.today().isoformat()
        posts_res = supabase.table('posts')\
            .select('id, content, post_type, scheduled_at')\
            .eq('instagram_account_id', account_id)\
            .eq('status', 'scheduled')\
            .gte('scheduled_at', f"{today}T00:00:00")\
            .lte('scheduled_at', f"{today}T23:59:59")\
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
                    time_str = dt.strftime('%H:%M')
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
