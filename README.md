# Asset Archive 专用 FFmpeg

独立编译仓库：完整上游源码、版本锁定、构建、实际导出测试和 GitHub Actions
都在这里。构建脚本不读取或写入 AssetArchive-Dev，也不在线下载源码。

## 保留的功能

依据 AssetArchive-Dev 提交 `a59fec528a4613fe37f54259aa8531fce56f95b4`
中 `src-tauri/src/ffmpeg.rs` 与 `src-tauri/src/scripts/renderer.lua` 的实际调用：

| 类别 | 组件 | 用途 |
| --- | --- | --- |
| 编码器 | `libx264`, `gif`, `png` | MP4/H.264、GIF、MOV/PNG（保留透明度） |
| 解码器 / 解封装器 | `rawvideo` | 从 stdin 读取连续 RGBA 帧 |
| 封装器 | `mp4`, `mov`, `gif` | 项目支持的三个导出格式 |
| 协议 | `pipe`, `file` | 输入管道、输出本地文件 |
| 滤镜 | `scale`, `pad`, `split`, `palettegen`, `paletteuse`, `format`, `buffer`, `buffersink` | Lanczos 缩放、偶数尺寸补齐、GIF 全局调色板与格式转换 |

FFmpeg CLI 和 MOV 封装器还会自动选入自身依赖的内部滤镜、解析器和位流过滤器，
完整列表可见发行包中的 `configuration/config_components.h`。
不包含音频编码器、网络协议、采集设备、硬件编解码、ffplay 或 ffprobe。
PNG 图片序列由主项目自己的图像代码导出；Rust 中预留的 WebP 分支未被 renderer 调用，
也不在本构建范围内。x264 仅启用 8 位、YUV420 和逐行编码，保留 SIMD 与多线程优化。

## 固定源码

`sources/` 直接保存完整、未修改的源码压缩包（不是 Git LFS 指针或构建时下载器）。
`sources/manifest.json` 记录上游 URL、版本与 SHA-256：FFmpeg 8.1.3、
x264 stable `31e19f92f00c7003fa115047ce50978bc98c3a0d`、zlib 1.3.2、NASM 2.16.03。
选择 FFmpeg 8.1 的维护版；新增版本需重新运行全部平台导出测试。
每次构建都会校验源码，解压到独立的 `build/<target>/src/`，不修改原始压缩包。

## 本地编译

需要 Bash、Python 3.9+、Make、Perl、pkg-config 与 C 编译器。使用不含空格的仓库路径。
构建源码和运行时依赖均已随仓库提供；编译器、系统 SDK 等系统工具需预先安装。
NASM 在第一次 x86_64 构建时从随附源码编译为宿主工具。

macOS 需要 Xcode Command Line Tools 和 `pkg-config`（如 `brew install pkg-config`）：

```sh
bash scripts/build.sh universal-apple-darwin
# 也可以单独构建其中一个架构：
bash scripts/build.sh aarch64-apple-darwin
bash scripts/build.sh x86_64-apple-darwin
```

产物兼容目标：Apple Silicon 为 macOS 11.0+，Intel 为 macOS 10.13+。
这是部署目标设置；CI 在当前 macOS runner 上验证，不代表在所有旧系统上实测。
不使用 `-march=native`。通用产物通过 `lipo` 合并两个独立构建并重新进行 ad-hoc 签名。

Windows x64 使用 MinGW-w64 交叉编译，可在 Linux 或 macOS 上执行。
例如 Ubuntu 安装 `build-essential gcc-mingw-w64-x86-64 pkg-config python3` 后：

```sh
bash scripts/build.sh x86_64-pc-windows-msvc
```

名称中的 `msvc` 是主应用/Tauri 的目标标识；该独立 EXE 由 MinGW 编译，
通过子进程与 MSVC 构建的主应用兼容，不提供用于 MSVC 链接的静态库。
Windows 发行目标为 Windows 10/11 x64（本地 MinGW 工具链使用系统自带的 UCRT）；
更早的 Windows 不在支持范围。CI 在 `windows-latest` 上运行实际导出测试。

可通过 `JOBS=4` 限制并行度，`PYTHON=python3` 指定 Python，
`CROSS_PREFIX=x86_64-w64-mingw32-` 指定 Windows 交叉编译工具前缀。
重复构建会清理对应目标的中间文件，不会删除其它目标的产物。
不要同时构建同一个 target；多个 x86_64 target 首次构建也应顺序执行以初始化 NASM。

产物在 `dist/<target>/bin/ffmpeg[.exe]`。FFmpeg、x264、zlib 都静态链接，
只动态链接系统库；打包时自动拒绝 Homebrew 路径和额外 Windows 运行时 DLL。

## 验证与打包

测试需要单独的完整 FFmpeg 与 ffprobe 作为参考解码器（例如 macOS 的
`brew install ffmpeg` 或 Windows 的 `choco install ffmpeg`），它们不进入发行包。

```sh
python3 scripts/smoke.py dist/aarch64-apple-darwin/bin/ffmpeg --report build/smoke.json
python3 scripts/package.py archive aarch64-apple-darwin
python3 scripts/package.py archive universal-apple-darwin
python3 scripts/package.py archive x86_64-pc-windows-msvc
python3 scripts/package.py source
```

只打包已经构建的目标即可。参考工具不在 PATH 时使用 `--reference-ffmpeg /path/to/ffmpeg`
和 `--ffprobe /path/to/ffprobe`。Windows EXE 应在 Windows 上运行 smoke 测试。

测试使用主项目完全相同的命令，包括 `-vcodec h264` 别名、`-preset veryslow`、
管道输入、GIF 隐式编码器选择和滤镜链。12 个用例覆盖整尺寸、奇数尺寸、0.5 倍缩放、
分数帧率、单帧、包含空格和中文的输出路径；参考解码器检查格式、帧数、尺寸、像素格式、
MOV RGBA 逐字节一致性和 GIF 透明像素。组件白名单防止裁剪配置意外扩大。

`dist/` 中生成平台压缩包、完整对应源码包，以及每个包的 `.sha256` 文件。
每个平台包附带许可证、构建配置、来源版本、构建脚本哈希、二进制 SHA-256 与系统依赖清单。
锁定源码不等于跨编译器或 SDK 的逐字节可复现；应使用随包的配置和 CI 平台记录定位差异。

## CI 与主项目集成

GitHub Actions 在 push、PR、手动触发或 reusable workflow 调用时构建两个 macOS 架构
及 Windows x64；Windows 交叉构建后必须通过 Windows 原生测试，macOS 构建额外合并通用包。
源码包与所有二进制均上传为 artifacts。推送与 `VERSION` 对应的标签
（例如 `v8.1.3-aa1`）后，只有全部构建和测试通过才创建包含源码的 **draft release**。

主项目后续接入方法见 [docs/integration.md](docs/integration.md)。
本仓库的构建完成不会自动修改应用的 FFmpeg 查找逻辑或发行配置。

## 许可证

由于使用 libx264，本 FFmpeg 可执行文件按 **GPL v2 或更新版本** 发行。
随主应用发行时同时提供本版本完整源码包与随附许可证，详见 [NOTICE.md](NOTICE.md)。
构建脚本同样采用 GPL v2 或更新版本；上游源码保留各自版权及许可。
