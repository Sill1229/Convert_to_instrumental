# 🎵 Convert to Instrumental

将音乐一键提取伴奏 / 卡拉OK版，支持网易云 NCM 加密格式。

---

## 功能

| 模式 | 说明 | 模型 | 效果 |
|------|------|------|------|
| 🎼 纯伴奏 | 去除全部人声（含和声） | BS-RoFormer | SDR 12.97 |
| 🎤 保留和声 | 只去主唱，保留背景和声 | MelBand-Roformer Karaoke | SDR 10.20 |

- 支持格式：`.ncm` `.mp3` `.wav` `.flac` `.aac` `.ogg` `.m4a` 等
- 支持批量处理，一次选多首逐首转换
- 输出格式：48kHz 24-bit WAV，保存到桌面

---

## 使用方法

1. 将 `Convert_to_instrumental.app` 拖入「**应用程序**」文件夹（重要，见下方说明）
2. 双击打开，弹窗选择分离模式
3. 在文件选择窗口中选择音频文件（可多选）
4. 等待处理完成，伴奏文件自动出现在桌面

> **首次运行**会自动安装依赖环境和下载模型（约 200MB），需要 5–15 分钟，请耐心等待。

---

## 系统要求

- macOS（Apple Silicon / Intel 均支持）
- 已安装 [Homebrew](https://brew.sh)（用于自动安装 ffmpeg）
- 无需手动安装 Python 或任何依赖，App 会全自动处理

---

## ⚠️ 首次使用必读：请先移到「应用程序」文件夹

从微信、QQ 等途径收到的 App，macOS 会启用 **Gatekeeper 隔离机制**，将其挂载到随机临时路径运行（AppTranslocation）。这会导致：

- 环境重建后无法自动重启
- 每次打开路径不固定，影响稳定性

**解决方法**：在 Finder 中把 App 拖入「应用程序」文件夹，再从那里打开即可。

---

## 常见问题

### 首次打开出现"samplerate 动态库架构不兼容"

这是自动修复提示，**无需任何操作**。App 会在启动时检测并卸载不兼容的 `samplerate` 包，随后正常进入主界面。此提示只会出现一次，之后启动不再显示。

### 提示"未找到 Homebrew，请手动安装 ffmpeg"

App 需要 ffmpeg 进行音频转换，通常会通过 Homebrew 自动安装。如果你没有安装 Homebrew，请先访问 [brew.sh](https://brew.sh) 安装，或手动运行：

```bash
brew install ffmpeg
```

### 「保留和声」模式报错：Model file not found

通常只在没有安装 Homebrew 的机器上出现。App 会自动通过 Homebrew 安装 Python 3.11，但如果连 Homebrew 都没有，则无法自动完成。

请先安装 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

然后删除旧环境，重新打开 App 即可自动完成剩余安装：

```bash
rm -rf ~/.ncm_venv
```

---

### 虚拟环境多次重启仍失败

手动重置环境：

```bash
rm -rf ~/.ncm_venv
```

重新打开 App 即可重新安装。

### NCM 文件解密失败

NCM 文件为网易云音乐的加密格式，仅支持通过正规客户端下载的文件。如解密报错，可设置环境变量查看详细诊断：

```bash
NCM_DEBUG=1 open /Applications/Convert_to_instrumental.app
```

---

## 输出文件命名

| 输入文件 | 输出文件 |
|----------|----------|
| `歌曲名.mp3` | `歌曲名_(Instrumental).wav` |
| `歌曲名.ncm` | `歌曲名_(Karaoke).wav` |

---

## 环境说明

App 首次运行时会在后台自动完成以下操作，无需手动干预：

1. 创建独立 Python 虚拟环境（`~/.ncm_venv`）
2. 安装 AI 分离所需依赖包
3. 下载模型文件（`~/.audio_separator_models`，约 200MB）
4. 检测并安装 ffmpeg（通过 Homebrew）

后续打开无需重复安装，启动很快。
