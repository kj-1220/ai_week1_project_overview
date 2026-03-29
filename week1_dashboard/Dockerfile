FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit==1.40.0 \
    plotly==5.24.0 \
    pandas==2.2.3 \
    numpy==1.26.4 \
    google-cloud-bigquery==3.27.0 \
    db-dtypes==1.3.1 \
    pyarrow==18.1.0

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
