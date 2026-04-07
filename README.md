# 🎵 Convert to Instrumental — 音频人声分离全流程自动化

一键完成网易云 NCM 解密 → 格式转换 → AI 人声分离 → 输出伴奏/卡拉OK，支持批量处理。

现已提供 **macOS .app**，双击即可使用，无需命令行。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **NCM 解密** | 自动解密网易云 `.ncm` 加密文件，提取内嵌音频 |
| **格式通吃** | 同时支持 WAV / FLAC / MP3 / AAC / OGG / M4A / OPUS / WMA / AIFF 直接输入 |
| **两种分离模式** | ① 纯伴奏（去除全部人声）② 保留和声（只去主唱，保留和声） |
| **批量处理** | 弹窗多选文件，逐首处理并实时显示进度 |
| **全自动环境** | 首次运行自动创建 venv、安装依赖、下载模型，零手动配置 |
| **48kHz / 24-bit 输出** | 制作级 WAV 品质，自动保存到桌面 |
| **NCM 清理** | 解密成功后自动将 .ncm 原文件移至废纸篓 |

### AI 分离模型

| 模式 | 模型 | SDR | 适用场景 |
|------|------|-----|----------|
| 纯伴奏 | BS-RoFormer ep317 | **12.97** | 制作纯伴奏、混音素材 |
| 保留和声 | MelBand-Roformer Karaoke (aufr33 & viperx) | **10.20** | 卡拉OK、翻唱伴奏 |

---

## 系统要求

- **操作系统**：macOS（已测试 macOS Sequoia 15.x / Tahoe 26.x）
- **Python**：3.11 或 3.12（脚本自动检测 Homebrew 安装的版本）
- **Homebrew**：用于自动安装 ffmpeg
- **磁盘空间**：首次运行约需 2~5 GB（PyTorch + 模型下载）
- **Apple Silicon**：自动启用 MPS/CoreML 加速

---

## 安装与运行

### 方式 A：双击 .app（推荐）

1. 打开 `Convert_to_instrumental.app`
2. 首次打开可能需要：右键 → 打开（绕过 Gatekeeper）
3. 自动在终端中启动，按弹窗提示操作即可

> ⚠️ 首次运行会自动安装环境（约 5~15 分钟），后续秒速启动。

### 方式 B：命令行运行

```bash
# 1. 安装 Homebrew（如已安装跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Python 3.11（推荐）
brew install python@3.11

# 3. 安装 ffmpeg（可选，脚本会自动安装）
brew install ffmpeg

# 4. 运行
python3 Convert_to_instrumental.py
```

---

## 使用方法

1. **选择模式** — 弹窗选择「纯伴奏」或「保留和声」
2. **选择文件** — 弹窗选择一个或多个音频文件（按住 ⌘ 多选）
3. **等待处理** — 终端实时显示每首歌的处理进度
4. **获取结果** — 完成后自动打开桌面，输出文件已就绪

### 输出

- 纯伴奏：`歌手-歌名_(Instrumental).wav` / 保留和声：`歌手-歌名_(Karaoke).wav`
- 格式：**WAV PCM 24-bit 48000Hz**，输出到 `~/Desktop/`

### 调试 / 重建

```bash
NCM_DEBUG=1 python3 Convert_to_instrumental.py   # 详细诊断日志
rm -rf ~/.ncm_venv && python3 Convert_to_instrumental.py   # 重建环境
```

---

## 处理流程

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────────┐
│  Step 1      │    │  Step 2      │    │  Step 3     │    │  Step 4       │
│  选择文件    │ →  │  解密/转换   │ →  │  AI 分离    │ →  │  48k/24bit    │
│  (弹窗多选)  │    │  NCM → WAV   │    │  RoFormer   │    │  输出到桌面   │
└─────────────┘    └──────────────┘    └─────────────┘    └───────────────┘
```

### NCM 解密

```
NCM 文件
  ├─ 验证魔数 (CTENFDAM)
  ├─ AES-ECB 解密 RC4 密钥（含 PKCS7 padding 校验）
  ├─ 解密元数据 (歌名/歌手/格式)
  ├─ 自动定位音频数据起始偏移
  │   ├─ 结构化解析 CRC+flag+img_size+img+[pad]
  │   ├─ 双图片块 / padding(+1~+16) 探测
  │   └─ 4MB 分块扫描 (加密魔数 → MP3帧头 → 原始魔数)
  ├─ RC4 流密码解密音频数据
  └─ 魔数检测真实格式（修正元数据不准）
```

### 格式转换 (→ 48kHz 24-bit WAV)

```
输入文件 (FLAC/MP3/...)
  ├─ ffprobe 探测 (codec/采样率/声道/位深)
  ├─ ffmpeg 多策略转换 (6种, pcm_s24le 48kHz, timeout 按文件大小缩放)
  └─ Python fallback (soundfile PCM_24 → torchaudio 24-bit)
```

### 伴奏识别（评分机制）

```
分离器输出多个文件
  ├─ 正分: instrumental(+100) / karaoke(+80) / inst(+60, 词边界) / other(+20)
  ├─ 负分: vocals/vocal/lead/singer(-120)
  ├─ 微调: 文件大小(+0~20)
  └─ 取最高分 → 伴奏轨
```

### 输出后处理

```
分离器输出 → _ensure_48k_24bit() → 48kHz 24-bit WAV → ~/Desktop/
```

---

## 版本历史

### v3.4 — 管线升级

- audio-separator 解锁版本，跟随最新上游
- 输出格式升级为 **48kHz 24-bit WAV**（符合制作流程标准）
- 中间转换和最终输出均保证 48k/24bit 规格
- `deliver()` 增加 `_ensure_48k_24bit()` 后处理保障
- 新增 **macOS .app** 打包，双击即用

### v3.3 — 融合优化 (Claude × GPT)

- `_in_venv()` 用 `resolve()` + `base_prefix` 双重判断，更通用
- 伴奏识别从关键词首匹配改为**评分机制**（正分/负分/大小加权），不再误选人声轨
- 全文件 `f.read()` 改为 **4MB 分块扫描**，大文件不整块读入内存
- `ensure_wav()` 用 `delete_source` 参数显式控制删除，接口安全
- `safe_name()` 增加 `strip(".")` / 连续空格合并 / 空值 fallback `"audio"`
- `TMP_DIR` 用 `tempfile.gettempdir()` + 时间戳 + PID，可读且防冲突
- `_find_audio_start` 结构解析加 `len(raw_hdr) >= 9` 安全检查 + fallback 加 `len` 检查

### v3.2 — 代码审计修复 (GPT review)

- AES 解密增加 PKCS7 padding 校验（容错 fallback，不 raise）
- 模型状态用脚本自己的 `_loaded_model_name` 追踪，不污染第三方对象
- 临时目录加 PID 后缀；锁定 `audio-separator==0.42.1`
- `safe_name()` 长度截断

### v3.1 — 鲁棒性增强

- venv 自举重试计数器（≥3 次报错退出）
- 单文件失败只清理当前文件临时产物
- 分离前 WAV 时长检查（< 1s 报错）
- ffmpeg timeout 按文件大小缩放（60s + 1.2s/MB）
- atexit + SIGTERM/SIGHUP 信号处理

### v3 — 核心修复

- ffmpeg 7.x/8.x 兼容
- NCM 解密偏移四层自动探测
- MP3 帧头严格验证
- soundfile / torchaudio fallback

---

## 目录结构

| 路径 | 说明 |
|------|------|
| `Convert_to_instrumental.app` | macOS 应用（双击运行） |
| `Convert_to_instrumental.py` | Python 脚本（命令行运行） |
| `~/.ncm_venv/` | Python 虚拟环境（自动创建） |
| `~/.audio_separator_models/` | AI 模型缓存 |
| `/tmp/ncm_pipeline_{时间}_{PID}/` | 临时目录（自动清理，带时间戳和 PID 防冲突） |
| `~/Desktop/` | 输出目录 |

---

## 依赖包

| 包名 | 版本 | 用途 |
|------|------|------|
| `pycryptodome` | latest | NCM 文件 AES-ECB 解密 |
| `audio-separator` | **latest** | AI 人声分离引擎（RoFormer 模型） |
| `onnxruntime` | latest | 推理加速 |
| `torch` / `torchaudio` | latest | PyTorch 推理 + 音频 I/O fallback |
| `soundfile` | latest | 格式转换 fallback + WAV 时长检测 |
| `send2trash` | latest | 安全删除 NCM 原文件到废纸篓 |

---

## .app 打包说明

`Convert_to_instrumental.app` 是一个标准的 macOS Application Bundle：

```
Convert_to_instrumental.app/
  Contents/
    Info.plist            # 应用元数据
    MacOS/
      launcher            # Bash 启动器 → 在 Terminal 中运行 Python 脚本
    Resources/
      Convert_to_instrumental.py  # 完整的分离脚本
      AppIcon.icns        # 应用图标
```

更新脚本后需同步更新 .app 内的副本：

```bash
cp Convert_to_instrumental.py Convert_to_instrumental.app/Contents/Resources/
```

---

## 已知限制

| 限制 | 说明 |
|------|------|
| **仅 macOS** | 使用 AppleScript 弹窗 + Homebrew。核心逻辑跨平台，替换 UI 部分即可适配 |
| **输出仅 WAV** | 如需 FLAC/MP3 可后续用 ffmpeg 转换 |

---

## FAQ

**Q: 首次运行很慢？** 正常，需安装 PyTorch（~2GB）和下载 AI 模型（~200MB）。

**Q: .app 打开提示「无法验证开发者」？** 右键 .app → 打开，在弹窗中选「打开」。或在系统设置 → 隐私与安全 → 允许。

**Q: 弹窗没出现？** 系统设置 → 隐私与安全 → 辅助功能，添加终端应用。也支持手动拖文件。

**Q: 报错「音频时长仅 0.05 秒」？** NCM 解密偏移可能不正确，开启 `NCM_DEBUG=1` 查看详情。

**Q: 报错「虚拟环境多次重启」？** 执行 `rm -rf ~/.ncm_venv` 重建。网络受限时可能需配置 pip 镜像。

**Q: 同时处理两批？** 可以。临时目录带时间戳+PID 隔离，多终端窗口不冲突。

**Q: 升级模型？** 修改脚本中的 `MODEL_FULL_INST` 或 `MODEL_KARAOKE` 常量，`rm -rf ~/.ncm_venv ~/.audio_separator_models` 重建。

**Q: 能否改变 .app 的存放路径？** 可以。.app 是自包含的 bundle，内部通过相对路径定位脚本，放在桌面、应用程序文件夹、U盘、任何位置都能正常运行。

**Q: 能否重命名 .app？** 可以。macOS 应用的可执行文件由 `Info.plist` 中的 `CFBundleExecutable` 决定（指向内部的 `launcher`），与 .app 外层文件夹名无关。随意改名不影响运行。

**Q: 发给别人的 Mac 能直接用吗？** 可以，前提是对方已安装 Homebrew 和 Python 3.11/3.12。脚本首次运行会自动完成剩余配置（创建 venv、安装依赖、下载模型、安装 ffmpeg）。首次打开需右键 → 打开以绕过 Gatekeeper。
