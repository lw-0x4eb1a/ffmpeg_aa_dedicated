# 本地验证记录

日期：2026-10-12。主项目只读审计基准：
`a59fec528a4613fe37f54259aa8531fce56f95b4`。

- 宿主：macOS 26.4 / Apple Silicon，Xcode macOS SDK 26.4。
- 参考解码器：独立安装的 FFmpeg / ffprobe 8.0.1。
- macOS arm64 与 x86_64 均完成源码编译。arm64 原生执行，x86_64 通过 Rosetta 执行。
- 两个单架构及 universal 二进制均通过组件白名单检查和 12 个实际导出用例。
- MOV 无缩放用例与输入 RGBA 逐字节一致，包括 0/128/255 alpha；GIF 保留透明像素。
- MP4 使用主项目的 `h264` 编码器别名和 `veryslow` preset，奇数尺寸正确补齐。
- macOS 产物仅链接系统 Framework / libSystem，universal 包含 arm64 和 x86_64，
  ad-hoc 签名验证通过。
- Windows x64 用 MinGW-w64 GCC 15.2.0 交叉编译完成，通过 PE 架构和系统 DLL 白名单检查。
  本机没有 Windows 环境，未运行 Windows EXE；仓库 CI 已安排 `windows-latest` 原生测试。
- 构建脚本通过 Bash 语法检查，Python 脚本通过编译检查，workflow YAML 可解析。
  GitHub Actions 尚未在远程触发，不能将本地验证等同于远程 CI 通过。

本地生成的详细报告在 `build/smoke-*.json`，构建日志在 `build/logs/`。
这些可再生输出没有加入源码管理。平台包中的 `BUILD-INFO.json` 和 `configuration/`
记录二进制哈希、源版本、构建参数与依赖。以后版本应更新此记录或以新 CI 结果为准。
