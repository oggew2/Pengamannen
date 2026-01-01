# Börslabbet App - Proxmox Deployment Guide

Complete guide to deploy the app on Proxmox with secure external access via Cloudflare Tunnel and automatic updates.

## Architecture Overview

```
Internet → Cloudflare Tunnel → Proxmox LXC → Docker Containers
                                    ↓
                            ┌───────────────┐
                            │   Frontend    │ :5173
                            │   (Vite)      │
                            └───────┬───────┘
                                    │
                            ┌───────▼───────┐
                            │   Backend     │ :8000
                            │   (FastAPI)   │
                            └───────┬───────┘
                                    │
                            ┌───────▼───────┐
                            │   SQLite DB   │
                            │   (app.db)    │
                            └───────────────┘
```

## Prerequisites

- Proxmox VE 8.x installed
- Domain name (for Cloudflare Tunnel)
- Cloudflare account (free tier works)
- GitHub account (for auto-updates)

---

## Part 1: Proxmox LXC Setup

### 1.1 Create LXC Container

```bash
# SSH into Proxmox host
ssh root@your-proxmox-ip

# Download Ubuntu 24.04 template
pveam update
pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst

# Create LXC container (adjust ID and storage as needed)
pct create 200 local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst \
  --hostname borslabbet \
  --memory 2048 \
  --cores 2 \
  --rootfs local-lvm:16 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1
```

### 1.2 Configure LXC for Docker

Edit the container config to enable Docker support:

```bash
# On Proxmox host
nano /etc/pve/lxc/200.conf
```

Add these lines:
```
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
```

### 1.3 Start and Enter Container

```bash
pct start 200
pct enter 200
```

### 1.4 Install Docker in LXC

```bash
# Update system
apt update && apt upgrade -y

# Install prerequisites
apt install -y ca-certificates curl gnupg lsb-release git

# Add Docker GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify Docker works
docker run hello-world
```

---

## Part 2: Deploy the Application

### 2.1 Clone Repository

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/borslabbet-app.git
cd borslabbet-app
```

### 2.2 Create Production Docker Compose

```bash
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: borslabbet-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
      - DATA_SYNC_ENABLED=true
      - DATA_SYNC_HOUR=6
      - TZ=Europe/Stockholm
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]
      interval: 60s
      timeout: 10s
      retries: 3
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  frontend:
    build: 
      context: ./frontend
      args:
        - VITE_API_BASE_URL=https://YOUR_DOMAIN.com
    container_name: borslabbet-frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    restart: unless-stopped
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  # Auto-update containers when new images are pushed
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=300
      - WATCHTOWER_INCLUDE_STOPPED=true
      - TZ=Europe/Stockholm
    restart: unless-stopped

  # Cloudflare Tunnel for secure external access
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    restart: unless-stopped
    depends_on:
      - frontend
      - backend

volumes:
  data:
EOF
```

### 2.3 Create Environment File

```bash
cat > .env << 'EOF'
CLOUDFLARE_TUNNEL_TOKEN=your_tunnel_token_here
EOF
chmod 600 .env
```

### 2.4 Update Frontend for Production

Create production Dockerfile for frontend:

```bash
cat > frontend/Dockerfile.prod << 'EOF'
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF

cat > frontend/nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
```

### 2.5 Build and Start

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

---

## Part 3: Cloudflare Tunnel Setup (Secure External Access)

Cloudflare Tunnel creates an outbound-only connection - no ports need to be opened on your router.

### 3.1 Create Cloudflare Tunnel

1. Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. Navigate to **Networks → Tunnels**
3. Click **Create a tunnel**
4. Name it `borslabbet`
5. Copy the tunnel token

### 3.2 Configure Tunnel Token

```bash
# Update .env with your token
nano /opt/borslabbet-app/.env
# Set: CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiYWJj...
```

### 3.3 Configure Public Hostname

In Cloudflare Dashboard:

1. Go to your tunnel → **Public Hostname**
2. Add hostname:
   - **Subdomain**: `stocks` (or your choice)
   - **Domain**: `yourdomain.com`
   - **Service**: `http://frontend:5173`

3. Add another for API:
   - **Subdomain**: `api.stocks`
   - **Domain**: `yourdomain.com`
   - **Service**: `http://backend:8000`

### 3.4 Restart with Tunnel

```bash
docker compose -f docker-compose.prod.yml up -d
```

Your app is now accessible at `https://stocks.yourdomain.com`

---

## Part 4: Auto-Updates from GitHub

### Option A: Watchtower + GitHub Container Registry (Recommended)

#### 4.1 Create GitHub Actions Workflow

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Build and Push Docker Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-backend:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-backend:latest

  build-frontend:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile.prod
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-frontend:latest
          build-args: |
            VITE_API_BASE_URL=https://api.stocks.yourdomain.com
```

#### 4.2 Update docker-compose to use GHCR images

```yaml
services:
  backend:
    image: ghcr.io/YOUR_USERNAME/borslabbet-app-backend:latest
    # ... rest of config

  frontend:
    image: ghcr.io/YOUR_USERNAME/borslabbet-app-frontend:latest
    # ... rest of config
```

#### 4.3 Authenticate Docker with GHCR

```bash
# Create GitHub Personal Access Token with packages:read scope
# Then login:
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

Watchtower will now automatically pull new images when you push to GitHub.

### Option B: Webhook-based Updates (Alternative)

```bash
# Install webhook handler
cat > /opt/borslabbet-app/update.sh << 'EOF'
#!/bin/bash
cd /opt/borslabbet-app
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
EOF
chmod +x /opt/borslabbet-app/update.sh
```

---

## Part 5: Security Hardening

### 5.1 Cloudflare Access (Optional - Restrict to Friends)

1. In Cloudflare Zero Trust → **Access → Applications**
2. Create application for `stocks.yourdomain.com`
3. Add policy: **Allow** → **Emails ending in** → `@gmail.com` (or specific emails)

Your friends will need to authenticate via email before accessing.

### 5.2 Firewall Rules

```bash
# In LXC container - only allow local network + Cloudflare
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow from 192.168.0.0/16  # Local network
ufw enable
```

### 5.3 Automatic Security Updates

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

---

## Part 6: Monitoring & Maintenance

### 6.1 View Logs

```bash
# All containers
docker compose -f docker-compose.prod.yml logs -f

# Specific container
docker logs -f borslabbet-backend
```

### 6.2 Check Status

```bash
docker compose -f docker-compose.prod.yml ps
```

### 6.3 Manual Update

```bash
cd /opt/borslabbet-app
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### 6.4 Backup Database

```bash
# Create backup script
cat > /opt/borslabbet-app/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/borslabbet"
mkdir -p $BACKUP_DIR
cp /opt/borslabbet-app/data/app.db "$BACKUP_DIR/app_$(date +%Y%m%d_%H%M%S).db"
# Keep only last 7 backups
ls -t $BACKUP_DIR/app_*.db | tail -n +8 | xargs -r rm
EOF
chmod +x /opt/borslabbet-app/backup.sh

# Add to cron (daily at 2 AM)
echo "0 2 * * * /opt/borslabbet-app/backup.sh" | crontab -
```

---

## Quick Reference

| Component | URL | Port |
|-----------|-----|------|
| Frontend | https://stocks.yourdomain.com | 5173→80 |
| Backend API | https://api.stocks.yourdomain.com | 8000 |
| Health Check | /v1/health | - |
| API Docs | /docs | - |

### Commands Cheat Sheet

```bash
# Start
docker compose -f docker-compose.prod.yml up -d

# Stop
docker compose -f docker-compose.prod.yml down

# Restart
docker compose -f docker-compose.prod.yml restart

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Update
git pull && docker compose -f docker-compose.prod.yml up -d --build

# Check Watchtower logs
docker logs watchtower

# Check tunnel status
docker logs cloudflared
```

---

## Troubleshooting

### Container won't start
```bash
docker compose -f docker-compose.prod.yml logs backend
```

### Tunnel not connecting
```bash
docker logs cloudflared
# Verify token in .env file
```

### Database issues
```bash
# Check database exists
ls -la /opt/borslabbet-app/data/

# Reset database (WARNING: loses data)
rm /opt/borslabbet-app/data/app.db
docker compose -f docker-compose.prod.yml restart backend
```

### Watchtower not updating
```bash
docker logs watchtower
# Check GHCR authentication
docker pull ghcr.io/YOUR_USERNAME/borslabbet-app-backend:latest
```

---

## Cost Summary

| Service | Cost |
|---------|------|
| Proxmox | Free (open source) |
| Cloudflare Tunnel | Free |
| Cloudflare Access | Free (up to 50 users) |
| GitHub Container Registry | Free (public repos) |
| Domain | ~$10-15/year |

**Total: ~$10-15/year** (just the domain)

---

*Content was rephrased for compliance with licensing restrictions.*

References:
[1] Cloudflare Tunnel Documentation - https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
[2] Watchtower GitHub - https://github.com/containrrr/watchtower
[3] GitHub Container Registry - https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
