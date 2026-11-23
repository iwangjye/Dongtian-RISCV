# Changelog

## 2026-11-24: Reproduction and onboarding

- Add a one-command demo that composes the existing preparation, build, and run scripts and records step outcomes.
- Add runtime/build environment checks and a real RV64 PIE-link probe.
- Add a Chinese quick start and a four-entity runtime architecture guide.
- Preserve the existing single-CVM runtime and component license boundaries.

## 2026-11-23: OpenSBI and Linux control interface

Commit `214f0b8` added OpenSBI 1.7 integration, a real Linux control module, management commands, and an interactive control console. Automatic boot/return, private-read denial, and terminal control were exercised.

## 2026-11-23: Initial public prototype

Commit `b1e21f2` published the standalone-firmware Linux deprivileging and single-guest example with reproduction tools and recorded serial evidence.
