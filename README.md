# Mona funding matcher

Matches small businesses with grants and loans they may qualify for, using the three CSV datasets in `data/`. Each result shows an eligibility status, a relevance score, and the reasons for both.

- `backend/` — Python + FastAPI API
- `frontend/` — React + TypeScript + Vite UI
- `data/` — the three Mona CSV datasets (read-only)

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer

## Setup (Windows PowerShell)

Run each block from the repository root.

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### Frontend

```powershell
cd frontend
npm install
```

## Run

Start the API (terminal 1):

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Start the UI (terminal 2):

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173. The API documentation is at http://localhost:8000/docs, and http://localhost:8000/api/meta shows how many rows were loaded from each CSV.

Always start the API with `.venv\Scripts\python -m uvicorn`, not the bare `uvicorn` command. A bare `uvicorn` may resolve to a copy installed in your system Python, which does not have this project's packages and fails with `ModuleNotFoundError: No module named 'fastapi'`. Activating the environment first (`.venv\Scripts\Activate.ps1`) also works, if your PowerShell execution policy allows scripts.

## Tests

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

```powershell
cd frontend
npm run test
npm run build
npm run lint
```

## Configuration

Optional environment variables for the backend:

| Variable | Purpose | Default |
|---|---|---|
| `MONA_AS_OF_DATE` | Pins "today" for deadline checks, as `YYYY-MM-DD`. Use it for repeatable demos. | Current date |
| `MONA_DATA_DIR` | Folder containing the three CSVs. | `data/` at the repository root |

Example:

```powershell
$env:MONA_AS_OF_DATE = "2026-10-13"
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | The API was started with the system Python, or with a global `uvicorn`. | Start it with `.venv\Scripts\python -m uvicorn app.main:app` from `backend/`. |
| `.venv\Scripts\python` is not recognized | The virtual environment has not been created. | Run the backend setup steps above. |
| `Could not import module "app.main"` | The command was run outside `backend/`. | `cd backend` first. |
| The UI shows "Check that the API is running on port 8000" | The backend is not running, or is on another port. | Start the API on port 8000. |
