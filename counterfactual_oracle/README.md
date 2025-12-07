# Counterfactual Financial Oracle

A production-ready web application for counterfactual financial analysis using multi-agent AI systems.

## 🏗️ Architecture

A production-ready full-stack web application:

- **Backend**: FastAPI (Python) with SQLAlchemy
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Database**: SQLite (dev) / PostgreSQL (prod)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Initialize database:
```bash
python init_db.py
```

5. Run backend server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API will be available at `http://localhost:8000`
API docs: `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run development server:
```bash
npm run dev
```

Frontend will be available at `http://localhost:5173`

## 📁 Project Structure

```
counterfactual_oracle/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py        # FastAPI app entry point
│   │   ├── core/          # Configuration, database
│   │   ├── api/           # API routes and schemas
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic services
│   │   └── domain/        # Domain logic (Monte Carlo, agents)
│   ├── requirements.txt
│   └── README.md
├── frontend/               # React frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── components/   # Reusable components
│   │   ├── hooks/        # Custom hooks
│   │   └── lib/          # API client, types
│   ├── package.json
│   └── README.md
└── src/                    # Original domain logic (preserved)
```

## 🔑 Environment Variables

### Backend (.env)

```env
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
LANDINGAI_API_KEY=...
DATABASE_URL=sqlite:///./counterfactual.db
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=["http://localhost:5173"]
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
```

## 📡 API Endpoints

### Reports
- `POST /api/reports/upload` - Upload PDF or JSON
- `GET /api/reports/{id}` - Get report details
- `GET /api/reports` - List all reports

### Scenarios
- `POST /api/scenarios` - Create scenario (triggers analysis)
- `GET /api/scenarios/{id}` - Get scenario details
- `GET /api/scenarios/{id}/status` - Poll scenario status
- `POST /api/scenarios/{id}/report` - Generate PDF report

## 🎯 Features

- ✅ PDF extraction via Landing AI ADE
- ✅ Monte Carlo simulation (10,000 scenarios)
- ✅ Multi-agent debate (OpenAI Optimist vs DeepSeek Skeptic)
- ✅ Adversarial validation with hallucination prevention
- ✅ Interactive charts and visualizations
- ✅ PDF report generation
- ✅ Real-time status polling

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 📝 Development Notes

- All financial math is preserved in pure Python (`backend/app/domain/logic.py`)
- Domain logic migrated from `src/` to `backend/app/domain/`
- Background jobs use FastAPI `BackgroundTasks` (can upgrade to RQ/Celery for production)
- Database: SQLite for local dev, PostgreSQL for production

## 📄 License

MIT

