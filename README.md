# 🏆 Promoter Performance Tracker

A full-stack WebApp that tracks promoter performance by automatically extracting usernames from app registration screenshots via OCR, performing duplicate detection, and maintaining a real-time leaderboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite + React 18 + TypeScript |
| Styling | Vanilla CSS (Dark Glassmorphism) |
| Backend | Python FastAPI |
| Database | SQLite + SQLAlchemy |
| OCR Engine | EasyOCR |

## Quick Start

### Prerequisites
- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> **Note:** The first API call that triggers OCR will download the EasyOCR model (~100MB). Subsequent calls will be faster.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app will be available at **http://localhost:3000**.

## Usage

### For Promoters
1. Open `http://localhost:3000/upload`
2. Enter your **Name** and **IC Number** (saved automatically for next time)
3. Upload one or more screenshots of the App profile page
4. View OCR results — valid registrations are counted on the leaderboard

### For Admins
1. Go to `http://localhost:3000/admin`
2. Enter PIN: **`1234`**
3. View all submissions, filter by status, and preview uploaded images

### Leaderboard
- Visit `http://localhost:3000` to see real-time rankings
- Auto-refreshes every 5 seconds
- Only valid (non-duplicate) registrations are counted

## Project Structure

```
promoter-tracker/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Configuration constants
│   ├── database.py           # SQLAlchemy models
│   ├── models.py             # Pydantic schemas
│   ├── ocr_service.py        # EasyOCR wrapper
│   ├── utils.py              # File management utilities
│   ├── routes/
│   │   ├── upload.py         # Upload + OCR pipeline
│   │   ├── leaderboard.py    # Leaderboard data
│   │   └── admin.py          # Admin authentication
│   ├── requirements.txt
│   └── uploads/              # Image storage
│
└── frontend/
    ├── src/
    │   ├── pages/            # Page components
    │   ├── components/       # Reusable UI components
    │   ├── hooks/            # Custom React hooks
    │   ├── utils/            # API client, compression, storage
    │   └── index.css         # Design system
    └── package.json
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload screenshots for OCR processing |
| GET | `/api/leaderboard` | Get ranked promoter leaderboard |
| POST | `/api/admin/login` | Admin PIN authentication |
| GET | `/api/admin/stats` | Admin dashboard data (requires token) |
| GET | `/api/health` | Health check |

## File Storage

- ✅ Valid uploads → `/uploads/Promoter_{Name}/`
- ❌ Duplicates & failures → `/uploads/duplicate-Promoter_{Name}/`
