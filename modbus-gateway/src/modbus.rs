//! Cliente Modbus minimalista (TCP y RTU-serial), un disparo por transacción.
//! Copia el estilo del gateway ABB del SCADA y lo amplía con RTU y escrituras.
//! El puerto serial se configura con termios vía libc (sin dependencias de sistema).

use anyhow::{bail, Context, Result};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::os::unix::io::AsRawFd;
use std::time::Duration;

use crate::types::{RtuConfig, TcpConfig};

const IO_TIMEOUT: Duration = Duration::from_secs(3);

// ---------------------------------------------------------------------------
// Puerto serial (termios / libc)
// ---------------------------------------------------------------------------

pub struct Serial {
    file: std::fs::File,
}

impl Serial {
    pub fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        Ok(self.file.read(buf)?)
    }
    pub fn write_all(&mut self, buf: &[u8]) -> Result<()> {
        Ok(self.file.write_all(buf)?)
    }
    pub fn flush(&mut self) -> Result<()> {
        Ok(self.file.flush()?)
    }
}

fn baud_constant(baud: u32) -> Option<libc::speed_t> {
    Some(match baud {
        1200 => libc::B1200,
        2400 => libc::B2400,
        4800 => libc::B4800,
        9600 => libc::B9600,
        19200 => libc::B19200,
        38400 => libc::B38400,
        57600 => libc::B57600,
        115200 => libc::B115200,
        230400 => libc::B230400,
        460800 => libc::B460800,
        921600 => libc::B921600,
        _ => return None,
    })
}

fn open_serial(cfg: &RtuConfig) -> Result<Serial> {
    let file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&cfg.serial_port)
        .with_context(|| format!("no se pudo abrir el puerto {}", cfg.serial_port))?;

    let fd = file.as_raw_fd();
    let mut termios: libc::termios = unsafe { std::mem::zeroed() };
    if unsafe { libc::tcgetattr(fd, &mut termios) } != 0 {
        bail!("tcgetattr falló en {}", cfg.serial_port);
    }

    let baud = baud_constant(cfg.baudrate)
        .ok_or_else(|| anyhow::anyhow!("baudrate {} no soportado", cfg.baudrate))?;
    unsafe {
        libc::cfsetspeed(&mut termios, baud);
    }

    // Modo raw: sin echo, sin canon, sin control de flujo.
    termios.c_iflag = 0;
    termios.c_oflag = 0;
    termios.c_lflag = 0;
    termios.c_cflag = libc::CLOCAL | libc::CREAD | libc::CS8;
    // Data bits
    termios.c_cflag &= !libc::CSIZE;
    termios.c_cflag |= match cfg.data_bits {
        5 => libc::CS5,
        6 => libc::CS6,
        7 => libc::CS7,
        _ => libc::CS8,
    };
    // Stop bits
    if cfg.stop_bits == 2 {
        termios.c_cflag |= libc::CSTOPB;
    } else {
        termios.c_cflag &= !libc::CSTOPB;
    }
    // Paridad
    match cfg.parity.to_lowercase().as_str() {
        "even" => {
            termios.c_cflag |= libc::PARENB;
            termios.c_cflag &= !libc::PARODD;
        }
        "odd" => {
            termios.c_cflag |= libc::PARENB | libc::PARODD;
        }
        _ => {
            termios.c_cflag &= !libc::PARENB;
        }
    }
    // Timeouts de lectura: VMIN=0, VTIME=8 -> 0.8 s como máximo por read().
    termios.c_cc[libc::VMIN] = 0;
    termios.c_cc[libc::VTIME] = 8;

    if unsafe { libc::tcsetattr(fd, libc::TCSANOW, &termios) } != 0 {
        bail!("tcsetattr falló en {}", cfg.serial_port);
    }
    unsafe { libc::tcflush(fd, libc::TCIOFLUSH) };

    Ok(Serial { file })
}

/// CRC16 Modbus (polinomio 0xA001). Se devuelve ya ordenado little-endian.
fn crc16(bytes: &[u8]) -> [u8; 2] {
    let mut crc: u16 = 0xFFFF;
    for &b in bytes {
        crc ^= b as u16;
        for _ in 0..8 {
            if crc & 1 != 0 {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    [(crc & 0xFF) as u8, (crc >> 8) as u8]
}

fn read_exact_serial(port: &mut Serial, buf: &mut [u8]) -> Result<()> {
    let mut filled = 0;
    while filled < buf.len() {
        let n = port.read(&mut buf[filled..])?;
        if n == 0 {
            bail!(
                "timeout de lectura serie (leídos {}/{} bytes)",
                filled,
                buf.len()
            );
        }
        filled += n;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// TCP
// ---------------------------------------------------------------------------

fn tcp_connect(cfg: &TcpConfig) -> Result<TcpStream> {
    let addr = (cfg.host.as_str(), cfg.port)
        .to_socket_addrs()?
        .next()
        .ok_or_else(|| anyhow::anyhow!("address inválida {}:{}", cfg.host, cfg.port))?;
    let stream = TcpStream::connect_timeout(&addr, IO_TIMEOUT)?;
    stream.set_read_timeout(Some(IO_TIMEOUT))?;
    stream.set_write_timeout(Some(IO_TIMEOUT))?;
    Ok(stream)
}

pub fn read_registers_tcp(
    cfg: &TcpConfig,
    unit_id: u8,
    function: u8,
    address: u16,
    quantity: u16,
) -> Result<Vec<u16>> {
    if !matches!(function, 3 | 4) {
        bail!("función de lectura {} no soportada; use 3 o 4", function);
    }
    if quantity == 0 || quantity > 125 {
        bail!("quantity de registros inválida {}", quantity);
    }
    let mut stream = tcp_connect(cfg)?;
    let transaction_id = 1u16;
    let mut req = Vec::with_capacity(12);
    req.extend_from_slice(&transaction_id.to_be_bytes());
    req.extend_from_slice(&0u16.to_be_bytes());
    req.extend_from_slice(&6u16.to_be_bytes());
    req.push(unit_id);
    req.push(function);
    req.extend_from_slice(&address.to_be_bytes());
    req.extend_from_slice(&quantity.to_be_bytes());
    stream.write_all(&req)?;
    stream.flush()?;

    let mut header = [0u8; 7];
    stream.read_exact(&mut header)?;
    if u16::from_be_bytes([header[0], header[1]]) != transaction_id
        || u16::from_be_bytes([header[2], header[3]]) != 0
    {
        bail!("cabecera Modbus/TCP inválida");
    }
    let length = u16::from_be_bytes([header[4], header[5]]) as usize;
    if length < 2 || length > 253 {
        bail!("length Modbus/TCP inválido {}", length);
    }
    let mut pdu = vec![0u8; length - 1];
    stream.read_exact(&mut pdu)?;
    parse_read_pdu(&pdu, function, quantity)
}

pub fn write_register_tcp(cfg: &TcpConfig, unit_id: u8, address: u16, value: u16) -> Result<()> {
    let mut stream = tcp_connect(cfg)?;
    let mut req = Vec::with_capacity(12);
    req.extend_from_slice(&2u16.to_be_bytes()); // transaction
    req.extend_from_slice(&0u16.to_be_bytes());
    req.extend_from_slice(&6u16.to_be_bytes());
    req.push(unit_id);
    req.push(6);
    req.extend_from_slice(&address.to_be_bytes());
    req.extend_from_slice(&value.to_be_bytes());
    stream.write_all(&req)?;
    stream.flush()?;
    let mut resp = [0u8; 12];
    stream.read_exact(&mut resp)?;
    let length = u16::from_be_bytes([resp[4], resp[5]]) as usize;
    if resp[6] != unit_id || resp[7] != 6 || length != 6 {
        bail!("respuesta de escritura inválida");
    }
    if resp[8..10] != address.to_be_bytes() || resp[10..12] != value.to_be_bytes() {
        bail!("eco de escritura no coincide");
    }
    Ok(())
}

pub fn write_coil_tcp(cfg: &TcpConfig, unit_id: u8, address: u16, value: bool) -> Result<()> {
    let mut stream = tcp_connect(cfg)?;
    let mut req = Vec::with_capacity(12);
    req.extend_from_slice(&3u16.to_be_bytes()); // transaction
    req.extend_from_slice(&0u16.to_be_bytes());
    req.extend_from_slice(&6u16.to_be_bytes());
    req.push(unit_id);
    req.push(5);
    req.extend_from_slice(&address.to_be_bytes());
    req.extend_from_slice(&if value { 0xFF00u16 } else { 0x0000u16 }.to_be_bytes());
    stream.write_all(&req)?;
    stream.flush()?;
    let mut resp = [0u8; 12];
    stream.read_exact(&mut resp)?;
    let length = u16::from_be_bytes([resp[4], resp[5]]) as usize;
    if resp[6] != unit_id || resp[7] != 5 || length != 6 {
        bail!("respuesta de coil inválida");
    }
    if resp[8..10] != address.to_be_bytes() {
        bail!("eco de coil no coincide");
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// RTU serial (framing sobre Serial)
// ---------------------------------------------------------------------------

fn rtu_request(port: &mut Serial, pdu: &[u8]) -> Result<()> {
    let mut frame = pdu.to_vec();
    frame.extend_from_slice(&crc16(pdu));
    port.write_all(&frame)?;
    port.flush()?;
    Ok(())
}

/// Lee una respuesta RTU de lectura: [addr, func, bytecount, data..., crcL, crcH].
/// Devuelve los bytes de datos (sin bytecount ni CRC).
fn read_rtu_response(port: &mut Serial) -> Result<Vec<u8>> {
    let mut head = [0u8; 3];
    read_exact_serial(port, &mut head)?;
    if head[1] & 0x80 != 0 {
        bail!("excepción Modbus código {}", head[2]);
    }
    let byte_count = head[2] as usize;
    let mut body = vec![0u8; byte_count + 2];
    read_exact_serial(port, &mut body)?;
    let mut frame = head.to_vec();
    frame.extend_from_slice(&body);
    let (data, crc) = frame.split_at(frame.len() - 2);
    if crc16(data) != [crc[0], crc[1]] {
        bail!("CRC inválido en respuesta RTU");
    }
    Ok(data[3..].to_vec())
}

/// Lee una respuesta RTU de escritura (eco): [addr, func, addrH, addrL, valH, valL, crc].
fn read_rtu_echo(port: &mut Serial) -> Result<Vec<u8>> {
    let mut frame = [0u8; 8];
    read_exact_serial(port, &mut frame)?;
    if frame[1] & 0x80 != 0 {
        bail!("excepción Modbus código {}", frame[2]);
    }
    if crc16(&frame[..6]) != [frame[6], frame[7]] {
        bail!("CRC inválido en eco RTU");
    }
    Ok(frame[..6].to_vec())
}

pub fn read_registers_rtu(
    cfg: &RtuConfig,
    unit_id: u8,
    function: u8,
    address: u16,
    quantity: u16,
) -> Result<Vec<u16>> {
    if !matches!(function, 3 | 4) {
        bail!("función de lectura {} no soportada; use 3 o 4", function);
    }
    if quantity == 0 || quantity > 125 {
        bail!("quantity de registros inválida {}", quantity);
    }
    let mut port = open_serial(cfg)?;
    let pdu = [
        unit_id,
        function,
        (address >> 8) as u8,
        (address & 0xFF) as u8,
        (quantity >> 8) as u8,
        (quantity & 0xFF) as u8,
    ];
    rtu_request(&mut port, &pdu)?;
    let data = read_rtu_response(&mut port)?;
    parse_read_data(&data, function, quantity)
}

pub fn write_register_rtu(cfg: &RtuConfig, unit_id: u8, address: u16, value: u16) -> Result<()> {
    let mut port = open_serial(cfg)?;
    let pdu = [
        unit_id,
        6,
        (address >> 8) as u8,
        (address & 0xFF) as u8,
        (value >> 8) as u8,
        (value & 0xFF) as u8,
    ];
    rtu_request(&mut port, &pdu)?;
    let echo = read_rtu_echo(&mut port)?;
    if echo[..6] != pdu {
        bail!("eco de escritura RTU no coincide");
    }
    Ok(())
}

pub fn write_coil_rtu(cfg: &RtuConfig, unit_id: u8, address: u16, value: bool) -> Result<()> {
    let mut port = open_serial(cfg)?;
    let pdu = [
        unit_id,
        5,
        (address >> 8) as u8,
        (address & 0xFF) as u8,
        if value { 0xFF } else { 0x00 },
        0,
    ];
    rtu_request(&mut port, &pdu)?;
    let echo = read_rtu_echo(&mut port)?;
    if echo[..6] != pdu {
        bail!("eco de coil RTU no coincide");
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Parseo compartido
// ---------------------------------------------------------------------------

fn parse_read_pdu(pdu: &[u8], function: u8, quantity: u16) -> Result<Vec<u16>> {
    if pdu.first() == Some(&(function | 0x80)) {
        bail!("excepción Modbus código {}", pdu.get(1).copied().unwrap_or(0));
    }
    if pdu.len() < 2 || pdu[0] != function {
        bail!("respuesta Modbus inesperada");
    }
    let byte_count = pdu[1] as usize;
    let expected = quantity as usize * 2;
    if byte_count != expected || pdu.len() != byte_count + 2 {
        bail!("byte count inválido: {}", byte_count);
    }
    Ok(pdu[2..]
        .chunks_exact(2)
        .map(|pair| u16::from_be_bytes([pair[0], pair[1]]))
        .collect())
}

fn parse_read_data(data: &[u8], function: u8, quantity: u16) -> Result<Vec<u16>> {
    if data.first() == Some(&(function | 0x80)) {
        bail!("excepción Modbus código {}", data.get(1).copied().unwrap_or(0));
    }
    let expected = quantity as usize * 2;
    if data.len() != expected {
        bail!("byte count inválido: {}", data.len());
    }
    Ok(data
        .chunks_exact(2)
        .map(|pair| u16::from_be_bytes([pair[0], pair[1]]))
        .collect())
}

pub fn float32(registers: &[u16], offset: usize) -> Result<f32> {
    let high = *registers.get(offset).context("falta palabra alta")? as u32;
    let low = *registers.get(offset + 1).context("falta palabra baja")? as u32;
    Ok(f32::from_bits((high << 16) | low))
}