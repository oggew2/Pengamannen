# Börslabbet App - Self-Hosting Guide

Deploy on Proxmox with Cloudflare Tunnel (no port forwarding needed).

## Quick Overview

```
Internet → Cloudflare Tunnel → Proxmox LXC → Docker (Frontend + Backend + SQLite)
```

**Cost: ~$10-15/year** (just the domain, everything else is free)

---

## Prerequisites

- Proxmox VE 8.x+
- Domain on Cloudflare (free tier works)
- GitHub account

---

## Step 1: Create Proxmox LXC

```bash
# On Proxmox host
pveam update
pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst

pct create 200 local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst \
  --hostname borslabbet \
  --memory 2048 \
  --cores 2 \
  --rootfs local-lvm:16 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1

pct start 200
pct enter 200
```

---

## Step 2: Install Docker

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl git

# Docker official install
curl -fsSL https://get.docker.com | sh

# Verify
docker run hello-world
```

---

## Step 3: Deploy the App

```bash
cd /opt
git clone https://github.com/oggew2/Pengamannen.git borslabbet
cd borslabbet

# Create data directory
mkdir -p data

# Start the app
docker compose up -d --build
```

The app is now running locally:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000

---

## Step 4: Cloudflare Tunnel (External Access)

### 4.1 Create Tunnel

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → Networks → Tunnels
2. Click "Create a tunnel" → name it `borslabbet`
3. Copy the tunnel token (starts with `eyJ...`)

### 4.2 Add Cloudflared to Docker Compose

Create `docker-compose.override.yml`:

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=eyJ...YOUR_TOKEN_HERE...
    restart: unless-stopped
    network_mode: host
```

```bash
docker compose up -d
```

### 4.3 Configure Public Hostname

In Cloudflare Dashboard → your tunnel → Public Hostname:

| Subdomain | Domain | Service |
|-----------|--------|---------|
| stocks | yourdomain.com | http://localhost:5173 |
| api.stocks | yourdomain.com | http://localhost:8000 |

Your app is now live at `https://stocks.yourdomain.com` 🎉

---

## Step 5: Auto-Updates (Optional)

### Option A: Maintained Watchtower Fork (Simple)

The original Watchtower is broken with Docker 29+. Use the maintained fork:

```yaml
# Add to docker-compose.override.yml
services:
  watchtower:
    image: nickfedor/watchtower:latest
    container_name: watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400  # Check daily
      - TZ=Europe/Stockholm
    restart: unless-stopped
```

### Option B: What's Up Docker (More Features)

WUD has a web UI and more control over updates:

```yaml
services:
  wud:
    image: ghcr.io/getwud/wud
    container_name: wud
    ports:
      - "3000:3000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WUD_WATCHER_LOCAL_CRON=0 6 * * *  # Check at 6 AM
    restart: unless-stopped
```

Access WUD dashboard at `http://your-server:3000`

---

## Common Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f

# Update manually
git pull && docker compose up -d --build

# Restart single service
docker compose restart backend
```

---

## Troubleshooting

### Tunnel not connecting
```bash
docker logs cloudflared
# Check token is correct in docker-compose.override.yml
```

### Backend errors
```bash
docker logs borslabbet-backend
# Check data/app.db exists
```

### LXC Docker issues
If Docker fails in unprivileged LXC, add to `/etc/pve/lxc/200.conf` on Proxmox host:
```
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
```
Then restart the container.

---

## Security (Optional)

### Restrict Access with Cloudflare Access

1. Zero Trust → Access → Applications → Add
2. Select your hostname
3. Add policy: Allow specific emails only

Your friends will need to authenticate via email before accessing.

---

## Backup

```bash
# Backup database
cp /opt/borslabbet/data/app.db ~/app_backup_$(date +%Y%m%d).db

# Automated daily backup (add to crontab -e)
0 2 * * * cp /opt/borslabbet/data/app.db /opt/backups/app_$(date +\%Y\%m\%d).db
```

---

## References

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [What's Up Docker](https://getwud.github.io/wud/)
- [Watchtower Fork](https://hub.docker.com/r/nickfedor/watchtower)
