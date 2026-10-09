use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::thread;

use rumqttc::{Client, Event, Incoming, MqttOptions, QoS};

pub struct MqttHandle {
    client: Client,
}

#[derive(Debug)]
pub struct WriteMessage {
    pub topic: String,
    pub payload: String,
}

impl MqttHandle {
    pub fn publish(&self, topic: &str, payload: &str) {
        if let Err(e) = self.client.publish(topic, QoS::AtMostOnce, false, payload) {
            log::error!("MQTT publish error: {}", e);
        }
    }

    pub fn publish_retained(&self, topic: &str, payload: &str) {
        if let Err(e) = self.client.publish(topic, QoS::AtMostOnce, true, payload) {
            log::error!("MQTT publish retained error: {}", e);
        }
    }

    fn new(client: Client) -> Self {
        Self { client }
    }
}

pub fn connect(
    client_id: &str,
    host: &str,
    port: u16,
    write_topic_prefix: &str,
) -> anyhow::Result<(
    MqttHandle,
    thread::JoinHandle<()>,
    mpsc::Receiver<WriteMessage>,
    Arc<AtomicBool>,
)> {
    let mut options = MqttOptions::new(client_id, host.to_owned(), port);
    options.set_keep_alive(std::time::Duration::from_secs(30));

    let (client, mut eventloop) = Client::new(options, 100);

    let (write_tx, write_rx) = mpsc::channel::<WriteMessage>();

    let write_topic = format!("{}/#", write_topic_prefix);
    client.subscribe(&write_topic, QoS::AtMostOnce)?;

    let host_owned = host.to_owned();
    let connected = Arc::new(AtomicBool::new(false));
    let connected_clone = connected.clone();

    let handle = thread::Builder::new()
        .name("mqtt-eventloop".into())
        .spawn(move || {
            loop {
                match eventloop.iter().next() {
                    Some(Ok(Event::Incoming(Incoming::Publish(p)))) => {
                        let topic = p.topic.clone();
                        let payload = String::from_utf8_lossy(&p.payload).to_string();
                        log::debug!("MQTT recv: {} -> {}", topic, payload);

                        if let Err(e) = write_tx.send(WriteMessage { topic, payload }) {
                            log::error!("MQTT channel send error: {}", e);
                            break;
                        }
                    }
                    Some(Ok(Event::Incoming(Incoming::ConnAck(_)))) => {
                        log::info!("MQTT conectado a {}", host_owned);
                        connected_clone.store(true, Ordering::Relaxed);
                    }
                    Some(Ok(Event::Incoming(Incoming::Disconnect))) => {
                        log::warn!("MQTT desconectado");
                        connected_clone.store(false, Ordering::Relaxed);
                    }
                    Some(Err(e)) => {
                        log::error!("MQTT event loop error: {}", e);
                        connected_clone.store(false, Ordering::Relaxed);
                        std::thread::sleep(std::time::Duration::from_secs(1));
                    }
                    None => break,
                    _ => {}
                }
            }
            log::info!("MQTT event loop terminado");
        })?;

    Ok((
        MqttHandle::new(client),
        handle,
        write_rx,
        connected,
    ))
}