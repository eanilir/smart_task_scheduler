# task_scheduler

Python project for scheduling tasks. Contains core scheduling logic, synthetic data generator, and visualization utilities.

## Contents
- `core/` — scheduler, task, evaluator, scorer
- `data/` — synthetic data utilities
- `tests/` — unit tests
- `viz/` — visualization helpers


##projeyi çalıştırmak için:
cd task_scheduler
pip install matplotlib
jupyter notebook demo.ipynb

mevcut klasördeyken:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
python -m pip install matplotlib notebook
python -m notebook demo.ipynb