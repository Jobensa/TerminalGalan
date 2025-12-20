#!/bin/bash

set -e

echo "📦 Creando estructura de carpetas para el stack..."

# Node-RED
mkdir -p node-red
chown -R 1000:1000 node-red

# InfluxDB v2
mkdir -p influxdb-data
chown -R 1000:1000 influxdb-data

# Grafana
mkdir -p grafana-data
chown -R 472:472 grafana-data

# Mosquitto
mkdir -p mosquitto/config mosquitto/data mosquitto/log
chown -R 1883:1883 mosquitto

# Crear archivo de configuración mínimo de Mosquitto si no existe
MOSQ_CONF=mosquitto/config/mosquitto.conf
if [ ! -f "$MOSQ_CONF" ]; then
  echo "🔧 Generando archivo mosquitto.conf básico..."
  cat > "$MOSQ_CONF" <<EOF
persistence true
persistence_location ./mosquitto/data/
log_dest file ./mosquitto/log/mosquitto.log
listener 1883
socket_domain ipv4
# Mosquitto >= 2.0 únicamente permite conexiones autenticadas mediante usuario/contraseña
# Permitimos temporalmente las conexiones anónimas para probar el entorno
allow_anonymous true
EOF
fi

echo "✅ Estructura creada exitosamente."
 
