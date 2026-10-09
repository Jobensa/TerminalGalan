//! Configuración del gateway Modbus RTU/TCP -> MQTT de Terminal Galán.
//! Mismo esquema que el gateway ABB del SCADA (pac_to_mqtt_rust), ampliado con:
//!  - transporte RTU (serial) y TCP
//!  - escrituras de registros (FC 6) y coils (FC 5) recibidas por MQTT
//!  - publicación de bloques crudos para que Node-RED siga usándolos
//!
//! El transporte de cada dispositivo se infiere de sus campos:
//!   host + port      -> TCP
//!   serial_port      -> RTU serial (el resto de campos seriales son opcionales)

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub mqtt_host: String,
    #[serde(default = "default_mqtt_port")]
    pub mqtt_port: u16,
    #[serde(default = "default_client_id")]
    pub client_id: String,

    /// Prefijo donde se publican las etiquetas tipo {tag,value,timestamp}
    /// (p. ej. "plant/read"). Node-RED se suscribe con "plant/read/#".
    #[serde(default = "default_read_prefix")]
    pub read_topic_prefix: String,
    /// Prefijo de los bloques crudos de registros (p. ej. "planta_modbus").
    #[serde(default = "default_raw_prefix")]
    pub raw_topic_prefix: String,
    /// Prefijo al que se suscribe para escrituras (p. ej. "plant/write").
    #[serde(default = "default_write_prefix")]
    pub write_topic_prefix: String,
    /// Prefijo para los tópicos de estado (p. ej. "planta_gateway").
    #[serde(default = "default_status_prefix")]
    pub status_topic: String,

    #[serde(default = "default_poll_ms")]
    pub poll_interval_ms: u64,

    /// Si es true, solo se publican bloques crudos (planta_modbus) y NINGUNA
    /// etiqueta individual. Útil en desarrollo cuando el mapa de etiquetas
    /// aún no está completo (evita errores de Node-RED por etiquetas vacías).
    #[serde(default)]
    pub publish_registers_only: bool,

    #[serde(default)]
    pub devices: Vec<Device>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Device {
    pub name: String,
    #[serde(default = "default_unit")]
    pub unit_id: u8,

    // --- TCP (si host y port presentes) ---
    #[serde(default)]
    pub host: Option<String>,
    #[serde(default)]
    pub port: Option<u16>,

    // --- RTU serial (si serial_port presente) ---
    #[serde(default)]
    pub serial_port: Option<String>,
    #[serde(default = "default_baud")]
    pub baudrate: u32,
    #[serde(default)]
    pub data_bits: u8,
    #[serde(default = "default_parity")]
    pub parity: String,
    #[serde(default = "default_stop_bits")]
    pub stop_bits: u8,

    #[serde(default)]
    pub reads: Vec<ReadBlock>,
    #[serde(default)]
    pub writes: Vec<WriteItem>,
}

impl Device {
    pub fn tcp(&self) -> Option<TcpConfig> {
        match (&self.host, self.port) {
            (Some(h), Some(p)) => Some(TcpConfig {
                host: h.clone(),
                port: p,
            }),
            _ => None,
        }
    }

    pub fn rtu(&self) -> Option<RtuConfig> {
        self.serial_port.as_ref().map(|port| RtuConfig {
            serial_port: port.clone(),
            baudrate: self.baudrate,
            data_bits: self.data_bits,
            parity: self.parity.clone(),
            stop_bits: self.stop_bits,
        })
    }
}

#[derive(Debug, Clone)]
pub struct RtuConfig {
    pub serial_port: String,
    pub baudrate: u32,
    pub data_bits: u8,
    pub parity: String,
    pub stop_bits: u8,
}

#[derive(Debug, Clone)]
pub struct TcpConfig {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ReadBlock {
    pub name: String,
    #[serde(default = "default_read_function")]
    pub function: u8,
    pub address: u16,
    pub quantity: u16,
    #[serde(default)]
    pub format: RegisterFormat,
    /// Etiquetas derivadas de los registros. Vacío -> solo bloque crudo.
    #[serde(default)]
    pub fields: Vec<Field>,
    /// Permite deshabilitar un bloque sin borrarlo (p. ej. mapa aún desconocido).
    #[serde(default = "default_true")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum RegisterFormat {
    #[default]
    Registers,
    Float32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Field {
    pub tag: String,
    pub register_offset: usize,
    #[serde(default = "default_scale")]
    pub scale: f32,
    #[serde(default)]
    pub offset: f32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WriteItem {
    pub tag: String,
    pub address: u16,
    /// true -> coil (FC 5), false -> holding register (FC 6).
    #[serde(default)]
    pub coil: bool,
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

fn default_mqtt_port() -> u16 { 1883 }
fn default_client_id() -> String { "terminalgalan_modbus_gateway".to_string() }
fn default_read_prefix() -> String { "plant/read".to_string() }
fn default_raw_prefix() -> String { "planta_modbus".to_string() }
fn default_write_prefix() -> String { "plant/write".to_string() }
fn default_status_prefix() -> String { "planta_gateway".to_string() }
fn default_poll_ms() -> u64 { 1000 }
fn default_unit() -> u8 { 1 }
fn default_baud() -> u32 { 57600 }
fn default_parity() -> String { "none".to_string() }
fn default_stop_bits() -> u8 { 1 }
fn default_scale() -> f32 { 1.0 }
fn default_true() -> bool { true }
fn default_read_function() -> u8 { 3 }