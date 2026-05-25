# task_scheduler

Python project for scheduling tasks. Contains core scheduling logic, synthetic data generator, and visualization utilities.

## Contents
- `core/` — scheduler, task, evaluator, scorer
- `data/` — synthetic data utilities
- `tests/` — unit tests
- `viz/` — visualization helpers


##projeyi çalıştırmak için:
Çalıştırma (yerel venv kullanımı önerilir):

1) Venv aktifleştir ve bağımlılıkları yükle

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2) Jupyter notebook ile demo'yu başlat

```powershell
python -m notebook demo.ipynb
```

Docker (alternatif):

```bash
docker build -t task_scheduler:latest .
docker run -p 8888:8888 task_scheduler:latest
```

Notlar:
- Eğer `pip` veya `jupyter` bulunamaz hatası alırsanız, komutları venv Python ile çalıştırmayı deneyin:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m notebook demo.ipynb
```