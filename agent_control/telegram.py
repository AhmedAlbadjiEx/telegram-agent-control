"""Minimal HTTPS Bot API client. Never log URLs containing the bot token."""
import asyncio
import json
import urllib.error
import urllib.request


def telegram_text(text):
    """Bound UTF-16 length, including emoji, below Telegram message limits."""
    return text.encode("utf-16-le")[-7000:].decode("utf-16-le", errors="ignore")


class TelegramError(Exception):
    def __init__(self, code, retry_after=0):
        self.code, self.retry_after = code, retry_after
        super().__init__(f'Telegram API error {code}')


class Telegram:
    def __init__(self, token):
        self.base = f'https://api.telegram.org/bot{token}/'
        self.send_lock = asyncio.Lock()

    def _request(self, method, payload):
        request = urllib.request.Request(self.base + method, data=json.dumps(payload).encode(),
                                        headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                result = json.load(exc)
            except (ValueError, OSError):
                raise TelegramError(exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TelegramError(0) from None
        if not result.get('ok'):
            raise TelegramError(result.get('error_code', 0), result.get('parameters', {}).get('retry_after', 0))
        return result['result']

    async def call(self, method, **payload):
        for attempt in range(3):
            try:
                return await asyncio.to_thread(self._request, method, payload)
            except TelegramError as exc:
                if exc.code != 429 or attempt == 2:
                    raise
                await asyncio.sleep(min(max(exc.retry_after, 1), 60))

    async def send(self, chat, text):
        async with self.send_lock:
            result = await self.call('sendMessage', chat_id=chat, text=telegram_text(text),
                                     link_preview_options={'is_disabled': True})
            await asyncio.sleep(1)
            return result['message_id']

    async def edit(self, chat, message, text):
        async with self.send_lock:
            await self.call('editMessageText', chat_id=chat, message_id=message, text=telegram_text(text),
                            link_preview_options={'is_disabled': True})
            await asyncio.sleep(1)
