# Earlier standalone-firmware example

The earlier example uses its own small M-mode firmware and a userspace MMIO trigger. It remains available for comparison; the expanded runtime uses OpenSBI and a kernel control driver.

After acquiring the pinned kernel:

```sh
python3 -B scripts/build.py --output ../minimal-build
python3 -B scripts/run.py --build ../minimal-build --output ../minimal-run
```

The two build/run entry points have separate receipts and output directories. The standalone example does not load the new kernel module.
