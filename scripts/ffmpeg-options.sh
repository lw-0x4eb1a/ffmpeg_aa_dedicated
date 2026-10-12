# Required by AssetArchive-Dev/src-tauri/src/ffmpeg.rs at
# a59fec528a4613fe37f54259aa8531fce56f95b4. Keep smoke.py in sync.
# FFmpeg may select internal filters, parsers and bitstream filters as dependencies.
FFMPEG_OPTIONS=(
  --disable-everything
  --disable-autodetect
  --disable-programs
  --enable-ffmpeg
  --disable-doc
  --disable-debug
  --disable-network
  --disable-avdevice
  --disable-swresample
  --disable-shared
  --enable-static
  --enable-small
  --enable-gpl
  --enable-libx264
  --enable-zlib
  --enable-avcodec
  --enable-avformat
  --enable-avfilter
  --enable-swscale
  --enable-encoder=libx264,gif,png
  --enable-decoder=rawvideo
  --enable-demuxer=rawvideo
  --enable-muxer=mp4,mov,gif
  --enable-protocol=file,pipe
  --enable-filter=buffer,buffersink,format,scale,pad,split,palettegen,paletteuse
)
