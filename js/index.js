const axios = require('axios');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const UserAgent = require('user-agents');
const fs = require('fs');
const path = require('path');
const HttpsProxyAgent = require('https-proxy-agent');
const Fore = require('colors');
require('dotenv').config({ path: path.resolve(__dirname, '.env') });

// Enhanced logger with account number support
const createLogger = (accountNum = '') => ({
  info: (msg) => console.log(`${Fore.green} ✓ ${accountNum} ${msg}${Fore.reset}`),
  warn: (msg) => console.log(`${Fore.yellow} ⚠️ ${accountNum} ${msg}${Fore.reset}`),
  error: (msg) => console.log(`${Fore.red} ✗ ${accountNum} ${msg}${Fore.reset}`),
  success: (msg) => console.log(`${Fore.green} ✅ ${accountNum} ${msg}${Fore.reset}`),
  loading: (msg) => console.log(`${Fore.cyan} ⟳ ${accountNum} ${msg}${Fore.reset}`),
  step: (msg) => console.log(`${Fore.white} ➤ ${accountNum} ${msg}${Fore.reset}`),
  countdown: (msg) => process.stdout.write(`\r${Fore.blue}[⏰]${accountNum} ${msg}${Fore.reset}`)
});

const showBanner = () => {
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
};

// Load accounts from .env with USER_ID_1, DEVICE_ID_1 format
const loadAccounts = () => {
  const accounts = [];
  let i = 1;
  
  while (process.env[`USER_ID_${i}`]) {
    accounts.push({
      number: i,
      userId: process.env[`USER_ID_${i}`],
      deviceId: process.env[`DEVICE_ID_${i}`] || uuidv4()
    });
    i++;
  }

  if (accounts.length === 0) {
    // Fallback to old format if no numbered accounts found
    if (process.env.USER_ID) {
      accounts.push({
        number: 1,
        userId: process.env.USER_ID,
        deviceId: process.env.DEVICE_ID || uuidv4()
      });
    }
  }

  return accounts;
};

// Load proxies from proxy.txt (one per line)
const loadProxies = () => {
  if (!fs.existsSync('proxy.txt')) return [];
  
  return fs.readFileSync('proxy.txt', 'utf8')
    .split('\n')
    .filter(line => line.trim() !== '')
    .map(line => line.trim());
};

const getRandomZoneId = () => Math.floor(Math.random() * 6).toString();

const createConfig = (account, proxy) => {
  const userAgent = new UserAgent({ deviceCategory: 'desktop' });
  const UA_STRING = userAgent.toString();

  return {
    wsUrl: `wss://ws.pingvpn.xyz/pingvpn/v1/clients/${account.userId}/events`,
    fallbackWsUrl: 'wss://ws.whirpoolmarble.com/pingvpn',
    user_id: account.userId,
    device_id: account.deviceId,
    proxy: proxy,
    zoneId: getRandomZoneId(),
    logger: createLogger(`[AKUN ${account.number}]`),
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
      'sec-gpc': '1',
      'user-agent': UA_STRING
    }
  };
};

async function sendAnalyticsEvent(config) {
  try {
    config.logger.loading('Sending analytics event...');
    const payload = {
      client_id: config.device_id,
      events: [{
        name: 'connect_clicked',
        params: {
          session_id: Date.now().toString(),
          engagement_time_msec: 100,
          zone: config.zoneId
        }
      }]
    };
    await axios.post('https://www.google-analytics.com/mp/collect?measurement_id=G-M0F9F7GGW0&api_secret=tdSjjplvRHGSEpXPfPDalA', payload, {
      headers: config.headers
    });
    config.logger.success('Analytics event sent successfully');
  } catch (error) {
    config.logger.error(`Failed to send analytics: ${error.message}`);
  }
}

function connectWebSocket(config) {
  const log = config.logger;
  let ws;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 7000;
  let isAlive = false;
  let currentWsUrl = config.wsUrl;

  const wsOptions = { 
    headers: {
      'accept-language': 'en-US,en;q=0.9,id;q=0.8',
      'user-agent': config.headers['user-agent']
    }
  };

  if (config.proxy) {
    wsOptions.agent = new HttpsProxyAgent(config.proxy);
    log.info(`Using proxy: ${config.proxy}`);
  }

  function establishConnection() {
    log.loading(`Establishing WebSocket connection to ${currentWsUrl}...`);
    ws = new WebSocket(currentWsUrl, wsOptions);

    ws.on('open', () => {
      log.success(`WebSocket connected to ${currentWsUrl}`);
      reconnectAttempts = 0;
      isAlive = true;
      sendAnalyticsEvent(config);
    });

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data);
        log.info(`Received message: ${JSON.stringify(message)}`);
        isAlive = true;
        if (message.type === 'client_points') {
          log.success(`Points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        } else if (message.type === 'referral_points') {
          log.success(`Referral points updated: ${message.data.amount} (Transaction ID: ${message.data.last_transaction_id})`);
        }
      } catch (error) {
        log.error(`Error parsing WebSocket message: ${error.message}`);
      }
    });

    ws.on('close', () => {
      log.warn('WebSocket disconnected');
      isAlive = false;
      attemptReconnect();
    });

    ws.on('error', (error) => {
      log.error(`WebSocket error: ${error.message}`);
      isAlive = false;
      
      if (currentWsUrl === config.wsUrl && config.fallbackWsUrl) {
        log.warn(`Trying fallback WebSocket URL: ${config.fallbackWsUrl}`);
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
      log.step('Sent ping to server');
    }
  }

  const pingInterval = setInterval(() => {
    if (!isAlive && ws && ws.readyState !== WebSocket.CLOSED) {
      log.warn('No messages received, closing connection...');
      ws.close();
    } else {
      sendPing();
    }
  }, 60000);

  function attemptReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) {
      log.error('Max reconnection attempts reached. Stopping reconnection.');
      clearInterval(pingInterval);
      return;
    }

    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
    log.warn(`Reconnecting in ${delay / 1000} seconds... (Attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);

    setTimeout(() => {
      reconnectAttempts++;
      establishConnection();
    }, delay);
  }

  establishConnection();

  return {
    close: () => {
      if (ws) ws.close();
      clearInterval(pingInterval);
    }
  };
}

async function startBot() {
  showBanner();
  
  const accounts = loadAccounts();
  const proxies = loadProxies();
  
  if (accounts.length === 0) {
    console.log(`${Fore.RED}No accounts found in .env${Fore.RESET}`);
    return;
  }

  const connections = [];
  
  for (const account of accounts) {
    const proxy = proxies[account.number - 1] || null;
    const config = createConfig(account, proxy);
    const log = config.logger;
    
    log.step(`Starting bot with user_id: ${config.user_id}`);
    log.info(`Device ID: ${config.device_id}`);
    log.info(`Zone ID: ${config.zoneId}`);
    
    connections.push(connectWebSocket(config));
    
    // Add delay between account initializations
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  process.on('SIGINT', () => {
    console.log('\n');
    const log = createLogger();
    log.warn('Shutting down all connections...');
    connections.forEach(conn => conn.close());
    process.exit(0);
  });
}

startBot().catch(error => {
  console.log(`${Fore.RED}Error: ${error.message}${Fore.RESET}`);
});
