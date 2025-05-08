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

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging for PM2
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('pingbot.log'),  # Log to file for PM2 monitoring
        logging.StreamHandler()  # Also log to console
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
        self.max_concurrent_tasks = 10  # Limit concurrent tasks to prevent overload

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message, level="info"):
        """Log messages with timestamp and level."""
        timestamp = datetime.now().astimezone(wib).strftime('%x %X %Z')
        log_message = f"[ {timestamp} ] | {message}"
        if level == "info":
            logger.info(log_message)
        elif level == "error":
            logger.error(log_message)
        elif level == "warning":
            logger.warning(log_message)

    def welcome(self):
        self.log(
            f"{Fore.GREEN + Style.BRIGHT}Auto Ping {Fore.BLUE + Style.BRIGHT}PingVPN Network - BOT\n"
            f"{Fore.GREEN + Style.BRIGHT}Rey? {Fore.YELLOW + Style.BRIGHT}<INI WATERMARK>",
            level="info"
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def load_accounts(self):
        filename = "accounts.json"
        try:
            if not os.path.exists(filename):
                self.log(f"{Fore.RED}File {filename} Not Found.", level="error")
                return []
            with open(filename, 'r') as file:
                data = json.load(file)
                if not isinstance(data, list):
                    self.log(f"{Fore.RED}Invalid format in {filename}. Expected a list.", level="error")
                    return []
                return data
        except json.JSONDecodeError as e:
            self.log(f"{Fore.RED}Failed to parse {filename}: {e}", level="error")
            return []

    async def load_proxies(self):
        """Load private proxies from proxy.txt."""
        filename = "proxy.txt"
        try:
            if not os.path.exists(filename):
                self.log(f"{Fore.RED + Style.BRIGHT}File {filename} Not Found.", level="error")
                return
            with open(filename, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
            
            if not self.proxies:
                self.log(f"{Fore.RED + Style.BRIGHT}No Proxies Found in {filename}.", level="error")
                return

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Proxies Total: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(self.proxies)}{Style.RESET_ALL}",
                level="info"
            )
        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Failed To Load Proxies: {e}", level="error")
            self.proxies = []

    def check_proxy_schemes(self, proxy):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxy.startswith(scheme) for scheme in schemes):
            return proxy
        return f"http://{proxy}"

    def get_next_proxy_for_account(self, email):
        if not self.proxies:
            self.log(f"No proxies available for account {email}.", level="warning")
            return None
        if email not in self.account_proxies:
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[email] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[email]

    def rotate_proxy_for_account(self, email):
        if not self.proxies:
            self.log(f"No proxies available to rotate for account {email}.", level="warning")
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

    def print_message(self, account, proxy, color, message):
        proxy_display = proxy or "No Proxy"
        self.log(
            f"{Fore.CYAN + Style.BRIGHT}[ Account: {Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT}{self.mask_account(account)}{Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT} - {Style.RESET_ALL}"
            f"{Fore.CYAN + Style.BRIGHT}Proxy: {Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT}{proxy_display}{Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT} - {Style.RESET_ALL}"
            f"{Fore.CYAN + Style.BRIGHT}Status: {Style.RESET_ALL}"
            f"{color + Style.BRIGHT}{message}{Style.RESET_ALL}"
            f"{Fore.CYAN + Style.BRIGHT}]{Style.RESET_ALL}",
            level="info"
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
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    self.log(f"Retrying VPN connection for {email} after {delay}s: {str(e)}", level="warning")
                    await asyncio.sleep(delay)
                    continue
                self.print_message(email, proxy, Fore.RED, f"Connect VPN Failed: {Fore.YELLOW + Style.BRIGHT}{str(e)}")
                return False

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
                            self.print_message(email, proxy, Fore.GREEN, "VPN Connected")
                            connected = True

                    while connected:
                        try:
                            response = await wss.receive_json()
                            if response.get("type") == "client_points":
                                client_points = response.get("data", {}).get("amount", 0)
                                last_transaction_id = response.get("data", {}).get("last_transaction_id", "N/A")
                                self.print_message(
                                    email, proxy, Fore.GREEN, 
                                    f"Client Earning {Fore.WHITE + Style.BRIGHT}{client_points} PTS{Style.RESET_ALL} "
                                    f"{Fore.MAGENTA + Style.BRIGHT}-{Style.RESET_ALL} "
                                    f"{Fore.CYAN + Style.BRIGHT}Transaction Id: {Style.RESET_ALL}"
                                    f"{Fore.WHITE + Style.BRIGHT}{last_transaction_id}{Style.RESET_ALL}"
                                )
                            elif response.get("type") == "referral_points":
                                referral_points = response.get("data", {}).get("amount", 0)
                                last_transaction_id = response.get("data", {}).get("last_transaction_id", "N/A")
                                self.print_message(
                                    email, proxy, Fore.GREEN, 
                                    f"Referral Earning {Fore.WHITE + Style.BRIGHT}{referral_points} PTS{Style.RESET_ALL} "
                                    f"{Fore.MAGENTA + Style.BRIGHT}-{Style.RESET_ALL} "
                                    f"{Fore.CYAN + Style.BRIGHT}Transaction Id: {Style.RESET_ALL}"
                                    f"{Fore.WHITE + Style.BRIGHT}{last_transaction_id}{Style.RESET_ALL}"
                                )
                        except Exception as e:
                            self.print_message(email, proxy, Fore.YELLOW, f"Websocket Connection Closed: {Fore.RED + Style.BRIGHT}{str(e)}")
                            await asyncio.sleep(5)
                            connected = False
                            break
            except Exception as e:
                self.print_message(email, proxy, Fore.RED, f"Websocket Not Connected: {Fore.YELLOW + Style.BRIGHT}{str(e)}")
                await asyncio.sleep(5)
            finally:
                await session.close()

    async def process_connect_vpn(self, email: str, device_id: str, use_proxy: bool):
        proxy = self.get_next_proxy_for_account(email) if use_proxy else None
        connect = None
        max_attempts = 3

        for attempt in range(max_attempts):
            connect = await self.connect_vpn(email, device_id, proxy)
            if connect:
                return True
            await asyncio.sleep(5)
            proxy = self.rotate_proxy_for_account(email) if use_proxy else None
        self.log(f"Failed to connect VPN for {email} after {max_attempts} attempts.", level="error")
        return False

    async def main(self):
        try:
            accounts = self.load_accounts()
            if not accounts:
                self.log(f"{Fore.RED + Style.BRIGHT}No Accounts Loaded.", level="error")
                return

            use_proxy = True  # Hardcode to use private proxies (equivalent to option 2)
            self.clear_terminal()
            self.welcome()
            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}",
                level="info"
            )

            if use_proxy:
                await self.load_proxies()

            if not self.proxies and use_proxy:
                self.log(f"{Fore.RED + Style.BRIGHT}No proxies available. Exiting.", level="error")
                return

            self.log(f"{Fore.CYAN + Style.BRIGHT}-" * 75, level="info")

            # Process accounts in batches to avoid overwhelming the system
            for i in range(0, len(accounts), self.max_concurrent_tasks):
                batch = accounts[i:i + self.max_concurrent_tasks]
                tasks = []
                for account in batch:
                    if account:
                        email = account.get("Email")
                        user_id = account.get("UserId")
                        device_id = account.get("DeviceId")
                        if not all([email, user_id, device_id]):
                            self.log(f"Invalid account data: {account}", level="error")
                            continue
                        tasks.append(self.connect_websocket(email, user_id, device_id, use_proxy))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(10)  # Delay between batches

        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Error in main: {e}", level="error")
            raise

if __name__ == "__main__":
    try:
        bot = PingVPN()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        logger.info(f"[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ] | "
                    f"{Fore.RED + Style.BRIGHT}[ EXIT ] PingVPN Network - BOT{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
