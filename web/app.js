// ==========================================================================
// Live-Cutter 智能切片工作台 前端交互控制逻辑 (ES6 Module)
// ==========================================================================

const API_BASE = window.location.origin;

// 全局应用状态
const state = {
  currentVideo: null,
  recordings: [],
  candidates: [],
  peaks: [],
  anchors: []
};

// DOM 元素引用
const dom = {
  aiModelTag: document.getElementById("ai-model-tag"),
  btnRefreshStatus: document.getElementById("btn-refresh-status"),
  inputRoomTarget: document.getElementById("input-room-target"),
  btnResolveStream: document.getElementById("btn-resolve-stream"),
  resolveResultBox: document.getElementById("resolve-result-box"),
  liveStatusPill: document.getElementById("live-status-pill"),
  liveAnchorName: document.getElementById("live-anchor-name"),
  liveRoomTitle: document.getElementById("live-room-title"),
  btnQuickRecord: document.getElementById("btn-quick-record"),
  recordingsCount: document.getElementById("recordings-count"),
  recordingsListContainer: document.getElementById("recordings-list-container"),
  mainVideoPlayer: document.getElementById("main-video-player"),
  currentPlayingLabel: document.getElementById("current-playing-label"),
  waveformCanvas: document.getElementById("waveform-canvas"),
  waveformStatsBar: document.getElementById("waveform-stats-bar"),
  btnTriggerAiAnalyze: document.getElementById("btn-trigger-ai-analyze"),
  candidatesBoard: document.getElementById("candidates-board"),
  btnOpenAnchors: document.getElementById("btn-open-anchors"),
  anchorsModal: document.getElementById("anchors-modal"),
  btnCloseAnchorsModal: document.getElementById("btn-close-anchors-modal"),
  anchorsListView: document.getElementById("anchors-list-view"),
  toast: document.getElementById("toast")
};

// 显示全局 Toast 提示
const showToast = (message, duration = 3000) => {
  dom.toast.textContent = message;
  dom.toast.classList.remove("hidden");
  setTimeout(() => {
    dom.toast.classList.add("hidden");
  }, duration);
};

// 1. 初始化系统状态
const fetchSystemStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/system/status`);
    const data = await res.json();
    if (data.llm_ready) {
      dom.aiModelTag.textContent = `AI大脑: ${data.llm_model} (在线)`;
    } else {
      dom.aiModelTag.textContent = `AI大脑: 规则模式 (未配置Key)`;
    }
  } catch (err) {
    console.error("获取系统状态失败:", err);
  }
};

// 2. 加载录像文件资产列表
const fetchRecordings = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/recordings`);
    const files = await res.json();
    state.recordings = files;
    dom.recordingsCount.textContent = files.length;

    if (files.length === 0) {
      dom.recordingsListContainer.innerHTML = `<div class="empty-state">暂无录像，请先录制或导入</div>`;
      return;
    }

    dom.recordingsListContainer.innerHTML = files.map((file, idx) => `
      <div class="recording-item ${state.currentVideo?.filename === file.filename ? 'active' : ''}" data-index="${idx}">
        <div>
          <div class="rec-title">${file.filename}</div>
          <div class="rec-size">${file.size_mb} MB</div>
        </div>
        <button class="btn btn-sm btn-secondary btn-select-video">选择</button>
      </div>
    `).join("");

    // 绑定点击事件
    document.querySelectorAll(".recording-item").forEach(item => {
      item.addEventListener("click", () => {
        const idx = item.getAttribute("data-index");
        selectVideo(state.recordings[idx]);
      });
    });

    // 默认选中第一个
    if (!state.currentVideo && files.length > 0) {
      selectVideo(files[0]);
    }
  } catch (err) {
    console.error("加载录像列表失败:", err);
  }
};

// 3. 选中视频进行播放并自动绘制模拟波形
const selectVideo = (video) => {
  state.currentVideo = video;
  dom.currentPlayingLabel.textContent = video.filename;
  dom.mainVideoPlayer.src = `${API_BASE}${video.url}`;
  dom.mainVideoPlayer.load();

  // 高亮侧边栏选中项
  document.querySelectorAll(".recording-item").forEach(el => el.classList.remove("active"));
  const activeEl = Array.from(document.querySelectorAll(".recording-item")).find(
    el => el.querySelector(".rec-title")?.textContent === video.filename
  );
  if (activeEl) activeEl.classList.add("active");

  // 绘制基础波形占位
  drawWaveform([], 5.0, 1800, 2500);
};

// 4. 解析直播间推流
const handleResolveStream = async () => {
  const target = dom.inputRoomTarget.value.trim();
  if (!target) {
    showToast("请输入直播间网址或房间号！");
    return;
  }

  dom.btnResolveStream.textContent = "解析中...";
  dom.btnResolveStream.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "解析失败");
    }

    const data = await res.json();
    dom.liveAnchorName.textContent = data.anchor_name;
    dom.liveRoomTitle.textContent = data.title;
    dom.liveStatusPill.textContent = data.is_living ? "● 正在直播" : "○ 已关播";
    dom.resolveResultBox.classList.remove("hidden");
    showToast(`成功解析主播: ${data.anchor_name}`);
  } catch (err) {
    showToast(`解析失败: ${err.message}`);
  } finally {
    dom.btnResolveStream.textContent = "解析推流";
    dom.btnResolveStream.disabled = false;
  }
};

// 5. 快速录制当前直播间样本
const handleQuickRecord = async () => {
  const target = dom.inputRoomTarget.value.trim();
  dom.btnQuickRecord.innerHTML = `<span class="record-dot"></span> 正在拉流录制 10s...`;
  dom.btnQuickRecord.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/record`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, duration: 10 })
    });
    if (!res.ok) throw new Error("录制发生异常");
    const data = await res.json();
    showToast(`录制完成: ${data.filename}`);
    await fetchRecordings();
    selectVideo(state.recordings[0]);
  } catch (err) {
    showToast(`录制失败: ${err.message}`);
  } finally {
    dom.btnQuickRecord.innerHTML = `<span class="record-dot"></span> 录制 10 秒样本`;
    dom.btnQuickRecord.disabled = false;
  }
};

// 6. Canvas 绘制音频波形心电图
const drawWaveform = (peaks, totalDuration = 10, avgEnergy = 1800, threshold = 2500) => {
  const canvas = dom.waveformCanvas;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  // 绘制深空背景网格
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += 30) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // 绘制模拟能量曲线 (正弦叠加噪声)
  ctx.beginPath();
  ctx.strokeStyle = "#6366F1";
  ctx.lineWidth = 2;

  const points = 120;
  for (let i = 0; i < points; i++) {
    const x = (i / points) * w;
    const timeAtX = (i / points) * totalDuration;

    // 检查是否在高潮波峰内
    const inPeak = peaks.some(p => timeAtX >= p.start_time && timeAtX <= p.end_time);
    let energyRatio = inPeak ? (0.7 + Math.random() * 0.25) : (0.2 + Math.random() * 0.2);

    const y = h - energyRatio * h * 0.85 - 10;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 标出高潮爆发矩形光晕
  peaks.forEach(p => {
    const x1 = (p.start_time / totalDuration) * w;
    const x2 = (p.end_time / totalDuration) * w;
    const pw = Math.max(x2 - x1, 14);

    ctx.fillStyle = "rgba(245, 158, 11, 0.25)";
    ctx.fillRect(x1, 0, pw, h);
    ctx.strokeStyle = "#F59E0B";
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, 0, pw, h);
  });
};

// 7. 触发 AI 智能切片全自动识别 (Whisper + Qwen)
const handleTriggerAiAnalyze = async () => {
  if (!state.currentVideo) {
    showToast("请先选择一个待分析的录制视频！");
    return;
  }

  dom.btnTriggerAiAnalyze.innerHTML = `<span>AI分析中...</span>`;
  dom.btnTriggerAiAnalyze.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_path: state.currentVideo.file_path })
    });

    if (!res.ok) throw new Error("AI 识别服务异常");

    const data = await res.json();
    state.candidates = data.candidates || [];
    state.peaks = data.peaks || [];

    // 更新波形统计栏
    dom.waveformStatsBar.innerHTML = `
      <span>总时长: ${data.total_duration}s</span>
      <span>平均能量: ${data.avg_energy}</span>
      <span>高潮爆发: ${data.peaks_count} 处</span>
      <span>AI精选: ${state.candidates.length} 条</span>
    `;

    // 绘制真实波形
    drawWaveform(state.peaks, data.total_duration, data.avg_energy);

    // 渲染切片卡片看板
    renderCandidates(state.candidates);
    showToast(`AI 大脑分析完成，成功识别 ${state.candidates.length} 条高价值切片！`);
  } catch (err) {
    showToast(`AI 识别失败: ${err.message}`);
  } finally {
    dom.btnTriggerAiAnalyze.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
      一键 AI 识别
    `;
    dom.btnTriggerAiAnalyze.disabled = false;
  }
};

// 8. 渲染 AI 切片卡片池
const renderCandidates = (candidates) => {
  if (candidates.length === 0) {
    dom.candidatesBoard.innerHTML = `
      <div class="empty-state">
        <p>未检测到明显高潮</p>
        <span>主播该时段状态平缓，建议分析较长录像</span>
      </div>
    `;
    return;
  }

  dom.candidatesBoard.innerHTML = candidates.map((cand, idx) => `
    <div class="candidate-card" data-index="${idx}">
      <div class="cand-top-row">
        <span class="score-badge">★ 热度: ${cand.heat_score}</span>
        <span class="cand-time">${cand.precise_start}s ➔ ${cand.precise_end}s (${cand.duration}s)</span>
      </div>
      <div class="cand-quote">「${cand.core_quote}」</div>
      <div class="cand-titles">
        ${cand.titles.map(t => `<span class="title-tag">🔥 ${t}</span>`).join("")}
      </div>
      <div class="cand-actions">
        <button class="btn btn-sm btn-export-mp4" data-action="export-mp4" data-index="${idx}">
          🎬 导出 9:16 成片
        </button>
        <button class="btn btn-sm btn-export-jy" data-action="export-jy" data-index="${idx}">
          ✂️ 导入剪映草稿
        </button>
      </div>
    </div>
  `).join("");

  // 绑定卡片导出动作
  dom.candidatesBoard.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const action = btn.getAttribute("data-action");
      const idx = btn.getAttribute("data-index");
      const cand = state.candidates[idx];
      await executeExport(cand, action === "export-mp4" ? "mp4" : "jy");
    });
  });

  // 卡片点击直接让播放器跳转到对应秒数
  dom.candidatesBoard.querySelectorAll(".candidate-card").forEach(card => {
    card.addEventListener("click", () => {
      const idx = card.getAttribute("data-index");
      const cand = state.candidates[idx];
      dom.mainVideoPlayer.currentTime = cand.precise_start;
      dom.mainVideoPlayer.play();
      showToast(`已跳转至高潮区间: ${cand.precise_start}s`);
    });
  });
};

// 9. 执行成片与剪映草稿导出
const executeExport = async (cand, targetType) => {
  showToast("正在渲染导出，请稍候...");
  try {
    const res = await fetch(`${API_BASE}/api/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_path: state.currentVideo.file_path,
        start_time: cand.precise_start,
        end_time: cand.precise_end,
        title: cand.titles[0] || cand.theme,
        subtitles: cand.subtitles || []
      })
    });

    if (!res.ok) throw new Error("导出服务返回错误");
    const data = await res.json();

    if (targetType === "mp4") {
      showToast(`✅ 9:16 成片已生成: ${data.mp4_path}`, 5000);
    } else {
      showToast(`✅ 剪映专业版草稿工程已就绪: ${data.draft_dir}`, 6000);
    }
  } catch (err) {
    showToast(`导出失败: ${err.message}`);
  }
};

// 10. 主播档案库模态弹窗
const fetchAnchors = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/anchors`);
    const list = await res.json();
    state.anchors = list;
    dom.anchorsListView.innerHTML = list.map(a => `
      <div class="card" style="margin-bottom: 10px; background: rgba(0,0,0,0.3);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h4 style="font-size:0.95rem; font-weight:700;">${a.anchor_name} (${a.category})</h4>
          <span style="font-size:0.75rem; color:var(--accent);">模版: ${a.layout_template}</span>
        </div>
        <p style="font-size:0.78rem; color:var(--text-secondary); margin: 6px 0;">专属Prompt: ${a.persona_prompt}</p>
        <div style="font-size:0.75rem; color:var(--gold);">黑话词库: ${a.exclusive_keywords.join(", ")}</div>
      </div>
    `).join("");
  } catch (err) {
    console.error("加载主播档案失败:", err);
  }
};

// 事件监听绑定
const initEvents = () => {
  dom.btnRefreshStatus.addEventListener("click", () => {
    fetchSystemStatus();
    fetchRecordings();
    showToast("状态已刷新");
  });

  dom.btnResolveStream.addEventListener("click", handleResolveStream);
  dom.btnQuickRecord.addEventListener("click", handleQuickRecord);
  dom.btnTriggerAiAnalyze.addEventListener("click", handleTriggerAiAnalyze);

  dom.btnOpenAnchors.addEventListener("click", () => {
    fetchAnchors();
    dom.anchorsModal.classList.remove("hidden");
  });

  dom.btnCloseAnchorsModal.addEventListener("click", () => {
    dom.anchorsModal.classList.add("hidden");
  });
};

// 启动入口
const initApp = async () => {
  initEvents();
  await fetchSystemStatus();
  await fetchRecordings();
  fetchAnchors();
};

document.addEventListener("DOMContentLoaded", initApp);
