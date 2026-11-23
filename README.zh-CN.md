# Dongtian

[English](README.md) · [架构说明](docs/ARCHITECTURE.md) · [复现细节](docs/REPRODUCIBILITY.md)

Dongtian 是一个 RISC-V 运行时：通过 OpenSBI 将已经运行的 Linux 宿主交给 HS 监控器管理，再运行一个独立的受保护 Linux 客体。它提供真实的 Linux 控制驱动、管理命令和交互控制台。

系统包含四个实体：M 模式 OpenSBI、HS 监控器、VS/VU 宿主 Linux、VS/VU 客体 Linux。后两者是两个 Linux 域，其中只有一个受保护客体；驱动和管理工具属于宿主，不是独立安全域。M 与 HS 构成可信监控栈。初始宿主在可信的 HS 环境启动，交接后继续在 VS/VU 运行，无需重启。客体运行时宿主暂停；当前单 hart 配置共享 UART 和 PLIC。

## 准备环境

完整构建使用 x86_64 Linux、Python 3.12 及以上、原生 GCC、GNU make、dtc、QEMU RISC-V 系统模拟器和完整的 GNU RISC-V 交叉工具链。OpenSBI 需要支持 PIE 链接的链接器。已记录的测试环境为 Ubuntu 26.04、QEMU 10.2.1、GCC 14.2、dtc 1.7.2。

在已测试的 Ubuntu 26.04 中，相关发行版软件包包括：`python3`、`gcc`、`make`、`gcc-riscv64-linux-gnu`、`binutils-riscv64-linux-gnu`、`device-tree-compiler`、`qemu-system-riscv`、`git`。其他发行版的包名以本机软件源为准；脚本不会替你安装软件。

```sh
git clone https://github.com/iwangjye/Dongtian-RISCV.git
cd Dongtian-RISCV
python3 -B scripts/check-env.py
```

完整环境检查包含实际 PIE 链接探测。非默认工具可用 `--cross-compile PREFIX`、`--dtc PATH`、`--qemu PATH` 指定。`--runtime-only` 只检查 Python 和 QEMU，不能替代完整构建或运行验收。

## 一键运行

在仓库根目录执行，输出目录必须是仓库外的新目录：

```sh
python3 -B scripts/demo.py --output ../dongtian-demo
```

该命令依次检查环境和源码、获取缺失的固定版本内核 Image、准备依赖、构建并自动运行 QEMU。首次运行可能下载固定版本第三方包，不会安装软件。日志和 `demo-receipt.json` 保存在输出目录，构建产物位于 `../dongtian-demo/build`。

正常自动验收以 `PASS_LINUX_HOST_AND_CVM` 结束。串口输出应依次显示 OpenSBI、驱动加载、宿主交接、客体 Linux 启动及返回宿主，最终 QEMU 正常退出。环境检查成功不代表这条执行链已经通过；已有运行证据和本轮新增工具验证范围见[验证记录](docs/VALIDATION.md)。

已有依赖可传 `--deps ../dongtian-deps`；已有构建可直接复用：

```sh
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-again
```

复用构建仍会核对产物哈希。`--build` 与 `--deps` 二选一。离线输入可通过 `--downloads /path/to/archive-cache`、`--kernel-deb /path/to/kernel.deb` 提供；`--jobs N` 控制构建并行数。

## 手动体验控制台

```sh
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-console --interactive
```

出现 `dongtian>` 后依次输入：

```text
info
demote
info
run
info
quit
```

第一次 `info` 显示 `NATIVE`；`demote` 后显示 `DEMOTED`，原宿主已经在 VS/VU 继续执行；`run` 启动客体 Linux，客体退出后宿主恢复，最后一次 `info` 显示 `GUEST_DONE`，运行次数为 1。每次 QEMU 会话只支持一次客体运行。控制台是管理接口，不是通用 shell；交互模式记录会话结果，不会自行声明自动 PASS。

CPU 私有页访问负例可单独运行：

```sh
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-denial --private-read
```

该负例只有观察到指定的真实 CPU 私有页访问故障和预期 QEMU 退出码 1 才通过；外层脚本成功表示已观察到预期拒绝；QEMU 的退出码 1 在此负例中是预期结果。

## 分步构建与范围

希望逐步查看准备、构建和运行过程时，使用[复现文档](docs/REPRODUCIBILITY.md)中的 `fetch-kernel.py`、`prepare-runtime.py`、`build-runtime.py` 和 `run-runtime.py`。驱动构建目标是 QEMU 中的 RISC-V Linux，不应加载到构建机的 x86_64 Linux。

当前实现是在精简公开监控器上扩充真实 OpenSBI 集成及模块管理，不是完整历史工程的直接裁剪。初始 HS 宿主与预加载镜像可信，初始宿主在交接前能访问客体数据。当前结果不声称安全启动或任意恶意初始宿主下的安全接管。完整边界见[执行范围](docs/LIMITATIONS.md)，具体交接机制见[架构说明](docs/ARCHITECTURE.md)。

## 许可证

原创固件扩展、监控器、管理工具、脚本及文档使用 [Apache-2.0](LICENSE)；Linux 驱动使用 GPL-2.0-only。下载的 OpenSBI 保留 BSD-2-Clause，Linux 保留其上游许可证。参见[第三方声明](THIRD_PARTY_NOTICES.md)和[文件许可清单](LICENSE_INVENTORY.json)。
