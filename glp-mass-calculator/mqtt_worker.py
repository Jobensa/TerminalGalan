"""Servicio MQTT para liquidación GLP basada en masa Coriolis."""

import json
import logging
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from glp_mass_calculator import CalculationError, calculate_glp_ticket


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
REQUEST_TOPIC = os.getenv("MQTT_REQUEST_TOPIC", "TIQUETE_LPG/CALCULAR")
RESULT_TOPIC = os.getenv("MQTT_RESULT_TOPIC", "TIQUETE_LPG")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "terminalgalan-glp-calculator")


def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties):
    if reason_code.is_failure:
        logging.error("Conexión MQTT rechazada: %s", reason_code)
        return
    logging.info("Conectado a MQTT %s:%s", MQTT_HOST, MQTT_PORT)
    client.subscribe(REQUEST_TOPIC, qos=1)
    logging.info("Suscrito a %s; resultados en %s", REQUEST_TOPIC, RESULT_TOPIC)


def on_message(client: mqtt.Client, _userdata, message: mqtt.MQTTMessage):
    try:
        request = json.loads(message.payload.decode("utf-8"))
        result = calculate_glp_ticket(request)
        result["status"] = "ok"
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        result.setdefault("fechaHora", result["timestamp"])
        client.publish(
            RESULT_TOPIC,
            json.dumps(result, ensure_ascii=False, allow_nan=False),
            qos=1,
            retain=False,
        )
        logging.info(
            "Liquidación publicada: pulsos_principal=%s pulsos_vapor=%s "
            "masa_vapor=%.3f kg masa_liquida=%.3f kg masa_neta=%.3f kg NSV=%.3f gal",
            result["mass_pulses"],
            result["vapor_mass_pulses"],
            result["vapor_mass_kg"],
            result["mass_liquid_gross_kg"],
            result["mass_net_kg"],
            result["nsv_us_gal"],
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CalculationError) as error:
        logging.warning("Solicitud de cálculo rechazada: %s", error)
        error_result = {
            "status": "error",
            "error": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            request = json.loads(message.payload.decode("utf-8"))
            for key in ("request_id", "cliente", "numeroTiquete", "stream"):
                if isinstance(request, dict) and key in request:
                    error_result[key] = request[key]
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        client.publish(
            RESULT_TOPIC,
            json.dumps(error_result, ensure_ascii=False),
            qos=1,
            retain=False,
        )
    except Exception:
        logging.exception("Error inesperado procesando solicitud MQTT")


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
