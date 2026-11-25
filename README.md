# 智能直播切片系统 (Live-Cutter PRO)

针对抖音平台主播的实时推流抓取、精彩片段智能识别与自动化切片系统。

---

## 项目里程碑全景 (100% 全部完成)

- [x] **阶段一：直播流解析与录制引擎**（已完成）
- [x] **阶段二：弹幕监听与音频能量检测引擎**（已完成）
- [x] **阶段三：ASR 语音转录与大模型语义精筛定位 (Qwen3.8-Flash)**（已完成）
- [x] **阶段四：自动化剪辑合成与直通剪映草稿工程导出**（已完成）
- [x] **阶段五：现代可视化桌面应用 (GUI) 与专属主播档案**（已完成）

---

## 阶段五成果：现代暗黑科技可视化工作台 (Web/桌面 GUI)

阶段五为系统打造了极具现代科技感与视觉美感的 **Bento Grid 响应式深色玻璃拟态工作台**。

### 核心功能区一览

1. **全局状态与 AI 大脑看板**：
   - 实时显示 Qwen3.8-Flash 在线状态与系统资产统计。
2. **直播间雷达与录像资产库**：
   - 输入任意抖音房间号或链接，实时解析主播信息、标题与推流状态。
   - 一键 10 秒快速录制样本，资产列表点击即在监视大屏预览。
3. **音频能量与高潮波峰心电图 (Canvas Radar)**：
   - 动态绘制音频能量基线与高潮黄色脉冲峰值，直观呈现精彩爆发点。
4. **AI 智能切片决策看板**：
   - 一键触发 Whisper 语音转录 + Qwen3.8-Flash 语义断句决策。
   - 自动生成核心金句、3 条爆款抖音标题与推荐起止时间。
   - 提供【🎬 一键导出 9:16 成片】与【✂️ 一键导入剪映草稿】双轨交付！
5. **主播专属性格档案库 (`config/anchors/`)**：
   - 支持配置不同主播的专属黑话字典、专属剪辑模版与人设 Prompt。

---

## 快速启动指南

进入目录：
```bash
cd live-cutter/src
```

### 1. 一键启动现代可视化工作台 (推荐)
```bash
python start_gui.py
# 或使用统一 CLI
python main.py gui
```
- 服务将自动在后台运行（`http://127.0.0.1:8765/`），并自动唤起浏览器打开操作大屏！

### 2. 命令行常用指令
- **解析直播间**：`python main.py resolve 80017709309`
- **录制直播**：`python main.py record 80017709309 -d 10`
- **持续分片**：`python main.py segment 80017709309 -d 300`
- **AI 全流程精修**：`python main.py analyze ../recordings/xxx.mp4`
- **双轨成片导出**：`python main.py export ../recordings/xxx.mp4 -s 0.0 -e 4.0 -t "标题"`

---

## 模块架构全景

```
live-cutter/
├── config/
│   ├── llm_config.json        # 🌟 大模型配置文件 (已配置 Qwen3.8-Flash)
│   └── anchors/               # 👤 主播专属档案库 (东方甄选 / 游戏主播模版)
├── recordings/                # 📹 原始直播流录像文件
├── output/                    # 🎬 渲染生成的 9:16 MP4 短视频成品
├── drafts/                    # ✂️ 导出的剪映专业版多轨道工程草稿 (draft_content.json)
├── web/                       # 💻 现代暗黑科技前端页面 (HTML5 + CSS3 + ES6)
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/
    ├── resolver.py            # 抖音推流解析器核心
    ├── recorder.py            # FFmpeg 流式录制与分段引擎
    ├── audio_analyzer.py      # 音频短时能量分析与波峰提取
    ├── danmu_monitor.py       # 弹幕 WebSocket 监听与滑动窗口热度
    ├── heat_scorer.py         # 多模态热度融合打分器
    ├── asr_transcriber.py     # Faster-Whisper 毫秒级语音转录与字幕打轴
    ├── semantic_filter.py     # 智能语义精筛与断句定位器 (句首句尾防腰斩)
    ├── llm_client.py          # 统一大模型客户端
    ├── video_composer.py      # FFmpeg 9:16 自适应竖屏画幅与花字压制
    ├── jianying_exporter.py   # 剪映专业版原生工程草稿导出器
    ├── anchor_profile.py      # 主播专属档案管理
    ├── api_server.py          # FastAPI RESTful API 后端服务
    ├── start_gui.py           # 可视化工作台一键启动器
    └── main.py                # 统一命令行入口
```
