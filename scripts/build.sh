#!/usr/bin/env bash
# Build dependencies and FFmpeg entirely within this repository, without downloads.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TARGET=${1:-}
PYTHON=${PYTHON:-python3}
JOBS=${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}

case "$TARGET" in
  aarch64-apple-darwin|x86_64-apple-darwin|x86_64-pc-windows-msvc) ;;
  universal-apple-darwin)
    bash "$ROOT/scripts/build.sh" aarch64-apple-darwin
    bash "$ROOT/scripts/build.sh" x86_64-apple-darwin
    "$PYTHON" "$ROOT/scripts/package.py" universal
    exit 0 ;;
  *) echo "Usage: $0 {aarch64-apple-darwin|x86_64-apple-darwin|universal-apple-darwin|x86_64-pc-windows-msvc}" >&2; exit 2 ;;
esac
for tool in "$PYTHON" make pkg-config perl; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
case "$ROOT" in *' '*) echo "Use a checkout path without spaces (upstream Makefiles requirement)." >&2; exit 1 ;; esac

WORK="$ROOT/build/$TARGET"
PREFIX="$WORK/prefix"
SOURCE="$WORK/src"
HOST_PREFIX="$ROOT/build/host-tools"
mkdir -p "$WORK" "$HOST_PREFIX/bin"
export PATH="$HOST_PREFIX/bin:$PATH"
# Never discover a Homebrew/MSYS2 shared x264 or zlib by accident.
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_PATH=
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
export SOURCE_DATE_EPOCH=1790035200
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS CPATH LIBRARY_PATH SDKROOT

CC=cc
AR=ar
RANLIB=ranlib
STRIP=strip
EXT=
CFLAGS_TARGET=-Os
LDFLAGS_TARGET=
X264_PLATFORM=()
FFMPEG_PLATFORM=()
if [[ "$TARGET" == *-apple-darwin ]]; then
  [[ $(uname -s) == Darwin ]] || { echo "macOS targets require Xcode on macOS." >&2; exit 1; }
  CC=clang
  ARCH=${TARGET%%-*}
  [[ "$ARCH" != aarch64 ]] || ARCH=arm64
  if [[ "$ARCH" == arm64 ]]; then MACOS_MIN=11.0; else MACOS_MIN=10.13; fi
  SDK=$(xcrun --sdk macosx --show-sdk-path)
  CFLAGS_TARGET="-Os -arch $ARCH -isysroot $SDK -mmacosx-version-min=$MACOS_MIN"
  LDFLAGS_TARGET="-arch $ARCH -isysroot $SDK -mmacosx-version-min=$MACOS_MIN"
  export MACOSX_DEPLOYMENT_TARGET=$MACOS_MIN
  X264_PLATFORM=("--host=$ARCH-apple-darwin")
  FFMPEG_PLATFORM=(--target-os=darwin "--arch=$ARCH" --enable-cross-compile)
else
  CROSS=${CROSS_PREFIX:-x86_64-w64-mingw32-}
  CC=${CROSS}gcc
  AR=${CROSS}ar
  RANLIB=${CROSS}ranlib
  STRIP=${CROSS}strip
  EXT=.exe
  CFLAGS_TARGET="-Os -D_WIN32_WINNT=0x0601"
  LDFLAGS_TARGET="-static -static-libgcc"
  X264_PLATFORM=(--host=x86_64-w64-mingw32 "--cross-prefix=$CROSS")
  FFMPEG_PLATFORM=(--target-os=mingw32 --arch=x86_64 --enable-cross-compile "--cross-prefix=$CROSS" --enable-w32threads --disable-pthreads)
fi
command -v "$CC" >/dev/null || { echo "Missing compiler: $CC" >&2; exit 1; }

# Clean only this known target's disposable outputs. Sources are always hash-checked.
rm -rf "$SOURCE" "$PREFIX" "$WORK/ffmpeg" "$WORK/x264"
"$PYTHON" "$ROOT/scripts/sources.py" --extract "$SOURCE"
mkdir -p "$PREFIX/lib/pkgconfig" "$PREFIX/include" "$WORK/ffmpeg" "$WORK/x264"
if [[ "$TARGET" == x86_64-* ]] && [[ ! -x "$HOST_PREFIX/bin/nasm" ]]; then
  (
    cd "$SOURCE/nasm"
    # NASM runs on the build host, even when the final target is Windows.
    CC=cc ./configure --prefix="$HOST_PREFIX"
    make -j"$JOBS"
    if [[ -f nasm.exe ]]; then
      cp nasm.exe "$HOST_PREFIX/bin/nasm.exe"
    else
      cp nasm "$HOST_PREFIX/bin/nasm"
    fi
  )
fi

(
  cd "$SOURCE/zlib"
  if [[ "$TARGET" == *-windows-msvc ]]; then
    make -f win32/Makefile.gcc -j"$JOBS" "PREFIX=$CROSS" "CFLAGS=$CFLAGS_TARGET" libz.a
    cp libz.a "$PREFIX/lib/"
    cp zlib.h zconf.h "$PREFIX/include/"
    sed -e "s|@prefix@|$PREFIX|g" -e 's|@exec_prefix@|${prefix}|g' \
      -e 's|@libdir@|${prefix}/lib|g' -e 's|@sharedlibdir@|${prefix}/lib|g' \
      -e 's|@includedir@|${prefix}/include|g' -e 's|@VERSION@|1.3.2|g' \
      zlib.pc.in > "$PREFIX/lib/pkgconfig/zlib.pc"
  else
    CC="$CC" AR="$AR" RANLIB="$RANLIB" CFLAGS="$CFLAGS_TARGET" LDFLAGS="$LDFLAGS_TARGET" \
      ./configure --static --prefix="$PREFIX"
    make -j"$JOBS"
    make install
  fi
)
(
  cd "$WORK/x264"
  CC="$CC" AR="$AR" RANLIB="$RANLIB" "$SOURCE/x264/configure" \
    --prefix="$PREFIX" --enable-static --enable-pic --disable-cli \
    --disable-opencl --disable-avs --disable-swscale --disable-lavf \
    --disable-ffms --disable-gpac --disable-lsmash --disable-interlaced \
    --bit-depth=8 --chroma-format=420 \
    "--extra-cflags=$CFLAGS_TARGET" "--extra-ldflags=$LDFLAGS_TARGET" \
    "${X264_PLATFORM[@]}"
  make -j"$JOBS"
  make install-lib-static
)
source "$ROOT/scripts/ffmpeg-options.sh"
(
  cd "$WORK/ffmpeg"
  "$SOURCE/ffmpeg/configure" "${FFMPEG_OPTIONS[@]}" "${FFMPEG_PLATFORM[@]}" \
    --prefix="$PREFIX" --cc="$CC" --ar="$AR" --ranlib="$RANLIB" \
    --strip="$STRIP" --pkg-config=pkg-config --pkg-config-flags=--static \
    "--extra-cflags=$CFLAGS_TARGET -I$PREFIX/include" \
    "--extra-ldflags=$LDFLAGS_TARGET -L$PREFIX/lib"
  make -j"$JOBS" all
)
"$PYTHON" "$ROOT/scripts/package.py" stage "$TARGET"
echo "Built $ROOT/dist/$TARGET/bin/ffmpeg$EXT"
