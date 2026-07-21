import asyncio
import sys
from pathlib import Path

import aiofiles
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from PyQt6.QtCore import QThread, pyqtSignal

from src.core.database import Database


API_BASE = "https://discord.com/api/v9"
GUILDS_URL = f"{API_BASE}/users/@me/guilds"
GUILD_CHANNELS_URL = f"{API_BASE}/guilds/{{guild_id}}/channels"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEAD = object()
NO_RIGHTS = object()
CHANNEL_FORBIDDEN = object()
SEND_RETRIES = 3
TEXT_CHANNEL_TYPES = (0, 5)


class BroadcastWorker(QThread):
    progress_signal = pyqtSignal(int, int)
    log_signal = pyqtSignal(str, str)
    account_status = pyqtSignal(object)
    finished_signal = pyqtSignal(dict)

    def __init__(self, accounts: list, proxies: list, message: str, attachments: list,
                 max_workers: int = 100, delay: float = 2.0, target_guild_id: str = None, parent=None):
        super().__init__(parent)
        self.accounts = accounts
        self.proxies = proxies
        self.message = message
        self.attachments = attachments
        self.max_workers = max_workers
        self.delay = delay
        self.target_guild_id = (target_guild_id or "").strip() or None
        self.should_stop = False
        self.stats = {"sent": 0, "failed": 0, "total": 0, "dead": 0, "no_rights": 0, "forbidden": 0}
        self.db = Database()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: list[asyncio.Task] = []

    def stop(self):
        self.should_stop = True
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._cancel_tasks)

    def _cancel_tasks(self):
        for task in self._tasks:
            task.cancel()

    def run(self):
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._dispatch())
        except Exception:
            return
        finally:
            self._loop = None
            loop.close()
        self.finished_signal.emit(self.stats)

    async def _dispatch(self):
        semaphore = asyncio.Semaphore(self.max_workers)
        self._tasks = [
            asyncio.ensure_future(self._broadcast(semaphore, account, self._proxy_for(i, account)))
            for i, account in enumerate(self.accounts)
        ]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _proxy_for(self, index: int, account: dict) -> dict | None:
        if self.proxies:
            return self.proxies[index % len(self.proxies)]
        return account.get("proxy")

    def _build_connector(self, proxy: dict | None) -> tuple[aiohttp.BaseConnector, str | None]:
        if not proxy or not proxy.get("ip") or not proxy.get("port"):
            return aiohttp.TCPConnector(ssl=False), None

        protocol = (proxy.get("protocol") or "http").lower()
        ip = proxy["ip"]
        port = int(proxy["port"])
        login = proxy.get("login")
        password = proxy.get("password")

        if protocol in ("socks5", "socks4"):
            proxy_type = ProxyType.SOCKS5 if protocol == "socks5" else ProxyType.SOCKS4
            connector = ProxyConnector(
                proxy_type=proxy_type, host=ip, port=port,
                username=login, password=password, rdns=True, verify_ssl=False,
            )
            return connector, None

        auth = f"{login}:{password}@" if login and password else ""
        return aiohttp.TCPConnector(ssl=False), f"http://{auth}{ip}:{port}"

    async def _broadcast(self, semaphore: asyncio.Semaphore, account: dict, proxy: dict | None):
        async with semaphore:
            if self.should_stop:
                return

            token = account.get("token")
            if not token:
                return

            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
            connector, proxy_url = self._build_connector(proxy)

            async with aiohttp.ClientSession(connector=connector) as session:
                guilds = await self._fetch_guilds(session, headers, proxy_url)
                if guilds is DEAD:
                    self._mark_dead(account, token)
                    return
                if guilds is NO_RIGHTS:
                    self._mark_no_rights(account, token)
                    return
                if not guilds:
                    self.log_signal.emit(f"{token[:20]}... | Нет серверов", "yellow")
                    return

                if self.target_guild_id:
                    guilds = [g for g in guilds if g == self.target_guild_id]
                    if not guilds:
                        self.log_signal.emit(f"{token[:20]}... | Нет целевого сервера", "yellow")
                        return

                channels = await self._collect_channels(session, headers, proxy_url, guilds)
                if not channels:
                    self.log_signal.emit(f"{token[:20]}... | Нет доступных каналов", "yellow")
                    return

                sent = self.db.get_sent_channels(token)
                channels = [c for c in channels if c not in sent]
                if not channels:
                    self.log_signal.emit(f"{token[:20]}... | Все каналы уже получили сообщение", "yellow")
                    return

                self.stats["total"] += len(channels)
                self._emit_status(account, len(guilds), len(channels), 0, 0, 0, False)

                await self._send_to_channels(session, headers, proxy_url, channels, account, token, len(guilds))

    async def _collect_channels(self, session, headers, proxy_url, guild_ids: list) -> list:
        tasks = [self._fetch_guild_channels(session, headers, proxy_url, gid) for gid in guild_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        channels = []
        for res in results:
            if isinstance(res, list):
                channels.extend(res)
        return channels

    async def _fetch_guilds(self, session, headers, proxy_url):
        kwargs = {"headers": headers}
        if proxy_url:
            kwargs["proxy"] = proxy_url
        try:
            async with session.get(GUILDS_URL, **kwargs) as resp:
                if resp.status == 200:
                    return [g.get("id") for g in await resp.json() if g.get("id")]
                if resp.status == 401:
                    return DEAD
                if resp.status == 403:
                    return NO_RIGHTS
                self.log_signal.emit(f"Guilds: HTTP {resp.status}", "yellow")
        except Exception as exc:
            self.log_signal.emit(f"Guilds error: {exc}", "red")
        return []

    async def _fetch_guild_channels(self, session, headers, proxy_url, guild_id: str) -> list:
        url = GUILD_CHANNELS_URL.format(guild_id=guild_id)
        kwargs = {"headers": headers}
        if proxy_url:
            kwargs["proxy"] = proxy_url
        try:
            async with session.get(url, **kwargs) as resp:
                if resp.status == 200:
                    return [
                        c.get("id") for c in await resp.json()
                        if c.get("type") in TEXT_CHANNEL_TYPES and c.get("id")
                    ]
        except Exception:
            return []
        return []

    async def _send_to_channels(self, session, headers, proxy_url, channels, account, token, servers: int):
        total = len(channels)
        sent = 0
        forbidden = 0
        failed = 0

        for channel_id in channels:
            if self.should_stop:
                break
            if not channel_id:
                continue

            result = await self._send_message(session, headers, proxy_url, channel_id)
            if result is DEAD:
                self._mark_dead(account, token)
                return
            if result is CHANNEL_FORBIDDEN:
                forbidden += 1
                self.stats["forbidden"] += 1
            elif result:
                self.db.save_sent_channel(token, channel_id)
                sent += 1
                self.stats["sent"] += 1
            else:
                failed += 1
                self.stats["failed"] += 1

            self.progress_signal.emit(self.stats["sent"], self.stats["total"])
            self._emit_status(account, servers, total, sent, forbidden, failed, False)

            if not self.should_stop and self.delay > 0:
                await asyncio.sleep(self.delay)

        self._emit_status(account, servers, total, sent, forbidden, failed, True)

    def _emit_status(self, account: dict, servers: int, channels: int,
                     sent: int, forbidden: int, failed: int, is_final: bool):
        token = account.get("token", "")
        self.account_status.emit({
            "id": account.get("id"),
            "token": f"{token[:20]}...",
            "servers": servers,
            "channels": channels,
            "sent": sent,
            "forbidden": forbidden,
            "failed": failed,
            "final": is_final,
        })

    def _mark_dead(self, account: dict, token: str):
        account_id = account.get("id")
        if account_id:
            self.db.move_to_dead([account_id])
        self.stats["dead"] += 1
        self.log_signal.emit(f"{token[:20]}... | Мертвый токен → перемещен", "red")

    def _mark_no_rights(self, account: dict, token: str):
        account_id = account.get("id")
        if account_id:
            self.db.move_to_insufficient_rights([account_id])
        self.stats["no_rights"] += 1
        self.log_signal.emit(f"{token[:20]}... | Нету прав → перемещен", "yellow")

    async def _send_message(self, session, headers, proxy_url, channel_id: str):
        url = f"{API_BASE}/channels/{channel_id}/messages"
        if self.attachments:
            return await self._send_with_attachments(session, headers, proxy_url, url, channel_id)

        kwargs = {"headers": headers, "json": {"content": self.message}}
        if proxy_url:
            kwargs["proxy"] = proxy_url

        for _ in range(SEND_RETRIES):
            try:
                async with session.post(url, **kwargs) as resp:
                    if resp.status in (200, 201):
                        return True
                    if resp.status == 429:
                        await asyncio.sleep(float((await resp.json()).get("retry_after", 2.0)))
                        continue
                    if resp.status == 401:
                        return DEAD
                    if resp.status == 403:
                        return CHANNEL_FORBIDDEN
                    await self._log_api_error(resp, channel_id)
                    return False
            except Exception:
                await asyncio.sleep(0.3)
        return False

    async def _send_with_attachments(self, session, headers, proxy_url, url: str, channel_id: str):
        send_headers = {k: v for k, v in headers.items() if k != "Content-Type"}

        for _ in range(SEND_RETRIES):
            try:
                form = aiohttp.FormData()
                form.add_field("content", self.message)
                for path in self.attachments:
                    file_path = Path(path)
                    if not file_path.exists():
                        continue
                    async with aiofiles.open(file_path, "rb") as f:
                        form.add_field("file", await f.read(), filename=file_path.name)

                kwargs = {"headers": send_headers, "data": form}
                if proxy_url:
                    kwargs["proxy"] = proxy_url

                async with session.post(url, **kwargs) as resp:
                    if resp.status in (200, 201):
                        return True
                    if resp.status == 429:
                        await asyncio.sleep(float((await resp.json()).get("retry_after", 2.0)))
                        continue
                    if resp.status == 401:
                        return DEAD
                    if resp.status == 403:
                        return CHANNEL_FORBIDDEN
                    await self._log_api_error(resp, channel_id)
                    return False
            except Exception:
                await asyncio.sleep(0.3)
        return False

    async def _log_api_error(self, resp, channel_id: str):
        try:
            data = await resp.json()
            self.log_signal.emit(
                f"HTTP {resp.status} [{data.get('code')}] {data.get('message', '')} | {channel_id}",
                "red",
            )
        except Exception:
            self.log_signal.emit(f"HTTP {resp.status} | {channel_id}", "red")
