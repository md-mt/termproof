# Rust Install (RUST-024)

The Rust engine is distributed via the same channels as the Python package, with a single version source (`pyproject.toml` + `rust/Cargo.toml`).

## From release archive

```sh
curl -LO https://github.com/md-mt/termproof/releases/download/v0.2.0/termproof-linux-x86_64.tar.gz
tar -xzf termproof-linux-x86_64.tar.gz
./termproof --help
```

Checksums and Sigstore attestations are published alongside each archive (`SHA256SUMS`, `*.sig`).

## Homebrew

```sh
brew tap md-mt/termproof https://github.com/md-mt/termproof
brew install termproof
```

The formula is updated automatically by `release-rust.yml`.

## Container

```sh
docker pull ghcr.io/md-mt/termproof:latest
docker run --rm ghcr.io/md-mt/termproof --help
# Mount recipes
docker run --rm -v $PWD:/workspace ghcr.io/md-mt/termproof run /workspace/.termproof/recipes
```

## PyPI wheel (platform)

```sh
pip install termproof
# The wheel bundles the Rust binary where available; otherwise it installs the Python fallback.
termproof --help
```

## From source

```sh
cd rust
cargo build --release
./target/release/termproof --help
```
