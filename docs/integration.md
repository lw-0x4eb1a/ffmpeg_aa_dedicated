# 主项目接入说明

本仓库不修改 AssetArchive-Dev；以下步骤由主项目后续变更完成。

1. 从同一个 FFmpeg release 取得平台包、对应源码包及 SHA-256，验证后解压。
   当前主项目发行 macOS universal 与 Windows x64，分别取
   `universal-apple-darwin` 和 `x86_64-pc-windows-msvc`。
2. 把 `bin/ffmpeg` 或 `bin/ffmpeg.exe` 放入应用 resources，保留执行权限。
   把 `licenses/`、`NOTICE.md`、`BUILD-INFO.json` 和 `configuration/` 一起分发。
   将匹配的 `*-source.tar.xz` 放到同一应用 release 的下载资产中。
3. 修改 FFmpeg 路径解析：用户明确设置的自定义路径优先，其次是随应用附带的资源路径，
   再考虑旧版下载目录。使用 Tauri 的资源路径解析 API，不依赖启动工作目录。
   更新 `IsAvailable` / 状态查询 / 安装界面，使附带版本被识别为可用。
   当前 `FFcore.Encoder` 已接受二进制绝对路径，导出命令不需要变化。
4. macOS 打包时使用主项目 Developer ID 重签 FFmpeg，然后对整个应用签名、公证。
   本仓库的 ad-hoc 签名只用于构建验证，不是 Developer ID 签名。
5. 在干净的 Windows 和 macOS 上测试，无预装 FFmpeg 也能导出 MP4/GIF/MOV，
   并确认卸载用户下载的 FFmpeg 不会删除应用自带资源。

如果采用 Tauri `bundle.externalBin` 而非 resources，请按其要求把二进制重命名为
`ffmpeg-<target-triple>[.exe]`。本仓库目录中的 target 与主项目一致。
当前应用使用自有 Rust `FfmpegCommand::new_with_path` 调用方式，resources 中的
绝对路径通常更直接。这里没有替主项目设置任何 bundle 配置。
