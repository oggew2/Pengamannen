#!/bin/bash
# Quick deployment script for Börslabbet App

echo "🚀 Deploying Börslabbet App with Docker..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build and start services
echo "📦 Building Docker images..."
docker compose build

echo "🔄 Starting services..."
docker compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running at http://localhost:8000"
else
    echo "⚠️  Backend may still be starting..."
fi

if curl -f http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is running at http://localhost:5173"
else
    echo "⚠️  Frontend may still be starting..."
fi

echo ""
echo "🎉 Deployment complete!"
echo "📊 Frontend: http://localhost:5173"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "💡 To sync data: curl -X POST http://localhost:8000/data/sync-now"
echo "🛑 To stop: docker compose down"
