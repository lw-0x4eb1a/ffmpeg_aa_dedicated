# Redistribution notices

This dedicated FFmpeg executable includes FFmpeg (GPL v2 or later when built
with `--enable-gpl`), x264 (GPL v2 or later), and zlib (zlib license).
It contains no `--enable-nonfree` or `--enable-version3` components.
The build scripts in this repository are licensed under GPL v2 or later.
Upstream files retain their own copyright and license notices.

Every binary release must be accompanied by its matching
`ffmpeg-aa-<version>-source.tar.xz` archive. That archive includes the complete,
unmodified upstream source archives, their pinned hashes, build scripts, and CI.
Keep the `licenses/`, `configuration/`, `BUILD-INFO.json`, and this notice with
the redistributed executable. When incorporating it into an application release,
make the matching source archive available from the same release/download location.
An upstream URL alone is not a substitute for supplying the corresponding source.

NASM is a build tool under the BSD 2-clause license; its complete source and license
are included in the source archive. It is not linked into or required to run FFmpeg.
Standard OS libraries are supplied by the operating system.

The application invokes FFmpeg as a separate process. This repository does not
change or determine the license of the Asset Archive application.

The macOS executables are ad-hoc signed for local execution. The application
distributor must sign the embedded executable with its Developer ID and include it
in the application's notarization process.
