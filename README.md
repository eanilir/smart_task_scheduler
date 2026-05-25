# task_scheduler

Python project for scheduling tasks. Contains core scheduling logic, synthetic data generator, and visualization utilities.

## Contents
- `core/` — scheduler, task, evaluator, scorer
- `data/` — synthetic data utilities
- `tests/` — unit tests
- `viz/` — visualization helpers

## Run the web app
This repository includes a FastAPI backend and a static UI for adding tasks and viewing the ranked list.

Run locally (venv active):
```
# activate venv (PowerShell)
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.app.txt
python -m uvicorn app:app --reload --port 8888
```

Then open http://127.0.0.1:8888 to use the UI and see the ranked list.

Alternative: legacy demo (Jupyter) and Docker instructions

If you prefer the original notebook demo or a containerized run, use the legacy instructions below.

Jupyter demo (legacy):
```
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m notebook demo.ipynb
```

Docker (alternative):
```
docker build -t task_scheduler:latest .
docker run -p 8888:8888 task_scheduler:latest
```

Notes:
- Use `requirements.app.txt` for running the FastAPI app; `requirements.txt` is for the legacy notebook demo.
- Data exports and the learning DB are stored under `data/` (e.g. `data/task_scheduler.sqlite3`, `data/dataset_train_900.csv`).
