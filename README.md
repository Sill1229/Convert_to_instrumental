# 🎵 Convert to Instrumental — 音频人声分离全流程自动化

一键完成网易云 NCM 解密 → 格式转换 → AI 人声分离 → 输出伴奏/卡拉OK，支持批量处理。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **NCM 解密** | 自动解密网易云 `.ncm` 加密文件，提取内嵌音频 |
| **格式通吃** | 同时支持 WAV / FLAC / MP3 / AAC / OGG / M4A / OPUS / WMA / AIFF 直接输入 |
| **两种分离模式** | ① 纯伴奏（去除全部人声）② 保留和声（只去主唱，保留和声） |
| **批量处理** | 弹窗多选文件，逐首处理并实时显示进度 |
| **全自动环境** | 首次运行自动创建 venv、安装依赖、下载模型，零手动配置 |
| **桌面输出** | 处理完成的文件自动保存到桌面，命名格式：`歌手-歌名_(Instrumental).wav` |
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

### 1. 安装 Homebrew（如已安装跳过）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. 安装 Python 3.11（推荐）

```bash
brew install python@3.11
```

> 脚本兼容 Python 3.14，但 `beartype`（`audio-separator` 的依赖）在 3.14 上有已知问题，建议用 3.11 或 3.12。

### 3. 安装 ffmpeg（可选，脚本会自动安装）

```bash
brew install ffmpeg
```

### 4. 下载脚本

将 `Convert_to_instrumental.py` 保存到任意位置（如 `~/Downloads/`）。

### 5. 运行

```bash
python3 ~/Downloads/Convert_to_instrumental.py
```

**首次运行**会自动完成（约 5~15 分钟）：

1. 创建虚拟环境 `~/.ncm_venv`（使用 Python 3.11/3.12）
2. 安装 Python 依赖包（pycryptodome, audio-separator==0.42.1, torch 等）
3. 下载 AI 分离模型到 `~/.audio_separator_models`（约 200MB）

后续运行秒速启动。

---

## 使用方法

```bash
python3 Convert_to_instrumental.py
```

1. **选择模式** — 弹窗选择「纯伴奏」或「保留和声」
2. **选择文件** — 弹窗选择一个或多个音频文件（按住 ⌘ 多选）
3. **等待处理** — 终端实时显示每首歌的处理进度
4. **获取结果** — 完成后自动打开桌面，输出文件已就绪

### 输出文件

- 纯伴奏模式：`歌手-歌名_(Instrumental).wav`
- 保留和声模式：`歌手-歌名_(Karaoke).wav`
- 输出位置：`~/Desktop/`

### 调试模式

```bash
NCM_DEBUG=1 python3 Convert_to_instrumental.py
```

### 重建环境

```bash
rm -rf ~/.ncm_venv
python3 Convert_to_instrumental.py
```

---

## 处理流程

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────────┐
│  Step 1      │    │  Step 2      │    │  Step 3     │    │  Step 4       │
│  选择文件    │ →  │  解密/转换   │ →  │  AI 分离    │ →  │  输出到桌面   │
│  (弹窗多选)  │    │  NCM → WAV   │    │  RoFormer   │    │  清理临时文件 │
└─────────────┘    └──────────────┘    └─────────────┘    └───────────────┘
```

### NCM 解密流程

```
NCM 文件
  ├─ 验证魔数 (CTENFDAM)
  ├─ AES-ECB 解密 RC4 密钥（含 PKCS7 padding 校验）
  ├─ 解密元数据 (歌名/歌手/格式)
  ├─ 自动定位音频数据起始偏移
  │   ├─ 策略1: 结构化解析 CRC+flag+img_size+img+[pad]
  │   ├─ 策略2: 双图片块检测
  │   ├─ 策略3: padding 探测 (+1~+16)
  │   └─ 策略4: 全文件快速扫描 (加密魔数/MP3帧头/原始魔数)
  ├─ RC4 流密码解密音频数据
  └─ 魔数检测真实格式（修正元数据不准的情况）
```

### 格式转换流程 (→ WAV)

```
输入文件 (FLAC/MP3/...)
  ├─ ffprobe 探测 (codec/采样率/声道/位深)
  ├─ ffmpeg 多策略转换 (6种策略依次尝试)
  │   ├─ 标准: 自动探测 + pcm_s16le + 显式选流
  │   ├─ 强制输入格式 / ffprobe codec / 强制 MP3
  │   └─ 完全自动 / 兼容旧版 ffmpeg
  └─ Python fallback (soundfile → torchaudio)
```

---

## 支持格式

### 输入

| 格式 | 说明 |
|------|------|
| `.ncm` | 网易云音乐加密格式（自动解密） |
| `.wav` `.flac` `.mp3` `.aac` `.ogg` `.m4a` `.opus` `.wma` `.aiff` | 自动转换为 WAV 后处理 |

### 输出

- WAV（PCM 16-bit, 44100 Hz）

---

## 已解决的问题

### v3 — ffmpeg 兼容性与 NCM 解密

**ffmpeg 7.x / 8.x 兼容性**：添加 `-nostdin` / `-map 0:a:0` / `-threads 1`，编码改为 `pcm_s16le`，ffmpeg 失败时用 soundfile/torchaudio 作为 Python fallback。

**NCM 解密偏移适配**：四层自动定位 — 结构化解析 → 双图片块/padding 探测 → 加密魔数快速扫描 → 严格 MP3 帧头搜索。

**MP3 帧头假阳性**：严格验证四字段（version / layer / bitrate / sample_rate），跳过图片区域。

**NCM 元数据与实际格式不符**：通过文件头魔数检测真实格式，自动修正。

### v3.1 — 鲁棒性增强

**venv 无限循环**：环境变量计数重启次数，≥3 次报错退出。

**单文件失败影响批量**：按文件名匹配只清理当前文件临时产物。

**过短音频 tensor crash**：分离前检查 WAV 时长，< 1 秒直接给出明确错误。

**ffmpeg 大文件超时**：timeout 按文件大小动态缩放。

**异常退出临时文件残留**：atexit + SIGTERM/SIGHUP 信号处理。

### v3.2 — 代码审计修复

**AES 解密 padding 无校验**：添加 PKCS7 校验（`1 ≤ pad ≤ 16` + 末尾一致性检查），损坏的 NCM 不再静默产生错误密钥。

**私有属性侵入第三方对象**：不再往 `Separator` 实例上写 `_loaded_model` 属性，改用脚本自己的 `_loaded_model_name` 变量追踪。

**ensure_wav 隐式删除输入文件**：删除副作用从 `ensure_wav()` 移到 `prepare_audio()`，函数职责更清晰，未来重构不会误删源文件。

**多实例临时目录冲突**：`/tmp/ncm_pipeline` → `/tmp/ncm_pipeline_{PID}`，多窗口同时运行不再互相干扰。

**audio-separator 版本锁定**：锁定 `audio-separator==0.42.1`，避免上游 API 变动导致 `load_model` / `separate` 行为不兼容。

**超长文件名**：`safe_name()` 增加 200 字符截断，防止触发文件系统限制。

---

## 目录结构

| 路径 | 说明 |
|------|------|
| `~/.ncm_venv/` | Python 虚拟环境（自动创建） |
| `~/.audio_separator_models/` | AI 模型缓存 |
| `/tmp/ncm_pipeline_{PID}/` | 临时处理目录（运行后自动清理，含进程 PID 防冲突） |
| `~/Desktop/` | 输出目录 |

---

## 依赖包

| 包名 | 版本 | 用途 |
|------|------|------|
| `pycryptodome` | latest | NCM 文件 AES-ECB 解密 |
| `audio-separator` | **0.42.1** | AI 人声分离引擎（RoFormer 模型） |
| `onnxruntime` | latest | 推理加速 |
| `torch` / `torchaudio` | latest | PyTorch 推理 + 音频 I/O fallback |
| `soundfile` | latest | 音频格式转换 fallback + WAV 时长检测 |
| `send2trash` | latest | 安全删除 NCM 原文件到废纸篓 |

所有依赖首次运行时自动安装到 `~/.ncm_venv`。

---

## 已知限制

| 限制 | 说明 |
|------|------|
| **仅 macOS** | 使用 AppleScript 弹窗 + Homebrew，不支持 Windows/Linux。核心逻辑跨平台，替换 UI 部分即可适配 |
| **无文件日志** | 仅控制台输出，可用 `NCM_DEBUG=1` 获取详细诊断。需要持久化日志可重定向: `python3 script.py 2>&1 \| tee log.txt` |
| **配置硬编码** | 模型参数、输出目录等写死在脚本中，如需自定义需直接修改源码 |
| **输出仅 WAV** | 分离器输出 WAV 格式，如需 FLAC/MP3 可后续用 ffmpeg 转换 |
| **上游 API 敏感** | audio-separator 已锁版本 0.42.1；如需升级，需验证 `Separator()` 构造参数和 `separate()` 返回格式未变 |

---

## FAQ

**Q: 首次运行很慢？**
正常，需安装 PyTorch（~2GB）和下载 AI 模型（~200MB）。后续秒速启动。

**Q: 弹窗没出现？**
终端需要辅助功能权限。前往 系统设置 → 隐私与安全 → 辅助功能，添加终端应用。脚本也支持手动拖入文件路径作为降级方案。

**Q: 报错「音频时长仅 0.05 秒」？**
NCM 解密偏移可能不正确，导致输出的音频文件几乎为空。开启 `NCM_DEBUG=1` 运行查看详细偏移探测日志。

**Q: 报错「虚拟环境多次重启仍无法加载依赖」？**
pip 安装可能不完整。执行 `rm -rf ~/.ncm_venv` 后重新运行。如果网络环境受限，可能需要配置 pip 镜像源。

**Q: 想同时处理两批歌？**
可以。v3.2 起临时目录带 PID 隔离，多终端窗口同时运行不会冲突。

**Q: 升级 audio-separator 版本？**
脚本锁定了 `audio-separator==0.42.1`。如需升级，修改脚本中 `PACKAGES` 列表的版本号，然后 `rm -rf ~/.ncm_venv` 重建环境。升级后请验证输出是否正常。

**Q: 支持 Windows / Linux 吗？**
当前仅支持 macOS（AppleScript 弹窗 + Homebrew）。核心解密和分离逻辑跨平台，替换 UI 交互部分即可适配。
