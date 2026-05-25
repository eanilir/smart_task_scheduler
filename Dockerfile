FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app

# Install python deps
RUN python -m pip install --upgrade pip setuptools
RUN if [ -f requirements.txt ]; then python -m pip install -r requirements.txt; fi

# Expose notebook port (if using demo notebook)
EXPOSE 8888

CMD ["python", "-m", "notebook", "demo.ipynb", "--ip=0.0.0.0", "--no-browser", "--allow-root"]
