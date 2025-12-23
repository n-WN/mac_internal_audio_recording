#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import math
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

if __package__ in {None, ""}:
    raise SystemExit("Run from repo root: python3 -m mac_internal_audio_recording.realtime_audio_sender ...")

from av_transport.net import is_loopback_host  # noqa: E402
from av_transport.sync_client import AvSyncClient, ConnectOptions, now_ms, new_id  # noqa: E402


def ensure_swift_recorder(script_dir: Path) -> Path:
    swift_source = script_dir / "core.swift"
    exe = script_dir / "recorder"
    if not swift_source.exists():
        raise FileNotFoundError(f"missing {swift_source}")

    if exe.exists():
        try:
            if exe.stat().st_mtime > swift_source.stat().st_mtime:
                return exe
        except OSError:
            pass

    cmd = ["swiftc", str(swift_source), "-o", str(exe)]
    print(f"[audio] compiling: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return exe


@dataclass(frozen=True)
class WavInfo:
    audio_format: int
    channels: int
    sample_rate: int
    sample_width: int
    block_align: int
    data_offset: int


def parse_wav_info(path: Path) -> WavInfo:
    # Minimal WAV parser for PCM-ish streams (little-endian RIFF/WAVE).
    import io

    data = path.read_bytes()
    if len(data) < 12:
        raise ValueError("wav header too small")
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")

    f = io.BytesIO(data)
    f.seek(12)

    fmt: Optional[Tuple[int, int, int, int, int]] = None  # (fmt, ch, sr, bps, align)
    data_offset: Optional[int] = None

    while True:
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        chunk_id = hdr[0:4]
        chunk_size = int.from_bytes(hdr[4:8], "little")
        chunk_start = f.tell()

        if chunk_id == b"fmt " and chunk_size >= 16:
            chunk = f.read(chunk_size)
            audio_format = int.from_bytes(chunk[0:2], "little")
            channels = int.from_bytes(chunk[2:4], "little")
            sample_rate = int.from_bytes(chunk[4:8], "little")
            block_align = int.from_bytes(chunk[12:14], "little")
            bits_per_sample = int.from_bytes(chunk[14:16], "little")
            fmt = (audio_format, channels, sample_rate, bits_per_sample, block_align)
        elif chunk_id == b"data":
            data_offset = chunk_start
            break

        f.seek(chunk_start + chunk_size)
        if chunk_size % 2 == 1:
            f.seek(1, os.SEEK_CUR)

    if not fmt or data_offset is None:
        raise ValueError("incomplete wav header (missing fmt/data)")

    audio_format, channels, sample_rate, bits_per_sample, block_align = fmt
    if channels <= 0 or sample_rate <= 0 or bits_per_sample <= 0 or block_align <= 0:
        raise ValueError("invalid wav fmt")
    sample_width = bits_per_sample // 8
    if sample_width <= 0:
        raise ValueError("invalid sample_width")

    return WavInfo(
        audio_format=audio_format,
        channels=channels,
        sample_rate=sample_rate,
        sample_width=sample_width,
        block_align=block_align,
        data_offset=data_offset,
    )


def wait_for_wav_header(path: Path, timeout_s: float = 10.0) -> WavInfo:
    deadline = time.time() + timeout_s
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        if path.exists() and path.stat().st_size >= 44:
            try:
                return parse_wav_info(path)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        time.sleep(0.05)
    raise TimeoutError(f"failed to parse wav header: {path} ({last_err})")


def send_audio_start(
    client: AvSyncClient,
    *,
    stream_id: str,
    source: str,
    info: WavInfo,
    max_wait_s: Optional[float] = None,
) -> None:
    msg_id = new_id()
    ack = client.request_ack(
        {
            "v": 1,
            "type": "audio_start",
            "id": msg_id,
            "ts": now_ms(),
            "client": "mac_internal_audio_recording",
            "source": source,
            "stream_id": stream_id,
            "codec": "pcm",
            "sample_rate": info.sample_rate,
            "channels": info.channels,
            "sample_width": info.sample_width,
        },
        max_wait_s=max_wait_s,
    )
    if not ack.get("ok"):
        raise RuntimeError(f"server error: {ack.get('error')}")
    resumed = " (resumed)" if ack.get("resumed") else ""
    print(f"[audio] started{resumed} -> {ack.get('path')}")


def send_audio_end(client: AvSyncClient, *, stream_id: str, max_wait_s: Optional[float] = None) -> None:
    msg_id = new_id()
    ack = client.request_ack(
        {
            "v": 1,
            "type": "audio_end",
            "id": msg_id,
            "ts": now_ms(),
            "client": "mac_internal_audio_recording",
            "stream_id": stream_id,
        },
        max_wait_s=max_wait_s,
    )
    if not ack.get("ok"):
        raise RuntimeError(f"server error: {ack.get('error')}")
    print(f"[audio] ended -> {ack.get('path')}")


def stream_pcm_from_wav_file(
    client: AvSyncClient,
    *,
    stream_id: str,
    source: str,
    wav_path: Path,
    proc: subprocess.Popen[str],
    chunk_sleep_s: float,
    refresh_interval_s: float,
) -> None:
    info = wait_for_wav_header(wav_path)

    client.options.on_connect = lambda c: send_audio_start(c, stream_id=stream_id, source=source, info=info)

    pos = info.data_offset
    remainder = b""
    seq = 0
    stop_requested_at: Optional[float] = None
    last_refresh = time.time()

    def _request_stop() -> None:
        nonlocal stop_requested_at
        if stop_requested_at is None:
            stop_requested_at = time.time()
            print("\n[audio] stop requested -> stopping swift recorder")
            try:
                proc.send_signal(signal.SIGINT)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

    try:
        with wav_path.open("rb") as f:
            f.seek(pos)
            while True:
                try:
                    # Read whatever has been appended so far.
                    try:
                        size = wav_path.stat().st_size
                    except FileNotFoundError:
                        size = 0
                    if size > pos:
                        f.seek(pos)
                        to_read = min(size - pos, 256 * 1024)
                        chunk = f.read(to_read)
                        pos += len(chunk)

                        buf = remainder + chunk
                        aligned = len(buf) - (len(buf) % info.block_align)
                        if aligned:
                            payload = buf[:aligned]
                            remainder = buf[aligned:]
                            client.send(
                                {
                                    "v": 1,
                                    "type": "audio_chunk",
                                    "id": new_id(),
                                    "ts": now_ms(),
                                    "client": "mac_internal_audio_recording",
                                    "stream_id": stream_id,
                                    "seq": seq,
                                },
                                payload,
                            )
                            seq += 1
                        else:
                            remainder = buf
                        continue

                    if proc.poll() is not None:
                        # Process finished; do a final drain then end.
                        final_size = wav_path.stat().st_size if wav_path.exists() else 0
                        if final_size > pos:
                            continue
                        break

                    if stop_requested_at is not None and proc.poll() is None:
                        elapsed = time.time() - stop_requested_at
                        if elapsed > 5:
                            try:
                                proc.terminate()
                            except Exception:
                                pass
                        if elapsed > 10:
                            try:
                                proc.kill()
                            except Exception:
                                pass

                    now = time.time()
                    if refresh_interval_s > 0 and client.is_connected and now - last_refresh >= refresh_interval_s:
                        send_audio_start(client, stream_id=stream_id, source=source, info=info)
                        last_refresh = now

                    time.sleep(chunk_sleep_s)
                except KeyboardInterrupt:
                    _request_stop()
                    continue
    finally:
        try:
            send_audio_end(client, stream_id=stream_id, max_wait_s=2.0)
        except Exception:
            pass


def gen_sine_pcm_s16le(
    *,
    sample_rate: int,
    channels: int,
    duration_s: float,
    freq_hz: float,
) -> bytes:
    total_frames = int(sample_rate * duration_s)
    out = bytearray()
    amp = 0.2
    for i in range(total_frames):
        t = i / sample_rate
        v = int(max(-1.0, min(1.0, math.sin(2 * math.pi * freq_hz * t) * amp)) * 32767)
        for _ in range(channels):
            out += int(v).to_bytes(2, "little", signed=True)
    return bytes(out)


def stream_test_sine(
    client: AvSyncClient,
    *,
    stream_id: str,
    duration_s: float,
    chunk_ms: int,
    sample_rate: int = 48_000,
    channels: int = 2,
    refresh_interval_s: float = 0.0,
) -> None:
    info = WavInfo(
        audio_format=1,
        channels=channels,
        sample_rate=sample_rate,
        sample_width=2,
        block_align=channels * 2,
        data_offset=0,
    )

    client.options.on_connect = lambda c: send_audio_start(c, stream_id=stream_id, source="test_sine", info=info)

    chunk_s = chunk_ms / 1000.0
    seq = 0
    freq = 440.0
    last_refresh = time.time()

    remaining: Optional[float] = None if duration_s <= 0 else duration_s
    try:
        while remaining is None or remaining > 0:
            step = chunk_s if remaining is None else min(chunk_s, remaining)
            payload = gen_sine_pcm_s16le(
                sample_rate=sample_rate,
                channels=channels,
                duration_s=step,
                freq_hz=freq,
            )
            client.send(
                {
                    "v": 1,
                    "type": "audio_chunk",
                    "id": new_id(),
                    "ts": now_ms(),
                    "client": "mac_internal_audio_recording",
                    "stream_id": stream_id,
                    "seq": seq,
                },
                payload,
            )
            seq += 1
            time.sleep(step)
            if remaining is not None:
                remaining -= step
            if refresh_interval_s > 0 and client.is_connected and time.time() - last_refresh >= refresh_interval_s:
                send_audio_start(client, stream_id=stream_id, source="test_sine", info=info)
                last_refresh = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            send_audio_end(client, stream_id=stream_id, max_wait_s=2.0)
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    def _env(name: str) -> Optional[str]:
        value = os.environ.get(name)
        return value.strip() if value else None

    parser = argparse.ArgumentParser(description="实时同步音频到本地对端平台（TCP 自定义协议）")
    parser.add_argument("--host", default=_env("AV_PLATFORM_HOST") or "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(_env("AV_PLATFORM_PORT") or 8765))
    parser.add_argument("--token", default=_env("AV_TOKEN") or "", help="共享 token（建议配合 TLS）")
    parser.add_argument("--session-id", default=_env("AV_SESSION_ID") or "", help="会话 id（为空则自动生成）")
    parser.add_argument("--tls", action=argparse.BooleanOptionalAction, default=False, help="启用 TLS")
    parser.add_argument("--tls-insecure", action=argparse.BooleanOptionalAction, default=False, help="跳过 TLS 证书校验（仅自签名联调）")
    parser.add_argument("--tls-ca", default=_env("AV_TLS_CA") or "", help="TLS CA 文件（PEM）")
    parser.add_argument("--tls-server-name", default=_env("AV_TLS_SERVER_NAME") or "", help="TLS SNI/校验域名")
    parser.add_argument("--unsafe-plain", action="store_true", help="允许非 localhost 明文传输（不安全，不推荐）")

    parser.add_argument("--test-sine", action="store_true", help="不调用 Swift，发送实时正弦波（用于 localhost 联调）")
    parser.add_argument(
        "--continuous",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="持续发送直到 Ctrl+C（等价于 --duration 0）",
    )
    parser.add_argument("--duration", type=float, default=3.0, help="录制/发送时长（秒，0=持续直到 Ctrl+C）")
    parser.add_argument("--chunk-ms", type=int, default=100, help="发送 chunk 大小（毫秒，仅 test-sine）")

    parser.add_argument(
        "--recording-type",
        choices=["internal", "microphone"],
        default="internal",
        help="Swift 录制源（仅非 test-sine）",
    )
    parser.add_argument("--stream-id", default=_env("AV_STREAM_ID") or "", help="音频流 id（为空则自动生成）")
    parser.add_argument(
        "--output",
        default="",
        help="本地 wav 输出路径（默认 output/recording_YYYYMMDD_HHMMSS.wav）",
    )
    parser.add_argument("--chunk-sleep", type=float, default=0.05, help="tail 文件轮询间隔（秒）")
    parser.add_argument("--refresh-interval", type=float, default=0.0, help="周期性发送 audio_start（秒，0=禁用）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.continuous:
        args.duration = 0.0
    if args.duration < 0:
        raise SystemExit("--duration must be >= 0")
    if not args.token:
        raise SystemExit("--token (or env AV_TOKEN) is required")
    if not args.tls and not args.unsafe_plain and not is_loopback_host(args.host):
        raise SystemExit("refuse plain TCP to non-localhost; use --tls (recommended) or --unsafe-plain")
    if not args.session_id:
        args.session_id = uuid.uuid4().hex
    if not args.stream_id:
        args.stream_id = uuid.uuid4().hex

    script_dir = Path(__file__).resolve().parent

    client = AvSyncClient(
        ConnectOptions(
            host=args.host,
            port=args.port,
            token=args.token,
            client_name="mac_internal_audio_recording",
            session_id=args.session_id,
            tls=bool(args.tls),
            tls_server_name=(args.tls_server_name or None),
            tls_ca_file=(args.tls_ca or None),
            tls_insecure=bool(args.tls_insecure),
        )
    )
    try:
        if args.test_sine:
            stream_test_sine(
                client,
                stream_id=args.stream_id,
                duration_s=args.duration,
                chunk_ms=args.chunk_ms,
                refresh_interval_s=args.refresh_interval,
            )
            return 0

        exe = ensure_swift_recorder(script_dir)

        if args.output:
            wav_path = Path(args.output)
        else:
            out_dir = script_dir / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            wav_path = out_dir / f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"

        # Start Swift recorder and tail the produced wav file.
        proc = subprocess.Popen(
            [str(exe), str(wav_path), str(args.duration), args.recording_type],
            cwd=str(script_dir),
            text=True,
        )
        stream_pcm_from_wav_file(
            client,
            stream_id=args.stream_id,
            source=args.recording_type,
            wav_path=wav_path,
            proc=proc,
            chunk_sleep_s=args.chunk_sleep,
            refresh_interval_s=args.refresh_interval,
        )
        if proc.poll() is None:
            proc.wait(timeout=10)

        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
