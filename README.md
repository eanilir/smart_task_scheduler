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
python -m pip install -r requirements.app.txt
uvicorn app:app --reload --port 8888
```

Then open http://127.0.0.1:8888 to use the UI and see the ranked list.