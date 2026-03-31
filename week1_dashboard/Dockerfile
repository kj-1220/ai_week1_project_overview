FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    streamlit==1.40.0 \
    altair==5.4.1 \
    pandas==2.2.3 \
    numpy==1.26.4
COPY . .
EXPOSE 8080
CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
