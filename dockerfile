FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY modbus_simulator.py .
COPY generar_tiquete_pdf.py .
RUN chmod +x generar_tiquete_pdf.py

EXPOSE 502

CMD ["python", "modbus_simulator.py"]
