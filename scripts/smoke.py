#!/usr/bin/env python3
"""Exercise Asset Archive's actual stdin RGBA export commands using a reference decoder."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def run(command, data=None):
    result = subprocess.run(command, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise AssertionError(f"Command failed: {command}\n{result.stderr.decode(errors='replace')}")
    return result.stdout


def component_names(binary, option, pattern):
    output = run([binary, "-hide_banner", option]).decode()
    return set(re.findall(pattern, output, re.M)) - {"="}


def check_components(binary):
    expected = {
        "-encoders": (r"^ [VAS][A-Z.]{5}\s+(\S+)", {"libx264", "gif", "png"}),
        "-decoders": (r"^ [VAS][A-Z.]{5}\s+(\S+)", {"rawvideo"}),
        "-demuxers": (r"^ D\s+(\S+)", {"rawvideo"}),
        "-muxers": (r"^  E\s+(\S+)", {"mp4", "mov", "gif"}),
    }
    for option, (pattern, wanted) in expected.items():
        actual = component_names(binary, option, pattern)
        if actual != wanted:
            raise AssertionError(f"{option}: expected {wanted}, got {actual}")
    protocols = run([binary, "-hide_banner", "-protocols"]).decode()
    actual = set(re.findall(r"^  (\S+)\s*$", protocols, re.M))
    if actual != {"file", "pipe"}:
        raise AssertionError(f"Unexpected protocols: {actual}")
    filters = component_names(binary, "-filters", r"^ [TSC.]{2,3}\s+(\S+)")
    wanted = {"buffer", "buffersink", "format", "scale", "pad", "split", "palettegen", "paletteuse"}
    if not wanted <= filters:
        raise AssertionError(f"Missing filters: {wanted - filters}")
    version = run([binary, "-version"]).decode()
    if "ffmpeg version" not in version or "--enable-gpl" not in version or "--enable-nonfree" in version:
        raise AssertionError("Unexpected version/license configuration")


def frames(width, height, count):
    # Few colors give GIF an exact palette; motion prevents frame deduplication.
    data = bytearray()
    for frame in range(count):
        for y in range(height):
            for x in range(width):
                color = ((255, 0, 0), (0, 255, 0), (0, 0, 255))[(x // 4 + y // 4 + frame) % 3]
                alpha = 0 if x < 3 else (128 if x < 6 else 255)
                data.extend((*color, alpha))
    return bytes(data)


def export(binary, decoder, probe, directory, fmt, width, height, scale, count, rate):
    output = directory / f"export {fmt} {width}x{height} {scale} {count}." / "动画"
    output.parent.mkdir(parents=True, exist_ok=True)
    output = output.with_suffix("." + fmt)
    data = frames(width, height, count)
    command = [binary, "-hide_banner", "-f", "rawvideo", "-video_size", f"{width}x{height}",
               "-pixel_format", "rgba", "-r", str(rate), "-i", "pipe:0"]
    filters = []
    if fmt == "mp4":
        # Deliberately use the app's codec alias, not an explicit libx264 override.
        command += ["-vcodec", "h264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryslow"]
    elif fmt == "mov":
        command += ["-vcodec", "png", "-pix_fmt", "rgba"]
    if scale != 1:
        filters.append(f"scale={scale:.2f}*iw:-1:flags=lanczos")
    if fmt == "mp4":
        filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
    elif fmt == "gif":
        filters.append("split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse")
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-y", "-f", fmt, str(output)]
    run(command, data)
    metadata = json.loads(run([probe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                              "-show_streams", "-of", "json", str(output)]))
    stream = metadata["streams"][0]
    expected_codec = {"mp4": "h264", "mov": "png", "gif": "gif"}[fmt]
    assert stream["codec_name"] == expected_codec, stream
    assert int(stream["nb_read_frames"]) == count, stream
    if fmt == "mp4":
        assert stream["pix_fmt"] == "yuv420p", stream
        assert stream["width"] % 2 == stream["height"] % 2 == 0, stream
    elif fmt == "mov":
        assert stream["pix_fmt"] == "rgba", stream
    if scale == 1:
        expected_width = width + (width % 2 if fmt == "mp4" else 0)
        expected_height = height + (height % 2 if fmt == "mp4" else 0)
        assert (stream["width"], stream["height"]) == (expected_width, expected_height), stream
    else:
        scaled_width = int(width * scale)
        scaled_height = int(height * scaled_width / width + 0.5)
        if fmt == "mp4":
            scaled_width += scaled_width % 2
            scaled_height += scaled_height % 2
        assert (stream["width"], stream["height"]) == (scaled_width, scaled_height), stream
    if fmt != "gif":
        numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
        assert abs(numerator / denominator - rate) < 0.01, stream
    decoded = run([decoder, "-v", "error", "-i", str(output), "-map", "0:v:0",
                   "-fps_mode", "passthrough", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"])
    assert len(decoded) == stream["width"] * stream["height"] * count * 4
    if fmt == "mov" and scale == 1:
        assert decoded == data, "MOV did not preserve RGBA bytes, including semi-transparent pixels"
    if fmt == "gif" and scale == 1:
        for i in range(0, len(data), 4):
            if data[i + 3] == 0:
                assert decoded[i + 3] == 0, "GIF lost transparent pixels"
            elif data[i + 3] == 255:
                assert decoded[i:i + 4] == data[i:i + 4], "GIF changed opaque palette colors"
    result = {"format": fmt, "input": [width, height], "scale": scale, "frames": count,
              "rate": rate, "output": [stream["width"], stream["height"]], "bytes": output.stat().st_size}
    print("PASS", json.dumps(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=lambda value: str(Path(value).resolve()))
    parser.add_argument("--reference-ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    check_components(args.binary)
    results = []
    with tempfile.TemporaryDirectory(prefix="ffmpeg-aa-") as temp:
        for fmt in ["mp4", "gif", "mov"]:
            for width, height, scale, count, rate in [(32, 24, 1, 6, 30), (31, 27, 1, 6, 12.5),
                                                      (31, 27, 0.5, 6, 30), (17, 19, 1, 1, 30)]:
                results.append(export(args.binary, args.reference_ffmpeg, args.ffprobe,
                                      Path(temp), fmt, width, height, scale, count, rate))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"binary": args.binary, "passed": results}, indent=2) + "\n")
    print(f"All {len(results)} export cases and component allowlists passed.")


if __name__ == "__main__":
    main()
