//! Gateway Modbus RTU/TCP -> MQTT de Terminal Galán.
//!
//! Reemplaza los nodos Modbus de Node-RED por un servicio Rust (como el gateway
//! ABB del SCADA):
//!  - lee registros (FC 3/4) de dispositivos RTU-serial o TCP y publica:
//!      * etiquetas individuales en <read_topic_prefix>/<TAG>  (plant/read/...)
//!      * el bloque crudo en <raw_topic_prefix>/<device>/<block> (planta_modbus/...)
//!  - se suscribe a <write_topic_prefix>/# (plant/write/...) y escribe
//!    registros (FC 6) o coils (FC 5) según el mapa de configuración.
//!  - publica estados retain en <status_topic>/...

mod modbus;
mod mqtt;
mod types;

use std::sync::mpsc;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::Context;
use log::{info, warn};
use mqtt::WriteMessage;
use types::{Config, Device, RegisterFormat};

fn timestamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn float32_or_raw(registers: &[u16], field: &types::Field, format: &RegisterFormat) -> f32 {
    match format {
        RegisterFormat::Float32 => modbus::float32(registers, field.register_offset)
            .map(|f| f * field.scale + field.offset)
            .unwrap_or(f32::NAN),
        RegisterFormat::Registers => {
            let raw = registers
                .get(field.register_offset)
                .copied()
                .unwrap_or(0) as f32;
            raw * field.scale + field.offset
        }
    }
}

/// Lee un bloque de un dispositivo (TCP o RTU).
fn read_block(device: &Device, block: &types::ReadBlock) -> anyhow::Result<Vec<u16>> {
    match device.tcp() {
        Some(cfg) => modbus::read_registers_tcp(
            &cfg,
            device.unit_id,
            block.function,
            block.address,
            block.quantity,
        ),
        None => match device.rtu() {
            Some(cfg) => modbus::read_registers_rtu(
                &cfg,
                device.unit_id,
                block.function,
                block.address,
                block.quantity,
            ),
            None => anyhow::bail!(
                "dispositivo {} sin host/port ni serial_port configurado",
                device.name
            ),
        },
    }
}

fn write_item(
    item: &types::WriteItem,
    device: &Device,
    value: u16,
    coil: bool,
) -> anyhow::Result<()> {
    if let Some(cfg) = device.tcp() {
        return if coil {
            modbus::write_coil_tcp(&cfg, device.unit_id, item.address, value != 0)
        } else {
            modbus::write_register_tcp(&cfg, device.unit_id, item.address, value)
        };
    }
    match device.rtu() {
        Some(cfg) => {
            if coil {
                modbus::write_coil_rtu(&cfg, device.unit_id, item.address, value != 0)
            } else {
                modbus::write_register_rtu(&cfg, device.unit_id, item.address, value)
            }
        }
        None => anyhow::bail!(
            "dispositivo {} sin host/port ni serial_port configurado",
            device.name
        ),
    }
}

fn format_transport(device: &Device) -> String {
    match device.tcp() {
        Some(c) => format!("tcp:{}:{}", c.host, c.port),
        None => match device.rtu() {
            Some(c) => format!("rtu:{}:{}", c.serial_port, c.baudrate),
            None => "sin-transporte".to_string(),
        },
    }
}

/// Hilo que consume las escrituras MQTT y las aplica al dispositivo adecuado.
fn writer_thread(rx: mpsc::Receiver<WriteMessage>, config: Config) -> thread::JoinHandle<()> {
    thread::Builder::new()
        .name("modbus-writer".into())
        .spawn(move || {
            for msg in rx {
                let tag = msg
                    .topic
                    .rsplit('/')
                    .next()
                    .unwrap_or(&msg.topic)
                    .to_string();
                let payload = msg.payload.trim().trim_matches('"').to_string();
                let parsed: Option<u16> = payload
                    .parse::<f32>()
                    .ok()
                    .map(|v| v as u16)
                    .or_else(|| payload.parse::<u16>().ok());

                let mut written = false;
                for device in &config.devices {
                    for item in &device.writes {
                        if item.tag == tag {
                            let value = parsed.unwrap_or(0);
                            match write_item(item, device, value, item.coil) {
                                Ok(()) => {
                                    info!(
                                        "escritura {} -> {} ({} addr {}) = {}",
                                        tag,
                                        device.name,
                                        if item.coil { "coil" } else { "register" },
                                        item.address,
                                        value
                                    );
                                    written = true;
                                }
                                Err(e) => warn!("escritura {} -> {}: {}", tag, device.name, e),
                            }
                            break;
                        }
                    }
                    if written {
                        break;
                    }
                }
                if !written {
                    warn!(
                        "escritura MQTT sin destino configurado: {} (topic {})",
                        tag, msg.topic
                    );
                }
            }
        })
        .expect("no se pudo lanzar el hilo de escrituras")
}

fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp_millis()
        .init();

    let path = std::env::args()
        .nth(1)
        .context("uso: modbus-gateway CONFIG.json")?;
    let config: Config = serde_json::from_str(&std::fs::read_to_string(&path)?)?;

    let devices = config.devices.clone();
    let (mqtt, _handle, write_rx, mqtt_connected) =
        mqtt::connect(&config.client_id, &config.mqtt_host, config.mqtt_port, &config.write_topic_prefix)?;

    let total_blocks: usize = devices
        .iter()
        .map(|d| d.reads.iter().filter(|b| b.enabled).count())
        .sum();
    info!(
        "gateway Modbus iniciado: {} dispositivo(s), {} bloque(s) de lectura, registers_only={}",
        config.devices.len(),
        total_blocks,
        config.publish_registers_only
    );

    // Hilo que aplica escrituras recibidas por MQTT.
    let _writer = writer_thread(write_rx, config.clone());

    // Estado inicial (retain) para que el dashboard sepa que aún no hay datos.
    for device in &devices {
        mqtt.publish_retained(
            &format!("{}/devices/{}/status", config.status_topic, device.name),
            &serde_json::json!({"connected": false, "timestamp": timestamp()}).to_string(),
        );
    }

    loop {
        for device in &devices {
            let mut device_ok = true;
            for block in device.reads.iter().filter(|b| b.enabled) {
                match read_block(device, block) {
                    Ok(registers) => {
                        mqtt.publish(
                            &format!(
                                "{}/{}/{}",
                                config.raw_topic_prefix, device.name, block.name
                            ),
                            &serde_json::json!({
                                "timestamp": timestamp(),
                                "device": device.name,
                                "block": block.name,
                                "address": block.address,
                                "function": block.function,
                                "registers": registers,
                            })
                            .to_string(),
                        );
                        if !config.publish_registers_only {
                            for field in &block.fields {
                                let value = float32_or_raw(&registers, field, &block.format);
                                if value.is_nan() {
                                    device_ok = false;
                                    warn!("{} / {}: campo fuera de rango", device.name, field.tag);
                                    continue;
                                }
                                mqtt.publish(
                                    &format!("{}/{}", config.read_topic_prefix, field.tag),
                                    &serde_json::json!({
                                        "tag": field.tag,
                                        "value": value,
                                        "source": device.name,
                                        "timestamp": timestamp(),
                                    })
                                    .to_string(),
                                );
                            }
                        }
                    }
                    Err(e) => {
                        device_ok = false;
                        warn!(
                            "Modbus {} ({}): bloque {} addr {}: {}",
                            device.name,
                            format_transport(device),
                            block.name,
                            block.address,
                            e
                        );
                    }
                }
            }
            mqtt.publish_retained(
                &format!("{}/devices/{}/status", config.status_topic, device.name),
                &serde_json::json!({"connected": device_ok, "timestamp": timestamp()}).to_string(),
            );
        }
        mqtt.publish_retained(
            &format!("{}/status", config.status_topic),
            &serde_json::json!({
                "mqtt_connected": mqtt_connected.load(std::sync::atomic::Ordering::Relaxed),
                "timestamp": timestamp(),
            })
            .to_string(),
        );
        thread::sleep(Duration::from_millis(config.poll_interval_ms));
    }
}