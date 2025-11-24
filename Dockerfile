# Używamy Pythona 3.12 w wersji slim
FROM python:3.12-slim

# Ustaw zmienną środowiskową, żeby logi szły od razu na stdout
ENV PYTHONUNBUFFERED=1

# Opcjonalnie: strefa czasowa (użyjemy TZ z env na etapie uruchamiania)
ENV TZ=Europe/Warsaw

# Zainstaluj potrzebne pakiety systemowe
# - nmap: do skanowania sieci (python-nmap go potrzebuje)
# - tzdata: dla poprawnej strefy czasowej
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nmap \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Katalog roboczy w kontenerze
WORKDIR /app

# Skopiuj requirements i zainstaluj zależności
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Skopiuj kod aplikacji
COPY app /app/app

# Upewnij się, że istnieje katalog na bazę (będzie podpięty jako volume)
RUN mkdir -p /app/data

# Otwórz port dla uvicorn
EXPOSE 8000

# Komenda startowa – produkcyjny uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
