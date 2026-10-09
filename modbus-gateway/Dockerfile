FROM rust:1-slim-bookworm AS builder

WORKDIR /build

COPY Cargo.toml Cargo.lock* ./
COPY src/ src/

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 gateway

COPY --from=builder /build/target/release/modbus-gateway /usr/local/bin/modbus-gateway

USER gateway
WORKDIR /home/gateway

ENTRYPOINT ["modbus-gateway"]