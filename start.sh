#!/usr/bin/env bash
# ── NewsIntel Quick Start Script ──────────────────────────────────────────────
# Run this from the project root: bash start.sh
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       NewsIntel — Intelligence Platform      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install from python.org"
    exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
    echo "❌ Node.js not found. Install from nodejs.org"
    exit 1
fi

echo "✅ Python and Node.js found"
echo ""

# Backend setup
echo "── Setting up backend ──"
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

echo "Installing TextBlob corpora..."
python -c "import textblob; textblob.download_corpora(quiet=True)" 2>/dev/null || true

echo "Installing Playwright browsers (for crawl4ai)..."
playwright install chromium 2>/dev/null || echo "⚠ Playwright install failed — crawl4ai will use fallback mode"

echo "✅ Backend ready"
echo ""

# Start backend in background
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "🚀 Backend started (PID: $BACKEND_PID) → http://localhost:8000"
echo ""

# Wait for backend to be ready
sleep 3

# Frontend setup
echo "── Setting up frontend ──"
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install --silent
fi

echo "✅ Frontend ready"
echo ""
echo "🚀 Starting frontend → http://localhost:3000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Open: http://localhost:3000"
echo "  API:  http://localhost:8000/docs"
echo "  Stop: Ctrl+C"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Trap Ctrl+C to kill backend
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT

# Start frontend (foreground)
npm start
