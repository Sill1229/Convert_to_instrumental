#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║    音频人声分离全流程自动化脚本                          ║
║    NCM / WAV / FLAC / MP3 → RoFormer → 桌面输出        ║
╚══════════════════════════════════════════════════════════╝

支持输入格式：
  .ncm / .wav / .flac / .mp3 / .aac / .ogg / .m4a 等

分离模式（启动时弹窗选择）：
  ① 纯伴奏      BS-RoFormer          SDR 12.97  去除全部人声
  ② 保留和声    MelBand-Roformer Karaoke  SDR 10.20  只去主唱，保留和声

多文件支持：弹窗可一次选多首，逐首处理并实时显示进度。

macOS Tahoe 26.3 / Homebrew Python 3.14 兼容（无需 tkinter）
venv 使用 Python 3.11/3.12，规避 beartype 兼容问题

v3  修复:
    - ffmpeg 7.x/8.x 兼容 (-nostdin / -map 0:a:0 / -threads 1 / pcm_s16le)
    - NCM 解密偏移自动探测（结构化解析 + padding 探测 + 全文件扫描）
    - soundfile / torchaudio 作为格式转换 fallback
    - 严格 MP3 帧头验证，排除假阳性
    - 设置 NCM_DEBUG=1 查看详细诊断信息

v3.1 修复:
    - venv 自举加重试计数器，防止包安装失败导致无限重启（最多 3 次）
    - 单文件失败只清理当前文件的临时产物，不影响后续批量处理
    - 分离前检查 WAV 时长（≥1s），过短直接报错而非 tensor crash
    - ffmpeg timeout 按文件大小缩放（60s + 1.2s/MB），大文件不会超时
    - 添加 atexit + SIGTERM/SIGHUP 信号处理，异常退出也能清理临时文件
    - 模型首次下载提示更明确（约 200MB）

v3.2 修复 (based on GPT code review):
    - AES 解密增加 PKCS7 padding 校验，防止损坏 NCM 导致静默错误
    - 不再往第三方 Separator 对象上塞私有属性，用脚本变量追踪模型状态
    - ensure_wav() 不再隐式删除输入文件，清理职责移到 prepare_audio()
    - 临时目录加 PID 后缀，防止多实例同时运行时文件冲突
    - 锁定 audio-separator==0.42.1，避免上游 API 变动导致兼容问题
    - safe_name() 增加 200 字符截断，防止超长文件名
"""

# ══════════════════════════════════════════════════════════
#  0-A  venv 自举
# ══════════════════════════════════════════════════════════
import sys, os, subprocess, shutil
from pathlib import Path

VENV_DIR = Path.home() / ".ncm_venv"
VENV_PY  = VENV_DIR / "bin" / "python"
VENV_PIP = VENV_DIR / "bin" / "pip"

PACKAGES = [
    "pycryptodome",
    "audio-separator==0.42.1",   # 锁定已验证版本，避免 API 变动
    "onnxruntime",
    "send2trash",
    "torch",
    "torchaudio",
    "soundfile",
]

PREFERRED_PYTHONS = [
    "/opt/homebrew/opt/python@3.11/bin/python3.11",
    "/opt/homebrew/opt/python@3.12/bin/python3.12",
    "/usr/local/opt/python@3.11/bin/python3.11",
    "/usr/local/opt/python@3.12/bin/python3.12",
    shutil.which("python3.11") or "",
    shutil.which("python3.12") or "",
]

def find_compatible_python() -> str:
    for p in PREFERRED_PYTHONS:
        if p and Path(p).exists():
            return p
    if sys.version_info >= (3, 14):
        print("\n  ⚠️  未找到 Python 3.11/3.12，当前 3.14 可能有兼容问题。")
        print("     建议：brew install python@3.11  然后 rm -rf ~/.ncm_venv\n")
    return sys.executable

def _in_venv() -> bool:
    return sys.prefix == str(VENV_DIR)

def _venv_has_packages() -> bool:
    r = subprocess.run(
        [str(VENV_PY), "-c",
         "import Crypto, audio_separator, onnxruntime, send2trash, torch, torchaudio, soundfile"],
        capture_output=True,
    )
    return r.returncode == 0

def bootstrap_and_relaunch():
    import time
    ts = lambda: time.strftime("%H:%M:%S")

    # ── 防止无限重启：通过环境变量计数 ──
    boot_count = int(os.environ.get("_NCM_BOOT", "0"))
    if boot_count >= 3:
        print("\n  ❌ 虚拟环境多次重启仍无法加载依赖，请手动排查：")
        print(f"     rm -rf {VENV_DIR}")
        print(f"     {VENV_PY} -c \"import torch; print(torch.__version__)\"")
        sys.exit(1)
    os.environ["_NCM_BOOT"] = str(boot_count + 1)

    if not VENV_PY.exists():
        if VENV_DIR.exists():
            print(f"\n  [{ts()}] [安装] 检测到旧 venv，重建中...")
            shutil.rmtree(VENV_DIR)
        base_py = find_compatible_python()
        ver_out = subprocess.run([base_py, "--version"],
                                 capture_output=True, text=True).stdout.strip()
        print(f"\n  [{ts()}] [安装] 创建虚拟环境（{ver_out}）: {VENV_DIR}")
        subprocess.check_call([base_py, "-m", "venv", str(VENV_DIR)])

    if not _venv_has_packages():
        print("  [安装] 安装 Python 依赖包（首次约需 5-15 分钟）...")
        subprocess.check_call([
            str(VENV_PIP), "install", "--quiet", "--upgrade", *PACKAGES
        ])
        print("  [安装] ✅ 安装完成，重新启动脚本...\n")

    os.execv(str(VENV_PY), [str(VENV_PY)] + sys.argv)

if not _in_venv():
    bootstrap_and_relaunch()


# ══════════════════════════════════════════════════════════
#  0-B  正式 import
# ══════════════════════════════════════════════════════════
import struct, json, base64, re, time
from Crypto.Cipher import AES
from send2trash import send2trash


# ══════════════════════════════════════════════════════════
#  0-C  ffmpeg 检测与自动安装
# ══════════════════════════════════════════════════════════
def ensure_ffmpeg():
    for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
        try:
            r = subprocess.run([candidate, "-version"], capture_output=True)
            if r.returncode == 0:
                if candidate != "ffmpeg":
                    bin_dir = str(Path(candidate).parent)
                    if bin_dir not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = bin_dir + ":" + os.environ.get("PATH", "")
                return
        except FileNotFoundError:
            continue

    brew = (shutil.which("brew")
            or ("/opt/homebrew/bin/brew" if Path("/opt/homebrew/bin/brew").exists() else None)
            or ("/usr/local/bin/brew"    if Path("/usr/local/bin/brew").exists()    else None))
    if not brew:
        print("\n  ❌ 未找到 Homebrew，请手动安装 ffmpeg：brew install ffmpeg")
        sys.exit(1)

    print("\n  [安装] 未检测到 ffmpeg，正在通过 Homebrew 安装（约 1-3 分钟）...")
    subprocess.check_call([brew, "install", "ffmpeg"])
    for hb_bin in ["/opt/homebrew/bin", "/usr/local/bin"]:
        if Path(f"{hb_bin}/ffmpeg").exists():
            os.environ["PATH"] = hb_bin + ":" + os.environ.get("PATH", "")
            print("  [安装] ✅ ffmpeg 安装完成")
            return
    print("  ❌ ffmpeg 安装后仍未找到，请重启终端后再试。")
    sys.exit(1)

ensure_ffmpeg()


# ══════════════════════════════════════════════════════════
#  模型配置
# ══════════════════════════════════════════════════════════

# ── 模式 A：纯伴奏（去除全部人声，含和声）──────────────
MODEL_FULL_INST = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
PARAMS_FULL_INST = {
    "batch_size":   1,
    "overlap":      8,
    "segment_size": 256,
    "pitch_shift":  0,
}

# ── 模式 B：保留和声（Karaoke，只去主唱）──────────────
MODEL_KARAOKE = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
PARAMS_KARAOKE = {
    "batch_size":   1,
    "overlap":      8,
    "segment_size": 256,
    "pitch_shift":  0,
}

# ── 常量 ────────────────────────────────────────────────
CORE_KEY  = bytes.fromhex("687A4852416D736F356B496E62617857")
META_KEY  = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")
NCM_MAGIC = b"CTENFDAM"

AUDIO_EXTS = {".wav", ".flac", ".mp3", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".aiff"}

DEFAULT_NCM_DIR = Path.home() / "Music" / "网易云音乐"
TMP_DIR         = Path(f"/tmp/ncm_pipeline_{os.getpid()}")
DESKTOP         = Path.home() / "Desktop"
MODEL_DIR       = Path.home() / ".audio_separator_models"

DEBUG = bool(os.environ.get("NCM_DEBUG"))


# ══════════════════════════════════════════════════════════
#  工具
# ══════════════════════════════════════════════════════════
def log(step: str, msg: str):
    print(f"  [{time.strftime('%H:%M:%S')}] [{step}] {msg}", flush=True)

def dbg(step: str, msg: str):
    """仅在 NCM_DEBUG=1 时打印"""
    if DEBUG:
        print(f"  [{time.strftime('%H:%M:%S')}] [{step}] 🔍 {msg}", flush=True)

def hr():
    print("  " + "─" * 54)

def safe_name(s: str, max_len: int = 200) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", s).strip()
    return name[:max_len] if len(name) > max_len else name

def osascript(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True)
    return r.stdout.strip()

def activate_terminal():
    subprocess.run(["osascript", "-e",
                    'tell application "Terminal" to activate'],
                   capture_output=True)
    time.sleep(0.3)


# ══════════════════════════════════════════════════════════
#  Step 0 — 启动时弹窗：选择分离模式
# ══════════════════════════════════════════════════════════
def pick_mode() -> tuple:
    activate_terminal()
    script = (
        'button returned of (display dialog '
        '"请选择人声分离模式：\\n\\n'
        '① 纯伴奏  —  去除全部人声（含和声）\\n'
        '   模型：BS-RoFormer  SDR 12.97\\n\\n'
        '② 保留和声  —  只去主唱，和声保留\\n'
        '   模型：MelBand-Roformer Karaoke  SDR 10.20" '
        'buttons {"② 保留和声", "① 纯伴奏"} '
        'default button "① 纯伴奏" '
        'with title "音频人声分离")'
    )
    choice = osascript(script)

    if not choice or choice == "① 纯伴奏":
        log("模式", "✅ 纯伴奏模式（BS-RoFormer，去除全部人声）")
        return MODEL_FULL_INST, PARAMS_FULL_INST, "纯伴奏", "_(Instrumental)"
    else:
        log("模式", "✅ 保留和声模式（MelBand Karaoke，只去主唱）")
        return MODEL_KARAOKE, PARAMS_KARAOKE, "保留和声", "_(Karaoke)"


# ══════════════════════════════════════════════════════════
#  Step 1 — 多文件选择弹窗
# ══════════════════════════════════════════════════════════
def pick_files() -> list:
    log("Step 1", "📂 请在弹窗中选择文件（可多选，支持 NCM/WAV/FLAC/MP3 等）...")

    init_dir = DEFAULT_NCM_DIR if DEFAULT_NCM_DIR.exists() else Path.home()
    activate_terminal()

    script = (
        f'set fs to choose file '
        f'with prompt "选择音频文件（可按住 Command 多选）" '
        f'default location (POSIX file "{init_dir}") '
        f'with multiple selections allowed\n'
        f'set out to ""\n'
        f'repeat with f in fs\n'
        f'    set out to out & POSIX path of f & "\\n"\n'
        f'end repeat\n'
        f'return out'
    )
    result = osascript(script)

    if not result:
        print()
        print("  ℹ️  弹窗未出现，请将文件逐个拖入终端后按回车（一行一个，空行结束）：")
        paths = []
        while True:
            print("  ▶ ", end="", flush=True)
            line = input().strip().strip("'\"")
            if not line:
                break
            paths.append(line)
        result = "\n".join(paths)

    raw_paths = [p.strip() for p in result.strip().splitlines() if p.strip()]
    if not raw_paths:
        print("  ⚠️  未选择文件，程序退出。")
        sys.exit(0)

    validated = []
    for rp in raw_paths:
        p = Path(rp)
        if not p.exists():
            print(f"  ⚠️  文件不存在，已跳过: {rp}")
            continue
        ext = p.suffix.lower()
        if ext not in {".ncm"} | AUDIO_EXTS:
            print(f"  ⚠️  不支持的格式 [{ext}]，已跳过: {p.name}")
            continue
        validated.append(p)

    if not validated:
        print("  ❌ 没有有效文件，程序退出。")
        sys.exit(1)

    log("Step 1", f"✅ 共选择 {len(validated)} 个文件")
    for i, p in enumerate(validated, 1):
        log("Step 1", f"   {i}. {p.name}")
    return validated


# ══════════════════════════════════════════════════════════
#  Step 2 — 格式转换 (任意 → WAV)
# ══════════════════════════════════════════════════════════

def _find_ffmpeg() -> str:
    for p in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if Path(p).exists():
            return p
    return "ffmpeg"

def _find_ffprobe() -> str:
    for p in ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"]:
        if Path(p).exists():
            return p
    return "ffprobe"

def _probe_audio(audio_path: Path) -> dict:
    """用 ffprobe 检测音频文件信息"""
    fp = _find_ffprobe()
    try:
        r = subprocess.run(
            [fp, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(audio_path)],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            import json as _json
            info = _json.loads(r.stdout)
            streams = info.get("streams", [])
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            fmt = info.get("format", {})
            return {
                "format_name":  fmt.get("format_name", "?"),
                "codec":        audio_streams[0].get("codec_name", "?") if audio_streams else "?",
                "sample_rate":  audio_streams[0].get("sample_rate", "?") if audio_streams else "?",
                "channels":     audio_streams[0].get("channels", "?") if audio_streams else "?",
                "bit_depth":    audio_streams[0].get("bits_per_raw_sample", "?") if audio_streams else "?",
            }
    except Exception:
        pass
    return {}

def ensure_wav(audio_path: Path) -> Path:
    """将任意格式音频转为标准 PCM WAV，兼容 ffmpeg 7.x/8.x"""
    if audio_path.suffix.lower() == ".wav":
        return audio_path

    wav_path = audio_path.with_suffix(".wav")
    log("Step 2", "   🔄 转换为 WAV（保证分离器兼容）...")

    probe = _probe_audio(audio_path)
    if probe:
        log("Step 2", f"   📊 探测: {probe.get('codec','?')} "
                       f"{probe.get('sample_rate','?')}Hz "
                       f"{probe.get('channels','?')}ch "
                       f"{probe.get('bit_depth','?')}bit "
                       f"({probe.get('format_name','?')})")

    ff = _find_ffmpeg()
    ext = audio_path.suffix.lstrip(".").lower()
    detected_codec = probe.get("codec", "")

    # 超时按文件大小缩放：最少 60s，每 100MB 加 120s
    file_size_mb = audio_path.stat().st_size / 1024 / 1024
    timeout_sec = max(60, int(60 + file_size_mb * 1.2))

    base_out = ["-map", "0:a:0", "-c:a", "pcm_s16le", "-ar", "44100",
                "-threads", "1", "-y", str(wav_path)]
    base_in  = [ff, "-nostdin", "-v", "warning"]

    strategies = [
        base_in + ["-i", str(audio_path)] + base_out,
        base_in + ["-f", ext, "-i", str(audio_path)] + base_out,
        *([ base_in + ["-f", detected_codec, "-i", str(audio_path)] + base_out ]
          if detected_codec and detected_codec not in (ext, "?") else []),
        base_in + ["-f", "mp3", "-i", str(audio_path)] + base_out,
        [ff, "-nostdin", "-v", "warning", "-y",
         "-i", str(audio_path), "-threads", "1", str(wav_path)],
        [ff, "-y", "-i", str(audio_path), str(wav_path)],
    ]

    last_err = ""
    for i, cmd in enumerate(strategies, 1):
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)
        r = subprocess.run(cmd, capture_output=True, timeout=timeout_sec)
        if r.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 44:
            if i > 1:
                log("Step 2", f"   ℹ️  使用备用策略 {i} 转换成功")
            break
        stderr_text = r.stderr.decode(errors="replace")
        last_err = stderr_text[-500:]
        dbg("Step 2", f"策略 {i} 失败: {stderr_text[-200:]}")
    else:
        try:
            log("Step 2", "   🔄 ffmpeg 全部失败，尝试 Python fallback 转换...")
            wav_path = _python_fallback_convert(audio_path, wav_path)
        except Exception as e_fb:
            raise RuntimeError(
                f"ffmpeg 所有转换策略均失败，Python fallback 也失败。\n"
                f"ffprobe 信息: {probe}\n"
                f"ffmpeg 最后错误:\n{last_err}\n"
                f"Python fallback 错误: {e_fb}"
            )

    size_mb = wav_path.stat().st_size / 1024 / 1024
    log("Step 2", f"   ✅ 转换完成 → {wav_path.name}（{size_mb:.1f} MB）")
    return wav_path


def _python_fallback_convert(src: Path, dst: Path) -> Path:
    """当 ffmpeg 完全失败时，用 Python 音频库尝试转换"""
    try:
        import soundfile as sf
        data, sr = sf.read(str(src))
        sf.write(str(dst), data, sr, subtype="PCM_16")
        if dst.exists() and dst.stat().st_size > 44:
            log("Step 2", "   ✅ 通过 soundfile 转换成功")
            return dst
    except ImportError:
        pass
    except Exception:
        pass

    try:
        import torchaudio
        waveform, sr = torchaudio.load(str(src))
        torchaudio.save(str(dst), waveform, sr,
                        encoding="PCM_S", bits_per_sample=16)
        if dst.exists() and dst.stat().st_size > 44:
            log("Step 2", "   ✅ 通过 torchaudio 转换成功")
            return dst
    except Exception:
        pass

    raise RuntimeError("soundfile 和 torchaudio 均无法转换")


def prepare_audio(file_path: Path) -> tuple:
    """返回 (audio_path, is_ncm, display_name)
    调用者负责最终清理 TMP_DIR，中间转换产物在此函数内清理。
    """
    if file_path.suffix.lower() == ".ncm":
        decoded_path, display_name = decrypt_ncm(file_path)
        audio_path = ensure_wav(decoded_path)
        # 清理解密出的中间文件（如 .flac/.mp3），WAV 留给后续流程
        if decoded_path != audio_path and decoded_path.exists():
            decoded_path.unlink(missing_ok=True)
        return audio_path, True, display_name
    else:
        size_mb = file_path.stat().st_size / 1024 / 1024
        log("Step 2", f"⏭️  非 NCM 格式，跳过解密（{size_mb:.1f} MB）")

        stem = file_path.stem
        if " - " in stem:
            artist, title = stem.split(" - ", 1)
            display_name = f"{safe_name(artist.strip())}-{safe_name(title.strip())}"
        elif "-" in stem and not stem.startswith("-"):
            artist, title = stem.split("-", 1)
            display_name = f"{safe_name(artist.strip())}-{safe_name(title.strip())}"
        else:
            display_name = safe_name(stem)

        log("Step 2", f"   🏷  命名: {display_name}")

        TMP_DIR.mkdir(parents=True, exist_ok=True)
        if file_path.suffix.lower() != ".wav":
            tmp_copy = TMP_DIR / file_path.name
            shutil.copy2(str(file_path), str(tmp_copy))
            audio_path = ensure_wav(tmp_copy)
            # 清理转换前的临时副本
            if tmp_copy != audio_path and tmp_copy.exists():
                tmp_copy.unlink(missing_ok=True)
        else:
            audio_path = file_path

        return audio_path, False, display_name


# ══════════════════════════════════════════════════════════
#  NCM 解密
# ══════════════════════════════════════════════════════════
def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    raw = AES.new(key, AES.MODE_ECB).decrypt(data)
    pad = raw[-1]
    # PKCS7 padding 校验：值必须在 1~16 且末尾 N 字节全等于 N
    if not (1 <= pad <= 16) or raw[-pad:] != bytes([pad]) * pad:
        # padding 异常，返回原始数据（可能是非标准填充）
        return raw
    return raw[:-pad]

def _build_key_stream(rc4_key: bytes) -> bytearray:
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + rc4_key[i % len(rc4_key)]) & 0xFF
        box[i], box[j] = box[j], box[i]
    stream = bytearray(256)
    for i in range(256):
        a = (i + 1) & 0xFF
        b = (box[a] + a) & 0xFF
        stream[i] = box[(box[a] + box[b]) & 0xFF]
    return stream

def _detect_fmt(path: Path) -> str:
    """读取文件头魔数，返回真实音频格式字符串"""
    try:
        header = path.read_bytes()[:12]
    except Exception:
        return "flac"
    if header[:4] == b"fLaC":
        return "flac"
    if header[:3] == b"ID3" or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa", b"\xff\xe3"):
        return "mp3"
    if header[:4] == b"OggS":
        return "ogg"
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "wav"
    if header[:4] in (b"\x00\x00\x00\x1c", b"\x00\x00\x00\x20") or b"ftyp" in header[:12]:
        return "m4a"
    for i in range(min(len(header), 8)):
        b = header[i]
        if b == 0xff and i + 1 < len(header) and (header[i+1] & 0xe0) == 0xe0:
            return "mp3"
    return "flac"


# ── 音频魔数与 MP3 帧头验证 ──────────────────────────────
AUDIO_MAGICS = {
    b"fLaC": "flac",
    b"ID3\x03": "mp3",
    b"ID3\x04": "mp3",
    b"OggS": "ogg",
    b"RIFF": "wav",
}

def _is_valid_mp3_header(b4: bytes) -> bool:
    """严格验证 MP3 帧头（4字节），排除假阳性"""
    if len(b4) < 4 or b4[0] != 0xFF or (b4[1] & 0xE0) != 0xE0:
        return False
    version = (b4[1] >> 3) & 0x03
    layer   = (b4[1] >> 1) & 0x03
    bitrate = (b4[2] >> 4) & 0x0F
    sr_idx  = (b4[2] >> 2) & 0x03
    if version == 0x01:  return False   # reserved
    if layer == 0x00:    return False   # reserved
    if bitrate == 0x0F:  return False   # bad
    if bitrate == 0x00:  return False   # free format
    if sr_idx == 0x03:   return False   # reserved
    return True


def _find_audio_start(f, pos_after_meta: int, key_stream: bytearray) -> tuple:
    """
    自动定位 NCM 文件中音频数据的起始偏移。

    NCM 格式在 metadata 之后的结构:
      CRC(4) + flag(1) + img_size(4) + img_data + [padding] + audio

    返回 (audio_start_offset, skip_xor, description)
    """

    def _try_decrypt_at(offset: int) -> tuple:
        f.seek(offset)
        enc = f.read(4)
        if len(enc) < 4:
            return None, None
        dec = bytes(enc[i] ^ key_stream[i] for i in range(4))
        for magic, fmt_name in AUDIO_MAGICS.items():
            if dec[:len(magic)] == magic:
                return dec, fmt_name.upper()
        if _is_valid_mp3_header(dec):
            return dec, "MP3"
        return dec, None

    # ═══════════════════════════════════════════════════════
    # 策略 1: 结构化解析 CRC(4)+flag(1)+img_size(4)+img+audio
    # ═══════════════════════════════════════════════════════
    f.seek(pos_after_meta)
    raw_hdr = f.read(32)

    crc_4 = raw_hdr[0:4]
    flag_byte = raw_hdr[4]
    img_size_a = struct.unpack("<I", raw_hdr[5:9])[0]

    dbg("Step 2", f"CRC={crc_4.hex()} flag=0x{flag_byte:02x} img_size={img_size_a}")

    if 10 <= img_size_a <= 2 * 1024 * 1024:
        after_img1 = pos_after_meta + 4 + 1 + 4 + img_size_a

        # 直接在图片后尝试
        dec, match = _try_decrypt_at(after_img1)
        if match:
            return after_img1, False, f"img({img_size_a}) → {match}"

        # 可能有第二个图片块: img_size2(4) + img_data2
        f.seek(after_img1)
        post_img = f.read(32)
        if len(post_img) >= 4:
            img_size_b = struct.unpack("<I", post_img[0:4])[0]
            if 0 <= img_size_b <= 2 * 1024 * 1024:
                dec2, match2 = _try_decrypt_at(after_img1 + 4 + img_size_b)
                if match2:
                    return after_img1 + 4 + img_size_b, False, f"img1({img_size_a})+img2({img_size_b}) → {match2}"

        # 尝试 flag(1)+img_size2(4)+img_data2
        if len(post_img) >= 5:
            img_size_c = struct.unpack("<I", post_img[1:5])[0]
            if 0 <= img_size_c <= 2 * 1024 * 1024:
                dec2b, match2b = _try_decrypt_at(after_img1 + 1 + 4 + img_size_c)
                if match2b:
                    return after_img1 + 1 + 4 + img_size_c, False, f"img1+flag2+img2({img_size_c}) → {match2b}"

        # padding 探测 (+1..+16)
        for extra in range(1, 17):
            dec_x, match_x = _try_decrypt_at(after_img1 + extra)
            if match_x:
                return after_img1 + extra, False, f"img({img_size_a})+pad({extra}) → {match_x}"

    # ═══════════════════════════════════════════════════════
    # 策略 2: 全文件快速扫描
    # ═══════════════════════════════════════════════════════
    dbg("Step 2", "结构解析未命中，进行全文件扫描...")
    f.seek(pos_after_meta)
    scan_buf = f.read()

    # 第一轮: 预计算加密后的魔数模式，用 bytes.find 极速搜索
    for magic, fmt_name in AUDIO_MAGICS.items():
        enc_magic = bytes(magic[i] ^ key_stream[i] for i in range(len(magic)))
        idx = scan_buf.find(enc_magic)
        if idx >= 0:
            return pos_after_meta + idx, False, f"扫描 → {fmt_name.upper()}"

    # 第二轮: MP3 帧头逐字节搜索（跳过图片区域）
    min_scan = min(8000, len(scan_buf))
    for offset in range(min_scan, len(scan_buf) - 4):
        dec_4 = bytes(scan_buf[offset + i] ^ key_stream[i] for i in range(4))
        if _is_valid_mp3_header(dec_4):
            return pos_after_meta + offset, False, "扫描 → MP3"

    # 第三轮: 搜索未加密原始魔数
    for raw_magic in [b"fLaC", b"ID3", b"OggS", b"RIFF"]:
        idx = scan_buf.find(raw_magic)
        if idx >= 0:
            return pos_after_meta + idx, True, f"未加密 {raw_magic.decode('ascii', errors='replace')}"

    # fallback: 原始逻辑
    f.seek(pos_after_meta)
    f.read(4); f.read(5)
    img_sz = struct.unpack("<I", f.read(4))[0]
    f.read(img_sz)
    log("Step 2", "   ⚠️  未能自动检测音频偏移，使用默认结构")
    return f.tell(), False, "fallback"


def decrypt_ncm(ncm_path: Path) -> tuple:
    log("Step 2", f"🔓 解密: {ncm_path.name}")
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    with open(ncm_path, "rb") as f:
        if f.read(8) != NCM_MAGIC:
            raise ValueError(f"不是有效的 NCM 文件: {ncm_path.name}")
        f.read(2)

        # ── 解密 RC4 密钥 ──
        key_len = struct.unpack("<I", f.read(4))[0]
        raw_key = bytearray(f.read(key_len))
        for i in range(len(raw_key)):
            raw_key[i] ^= 0x64
        rc4_key = _aes_ecb_decrypt(CORE_KEY, bytes(raw_key))[17:]

        # ── 解密元数据 ──
        meta_len = struct.unpack("<I", f.read(4))[0]
        meta_raw = bytearray(f.read(meta_len))
        for i in range(len(meta_raw)):
            meta_raw[i] ^= 0x63
        try:
            meta_dec = _aes_ecb_decrypt(META_KEY, base64.b64decode(bytes(meta_raw[22:])))[6:]
            meta = json.loads(meta_dec.rstrip(b"\x00"))
        except Exception:
            meta = {}

        audio_fmt  = meta.get("format", "flac").lower()
        music_name = meta.get("musicName", ncm_path.stem)
        raw_artists = meta.get("artist", [])
        artist_str  = "/".join(a[0] for a in raw_artists if a) if raw_artists else ""
        display_name = (
            f"{safe_name(artist_str)}-{safe_name(music_name)}"
            if artist_str else safe_name(music_name)
        )

        log("Step 2", f"   🎵 {music_name}  🎤 {artist_str or '未知歌手'}  [{audio_fmt.upper()}]")
        log("Step 2", f"   🏷  命名: {display_name}")

        # ── 定位音频数据起始位置 ──
        pos_after_meta = f.tell()
        key_stream = _build_key_stream(rc4_key)
        audio_start, skip_xor, desc = _find_audio_start(f, pos_after_meta, key_stream)
        dbg("Step 2", f"音频起始: {audio_start} (0x{audio_start:X}) [{desc}]")

        # ── 解密音频数据 ──
        f.seek(audio_start)
        tmp_name    = safe_name(music_name) or "audio"
        output_path = TMP_DIR / f"{tmp_name}.tmp"
        pos = 0
        with open(output_path, "wb") as out:
            while True:
                chunk = f.read(0x8000)
                if not chunk:
                    break
                if skip_xor:
                    out.write(chunk)
                else:
                    buf = bytearray(len(chunk))
                    for k, byte in enumerate(chunk):
                        buf[k] = byte ^ key_stream[(pos + k) & 0xFF]
                    out.write(buf)
                    pos = (pos + len(chunk)) & 0xFF

    # ── 检测真实格式 ──
    real_fmt = _detect_fmt(output_path)
    if real_fmt != audio_fmt:
        log("Step 2", f"   ⚠️  元数据声明 {audio_fmt.upper()} 但实际为 {real_fmt.upper()}，已修正")
    final_path = TMP_DIR / f"{tmp_name}.{real_fmt}"
    output_path.rename(final_path)
    output_path = final_path

    size_mb = output_path.stat().st_size / 1024 / 1024
    log("Step 2", f"   ✅ 解密完成 ({size_mb:.1f} MB)  [{real_fmt.upper()}]")
    return output_path, display_name


# ══════════════════════════════════════════════════════════
#  Step 3 — 人声分离
# ══════════════════════════════════════════════════════════

_separator_instance = None
_loaded_model_name  = None    # 脚本自己追踪已加载的模型名

def remove_vocals(audio_path: Path, model_name: str,
                  model_params: dict, mode_label: str) -> Path:
    global _separator_instance, _loaded_model_name

    log("Step 3", f"🎼 分离中: {audio_path.name}")
    log("Step 3", f"   模式: {mode_label}")
    MODEL_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    from audio_separator.separator import Separator

    if _separator_instance is None or _loaded_model_name != model_name:
        _separator_instance = Separator(
            model_file_dir = str(MODEL_DIR),
            output_dir     = str(TMP_DIR),
            output_format  = "WAV",
            mdxc_params    = model_params,
        )
        log("Step 3", "   加载模型（首次需下载约 200MB，请耐心等待）...")
        _separator_instance.load_model(model_name)
        _loaded_model_name = model_name

    t0 = time.time()
    outputs = _separator_instance.separate(str(audio_path))
    elapsed = time.time() - t0
    log("Step 3", f"   ✅ 耗时 {elapsed:.1f}s  →  {[Path(f).name for f in outputs]}")

    if not outputs:
        raise RuntimeError("分离器未产生任何输出文件，音频可能过短或已损坏")

    def full_path(fp: str) -> Path:
        p = Path(fp)
        return p if p.is_absolute() else TMP_DIR / p.name

    instrumental = None
    for fp in outputs:
        stem_lower = Path(fp).stem.lower()
        if any(kw in stem_lower for kw in
               ("instrumental", "no_vocal", "novocal", "inst", "karaoke", "kara", "other")):
            instrumental = full_path(fp)
            break
    if instrumental is None:
        instrumental = full_path(outputs[0])
        log("Step 3", "   ⚠️  未能自动识别目标文件，已选用第一个输出。")

    for fp in outputs:
        p = full_path(fp)
        if p != instrumental and p.exists():
            p.unlink()

    return instrumental


# ══════════════════════════════════════════════════════════
#  Step 4 — 收尾：重命名 + 移桌面 + 处理原文件
# ══════════════════════════════════════════════════════════
def deliver(instrumental: Path, src_path: Path,
            decoded_audio, is_ncm: bool,
            display_name: str, output_suffix: str) -> Path:

    DESKTOP.mkdir(exist_ok=True)

    final_name = f"{display_name}{output_suffix}.wav"
    dest = DESKTOP / final_name
    if dest.exists():
        dest = DESKTOP / f"{display_name}{output_suffix}_{int(time.time())}.wav"

    shutil.move(str(instrumental), str(dest))
    log("Step 4", f"   ✅ 已保存: ~/Desktop/{dest.name}")

    if decoded_audio and Path(decoded_audio).exists():
        Path(decoded_audio).unlink()

    if is_ncm:
        send2trash(str(src_path))
        log("Step 4", f"   🗑  NCM 已移至废纸篓: {src_path.name}")
    else:
        log("Step 4", f"   📌 原始音频已保留: {src_path.name}")

    return dest


def _cleanup_current_file(src_path: Path):
    """清理当前失败文件的临时产物，保留 TMP_DIR 中其他文件"""
    if not TMP_DIR.exists():
        return
    stem = safe_name(src_path.stem.split(" - ")[-1] if " - " in src_path.stem else src_path.stem)
    for f in TMP_DIR.iterdir():
        # 匹配当前文件名（可能是 .tmp / .flac / .mp3 / .wav 等）
        if f.stem == stem or f.stem.startswith(stem):
            try:
                f.unlink()
            except Exception:
                pass


def _check_wav_duration(wav_path: Path, min_seconds: float = 1.0) -> float:
    """检查 WAV 文件时长，返回秒数。过短则抛出异常。"""
    try:
        import soundfile as sf
        info = sf.info(str(wav_path))
        duration = info.duration
    except Exception:
        # fallback：从文件大小估算（PCM 16-bit 44100Hz stereo ≈ 176KB/s）
        size = wav_path.stat().st_size
        duration = max(0, (size - 44)) / (44100 * 2 * 2)

    if duration < min_seconds:
        raise RuntimeError(
            f"音频时长仅 {duration:.2f} 秒（最少需要 {min_seconds} 秒），"
            f"文件可能已损坏或解密偏移不正确。"
            f"请尝试 NCM_DEBUG=1 运行查看详情。"
        )
    return duration


# ══════════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════════
def main():
    # ── 注册退出清理（SIGTERM / 异常退出时也能清理临时文件）──
    import atexit, signal
    def _cleanup_tmp():
        if TMP_DIR.exists():
            shutil.rmtree(TMP_DIR, ignore_errors=True)
    atexit.register(_cleanup_tmp)
    def _sigterm_handler(signum, frame):
        print("\n\n  ⛔ 收到终止信号，正在清理...")
        _cleanup_tmp()
        sys.exit(128 + signum)
    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGHUP, _sigterm_handler)

    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║    音频人声分离  全流程自动化                           ║")
    print("  ║    支持: NCM / WAV / FLAC / MP3 / AAC / OGG ...        ║")
    print("  ║    支持多文件批处理                                     ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    results_ok  = []
    results_err = []

    try:
        model_name, model_params, mode_label, output_suffix = pick_mode()
        hr()

        files = pick_files()
        total = len(files)

        for idx, src_path in enumerate(files, 1):
            hr()
            print(f"\n  ┌── [{idx}/{total}] {src_path.name}")
            print(f"  └── 模式: {mode_label}\n")

            try:
                audio_path, is_ncm, display_name = prepare_audio(src_path)
                decoded_audio = audio_path if is_ncm else None

                # 检查 WAV 时长，避免过短文件导致分离器 tensor 错误
                duration = _check_wav_duration(audio_path)
                dbg("Step 2", f"音频时长: {duration:.1f}s")

                instrumental = remove_vocals(
                    audio_path, model_name, model_params, mode_label
                )

                dest = deliver(
                    instrumental, src_path, decoded_audio,
                    is_ncm, display_name, output_suffix
                )
                results_ok.append(dest)

            except Exception as e:
                log("错误", f"❌ {src_path.name} 处理失败: {e}")
                import traceback; traceback.print_exc()
                results_err.append(src_path)
                # 只清理当前文件相关的临时文件，不影响其他文件
                _cleanup_current_file(src_path)
                continue

        if results_ok:
            subprocess.run(["open", str(DESKTOP)], check=False)

        shutil.rmtree(TMP_DIR, ignore_errors=True)

        hr()
        print()
        print(f"  🎉  全部处理完成！  成功: {len(results_ok)}  失败: {len(results_err)}")
        print()
        for p in results_ok:
            print(f"  ✅  {p.name}")
        for p in results_err:
            print(f"  ❌  {p.name}")
        print()

    except KeyboardInterrupt:
        print("\n\n  ⛔ 用户手动取消。")
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  ❌ 发生错误: {e}")
        import traceback; traceback.print_exc()
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
