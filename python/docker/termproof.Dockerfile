# The Rust toolchain here builds `agg`, the asciinema cast renderer. It is not
# a TermProof engine — the image ships the Python implementation only.
FROM rust:1.97-slim AS agg-builder

ARG AGG_TAG=v1.9.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN cargo install --locked --git https://github.com/asciinema/agg --tag "${AGG_TAG}" --root /opt/agg

FROM python:3.14-slim

ENV TERM=xterm-256color
WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=agg-builder /opt/agg/bin/agg /usr/local/bin/agg
COPY . /opt/termproof

RUN python -m pip install --no-cache-dir /opt/termproof \
    && termproof --help >/dev/null \
    && agg --version >/dev/null \
    && ffmpeg -version >/dev/null

ENTRYPOINT ["termproof"]
CMD ["--help"]
