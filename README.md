# p1ng n3twork

## The risk's yours to bear, I have created tools that can be used by everyone.

<img width="1224" height="798" alt="image" src="https://github.com/user-attachments/assets/a3f25ed6-a3eb-4714-aedf-aa8ef84e8109" />

## 1. Preparation Ping
**1. Hardware requirements** 

`In order to need a Linux server (VPS) with the minimum recommended hardware`
| Requirement                       | Details                         |
|-----------------------------------|---------------------------------|
| RAM                               | 2 GB - up                       |
| CPU/vCPU                          | 2 Core - up                     |
| Storage Space                     | 50 GB - up                      |
| Supported OS                      | Ubuntu 20.04, 22.04, 24.04 LTS  |
| Internet/Processor                | 1 - 100 Mbps |

## 3. Installation & Run P1ngnet

### a. Clone Repository
```
git clone https://github.com/arcxteam/pingnet.git
cd pingnet/js
```
### b. Run Install & Follow Instructions

- Need download [extention](https://chromewebstore.google.com/detail/ping-network-vpn/geeedmdpncfeomhgbjeafcahepjelimg)
- Sign up or login you can put my Refferal at this code bonus **`6D2YPS`**
- Go to `chrome://extensions/?id=geeedmdpncfeomhgbjeafcahepjelimg` and
- Checking `Inspect views:click service worker-Application-Extention-Storage-Local-persist:auth`
- Command this & save
```
nano .env
```
```diff
- USER_ID_1=xxxxx
- DEVICE_ID_1=xxxxx
```
### c. Install depedency
```
npm install
```

### d. Run Executable
```
node index.js
```
- or with pm2 background, install `npm install -g pm2`
```
pm2 start index.js --name pingnet
```

### NOTE

- You dont off this toogle, but you off on extention like on menu `tap to connect`

<img width="838" height="292" alt="image" src="https://github.com/user-attachments/assets/3aa5b9b2-a0af-4c82-be8b-150c2f6ad4ee" />

## 4. Update Usefull Command Logs

```diff
> this command go to help

- pm2 logs pingnet # optional check logs
- pm2 stop pingnet
- pm2 delete pingnet
- pm2 status
- pm2 save
- pm2 -v
```
