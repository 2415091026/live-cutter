# 智能直播切片系统 (Live-Cutter PRO)

针对抖音平台主播的实时推流抓取、多模态高能片段智能识别（音频能量 + 弹幕热度 + Whisper 语音转录 + 大模型音画语义精修）与自动化双轨切片系统（9:16 成品直出 / 剪映专业版草稿直通）。

---

## 项目里程碑全景

- [x] **阶段一：直播流解析与录制引擎**（抖音推流解析、FFmpeg 流式录制与循环分片）
- [x] **阶段二：弹幕监听与音频能量检测引擎**（实时弹幕/礼物抓取、音频短时能量与高潮波峰提取）
- [x] **阶段三：ASR 语音转录与大模型双模语义精筛**（Faster-Whisper 打轴 + LangChain 双模引擎：经典声文 / 多模态音画全感知）
- [x] **阶段四：自动化剪辑合成与剪映草稿导出**（9:16 自适应竖屏成片 + 剪映原生多轨道工程直通）
- [x] **阶段五：现代可视化工作台 (Vue 3 + FastAPI) 与专属主播档案**

---

## 核心功能一览

1. **全局状态与 AI 大脑看板**：实时展示大模型引擎模式（多模态音画 / 经典声文）、在线状态与系统录像/切片资产统计。
2. **直播间雷达与实时高能监控**：输入抖音房间号或直播间链接，实时解析主播状态，支持自动滚存录制与高能片段触发。
3. **弹幕礼物面板与音频能量心电图 (Canvas Radar)**：实时展示直播间弹幕/礼物热度，动态绘制音频能量基线与高潮脉冲峰值。
4. **AI 智能切片决策看板**：一键触发 Whisper 语音转录 + LangChain 大模型流式分析，自动生成核心金句、3 条爆款标题与精确起止时间，提供【一键导出 9:16 成片】与【一键导入剪映草稿】双轨交付。
5. **主播专属档案库 (`config/anchors/`)**：支持为不同主播配置专属关键词字典、竖屏排版模板与人设 Prompt。

---

## 环境准备

- **Python**：3.10 及以上
- **FFmpeg**：需安装并添加到系统环境变量 `PATH`（用于拉流录制、视频抽帧与 9:16 成片合成）
- **浏览器（可选）**：本机安装 Chrome 或 Edge（用于抖音直播间扫码登录获取 Cookie 及浏览器通道弹幕监听）
- **Node.js（可选）**：18+（仅修改 `gui/` 前端源码时需要）

---

## 首次拉取与配置指南（必读）

> **注意**：为保护个人隐私与密钥安全，`config/llm_config.json` 与 `config/douyin_cookies.json` 已被 `.gitignore` 忽略，首次 `git clone` 后必须手动初始化配置文件，否则启动时会因缺少 API Key 报错。

### 1. 克隆项目并安装 Python 依赖

```bash
git clone https://github.com/2415091026/live-cutter.git
cd live-cutter

pip install fastapi uvicorn requests websocket-client numpy faster-whisper openai langchain-openai langchain-core pydantic
```

### 2. 初始化大模型配置文件（必做）

复制示例配置为正式配置文件：

```bash
# Windows (PowerShell)
Copy-Item config\llm_config.example.json config\llm_config.json

# macOS / Linux
cp config/llm_config.example.json config/llm_config.json
```

打开 `config/llm_config.json`，将 `api_key` 替换为你真实的大模型 API Key（默认兼容阿里百炼 DashScope，也内置了 DeepSeek、智谱等预设，可在文件内或启动后于网页右上角配置抽屉中自由切换）：

```json
{
  "engine_mode": "multimodal",
  "provider": "qwen",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key": "填入你的真实 API Key",
  "model": "qwen3.8-omni-flash",
  "text_model": "qwen3.8-flash",
  "multimodal_model": "qwen3.8-omni-flash"
}
```

### 3. （可选）配置抖音登录态 Cookie

如需在直播监听时解锁完整礼物与弹幕数据，启动工作台后可在界面中点击【扫码登录抖音】或手动粘贴浏览器 Cookie，系统会自动保存至本地 `config/douyin_cookies.json`（不会被提交至 Git）。

---

## 快速启动

### 1. 一键启动可视化工作台（推荐）

```bash
cd src
python start_gui.py
# 或使用统一 CLI
python main.py gui
```

服务将在 `http://127.0.0.1:8765/` 启动，并自动唤起默认浏览器打开工作台。

### 2. 前端开发模式（仅二次开发 UI 时使用）

项目已内置编译好的前端静态资源（位于 `web/` 目录），常规使用无需启动前端构建。如需修改 `gui/` 下的 Vue 3 源码：

```bash
cd gui
npm install
npm run dev      # 开发调试，默认监听 http://localhost:5173 并代理 /api 到 8765
npm run build    # 构建生产包并输出到 ../web 目录
```

### 3. 命令行常用指令

在 `src/` 目录下执行：

```bash
# 解析直播间信息
python main.py resolve 80017709309

# 录制指定时长直播（单位：秒）
python main.py record 80017709309 -d 10

# 持续分段录制
python main.py segment 80017709309 -d 300

# 对本地录像执行 AI 全流程精修分析
python main.py analyze ../recordings/xxx.mp4

# 双轨导出（9:16 成片 + 剪映草稿）
python main.py export ../recordings/xxx.mp4 -s 0.0 -e 20.0 -t "爆款标题"
```

---

## 目录与模块架构

```text
live-cutter/
├── config/
│   ├── llm_config.example.json # 大模型配置模板（首次使用需复制为 llm_config.json）
│   ├── llm_config.json         # 本地大模型配置（已忽略，不上传 Git）
│   ├── douyin_cookies.json     # 本地抖音登录态 Cookie（已忽略，不上传 Git）
│   ├── system_config.json      # 录制、切片时长与能量阈值等系统参数
│   └── anchors/                # 主播专属档案库（黑话词典、模板、人设 Prompt）
├── gui/                        # Vue 3 + Vite 前端工程源码
│   └── src/components/         # 工作台各业务组件
├── web/                        # 前端构建产物（供 FastAPI 直接托管）
├── recordings/                 # 原始直播流录像（运行期生成，已忽略）
├── output/                     # 渲染生成的 9:16 MP4 成品（运行期生成，已忽略）
├── drafts/                     # 导出的剪映专业版工程草稿
└── src/
    ├── resolver.py             # 抖音推流解析器核心
    ├── recorder.py             # FFmpeg 流式录制与分段引擎
    ├── realtime_monitor.py     # 实时高能监控与滚存触发引擎
    ├── audio_analyzer.py       # 音频短时能量分析与波峰提取
    ├── danmu_monitor.py        # 弹幕/礼物监听与滑动窗口热度
    ├── heat_scorer.py          # 多模态热度融合打分器
    ├── asr_transcriber.py      # Faster-Whisper 毫秒级语音转录与字幕打轴
    ├── vision_sampler.py       # 视频关键帧采样器（供多模态模型感知画面）
    ├── langchain_analyzer.py   # LangChain 双模智能分析引擎（流式输出）
    ├── semantic_filter.py      # 智能语义精筛与断句定位器
    ├── llm_client.py           # 统一大模型客户端
    ├── video_composer.py       # FFmpeg 9:16 自适应竖屏画幅与花字压制
    ├── jianying_exporter.py    # 剪映专业版原生工程草稿导出器
    ├── anchor_profile.py       # 主播专属档案管理
    ├── api_server.py           # FastAPI RESTful & SSE 后端服务
    ├── start_gui.py            # 可视化工作台一键启动器
    └── main.py                 # 统一命令行入口
```

---

## 常见问题排查 (FAQ)

1. **首次启动报错 `openai.OpenAIError: Missing credentials`**
   - **原因**：本地缺少 `config/llm_config.json`，或其中的 `api_key` 为空。
   - **解决**：按上方【初始化大模型配置文件】步骤，将 `config/llm_config.example.json` 复制为 `config/llm_config.json` 并填入有效 API Key。
2. **录制或导出成片报错找不到 `ffmpeg`**
   - **解决**：请先安装 FFmpeg，并在终端运行 `ffmpeg -version` 确认其已加入系统 `PATH`。
3. **剪映专业版看不到导出的草稿**
   - **解决**：系统会自动探测常见剪映草稿目录（如 `D:\JianyingPro Drafts\com.lveditor.draft` 等），若未自动识别，可将 `drafts/` 下生成的草稿文件夹手动复制到你的剪映草稿根目录后重启剪映。
