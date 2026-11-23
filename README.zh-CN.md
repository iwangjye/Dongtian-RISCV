# Dongtian

[English](README.md)

Dongtian 是一个研究原型：将正在运行的 RISC-V Linux 宿主降权，交由 HS 监控器管理，并运行一个独立的 Linux 客体。

系统由 OpenSBI、HS 监控器、Linux 控制驱动和管理工具组成，用于完成宿主交接与客体运行。

## 一键运行

在仓库根目录执行，使用仓库外的新输出目录：

```sh
python3 -B scripts/demo.py --output ../dongtian-demo
```

脚本会准备依赖、构建运行时并启动 QEMU。需要 x86_64 Linux、Python 3.12 及以上、构建工具、GNU RISC-V 交叉工具链、dtc 和 QEMU。环境配置及详细命令见[复现文档](docs/REPRODUCIBILITY.md)。

## 范围与文档

当前已在单 hart RISC-V QEMU TCG、可信初始宿主条件下验证。详细说明见以下文档。

- [架构说明](docs/ARCHITECTURE.md)
- [复现文档](docs/REPRODUCIBILITY.md)
- [验证记录](docs/VALIDATION.md)

## 许可证

Dongtian 原创代码及文档使用 [Apache-2.0](LICENSE)；Linux 驱动使用 GPL-2.0-only。上游组件保留各自许可证。参见[第三方声明](THIRD_PARTY_NOTICES.md)和[文件许可清单](LICENSE_INVENTORY.json)。
