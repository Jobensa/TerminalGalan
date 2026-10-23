FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY glp_properties.py glp_mass_calculator.py mqtt_worker.py ./

CMD ["python", "mqtt_worker.py"]
