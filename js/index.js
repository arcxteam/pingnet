const axios = require('axios');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const UserAgent = require('user-agents');
const fs = require('fs');
const path = require('path');
const Fore = require('colors');
require('dotenv').config({ path: path.resolve(__dirname, '.env') });

const logger = {
  info: (msg) => console.log(`${Fore.green}[✓] ${msg}${Fore.reset}`),
  warn: (msg) => console.log(`${Fore.yellow}[⚠️] ${msg}${Fore.reset}`),
  error: (msg) => console.log(`${Fore.red}[✗] ${msg}${Fore.reset}`),
  success: (msg) => console.log(`${Fore.green}[✅] ${msg}${Fore.reset}`),
  loading: (msg) => console.log(`${Fore.cyan}[⟳] ${msg}${Fore.reset}`),
  step: (msg) => console.log(`${Fore.white}[➤] ${msg}${Fore.reset}`),
  countdown: (msg) => process.stdout.write(`\r${Fore.blue}[⏰] ${msg}${Fore.reset}`),
  banner: () => {
    console.log(`${Fore.GREEN}============================ WELCOME TO DAPPs ============================${Fore.RESET}`);
    console.log(`${Fore.YELLOW}
 ██████╗██╗   ██╗ █████╗ ███╗   ██╗███╗   ██╗ ██████╗ ██████╗ ███████╗
██╔════╝██║   ██║██╔══██╗████╗  ██║████╗  ██║██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║███████║██╔██╗ ██║██╔██╗ ██║██║   ██║██║  ██║█████╗  
██║     ██║   ██║██╔══██║██║╚██╗██║██║╚██╗██║██║   ██║██║  ██║██╔══╝  
╚██████╗╚██████╔╝██║  ██║██║ ╚████║██║ ╚████║╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝
${Fore.RESET}`);
    console.log(`${Fore.CYAN}=========================================================================${Fore.RESET}`);
    console.log(`${Fore.MAGENTA}       Welcome to Greyscope&Co Onchain Testnet & Mainnet Interactive   ${Fore.RESET}`);
    console.log(`${Fore.YELLOW}           - CUANNODE By Greyscope&Co, Credit By Arcxteam -     ${Fore.RESET}`);
    console.log(`${Fore.CYAN}=========================================================================${Fore.RESET}`);
  }
};

// Load multiple accounts from .env or proxy.txt if available
let accounts = [];
if (fs.existsSync('proxy.txt')) {
  try {
    const proxyContent = fs.readFileSync('proxy.txt', 'utf8');
    accounts = proxyContent.split('\n')
      .filter(line => line.trim() !== '')
      .map(line => {
        const [userId, deviceId] = line.split(':').map(item => item.trim());
        return { userId, deviceId: deviceId || uuidv4() };
      });
    logger.success(`Loaded ${accounts.length} accounts from proxy.txt`);
  } catch (error) {
    logger.error(`Error reading proxy.txt: ${error.message}`);
  }
}

// If no accounts loaded from proxy.txt, use .env
if (accounts.length === 0) {
  const USER_ID = process.env.USER_ID || '00000';
  let DEVICE_ID = process.env.DEVICE_ID;

  if (!DEVICE_ID) {
    DEVICE_ID = uuidv4();
    const envContent = fs.existsSync('.env')
      ? fs.readFileSync('.env', 'utf8').replace(/DEVICE_ID=.*/g, '') + `\nDEVICE_ID=${DEVICE_ID}\n`
      : `USER_ID=${USER_ID}\nDEVICE_ID=${DEVICE_ID}\n`;
    fs.writeFileSync('.env', envContent.trim());
    logger.success(`Generated and saved new device_id: ${DEVICE_ID}`);
  }

  accounts.push({ userId: USER_ID, deviceId: DEVICE_ID });
}

const getRandomZoneId = () => Math.floor(Math.random() * 6).toString();

const userAgent = new UserAgent({ deviceCategory: 'desktop' });
const UA_STRING = userAgent.toString();

const createConfig = (userId, deviceId) => ({
  wsUrl: `wss://ws.pingvpn.xyz/pingvpn/v1/clients/${userId}/events`,
  fallbackWsUrl: 'wss://ws.whirpoolmarble.com/pingvpn',
  user_id: userId,
  device_id: deviceId,
  proxy: {
    zoneId: getRandomZoneId()
  },
  headers: {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,id;q=0.8',
    'content-type': 'text/plain;charset=UTF-8',
    'sec-ch-ua': userAgent.data.userAgent,
    'sec-ch-ua-mobile': userAgent.data.isMobile ? '?1' : '?0',
    'sec-ch-ua-platform': `"${userAgent.data.platform}"`,
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'none',
    'sec-fetch-storage-access': 'active',
    'sec-gpc': '1'
  }
});

const WS_HEADERS = {
  'accept-language': 'en-US,en;q=0.9,id;q=0.8',
  'cache-control': 'no-cache',
  'pragma': 'no-cache',
  'user-agent': UA_STRING
};

async function sendAnalyticsEvent(config) {
  try {
    logger.loading(`[${config.user_id}] Sending analytics event...`);
    const payload = {
      client_id: config.device_id,
      events: [{
        name: 'connect_clicked',
        params: {
          session_id: Date.now().toString(),
          engagement_time_msec: 100,
          zone: config.proxy.zoneId
        }
      }]
    };
    await axios.post('https://www.google-analytics.com/mp/collect?measurement_id=G-M0F9F7GGW0&api_secret=tdSjjplvRHGSEpXPfPDalA', payload, {
      headers: config.headers
    });
    logger.success(`[${config.user_id}] Analytics event sent successfully`);
  } catch (error) {
    logger.error(`[${config.user_id}] Failed to send analytics: ${error.message}`);
  }
}

function connectWebSocket(config) {
  let ws;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 7000;
  let isAlive = false;
  let currentWsUrl = config.wsUrl;

  function establishConnection() {
    logger.loading(`[${config.user_id}] Establishing WebSocket connection to ${currentWsUrl}...`);
    ws = new WebSocket(currentWsUrl, { headers: WS_HEADERS });

    ws.on('open', () => {
      logger.success(`[${config.user_id}] WebSocket connected to ${currentWsUrl}`);
      reconnectAttempts = 0;
      isAlive = true;
      sendAnalyticsEvent(config);
    });

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data);
        logger.info(`[${config.user_id}] Received message: ${JSON.stringify(message)}`);
        isAlive = true;
        if (message.type === 'client_points') {
          logger.success(`[${config.user_id}] Points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        } else if (message.type === 'referral_points') {
          logger.success(`[${config.user_id}] Referral points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        }
      } catch (error) {
        logger.error(`[${config.user_id}] Error parsing WebSocket message: ${error.message}`);
      }
    });

    ws.on('close', () => {
      logger.warn(`[${config.user_id}] WebSocket disconnected`);
      isAlive = false;
      attemptReconnect();
    });

    ws.on('error', (error) => {
      logger.error(`[${config.user_id}] WebSocket error: ${error.message}`);
      isAlive = false;
      
      // Try fallback URL if main URL fails
      if (currentWsUrl === config.wsUrl && config.fallbackWsUrl) {
        logger.warn(`[${config.user_id}] Trying fallback WebSocket URL: ${config.fallbackWsUrl}`);
        currentWsUrl = config.fallbackWsUrl;
        setTimeout(establishConnection, 1000);
      } else {
        attemptReconnect();
      }
    });
  }

  function sendPing() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
      logger.step(`[${config.user_id}] Sent ping to server`);
    }
  }

  setInterval(() => {
    if (!isAlive && ws && ws.readyState !== WebSocket.CLOSED) {
      logger.warn(`[${config.user_id}] No messages received, closing connection...`);
      ws.close();
    } else {
      sendPing();
    }
  }, 60000);

  function attemptReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) {
      logger.error(`[${config.user_id}] Max reconnection attempts reached. Stopping reconnection.`);
      return;
    }

    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
    logger.warn(`[${config.user_id}] Reconnecting in ${delay / 1000} seconds... (Attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);

    setTimeout(() => {
      reconnectAttempts++;
      establishConnection();
    }, delay);
  }

  establishConnection();

  return ws;
}

async function startBot() {
  logger.banner();
  
  for (const account of accounts) {
    const config = createConfig(account.userId, account.deviceId);
    logger.step(`Starting bot with user_id: ${config.user_id}, device_id: ${config.device_id}`);
    logger.info(`Using User-Agent: ${UA_STRING}`);
    logger.info(`Selected random zoneId: ${config.proxy.zoneId}`);

    connectWebSocket(config);
    
    // Add small delay between account initializations
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

process.on('SIGINT', () => {
  logger.warn('Shutting down bot...');
  process.exit(0);
});

startBot().catch((error) => {
  logger.error(`Bot startup failed: ${error.message}`);
});
