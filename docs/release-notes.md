Asset Archive 专用 FFmpeg：仅保留 RGBA 管道输入与 MP4/H.264、GIF、透明 MOV/PNG 导出链路。

- macOS：Apple Silicon、Intel 及 universal 二进制；Windows：x64 独立 EXE。
- FFmpeg、x264、zlib 静态链接，运行时仅依赖系统库。
- 每个平台已通过原生环境的导出测试；随包提供配置、许可证及 SHA-256。
- `*-source.tar.xz` 是与二进制对应的完整源码和构建脚本。再发行时必须一并提供。
- 此构建适用 GPL v2 或更新版本；详情见包内 NOTICE.md。
- macOS 二进制使用 ad-hoc 签名；应用发行时需使用自己的 Developer ID 重签及公证。
