const axios = require('axios');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const UserAgent = require('user-agents');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '.env') });

const colors = {
  reset: "\x1b[0m",
  cyan: "\x1b[36m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  white: "\x1b[37m",
  bold: "\x1b[1m"
};

const logger = {
  info: (msg) => console.log(`${colors.green}[✓] ${msg}${colors.reset}`),
  warn: (msg) => console.log(`${colors.yellow}[⚠️] ${msg}${colors.reset}`),
  error: (msg) => console.log(`${colors.red}[✗] ${msg}${colors.reset}`),
  success: (msg) => console.log(`${colors.green}[✅] ${msg}${colors.reset}`),
  loading: (msg) => console.log(`${colors.cyan}[⟳] ${msg}${colors.reset}`),
  step: (msg) => console.log(`${colors.white}[➤] ${msg}${colors.reset}`),
  countdown: (msg) => process.stdout.write(`\r${colors.blue}[⏰] ${msg}${colors.reset}`),
  banner: () => {
    const { cyan, magenta, reset } = colors;
    console.log(magenta + '=============================================' + reset);
    console.log(cyan + '  FOLLOW ME ' + reset);
    console.log(cyan + '       CUANNODE from Insider' + reset);
    console.log(magenta + '=============================================' + reset);
    console.log();
  }
};

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

const getRandomZoneId = () => Math.floor(Math.random() * 6).toString(); 
const ZONE_ID = getRandomZoneId();

const userAgent = new UserAgent({ deviceCategory: 'desktop' });
const UA_STRING = userAgent.toString();

const CONFIG = {
  wsUrl: `wss://ws.pingvpn.xyz/pingvpn/v1/clients/${USER_ID}/events`, 
  user_id: USER_ID,
  device_id: DEVICE_ID,
  proxy: {
    zoneId: ZONE_ID 
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
};

const WS_HEADERS = {
  'accept-language': 'en-US,en;q=0.9,id;q=0.8',
  'cache-control': 'no-cache',
  'pragma': 'no-cache',
  'user-agent': UA_STRING
};

async function sendAnalyticsEvent() {
  try {
    logger.loading('Sending analytics event...');
    const payload = {
      client_id: CONFIG.device_id,
      events: [{
        name: 'connect_clicked',
        params: {
          session_id: Date.now().toString(),
          engagement_time_msec: 100,
          zone: CONFIG.proxy.zoneId 
        }
      }]
    };
    await axios.post('https://www.google-analytics.com/mp/collect?measurement_id=G-M0F9F7GGW0&api_secret=tdSjjplvRHGSEpXPfPDalA', payload, {
      headers: CONFIG.headers
    });
    logger.success('Analytics event sent successfully');
  } catch (error) {
    logger.error(`Failed to send analytics: ${error.message}`);
  }
}

function connectWebSocket() {
  let ws;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 5000; 
  let isAlive = false;

  function establishConnection() {
    logger.loading('Establishing WebSocket connection...');
    ws = new WebSocket(CONFIG.wsUrl, { headers: WS_HEADERS });

    ws.on('open', () => {
      logger.success(`WebSocket connected to ${CONFIG.wsUrl}`);
      reconnectAttempts = 0;
      isAlive = true;
      sendAnalyticsEvent();
    });

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data);
        logger.info(`Received message: ${JSON.stringify(message)}`);
        isAlive = true;
        if (message.type === 'client_points') {
          logger.success(`Points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        } else if (message.type === 'referral_points') {
          logger.success(`Referral points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        }
      } catch (error) {
        logger.error(`Error parsing WebSocket message: ${error.message}`);
      }
    });

    ws.on('close', () => {
      logger.warn('WebSocket disconnected');
      isAlive = false;
      attemptReconnect();
    });

    ws.on('error', (error) => {
      logger.error(`WebSocket error: ${error.message}`);
      isAlive = false;
    });
  }

  function sendPing() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
      logger.step('Sent ping to server');
    }
  }

  setInterval(() => {
    if (!isAlive && ws && ws.readyState !== WebSocket.CLOSED) {
      logger.warn('No messages received, closing connection...');
      ws.close();
    } else {
      sendPing();
    }
  }, 60000); 

  function attemptReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) {
      logger.error('Max reconnection attempts reached. Stopping reconnection.');
      return;
    }

    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
    logger.warn(`Reconnecting in ${delay / 1000} seconds... (Attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);

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
  logger.step(`Starting bot with user_id: ${CONFIG.user_id}, device_id: ${CONFIG.device_id}`);
  logger.info(`Using User-Agent: ${UA_STRING}`);
  logger.info(`Selected random zoneId: ${CONFIG.proxy.zoneId}`);

  connectWebSocket();
}

process.on('SIGINT', () => {
  logger.warn('Shutting down bot...');
  process.exit(0);
});

startBot().catch((error) => {
  logger.error(`Bot startup failed: ${error.message}`);
});
