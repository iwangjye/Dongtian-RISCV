# Dongtian

[简体中文](README.zh-CN.md)

Dongtian is a research prototype that demotes a running RISC-V Linux host under an HS monitor and runs an independent Linux guest.

It combines OpenSBI, an HS monitor, a Linux control driver, and management tools for host handoff and guest execution.

## Quick start

From the repository root, run the demo with a new output directory outside the checkout:

```sh
python3 -B scripts/demo.py --output ../dongtian-demo
```

The demo prepares dependencies, builds the runtime, and runs QEMU. It requires x86_64 Linux with Python 3.12+, build tools, a GNU RISC-V cross toolchain, dtc, and QEMU. See the [reproduction guide](docs/REPRODUCIBILITY.md) for setup and detailed commands.

## Scope and documentation

Validated with single-hart RISC-V QEMU TCG and a trusted initial host. See the documents below for details.

- [Architecture](docs/ARCHITECTURE.md)
- [Reproduction](docs/REPRODUCIBILITY.md)
- [Validation](docs/VALIDATION.md)
- [Limitations](docs/LIMITATIONS.md)

## License

Original Dongtian code and documentation use [Apache-2.0](LICENSE); the Linux driver uses GPL-2.0-only. Upstream components retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) and the [license inventory](LICENSE_INVENTORY.json).
