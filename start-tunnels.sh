#!/bin/bash
# Start app with Cloudflare tunnels

cd "$(dirname "$0")"

# Start backend first
docker compose up -d backend

# Wait for backend to be healthy
echo "Waiting for backend..."
sleep 5

# Start backend tunnel and capture URL
docker compose up -d tunnel-backend
sleep 3

# Get backend tunnel URL
BACKEND_URL=$(docker compose logs tunnel-backend 2>&1 | grep -o 'https://[^[:space:]]*\.trycloudflare\.com' | head -1)

if [ -z "$BACKEND_URL" ]; then
    echo "Failed to get backend tunnel URL. Check: docker compose logs tunnel-backend"
    exit 1
fi

echo "Backend tunnel: $BACKEND_URL"

# Start frontend with backend URL
BACKEND_TUNNEL_URL=$BACKEND_URL docker compose up -d frontend

# Start frontend tunnel
docker compose up -d tunnel-frontend
sleep 3

# Get frontend tunnel URL
FRONTEND_URL=$(docker compose logs tunnel-frontend 2>&1 | grep -o 'https://[^[:space:]]*\.trycloudflare\.com' | head -1)

echo ""
echo "==================================="
echo "Share this URL with your friends:"
echo "Frontend: $FRONTEND_URL"
echo "Backend API: $BACKEND_URL"
echo "==================================="
