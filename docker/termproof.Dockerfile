FROM rust:1.96-slim AS rust-builder
WORKDIR /src
COPY rust/ ./rust/
RUN cargo build --manifest-path rust/Cargo.toml --release --bin termproof

FROM rust:1.85-slim AS agg-builder

ARG AGG_TAG=v1.9.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN cargo install --locked --git https://github.com/asciinema/agg --tag "${AGG_TAG}" --root /opt/agg

FROM python:3.12-slim

ENV TERM=xterm-256color
WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=agg-builder /opt/agg/bin/agg /usr/local/bin/agg
COPY --from=rust-builder /src/rust/target/release/termproof /usr/local/bin/termproof-rust
COPY . /opt/termproof

RUN python -m pip install --no-cache-dir /opt/termproof \
    && termproof --help >/dev/null \
    && termproof-rust --help >/dev/null \
    && agg --version >/dev/null \
    && ffmpeg -version >/dev/null

ENTRYPOINT ["termproof"]
CMD ["--help"]
