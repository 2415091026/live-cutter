<template>
  <div class="app-root">
    <!-- 顶部专业导播导航栏 Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand-badge">
          <div class="brand-logo-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <polygon points="23 7 16 12 23 17 23 7"></polygon>
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
          </div>
          <div class="brand-text-group">
            <div class="brand-title-row">
              <span class="brand-title">LIVE-CUTTER</span>
              <span class="pro-tag">STUDIO PRO</span>
            </div>
            <span class="brand-subtitle">抖音直播实时高能感知与智能切片工作台</span>
          </div>
        </div>

        <div class="header-divider"></div>

        <!-- 顶栏核心遥测胶囊组 -->
        <div class="telemetry-bar">
          <div class="telemetry-pill" @click="showConfigDrawer = true" style="cursor: pointer;" title="点击切换双模认知引擎">
            <span class="pulse-dot online"></span>
            <span class="pill-label">认知引擎</span>
            <span class="pill-value mono-num">{{ systemStatus.llm_model }}</span>
            <span class="pill-tag" :class="{ 'omni-tag': systemStatus.engine_mode === 'multimodal' }">
              {{ systemStatus.engine_mode === 'multimodal' ? '👁️ 多模态 Omni' : '⚡ 声文极速' }}
            </span>
          </div>

          <div class="telemetry-pill" :class="{ 'is-monitoring': isMonitoring }">
            <span class="pulse-dot" :class="{ online: isMonitoring }"></span>
            <span class="pill-label">监听状态</span>
            <span class="pill-value">
              {{ isMonitoring ? `${currentAnchor || currentTarget}` : '待机中' }}
            </span>
          </div>

          <div class="telemetry-pill" :class="{ 'is-monitoring': danmuTelemetry.isRunning }">
            <span class="pulse-dot" :class="{ online: danmuTelemetry.connectionState === 'connected' }"></span>
            <span class="pill-label">弹幕/礼物</span>
            <span class="pill-value mono-num">
              {{ danmuTelemetry.isRunning ? `${danmuTelemetry.totalChats} 条 / ${danmuTelemetry.totalGifts} 礼` : '-' }}
            </span>
          </div>

          <div class="telemetry-pill">
            <span class="pill-label">资产/切片</span>
            <span class="pill-value mono-num">{{ recordings.length }} 录播 / {{ candidates.length }} 切片</span>
          </div>
        </div>
      </div>

      <div class="header-right">
        <button class="btn btn-secondary" @click="showAnchorModal = true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
          <span>主播专属档案 ({{ anchors.length }})</span>
        </button>

        <button class="btn btn-secondary" @click="showConfigDrawer = true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
          <span>系统与模型参数</span>
        </button>

        <button class="btn btn-primary" @click="refreshAll">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          <span>全局同步</span>
        </button>
      </div>
    </header>

    <!-- 工作台 Bento 网格三栏主视图 -->
    <main class="workbench-grid">
      <!-- 左栏：直播推流雷达、长效高能监听与本地素材库 -->
      <section class="col-left">
        <LiveResolver 
          :is-monitoring="isMonitoring"
          :current-target="currentTarget"
          :current-anchor="currentAnchor"
          :elapsed-seconds="elapsedSeconds"
          :captured-count="capturedCount"
          @start-monitor="handleStartMonitor"
          @stop-monitor="handleStopMonitor"
          @connect-danmu="handleConnectDanmu"
          @watch-live="handleWatchLive"
          @recording-created="handleRecordingCreated"
          @show-toast="triggerToast" 
        />
        <RecordingsList 
          :recordings="recordings" 
          :current-video="currentVideo"
          @select-video="handleSelectVideo" 
          @refresh="fetchRecordings"
          @video-deleted="handleVideoDeleted"
          @show-toast="triggerToast"
        />
      </section>

      <!-- 中栏：大屏导播监视器、实时弹幕与礼物雷达 -->
      <section class="col-center">
        <MonitorPlayer 
          ref="playerRef"
          :current-video="currentVideo"
          :live-meta="activeLiveMeta"
          :monitor-mode="monitorMode"
          @switch-mode="handleSwitchMonitorMode"
        />
        <DanmuGiftPanel
          ref="danmuPanelRef"
          :active-target="currentTarget"
          @status-change="handleDanmuStatusChange"
          @show-toast="triggerToast"
        />
      </section>

      <!-- 右栏：AI 智能切片决策池与流式认知终端 -->
      <section class="col-right">
        <CandidateBoard 
          :candidates="candidates"
          :current-video="currentVideo"
          @start-analyze="runAiAnalyze"
          @update-candidates="handleUpdateCandidates"
          @select-candidate="handleSelectCandidate"
          @seek-to="handleSeekTo"
          @show-toast="triggerToast"
        />
      </section>
    </main>

    <!-- 主播档案弹窗 -->
    <AnchorModal 
      :visible="showAnchorModal"
      :anchors="anchors"
      @close="showAnchorModal = false"
    />

    <!-- 系统与大模型高级配置抽屉 -->
    <ConfigDrawer 
      :visible="showConfigDrawer"
      @close="showConfigDrawer = false"
      @config-saved="refreshAll"
      @show-toast="triggerToast"
    />

    <!-- 全局悬浮通知 Toast -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="toast-box">
        <span class="toast-indicator"></span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import LiveResolver from './components/LiveResolver.vue'
import RecordingsList from './components/RecordingsList.vue'
import MonitorPlayer from './components/MonitorPlayer.vue'
import DanmuGiftPanel from './components/DanmuGiftPanel.vue'
import CandidateBoard from './components/CandidateBoard.vue'
import AnchorModal from './components/AnchorModal.vue'
import ConfigDrawer from './components/ConfigDrawer.vue'

// 响应式状态定义
const systemStatus = ref({ llm_model: 'qwen3.8-flash', llm_ready: true })
const recordings = ref([])
const currentVideo = ref(null)
const activeLiveMeta = ref(null)
const monitorMode = ref('vod') // 'live' | 'vod'
const candidates = ref([])
const peaks = ref([])
const totalDuration = ref(0)
const avgEnergy = ref(0)
const anchors = ref([])

// 高能实时监控状态
const isMonitoring = ref(false)
const currentTarget = ref('')
const currentAnchor = ref('')
const elapsedSeconds = ref(0)
const capturedCount = ref(0)
const lastRecordingsCount = ref(0)
const lastLatestRecording = ref('')
let monitorPollTimer = null
let idleSyncTimer = null

const showAnchorModal = ref(false)
const showConfigDrawer = ref(false)
const toastMessage = ref('')
const playerRef = ref(null)
const danmuPanelRef = ref(null)
const danmuTelemetry = ref({
  isRunning: false,
  connectionState: 'idle',
  totalChats: 0,
  totalGifts: 0
})
let toastTimer = null

// 接收弹幕礼物组件状态同步
const handleDanmuStatusChange = (st) => {
  danmuTelemetry.value = { ...danmuTelemetry.value, ...st }
}

// 联动开启指定房间的实时弹幕与礼物采集（透传元数据秒切；若长效监听已开启则同步切台）
const handleConnectDanmu = (rid, resolvedMeta = null) => {
  if (danmuPanelRef.value && rid) {
    danmuPanelRef.value.startForTarget(rid, resolvedMeta)
  }
  if (isMonitoring.value && rid && rid !== currentTarget.value) {
    handleStartMonitor(rid)
  }
}

// 在导播主监视器中实时播放已解析的直播流
const handleWatchLive = (meta) => {
  if (!meta || !meta.is_living) return
  activeLiveMeta.value = meta
  monitorMode.value = 'live'
}

// 在实时直播画面与本地录像回放之间切换
const handleSwitchMonitorMode = (mode) => {
  monitorMode.value = mode
}

// 弹出 Toast 提示
const triggerToast = (msg, duration = 4000) => {
  toastMessage.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
  }, duration)
}

// 快速录制样本完成后的即时自动同步与预览
const handleRecordingCreated = async (data) => {
  await fetchRecordings()
  if (data && data.filename) {
    const target = recordings.value.find(r => r.filename === data.filename)
    if (target) {
      handleSelectVideo(target)
    }
  }
}

// 启动或切换实时长效监听
const handleStartMonitor = async (target, doneCb) => {
  try {
    const res = await fetch('/api/monitor/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target })
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '启动失败')
    }

    const data = await res.json()
    isMonitoring.value = true
    currentTarget.value = data.target || target
    currentAnchor.value = data.anchor_name || '-'
    triggerToast(`🟢 已成功开启对【${data.anchor_name}】(${currentTarget.value}) 的实时高能监听！`)
    await fetchRecordings()
    startPollingMonitor()
  } catch (err) {
    triggerToast(`监听启动失败: ${err.message}`)
  } finally {
    if (doneCb) doneCb()
  }
}

// 停止实时监听
const handleStopMonitor = async (doneCb) => {
  try {
    // 立即终止前端轮询，网络请求瞬间归零
    stopPollingMonitor()
    isMonitoring.value = false
    currentTarget.value = ''
    currentAnchor.value = ''

    await fetch('/api/monitor/stop', { method: 'POST' })
    triggerToast('🔴 高能实时监听已停止，录制与切片已彻底中止')
    await fetchRecordings()
  } catch (err) {
    triggerToast(`停止异常: ${err.message}`)
  } finally {
    if (doneCb) doneCb()
  }
}

// 轮询后台监控状态与自动捕获的最新高能切片与录像分片资产 (仅在监听中启动)
const startPollingMonitor = () => {
  stopPollingMonitor()
  monitorPollTimer = setInterval(async () => {
    // 若前端或后台非监听状态，立即自毁定时器，不再发送网络请求
    if (!isMonitoring.value) {
      stopPollingMonitor()
      return
    }

    try {
      const res = await fetch('/api/monitor/status')
      if (res.ok) {
        const data = await res.json()
        if (!data.is_monitoring) {
          isMonitoring.value = false
          stopPollingMonitor()
          return
        }

        currentTarget.value = data.target || ''
        currentAnchor.value = data.anchor_name || ''
        elapsedSeconds.value = data.elapsed_seconds
        
        // 实时检测录像文件资产变动
        const recCount = data.recordings_count !== undefined ? data.recordings_count : 0
        const latestRec = data.latest_recording || ''
        const countChanged = lastRecordingsCount.value > 0 && recCount !== lastRecordingsCount.value
        const fileChanged = lastLatestRecording.value && latestRec && latestRec !== lastLatestRecording.value

        if (countChanged || fileChanged) {
          lastRecordingsCount.value = recCount
          lastLatestRecording.value = latestRec
          await fetchRecordings()
        } else {
          lastRecordingsCount.value = recCount
          lastLatestRecording.value = latestRec
        }

        // 同步新切片
        const latestList = data.recent_highlights || []
        const hasNew = data.captured_count > capturedCount.value
        const isInitEmpty = candidates.value.length === 0 && latestList.length > 0

        if (hasNew || isInitEmpty) {
          capturedCount.value = data.captured_count
          latestList.forEach(hl => {
            const exists = candidates.value.some(c => (c.id && c.id === hl.id) || (c.title === hl.title))
            if (!exists) {
              candidates.value.unshift(hl)
              if (hasNew && !isInitEmpty) {
                triggerToast(`⚡ 自动捕获高能时刻！归因: ${hl.trigger_reason}`)
              }
            }
          })
          await fetchRecordings()
        }
      }
    } catch (e) {}
  }, 2000)
}

const stopPollingMonitor = () => {
  if (monitorPollTimer) {
    clearInterval(monitorPollTimer)
    monitorPollTimer = null
  }
}

// 刷新系统全局状态
const fetchStatus = async () => {
  try {
    const res = await fetch('/api/system/status')
    if (res.ok) {
      systemStatus.value = await res.json()
    }
  } catch (err) {
    console.error('获取系统状态失败:', err)
  }
}

// 获取录像列表
const fetchRecordings = async () => {
  try {
    const res = await fetch('/api/recordings')
    if (res.ok) {
      recordings.value = await res.json()
      if (!currentVideo.value && recordings.value.length > 0) {
        handleSelectVideo(recordings.value[0])
      }
    }
  } catch (err) {
    console.error('获取录像列表失败:', err)
  }
}

// 获取主播档案
const fetchAnchors = async () => {
  try {
    const res = await fetch('/api/anchors')
    if (res.ok) {
      anchors.value = await res.json()
    }
  } catch (err) {
    console.error('获取主播档案失败:', err)
  }
}

// 选中录像（自动切回录像回放模式）
const handleSelectVideo = (video) => {
  currentVideo.value = video
  if (video) {
    monitorMode.value = 'vod'
  }
}

// 当录像被删除后的平滑切台处理
const handleVideoDeleted = (deletedRec) => {
  if (currentVideo.value && (currentVideo.value.filename === deletedRec.filename || currentVideo.value.file_path === deletedRec.file_path)) {
    const remaining = recordings.value.filter(r => r.filename !== deletedRec.filename)
    if (remaining.length > 0) {
      handleSelectVideo(remaining[0])
    } else {
      currentVideo.value = null
    }
  }
}

// 接收流式分析完成后的切片与声波数据
const handleUpdateCandidates = (payload) => {
  candidates.value = payload.candidates || []
  peaks.value = payload.peaks || []
  totalDuration.value = payload.total_duration || 0
  avgEnergy.value = payload.avg_energy || 0
}

// 执行全流程 AI 分析
const runAiAnalyze = async (doneCallback) => {
  if (!currentVideo.value) return
  triggerToast('正在调度 Whisper 语音转录与 Qwen3.8-Flash 语义精修...')

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: currentVideo.value.file_path })
    })

    if (!res.ok) throw new Error('AI识别服务异常')
    const data = await res.json()

    candidates.value = data.candidates || []
    peaks.value = data.peaks || []
    totalDuration.value = data.total_duration || 0
    avgEnergy.value = data.avg_energy || 0

    triggerToast(`AI分析完毕！成功提取 ${candidates.value.length} 个高能切片并标明归因！`)
  } catch (err) {
    triggerToast(`AI分析失败: ${err.message}`)
  } finally {
    if (doneCallback) doneCallback()
  }
}

// 核心联动：点击切片卡片智能关联素材库并驱动大屏精准播放
const handleSelectCandidate = async (cand) => {
  if (!cand) return
  monitorMode.value = 'vod'

  const targetFilename = cand.source_video || cand.source_filename || (cand.video_path ? cand.video_path.replace(/\\/g, '/').split('/').pop() : null)
  const startSec = cand.precise_start !== undefined ? cand.precise_start : (cand.start_time || 0)

  if (targetFilename) {
    let matched = recordings.value.find(r => r.filename === targetFilename)

    if (!matched) {
      const cleanTarget = targetFilename.replace('.mp4', '')
      matched = recordings.value.find(r => r.filename.includes(cleanTarget) || cleanTarget.includes(r.filename.replace('.mp4', '')))
    }

    if (!matched) {
      await fetchRecordings()
      matched = recordings.value.find(r => r.filename === targetFilename)
    }

    if (matched) {
      currentVideo.value = matched
      triggerToast(`已精准联动素材【${matched.filename}】，定位至 ${startSec}s 播放！`)
    } else {
      currentVideo.value = {
        filename: targetFilename,
        file_path: cand.source_path || cand.video_path,
        url: cand.source_url || `/static/recordings/${targetFilename}`,
        time_display: cand.created_at || '刚刚',
        anchor_label: cand.anchor_name || '-'
      }
      triggerToast(`已联动载入切片素材【${targetFilename}】，定位至 ${startSec}s 播放！`)
    }
  } else {
    triggerToast(`已定位至切片起点: ${startSec} 秒`)
  }

  if (playerRef.value) {
    playerRef.value.seekAndPlay(startSec)
  }
}

// 播放器时间跳转
const handleSeekTo = (sec) => {
  if (playerRef.value) {
    playerRef.value.seekAndPlay(sec)
  }
}

// 全局刷新
const refreshAll = () => {
  fetchStatus()
  fetchRecordings()
  fetchAnchors()
  triggerToast('工作台状态已全局同步')
}

onMounted(() => {
  refreshAll()
})

onUnmounted(() => {
  stopPollingMonitor()
  if (idleSyncTimer) {
    clearInterval(idleSyncTimer)
    idleSyncTimer = null
  }
})
</script>

<style scoped>
.app-root {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 顶部专业导播导航栏 */
.app-header {
  height: 68px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(9, 12, 21, 0.82);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 18px;
}

.brand-badge {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(6, 182, 212, 0.2) 100%);
  border: 1px solid rgba(99, 102, 241, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818CF8;
  box-shadow: 0 0 18px rgba(99, 102, 241, 0.25);
}

.brand-text-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-title {
  font-family: 'Outfit', sans-serif;
  font-size: 1.12rem;
  font-weight: 800;
  letter-spacing: 0.6px;
  background: linear-gradient(135deg, #FFFFFF 0%, #C7D2FE 60%, #38BDF8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.pro-tag {
  font-size: 0.62rem;
  padding: 2px 7px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.28), rgba(168, 85, 247, 0.25));
  color: #C7D2FE;
  border-radius: 999px;
  border: 1px solid rgba(129, 140, 248, 0.4);
  font-weight: 700;
  letter-spacing: 0.5px;
}

.brand-subtitle {
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.header-divider {
  width: 1px;
  height: 28px;
  background: var(--border-subtle);
}

/* 遥测状态胶囊栏 */
.telemetry-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.telemetry-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-subtle);
  box-shadow: var(--inner-highlight);
  transition: var(--transition);
}

.telemetry-pill.is-monitoring {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.35);
}

.pill-label {
  color: var(--text-muted);
  font-weight: 500;
}

.pill-value {
  color: var(--text-main);
  font-weight: 700;
}

.pill-tag {
  font-size: 0.64rem;
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent-light);
  background: rgba(6, 182, 212, 0.14);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 主工作区 Bento 网格：三栏等高黄金比例控制台 */
.workbench-grid {
  display: grid;
  grid-template-columns: 360px minmax(540px, 1fr) 460px;
  gap: 16px;
  padding: 16px 22px;
  flex: 1;
  min-height: 0;
  max-width: 2240px;
  margin: 0 auto;
  width: 100%;
  align-items: stretch;
}

.col-left, .col-center, .col-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

/* 全局悬浮通知 Toast */
.toast-box {
  position: fixed;
  bottom: 28px;
  right: 28px;
  background: rgba(14, 19, 32, 0.94);
  border: 1px solid rgba(99, 102, 241, 0.5);
  color: #FFFFFF;
  padding: 12px 20px;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 500;
  box-shadow: var(--shadow-float), 0 0 24px rgba(99, 102, 241, 0.25);
  z-index: 200;
  backdrop-filter: blur(16px);
  max-width: 440px;
  line-height: 1.45;
  display: flex;
  align-items: center;
  gap: 10px;
}

.toast-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-light);
  box-shadow: 0 0 10px var(--accent-light);
  flex-shrink: 0;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}

@media (max-width: 1580px) {
  .telemetry-bar .telemetry-pill:nth-child(4) {
    display: none;
  }
  .workbench-grid {
    grid-template-columns: 335px minmax(460px, 1fr) 430px;
    gap: 14px;
    padding: 14px 18px;
  }
}

@media (max-width: 1240px) {
  .app-root {
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }
  .telemetry-bar {
    display: none;
  }
  .workbench-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .col-left, .col-center, .col-right {
    height: auto;
  }
}
</style>
