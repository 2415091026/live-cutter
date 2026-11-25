<template>
  <div class="glass-card resolver-card">
    <div class="card-header-bar">
      <div class="card-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="2"></circle>
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path>
        </svg>
        <span>直播推流雷达与实时监听</span>
      </div>
      <span class="radar-tag">DOUYIN STREAM</span>
    </div>

    <!-- 房间号/链接输入栏 -->
    <div class="input-row">
      <div class="input-field-wrap">
        <svg class="input-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
        </svg>
        <input 
          v-model="targetInput" 
          type="text" 
          placeholder="输入抖音房间号或直播链接 (如 921169302662)"
          @keyup.enter="handleResolve"
        />
      </div>
      <button class="btn btn-accent" :disabled="loading" @click="handleResolve">
        {{ loading ? '解析中...' : '解析推流' }}
      </button>
    </div>

    <!-- 快捷主播房间填入条 -->
    <div class="quick-presets-row">
      <span class="preset-label">快捷定位:</span>
      <button class="preset-chip" @click="quickFill('921169302662')">🏎️ 陈伯(全能王)</button>
      <button class="preset-chip" @click="quickFill('80017709309')">📚 东方甄选</button>
    </div>

    <!-- 实时高能监听控制面板 -->
    <div class="monitor-control-panel" :class="{ 'is-active': isMonitoring }">
      <div class="monitor-status-row">
        <div class="monitor-indicator">
          <span class="pulse-dot" :class="isMonitoring ? 'online' : ''"></span>
          <span class="status-text">
            {{ isMonitoring ? `高能雷达监听中 (${formatTime(elapsedSeconds)})` : '长效监听待机中' }}
          </span>
        </div>
        <span class="captured-badge mono-num" v-if="isMonitoring">
          ⚡ 已捕获 {{ capturedCount }} 条
        </span>
      </div>

      <!-- 当前实际正在监听的目标信息展示 -->
      <div v-if="isMonitoring" class="active-target-info">
        <div class="target-row">
          <span class="target-label">锁定主播</span>
          <span class="target-name">{{ currentAnchor || '-' }}</span>
        </div>
        <div class="target-rid-row">
          <span class="rid-tag">RID</span>
          <span class="target-rid mono-num">{{ currentTarget || '-' }}</span>
        </div>
      </div>

      <!-- 操作按钮群：未启动 / 运行中 / 检测到新房间切换 -->
      <div class="actions-wrapper">
        <button 
          v-if="!isMonitoring"
          class="btn btn-sm btn-monitor-toggle btn-start-monitor"
          :disabled="monitorOperating"
          @click="startWithCurrentInput"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          <span>启动长效高能监听 (自动捕获切片)</span>
        </button>

        <template v-else>
          <div class="switch-buttons-group" :class="{ 'single-col': !isTargetDifferent }">
            <button 
              v-if="isTargetDifferent"
              class="btn btn-sm btn-switch-monitor"
              :disabled="monitorOperating"
              @click="startWithCurrentInput"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="23 4 23 10 17 10"></polyline>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              <span>切换至当前房间</span>
            </button>

            <button 
              class="btn btn-sm btn-stop-monitor"
              :disabled="monitorOperating"
              @click="stopMonitor"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="1"></rect>
              </svg>
              <span>停止实时监听</span>
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- 解析结果详情卡片 -->
    <div v-if="liveMeta" class="live-meta-box">
      <div class="meta-header">
        <span class="status-pill" :class="liveMeta.is_living ? 'live-on' : 'live-off'">
          {{ liveMeta.is_living ? '● 正在直播' : '○ 已关播' }}
        </span>
        <span class="anchor-name">{{ liveMeta.anchor_name || '-' }}</span>
      </div>
      <div class="room-title">{{ liveMeta.title || '-' }}</div>

      <div class="quality-tags">
        <span class="tag">FULL_HD1 原画直拉</span>
        <span class="tag">FLV / HLS 零损转存</span>
      </div>

      <!-- 快速录制样本、实时直播画面与弹幕监听操作组 -->
      <div class="meta-record-row live-watch-row">
        <button
          class="btn btn-sm btn-watch-live"
          :disabled="!liveMeta.is_living"
          @click="emit('watch-live', liveMeta)"
        >
          <span>📺 在主监视器播放实时直播</span>
        </button>
      </div>

      <div class="meta-record-row dual-actions">
        <button 
          class="btn btn-sm btn-quick-record"
          :disabled="quickRecordLoading || !liveMeta.is_living"
          @click="handleQuickRecord(10)"
        >
          <span class="rec-dot" :class="{ 'pulsing': quickRecordLoading }"></span>
          <span>{{ quickRecordLoading ? '录制 10s...' : '录制 10 秒样本' }}</span>
        </button>

        <button
          class="btn btn-sm btn-open-danmu"
          :disabled="!liveMeta.is_living"
          @click="emit('connect-danmu', liveMeta.web_rid || targetInput.trim(), liveMeta)"
        >
          <span>💬 监听弹幕礼物</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  isMonitoring: {
    type: Boolean,
    default: false
  },
  currentTarget: {
    type: String,
    default: ''
  },
  currentAnchor: {
    type: String,
    default: ''
  },
  elapsedSeconds: {
    type: Number,
    default: 0
  },
  capturedCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['start-monitor', 'stop-monitor', 'show-toast', 'recording-created', 'connect-danmu', 'live-resolved', 'watch-live'])

const targetInput = ref('')
const loading = ref(false)
const quickRecordLoading = ref(false)
const monitorOperating = ref(false)
const liveMeta = ref(null)

watch(() => props.currentTarget, (newVal) => {
  if (newVal && !targetInput.value) {
    targetInput.value = newVal
  }
}, { immediate: true })

const isTargetDifferent = computed(() => {
  const current = (props.currentTarget || '').trim()
  const input = targetInput.value.trim()
  return input && current && input !== current
})

const formatTime = (secs) => {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const quickFill = (rid) => {
  targetInput.value = rid
  handleResolve()
}

const handleResolve = async () => {
  const target = targetInput.value.trim()
  if (!target) {
    emit('show-toast', '请输入直播间网址或房间号')
    return
  }

  loading.value = true
  try {
    const res = await fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target })
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '解析失败')
    }

    liveMeta.value = await res.json()
    emit('live-resolved', liveMeta.value)
    if (liveMeta.value.is_living) {
      emit('watch-live', liveMeta.value)
      emit('connect-danmu', liveMeta.value.web_rid || target, liveMeta.value)
    }
    emit('show-toast', `成功解析主播: ${liveMeta.value.anchor_name}`)
  } catch (err) {
    emit('show-toast', `解析异常: ${err.message}`)
  } finally {
    loading.value = false
  }
}

// 快速拉流截取样本
const handleQuickRecord = async (duration = 10) => {
  const target = targetInput.value.trim() || props.currentTarget
  if (!target) {
    emit('show-toast', '请先输入直播间房间号或粘贴链接')
    return
  }
  quickRecordLoading.value = true
  emit('show-toast', `正在拉流录制 ${duration} 秒直播样本...`)
  try {
    const res = await fetch('/api/record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, duration })
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '录制异常')
    }
    const data = await res.json()
    emit('show-toast', `✅ 录制完成: ${data.filename}`)
    // 立即通知父组件刷新录像列表并自动选中新录制的视频
    emit('recording-created', data)
  } catch (err) {
    emit('show-toast', `❌ 录制失败: ${err.message}`)
  } finally {
    quickRecordLoading.value = false
  }
}

const startWithCurrentInput = () => {
  const target = targetInput.value.trim()
  if (!target) {
    emit('show-toast', '请输入直播间房间号或粘贴链接后再开启监听')
    return
  }

  monitorOperating.value = true
  emit('start-monitor', target, () => {
    monitorOperating.value = false
  })
}

const stopMonitor = () => {
  monitorOperating.value = true
  emit('stop-monitor', () => {
    monitorOperating.value = false
  })
}
</script>

<style scoped>
.resolver-card {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.card-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.radar-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  font-weight: 700;
  color: var(--accent-light);
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.28);
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.input-row {
  display: flex;
  gap: 8px;
}

.input-field-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
}

.input-icon {
  position: absolute;
  left: 11px;
  color: var(--text-muted);
  pointer-events: none;
}

.input-field-wrap input {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  color: #FFFFFF;
  padding: 9px 12px 9px 32px;
  font-size: 0.82rem;
  font-family: 'JetBrains Mono', 'Inter', sans-serif;
  outline: none;
  transition: var(--transition);
}

.input-field-wrap input::placeholder {
  color: var(--text-muted);
  font-family: 'Inter', sans-serif;
}

.input-field-wrap input:focus {
  border-color: var(--primary);
  background: rgba(9, 13, 24, 0.9);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
}

.input-row .btn-accent {
  white-space: nowrap;
  flex-shrink: 0;
  padding: 8px 14px;
}

/* 快捷预设标签栏 */
.quick-presets-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.preset-chip {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-sub);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  cursor: pointer;
  transition: var(--transition);
}

.preset-chip:hover {
  background: rgba(99, 102, 241, 0.16);
  border-color: rgba(99, 102, 241, 0.4);
  color: #FFFFFF;
}

/* 监听控制卡片 */
.monitor-control-panel {
  background: rgba(8, 11, 19, 0.68);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 13px;
  display: flex;
  flex-direction: column;
  gap: 11px;
  transition: var(--transition);
}

.monitor-control-panel.is-active {
  background: linear-gradient(180deg, rgba(16, 185, 129, 0.09) 0%, rgba(6, 78, 59, 0.12) 100%);
  border-color: rgba(16, 185, 129, 0.4);
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.12), inset 0 1px 0 rgba(52, 211, 153, 0.15);
}

.monitor-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.monitor-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.status-text {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-main);
}

.captured-badge {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--gold-light);
  background: rgba(245, 158, 11, 0.16);
  border: 1px solid rgba(245, 158, 11, 0.32);
  padding: 2px 8px;
  border-radius: 999px;
}

/* 正在监听的目标详情展示 */
.active-target-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.48);
  padding: 8px 11px;
  border-radius: var(--radius-xs);
  border-left: 3px solid var(--success);
}

.target-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.target-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.target-name {
  color: #FFFFFF;
  font-weight: 700;
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.target-rid-row {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.rid-tag {
  font-size: 0.62rem;
  background: rgba(6, 182, 212, 0.16);
  color: var(--accent-light);
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 700;
}

.target-rid {
  font-size: 0.74rem;
  color: #CBD5E1;
}

.actions-wrapper {
  display: flex;
  flex-direction: column;
}

.switch-buttons-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.switch-buttons-group.single-col {
  grid-template-columns: 1fr;
}

.btn-monitor-toggle {
  width: 100%;
  font-weight: 700;
  padding: 9px;
}

.btn-start-monitor {
  background: linear-gradient(135deg, #059669 0%, #10B981 100%);
  color: #FFFFFF;
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.28);
}
.btn-start-monitor:hover:not(:disabled) {
  box-shadow: 0 6px 18px rgba(16, 185, 129, 0.42);
  transform: translateY(-1px);
}

.btn-switch-monitor {
  background: linear-gradient(135deg, #D97706 0%, #F59E0B 100%);
  color: #FFFFFF;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.28);
}

.btn-stop-monitor {
  background: rgba(239, 68, 68, 0.14);
  border: 1px solid rgba(239, 68, 68, 0.38);
  color: #FCA5A5;
  font-weight: 700;
}
.btn-stop-monitor:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.24);
  color: #FFFFFF;
}

/* 解析结果详情 */
.live-meta-box {
  background: rgba(5, 7, 11, 0.55);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 11px 13px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-pill {
  font-size: 0.7rem;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 700;
}
.status-pill.live-on {
  background: rgba(16, 185, 129, 0.16);
  color: #34D399;
  border: 1px solid rgba(16, 185, 129, 0.35);
}
.status-pill.live-off {
  background: rgba(239, 68, 68, 0.15);
  color: #F87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.anchor-name {
  font-weight: 700;
  font-size: 0.86rem;
  color: #FFFFFF;
}

.room-title {
  font-size: 0.76rem;
  color: var(--text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quality-tags {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}

.quality-tags .tag {
  font-size: 0.66rem;
  background: rgba(99, 102, 241, 0.14);
  border: 1px solid rgba(99, 102, 241, 0.26);
  color: #C7D2FE;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 600;
}

.meta-record-row {
  margin-top: 4px;
}

.meta-record-row.dual-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.btn-watch-live {
  width: 100%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.32) 0%, rgba(168, 85, 247, 0.36) 100%);
  border: 1px solid rgba(129, 140, 248, 0.52);
  color: #FFFFFF;
  font-weight: 700;
  padding: 7px 12px;
}

.btn-watch-live:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.48) 0%, rgba(168, 85, 247, 0.54) 100%);
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.35);
}

.btn-open-danmu {
  width: 100%;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(99, 102, 241, 0.3) 100%);
  border: 1px solid rgba(56, 189, 248, 0.45);
  color: #E0F2FE;
  font-weight: 700;
  padding: 7px 10px;
}

.btn-open-danmu:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.35) 0%, rgba(99, 102, 241, 0.48) 100%);
  border-color: rgba(56, 189, 248, 0.72);
  box-shadow: 0 0 14px rgba(6, 182, 212, 0.28);
}

.btn-quick-record {
  width: 100%;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(220, 38, 38, 0.35) 100%);
  border: 1px solid rgba(239, 68, 68, 0.45);
  color: #FEE2E2;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 7px 12px;
}

.btn-quick-record:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(220, 38, 38, 0.55) 100%);
  border-color: rgba(239, 68, 68, 0.7);
  box-shadow: 0 0 14px rgba(239, 68, 68, 0.3);
}

.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #EF4444;
  box-shadow: 0 0 8px #EF4444;
}

.rec-dot.pulsing {
  animation: recPulse 1s infinite;
}

@keyframes recPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(0.8); }
}
</style>
