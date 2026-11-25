<template>
  <div class="glass-card player-card">
    <div class="card-title player-header">
      <div class="title-left">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
          <line x1="8" y1="21" x2="16" y2="21"></line>
          <line x1="12" y1="17" x2="12" y2="21"></line>
        </svg>
        <span>导播主监视器 (Program Monitor)</span>

        <!-- 双模切换开关：实时直播 ⇄ 录像回放 -->
        <div v-if="liveMeta && liveMeta.is_living" class="mode-switch-group">
          <button
            class="mode-btn"
            :class="{ active: monitorMode === 'live', 'live-active': monitorMode === 'live' }"
            @click="emit('switch-mode', 'live')"
          >
            <span class="live-dot"></span>
            <span>实时直播</span>
          </button>
          <button
            class="mode-btn"
            :class="{ active: monitorMode === 'vod' }"
            @click="emit('switch-mode', 'vod')"
          >
            <span>录像回放</span>
          </button>
        </div>
      </div>

      <div class="header-right-meta">
        <!-- 实时直播模式工具条 -->
        <template v-if="isLiveMode">
          <span class="file-tag live-tag mono-num" :title="liveMeta.title || liveMeta.anchor_name">
            {{ liveMeta.anchor_name || '-' }} • {{ liveMeta.web_rid || '-' }}
          </span>
          <button class="btn-mini-player" title="重新拉取最新直播流" @click="reloadLiveStream">
            刷新流
          </button>
          <button class="btn-mini-player btn-stop-live" title="关闭实时画面预览" @click="emit('switch-mode', 'vod')">
            关闭
          </button>
        </template>

        <!-- 录像回放模式标签 -->
        <template v-else>
          <span class="file-tag mono-num" :title="currentVideo ? currentVideo.filename : ''">
            {{ currentVideo ? currentVideo.filename : 'NO SIGNAL / STANDBY' }}
          </span>
          <span v-if="currentVideo" class="quality-badge">REC • 1080P</span>
        </template>
      </div>
    </div>

    <!-- 专业导播级视频监视窗口容器 -->
    <div class="video-box" :class="{ 'has-video': isLiveMode || !!currentVideo, 'is-live-box': isLiveMode }">
      <!-- 四角取景框装饰准星 -->
      <span class="corner-mark tl"></span>
      <span class="corner-mark tr"></span>
      <span class="corner-mark bl"></span>
      <span class="corner-mark br"></span>

      <!-- 实时直播状态悬浮角标 -->
      <div v-if="isLiveMode && !videoError" class="live-overlay-badge">
        <span class="live-rec-pulse"></span>
        <span>LIVE 实时画面</span>
        <span class="overlay-sep">|</span>
        <span class="overlay-anchor">{{ liveMeta.anchor_name || '-' }}</span>
      </div>

      <!-- 视频缓冲加载提示层 -->
      <div v-if="isLiveMode && liveBuffering && !videoError" class="live-loading-mask">
        <div class="loading-spinner"></div>
        <span>正在接入抖音原画直播流...</span>
      </div>

      <!-- 模式 1：实时直播流播放 -->
      <video
        v-if="isLiveMode && liveProxyUrl && !videoError"
        :key="'live_' + streamNonce"
        ref="videoRef"
        controls
        autoplay
        muted
        playsinline
        :src="liveProxyUrl"
        @playing="onLivePlaying"
        @canplay="onCanPlay"
        @waiting="liveBuffering = true"
        @error="onVideoError"
      >
        您的浏览器不支持视频播放。
      </video>

      <!-- 模式 2：本地录像回放 -->
      <video
        v-else-if="!isLiveMode && currentVideo && currentVideo.url && !videoError"
        ref="videoRef"
        controls
        autoplay
        muted
        preload="metadata"
        :src="currentVideo.url"
        @loadedmetadata="onMetaLoaded"
        @canplay="onCanPlay"
        @error="onVideoError"
      >
        您的浏览器不支持视频播放。
      </video>

      <!-- 无素材或流解码异常时的导播雷达占位台 -->
      <div v-else class="video-placeholder">
        <div class="radar-scan-circle">
          <div class="radar-scanner"></div>
          <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <polygon points="23 7 16 12 23 17 23 7"></polygon>
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
          </svg>
        </div>
        <p class="placeholder-title">
          {{ videoError ? (isLiveMode ? '实时直播流连接波动或编码不兼容' : '素材解码异常或文件尚在写入') : '导播监视通道已就绪' }}
        </p>
        <span class="placeholder-sub">
          {{
            videoError
              ? (isLiveMode ? '请点击右上角【刷新流】重试，或确认主播仍在开播状态' : '当前录像文件可能正在合成或分段写入中，请稍候或切换其他素材预览')
              : '在左侧解析直播间即可实时观看直播画面，或点选本地录像 / 切片卡片跳帧预监'
          }}
        </span>
        <button v-if="videoError && isLiveMode" class="btn btn-sm btn-accent" @click="reloadLiveStream">
          🔄 重新连接直播流
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  currentVideo: {
    type: Object,
    default: null
  },
  liveMeta: {
    type: Object,
    default: null
  },
  monitorMode: {
    type: String,
    default: 'vod' // 'live' | 'vod'
  }
})

const emit = defineEmits(['switch-mode'])

const videoRef = ref(null)
const videoError = ref(false)
const liveBuffering = ref(false)
const pendingSeekTime = ref(null)
const streamNonce = ref(1)

// 是否处于实时直播播放模式
const isLiveMode = computed(() => {
  return props.monitorMode === 'live' && props.liveMeta && props.liveMeta.is_living
})

// 构造后端零转码直播流代理 URL
const liveProxyUrl = computed(() => {
  if (!isLiveMode.value) return ''
  const pullUrl = props.liveMeta.best_flv || props.liveMeta.best_hls || ''
  if (pullUrl) {
    return `/api/live/proxy?stream_url=${encodeURIComponent(pullUrl)}&_t=${streamNonce.value}`
  }
  const target = props.liveMeta.web_rid || ''
  return target ? `/api/live/proxy?target=${encodeURIComponent(target)}&_t=${streamNonce.value}` : ''
})

watch(() => [props.currentVideo, props.liveMeta, props.monitorMode], () => {
  videoError.value = false
  if (isLiveMode.value) {
    liveBuffering.value = true
  } else {
    liveBuffering.value = false
  }
})

const reloadLiveStream = () => {
  videoError.value = false
  liveBuffering.value = true
  streamNonce.value += 1
}

const tryExecutePendingSeek = () => {
  if (isLiveMode.value) return
  if (pendingSeekTime.value !== null && videoRef.value) {
    const targetTime = pendingSeekTime.value
    try {
      videoRef.value.currentTime = targetTime
      videoRef.value.play().catch(() => {})
      pendingSeekTime.value = null
    } catch (e) {
      console.warn('跳转定位暂不可用，稍后重试:', e)
    }
  }
}

const onMetaLoaded = () => {
  videoError.value = false
  tryExecutePendingSeek()
}

const onCanPlay = () => {
  videoError.value = false
  liveBuffering.value = false
  tryExecutePendingSeek()
}

const onLivePlaying = () => {
  videoError.value = false
  liveBuffering.value = false
}

const onVideoError = () => {
  videoError.value = true
  liveBuffering.value = false
  pendingSeekTime.value = null
}

const seekAndPlay = (timeSec) => {
  pendingSeekTime.value = timeSec
  if (!isLiveMode.value && videoRef.value && videoRef.value.readyState >= 1) {
    tryExecutePendingSeek()
  }
}

defineExpose({
  seekAndPlay,
  reloadLiveStream
})
</script>

<style scoped>
.player-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}

.player-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 双模切换胶囊 */
.mode-switch-group {
  display: inline-flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
}

.mode-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 4px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: var(--transition);
}

.mode-btn:hover {
  color: #FFFFFF;
}

.mode-btn.active {
  background: rgba(99, 102, 241, 0.28);
  color: #C7D2FE;
}

.mode-btn.live-active {
  background: rgba(239, 68, 68, 0.24);
  color: #FCA5A5;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #EF4444;
  box-shadow: 0 0 8px #EF4444;
}

.header-right-meta {
  display: flex;
  align-items: center;
  gap: 7px;
}

.file-tag {
  font-size: 0.72rem;
  color: #C7D2FE;
  background: rgba(99, 102, 241, 0.14);
  border: 1px solid rgba(99, 102, 241, 0.28);
  padding: 3px 9px;
  border-radius: 4px;
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-tag.live-tag {
  color: #FECACA;
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.35);
}

.btn-mini-player {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border-subtle);
  color: #E2E8F0;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: var(--transition);
}

.btn-mini-player:hover {
  background: rgba(6, 182, 212, 0.2);
  border-color: rgba(6, 182, 212, 0.45);
  color: #FFFFFF;
}

.btn-stop-live:hover {
  background: rgba(239, 68, 68, 0.24);
  border-color: rgba(239, 68, 68, 0.45);
}

.quality-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem;
  color: #34D399;
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.32);
  padding: 3px 7px;
  border-radius: 4px;
  font-weight: 700;
}

/* 导播主监视屏 */
.video-box {
  background:
    radial-gradient(circle at center, rgba(17, 24, 39, 0.9) 0%, #04060A 100%);
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.9), 0 10px 28px rgba(0, 0, 0, 0.5);
  height: clamp(300px, 41vh, 430px);
  min-height: 280px;
  position: relative;
}

.video-box.is-live-box {
  border-color: rgba(239, 68, 68, 0.35);
}

/* 实时直播角标 */
.live-overlay-badge {
  position: absolute;
  top: 14px;
  left: 16px;
  z-index: 6;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(9, 12, 21, 0.78);
  border: 1px solid rgba(239, 68, 68, 0.48);
  backdrop-filter: blur(8px);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  color: #FFFFFF;
  pointer-events: none;
}

.live-rec-pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #EF4444;
  box-shadow: 0 0 10px #EF4444;
  animation: liveBlink 1.1s infinite;
}

@keyframes liveBlink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.8); }
}

.overlay-sep {
  opacity: 0.35;
}

.overlay-anchor {
  color: #FDE68A;
}

/* 直播流加载遮罩 */
.live-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 4;
  background: rgba(4, 6, 11, 0.68);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 0.78rem;
  color: #E2E8F0;
  pointer-events: none;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2.5px solid rgba(255, 255, 255, 0.14);
  border-top-color: #38BDF8;
  animation: radarRotate 0.9s linear infinite;
}

/* 导播取景框四角标线 */
.corner-mark {
  position: absolute;
  width: 12px;
  height: 12px;
  border-color: rgba(255, 255, 255, 0.22);
  border-style: solid;
  pointer-events: none;
  z-index: 5;
}
.corner-mark.tl { top: 10px; left: 10px; border-width: 1.5px 0 0 1.5px; }
.corner-mark.tr { top: 10px; right: 10px; border-width: 1.5px 1.5px 0 0; }
.corner-mark.bl { bottom: 10px; left: 10px; border-width: 0 0 1.5px 1.5px; }
.corner-mark.br { bottom: 10px; right: 10px; border-width: 0 1.5px 1.5px 0; }

.video-box video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
  display: block;
}

/* 占位符雷达动效 */
.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  padding: 20px;
}

.radar-scan-circle {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  border: 1px dashed rgba(99, 102, 241, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, transparent 70%);
}

.radar-scan-circle svg {
  color: #818CF8;
}

.radar-scanner {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border-top: 2px solid var(--accent-light);
  animation: radarRotate 2.4s linear infinite;
}

@keyframes radarRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.placeholder-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-sub);
}

.placeholder-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  max-width: 360px;
  text-align: center;
  line-height: 1.5;
}
</style>
