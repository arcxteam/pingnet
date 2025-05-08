import asyncio
import json
import os
import pytz
import time
import logging
from datetime import datetime
from aiohttp import ClientResponseError, ClientSession, ClientTimeout
from aiohttp_socks import ProxyConnector
from fake_useragent import FakeUserAgent
from colorama import Fore, Style, init

init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('pingbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

wib = pytz.timezone('Asia/Jakarta')

class PingVPN:
    def __init__(self) -> None:
        self.USER_AGENT = FakeUserAgent().random
        self.HEADERS = {
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Priority": "u=1, i",
            "Origin": "chrome-extension://geeedmdpncfeomhgbjeafcahepjelimg",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Storage-Access": "active",
            "User-Agent": self.USER_AGENT
        }
        self.WSS_API = "wss://ws.pingvpn.xyz/pingvpn/v1"
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.account_points = {}  # Melacak poin per akun
        self.account_connection_time = {}  # Melacak waktu koneksi
        self.max_concurrent_tasks = 10  # Batas tugas bersamaan

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message, level="info"):
        timestamp = datetime.now().astimezone(wib).strftime('%x %X %Z')
        color = Fore.GREEN if level == "info" else Fore.RED if level == "error" else Fore.YELLOW
        log_message = f"[ {timestamp} ] | {color}{message}{Style.RESET_ALL}"
        if level == "info":
            logger.info(log_message)
        elif level == "error":
            logger.error(log_message)
        elif level == "warning":
            logger.warning(log_message)

    def welcome(self):
        """Menampilkan banner kustom untuk PingVPN."""
        banner = f"""
    {Fore.GREEN}========================  WELCOME TO INTERACTIVE TESTNET ========================{Style.RESET_ALL}
    {Fore.YELLOW}
     ██████╗██╗   ██╗ █████╗ ███╗   ██╗███╗   ██╗ ██████╗ ██████╗ ███████╗
    ██╔════╝██║   ██║██╔══██╗████╗  ██║████╗  ██║██╔═══██╗██╔══██╗██╔════╝
    ██║     ██║   ██║███████║██╔██╗ ██║██╔██╗ ██║██║   ██║██║  ██║█████╗  
    ██║     ██║   ██║██╔══██║██║╚██╗██║██║╚██╗██║██║   ██║██║  ██║██╔══╝  
    ╚██████╗╚██████╔╝██║  ██║██║ ╚████║██║ ╚████║╚██████╔╝██████╔╝███████╗
     ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝
    {Style.RESET_ALL}
    {Fore.CYAN}======================================================================={Style.RESET_ALL}
    {Fore.MAGENTA}       Welcome to Onchain Testnet & Mainnet Interactive          {Style.RESET_ALL}
    {Fore.YELLOW}        - CUANNODE By Greyscope&Co, Credit By Arcxteam -          {Style.RESET_ALL}
    {Fore.CYAN}======================================================================={Style.RESET_ALL}
    """
        self.log(banner, level="info")
    
    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def load_accounts(self):
        filename = "accounts.json"
        try:
            if not os.path.exists(filename):
                self.log(f"File {filename} tidak ditemukan.", level="error")
                return []
            with open(filename, 'r') as file:
                data = json.load(file)
                if not isinstance(data, list):
                    self.log(f"Format tidak valid di {filename}. Harus berupa daftar.", level="error")
                    return []
                for account in data:
                    if not all(key in account for key in ["Email", "UserId", "DeviceId"]):
                        self.log(f"Akun tidak valid: {account}", level="error")
                        return []
                return data
        except json.JSONDecodeError as e:
            self.log(f"Gagal mem-parsing {filename}: {e}", level="error")
            return []

    async def load_proxies(self):
        """Memuat proxy private dari proxy.txt."""
        filename = "proxy.txt"
        try:
            if not os.path.exists(filename):
                self.log(f"File {filename} tidak ditemukan.", level="error")
                return
            with open(filename, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
            
            if not self.proxies:
                self.log(f"Tidak ada proxy yang ditemukan di {filename}.", level="error")
                return

            # Validasi proxy
            valid_proxies = []
            for proxy in self.proxies:
                if await self.test_proxy(proxy):
                    valid_proxies.append(proxy)
                else:
                    self.log(f"Proxy tidak valid: {proxy}", level="warning")
            self.proxies = valid_proxies

            self.log(
                f"Total Proxy: {len(self.proxies)}",
                level="info"
            )
        except Exception as e:
            self.log(f"Gagal memuat proxy: {e}", level="error")
            self.proxies = []

    async def test_proxy(self, proxy):
        """Menguji apakah proxy berfungsi."""
        test_url = "https://www.google.com"
        connector = ProxyConnector.from_url(self.check_proxy_schemes(proxy))
        try:
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                async with session.get(test_url) as response:
                    response.raise_for_status()
                    return True
        except Exception:
            return False

    def check_proxy_schemes(self, proxy):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxy.startswith(scheme) for scheme in schemes):
            return proxy
        return f"http://{proxy}"

    def get_next_proxy_for_account(self, email):
        if not self.proxies:
            self.log(f"Tidak ada proxy tersedia untuk akun {email}. Menggunakan jaringan lokal.", level="warning")
            return None
        if email not in self.account_proxies:
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[email] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[email]

    def rotate_proxy_for_account(self, email):
        if not self.proxies:
            self.log(f"Tidak ada proxy untuk dirotasi untuk akun {email}. Menggunakan jaringan lokal.", level="warning")
            return None
        proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
        self.account_proxies[email] = proxy
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy

    def mask_account(self, account):
        if "@" in account:
            local, domain = account.split('@', 1)
            mask_account = local[:3] + '*' * 3 + local[-3:] if len(local) > 6 else local
            return f"{mask_account}@{domain}"
        return account[:3] + '*' * 3 + account[-3:] if len(account) > 6 else account

    def print_message(self, account, proxy, message, status="info"):
        proxy_display = proxy or "Jaringan Lokal"
        color = Fore.GREEN if status == "info" else Fore.RED if status == "error" else Fore.YELLOW
        self.log(
            f"[ Akun: {self.mask_account(account)} - Proxy: {proxy_display} - Status: {color}{message}{Style.RESET_ALL}]",
            level=status
        )

    async def connect_vpn(self, email: str, device_id: str, proxy=None, retries=5):
        url = "https://www.google-analytics.com/mp/collect?measurement_id=G-M0F9F7GGW0&api_secret=tdSjjplvRHGSEpXPfPDalA"
        data = json.dumps({
            "client_id": device_id,
            "events": [{
                "name": "connect_clicked",
                "params": {
                    "session_id": str(int(time.time() * 1000)),
                    "engagement_time_msec": 100,
                    "zone": "0"
                }
            }]
        })
        headers = {
            **self.HEADERS,
            "Content-Length": str(len(data)),
            "Content-Type": "text/plain;charset=UTF-8"
        }
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.post(url=url, headers=headers, data=data) as response:
                        response.raise_for_status()
                        return True
            except Exception as e:
                if attempt < retries - 1:
                    delay = 2 ** attempt  # Backoff eksponensial
                    self.log(f"Mencoba ulang koneksi VPN untuk {email} setelah {delay}s: {str(e)}", level="warning")
                    await asyncio.sleep(delay)
                    continue
                self.print_message(email, proxy, f"Koneksi VPN gagal: {str(e)}", status="error")
                return False

    async def track_points(self, email):
        """Melacak dan mencatat poin setiap 10 menit."""
        self.account_points[email] = self.account_points.get(email, 0)
        self.account_connection_time[email] = self.account_connection_time.get(email, time.time())
        
        while True:
            await asyncio.sleep(600)  # 10 menit
            if email in self.account_connection_time:
                elapsed = time.time() - self.account_connection_time[email]
                if elapsed >= 600:  # Pastikan koneksi aktif selama 10 menit
                    self.account_points[email] += 1
                    self.print_message(
                        email, 
                        self.account_proxies.get(email), 
                        f"Total Poin Akumulatif: {self.account_points[email]} PTS",
                        status="info"
                    )

    async def connect_websocket(self, email: str, user_id: str, device_id: str, use_proxy: bool):
        wss_url = f"{self.WSS_API}/clients/{user_id}/events"
        headers = {
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "Upgrade",
            "Host": "ws.pingvpn.xyz",
            "Origin": "chrome-extension://geeedmdpncfeomhgbjeafcahepjelimg",
            "Pragma": "no-cache",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "Sec-WebSocket-Key": "g0PDYtLWQOmaBE5upOBXew==",
            "Sec-WebSocket-Version": "13",
            "Upgrade": "websocket",
            "User-Agent": self.USER_AGENT
        }
        connected = False

        while True:
            proxy = self.get_next_proxy_for_account(email) if use_proxy else None
            connector = ProxyConnector.from_url(proxy) if proxy else None
            session = ClientSession(connector=connector, timeout=ClientTimeout(total=60))
            try:
                async with session.ws_connect(wss_url, headers=headers) as wss:
                    if not connected:
                        is_connected = await self.process_connect_vpn(email, device_id, use_proxy)
                        if is_connected:
                            self.print_message(email, proxy, "VPN Terhubung", status="info")
                            self.account_connection_time[email] = time.time()  # Mulai pelacakan waktu
                            asyncio.create_task(self.track_points(email))  # Mulai pelacakan poin
                            connected = True

                    while connected:
                        try:
                            response = await wss.receive_json()
                            if response.get("type") == "client_points":
                                client_points = response.get("data", {}).get("amount", 0)
                                last_transaction_id = response.get("data", {}).get("last_transaction_id", "N/A")
                                self.account_points[email] = self.account_points.get(email, 0) + client_points
                                self.print_message(
                                    email, proxy, 
                                    f"Pendapatan Klien: {client_points} PTS - ID Transaksi: {last_transaction_id}",
                                    status="info"
                                )
                            elif response.get("type") == "referral_points":
                                referral_points = response.get("data", {}).get("amount", 0)
                                last_transaction_id = response.get("data", {}).get("last_transaction_id", "N/A")
                                self.account_points[email] = self.account_points.get(email, 0) + referral_points
                                self.print_message(
                                    email, proxy, 
                                    f"Pendapatan Referal: {referral_points} PTS - ID Transaksi: {last_transaction_id}",
                                    status="info"
                                )
                        except Exception as e:
                            self.print_message(email, proxy, f"Koneksi WebSocket terputus: {str(e)}", status="warning")
                            await asyncio.sleep(5)
                            connected = False
                            break
            except Exception as e:
                self.print_message(email, proxy, f"WebSocket tidak terhubung: {str(e)}", status="error")
                await asyncio.sleep(5)
            finally:
                await session.close()

    async def process_connect_vpn(self, email: str, device_id: str, use_proxy: bool):
        proxy = self.get_next_proxy_for_account(email) if use_proxy else None
        max_attempts = 3

        for attempt in range(max_attempts):
            if proxy and not await self.test_proxy(proxy):
                self.log(f"Proxy {proxy} tidak berfungsi untuk {email}.", level="warning")
                proxy = self.rotate_proxy_for_account(email)
                if not proxy and attempt == max_attempts - 1:
                    self.log(f"Tidak ada proxy yang berfungsi untuk {email}. Beralih ke jaringan lokal.", level="warning")
                    proxy = None
                continue
            connect = await self.connect_vpn(email, device_id, proxy)
            if connect:
                return True
            await asyncio.sleep(5)
            proxy = self.rotate_proxy_for_account(email) if use_proxy else None
            if not proxy and attempt == max_attempts - 1:
                self.log(f"Tidak ada proxy yang berfungsi untuk {email}. Beralih ke jaringan lokal.", level="warning")
                connect = await self.connect_vpn(email, device_id, None)
                if connect:
                    return True
        self.log(f"Gagal menghubungkan VPN untuk {email} setelah {max_attempts} percobaan.", level="error")
        return False

    async def main(self):
        try:
            accounts = self.load_accounts()
            if not accounts:
                self.log("Tidak ada akun yang dimuat.", level="error")
                return

            use_proxy = True  # Menggunakan proxy private
            self.clear_terminal()
            self.welcome()
            self.log(
                f"Total Akun: {len(accounts)}",
                level="info"
            )

            if use_proxy:
                await self.load_proxies()

            if not self.proxies and use_proxy:
                self.log("Tidak ada proxy yang tersedia. Menggunakan jaringan lokal.", level="warning")
                use_proxy = False

            self.log("-" * 75, level="info")

            # Proses akun dalam batch
            for i in range(0, len(accounts), self.max_concurrent_tasks):
                batch = accounts[i:i + self.max_concurrent_tasks]
                tasks = []
                for account in batch:
                    email = account.get("Email")
                    user_id = account.get("UserId")
                    device_id = account.get("DeviceId")
                    if not all([email, user_id, device_id]):
                        self.log(f"Data akun tidak valid: {account}", level="error")
                        continue
                    tasks.append(self.connect_websocket(email, user_id, device_id, use_proxy))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(10)

        except Exception as e:
            self.log(f"Error di main: {e}", level="error")
            raise

if __name__ == "__main__":
    try:
        bot = PingVPN()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        logger.info(f"[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ] | "
                    f"{Fore.RED}[ EXIT ] Ping Network - BOT{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Error tak terduga: {e}")
