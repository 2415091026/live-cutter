<template>
  <div class="glass-card board-card">
    <!-- 头部导航与操作栏 -->
    <div class="card-title board-header">
      <div class="header-tabs">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'candidates' }"
          @click="activeTab = 'candidates'"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span>切片池 ({{ allCandidates.length }})</span>
        </button>

        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'stream' }"
          @click="activeTab = 'stream'"
        >
          <span class="stream-dot" :class="{ pulsing: analyzing }"></span>
          <span>AI 推理流</span>
          <span class="tokens-badge" v-if="streamTokensCount > 0">{{ streamTokensCount }} chars</span>
        </button>
      </div>

      <button 
        class="btn btn-sm btn-ai-run" 
        :disabled="analyzing" 
        @click="triggerAnalyze"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        <span>{{ analyzing ? '推理中...' : '一键 AI 识别' }}</span>
      </button>
    </div>

    <!-- 主展示区 1：AI 流式推理与格式化输出监控台 (Streaming & Formatted View) -->
    <div v-show="activeTab === 'stream'" class="stream-console-container">
      <!-- 阶段步骤状态指示条 -->
      <div class="stream-status-bar">
        <span class="step-badge">
          <span class="pulse-dot" :class="analyzing ? 'online' : ''"></span>
          {{ currentStepText }}
        </span>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button v-if="allCandidates.length > 0" class="btn-view-cards" @click="activeTab = 'candidates'">
            查看最终卡片 ({{ allCandidates.length }})
          </button>
          <button class="btn-clear-log" @click="clearLog" title="清空日志">清空</button>
        </div>
      </div>

      <!-- HumanMessage 语音台词上下文折叠查看器 -->
      <div class="prompt-box human-box" v-if="humanMessage">
        <div class="prompt-box-header" @click="showHumanMsg = !showHumanMsg">
          <div class="box-tag human-tag">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
            🎙️ 语音转写台词上下文与爆发点
          </div>
          <span class="arrow-toggle">{{ showHumanMsg ? '▲ 收起' : '▼ 查看注入台词' }}</span>
        </div>
        <div v-show="showHumanMsg" class="prompt-content">
          <pre>{{ humanMessage }}</pre>
        </div>
      </div>

      <!-- 🌟 核心看点：大模型结构化格式化输出卡片 (Formatted Structure View) -->
      <div v-if="lastResult" class="formatted-output-card">
        <div class="formatted-header">
          <span class="formatted-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            ✨ 大模型格式化解析输出 (Pretty Formatted JSON)
          </span>
          <span class="format-badge">JSON 校验通过</span>
        </div>

        <div class="formatted-grid">
          <div class="format-item">
            <span class="item-label">核心看点主题:</span>
            <span class="item-value theme-val">{{ lastResult.highlight_theme || '-' }}</span>
          </div>

          <div class="format-item">
            <span class="item-label">精确剪辑区间:</span>
            <span class="item-value time-val">
              {{ lastResult.recommended_cut_start }}s ➔ {{ lastResult.recommended_cut_end }}s (时长: {{ lastResult.duration }}s)
            </span>
          </div>

          <div class="format-item full-width">
            <span class="item-label">提炼核心金句:</span>
            <span class="item-value quote-val">「{{ lastResult.core_quote || '-' }}」</span>
          </div>

          <!-- 触发归因明确高亮 -->
          <div class="format-item full-width trigger-item">
            <span class="item-label">⚡ 触发原因归因:</span>
            <span class="item-value trigger-val">{{ lastResult.trigger_reason || lastResult.reason }}</span>
          </div>

          <!-- 抖音爆款标题清单 -->
          <div class="format-item full-width" v-if="lastResult.generated_titles && lastResult.generated_titles.length">
            <span class="item-label">🔥 抖音爆款标题 (3条推荐):</span>
            <div class="titles-column">
              <div v-for="(t, idx) in lastResult.generated_titles" :key="idx" class="formatted-title-row">
                <span class="title-idx">#{{ idx + 1 }}</span>
                <span class="title-txt">{{ t }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 终端代码流：支持原始流式打字与 Pretty-printed JSON 格式高亮 -->
      <div class="terminal-card">
        <div class="terminal-header">
          <div class="terminal-dots">
            <span class="dot red"></span>
            <span class="dot yellow"></span>
            <span class="dot green"></span>
          </div>
          <span class="terminal-title">LangChain LCEL Output Stream (qwen3.8-flash)</span>
          <div class="terminal-view-switch">
            <button 
              class="switch-btn" 
              :class="{ active: terminalMode === 'pretty' }" 
              @click="terminalMode = 'pretty'"
            >
              格式化代码
            </button>
            <button 
              class="switch-btn" 
              :class="{ active: terminalMode === 'raw' }" 
              @click="terminalMode = 'raw'"
            >
              实时打字流
            </button>
          </div>
        </div>

        <div class="terminal-body" ref="terminalBodyRef">
          <div v-if="!streamOutput && !analyzing" class="terminal-empty">
            点击右上角【一键 AI 识别】，此处将毫秒级流式展现 LangChain 认知推理全过程与格式化 JSON 结果...
          </div>
          <!-- 格式化代码视图 -->
          <pre v-else-if="terminalMode === 'pretty' && formattedJson" class="terminal-text pretty-code"><code v-html="highlightedJson"></code></pre>
          <!-- 原始流式打字机视图 -->
          <pre v-else class="terminal-text">{{ streamOutput }}<span v-if="analyzing" class="cursor-blink">▋</span></pre>
        </div>
      </div>
    </div>

    <!-- 主展示区 2：高能切片卡片决策池 (Candidates List) -->
    <div v-show="activeTab === 'candidates'" class="candidates-scroll">
      <div v-if="allCandidates.length === 0" class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="m9 12 2 2 4-4"></path>
        </svg>
        <p>暂无高能切片</p>
        <span>选择录像点击【一键 AI 识别】或切换至【AI 推理流】查看实时分析！</span>
      </div>

      <div 
        v-for="(cand, idx) in allCandidates" 
        :key="cand.id || cand.segment_id || idx" 
        class="cand-card"
        :class="{ active: isCardActive(cand) }"
        @click="previewClip(cand)"
      >
        <!-- 顶部指标栏 -->
        <div class="cand-top">
          <span class="score-pill">
            ★ {{ cand.trigger_tag ? cand.trigger_tag : (cand.theme || '高能') }} 
            <span v-if="cand.heat_score">({{ cand.heat_score }}分)</span>
          </span>
          <span class="time-range">
            {{ cand.precise_start !== undefined ? cand.precise_start : (cand.start_time || 0) }}s ➔ {{ cand.precise_end !== undefined ? cand.precise_end : (cand.end_time || 10) }}s ({{ cand.duration }}s)
          </span>
        </div>

        <!-- 来源素材文件名指示条 (关联左侧素材库) -->
        <div class="cand-source-tag" :title="cand.source_video || cand.source_filename || '当前录像素材'">
          <span class="source-icon">📼</span>
          <span class="source-label">素材:</span>
          <span class="source-name">{{ cand.source_video || cand.source_filename || (currentVideo ? currentVideo.filename : '当前录像素材') }}</span>
          <span class="source-jump-hint">点击联动 ➔</span>
        </div>

        <!-- 🌟 核心看点：触发归因详细提示 -->
        <div class="trigger-reason-box" v-if="cand.trigger_reason || cand.reason">
          <span class="lightning-icon">⚡</span>
          <span class="reason-text"><strong>触发原因:</strong> {{ cand.trigger_reason || cand.reason }}</span>
        </div>

        <!-- 👁️ 多模态画面视觉感知描述 (当启用 qwen3.8-omni-flash 时展示) -->
        <div class="vision-action-box" v-if="cand.visual_action_summary">
          <span class="vision-icon">👁️</span>
          <span class="vision-text"><strong>多模态画面感知:</strong> {{ cand.visual_action_summary }}</span>
        </div>

        <!-- 提炼金句 -->
        <div class="cand-quote">「{{ cand.core_quote || '-' }}」</div>

        <!-- 抖音爆款标题池 -->
        <div class="titles-list" v-if="cand.titles && cand.titles.length">
          <span v-for="title in cand.titles" :key="title" class="title-item">
            🔥 {{ title }}
          </span>
        </div>
        <div class="titles-list" v-else-if="cand.title">
          <span class="title-item">🔥 {{ cand.title }}</span>
        </div>

        <!-- 底部一键交付按钮 -->
        <div class="cand-actions" @click.stop>
          <button 
            class="btn btn-sm btn-export-mp4" 
            :disabled="exporting"
            @click="exportMedia(cand, 'mp4')"
          >
            🎬 导出 9:16 成片
          </button>
          <button 
            class="btn btn-sm btn-export-jy" 
            :disabled="exporting"
            @click="exportMedia(cand, 'jy')"
          >
            ✂️ 导入剪映草稿
          </button>
        </div>
      </div>
    </div>

    <!-- 直发级 9:16 成品交付与一键发布弹窗 -->
    <div v-if="showPublishModal" class="publish-modal-backdrop" @click="showPublishModal = false">
      <div class="publish-modal-card glass-card" @click.stop>
        <div class="modal-header">
          <div class="modal-title-box">
            <span class="badge-direct">直发级成品已就绪</span>
            <h3 class="modal-title">9:16 免剪短视频直发交付台</h3>
          </div>
          <button class="btn-close" @click="showPublishModal = false">✕</button>
        </div>

        <div class="modal-body-layout">
          <!-- 左侧：竖屏成片播放器 -->
          <div class="preview-player-col">
            <div class="phone-frame">
              <video 
                :src="publishData.mp4_url" 
                controls 
                autoplay 
                loop 
                class="direct-video"
              ></video>
            </div>
            <div class="format-tag mono-num">1080x1920 • 9:16 动态虚化背景 • 顶部大标题 • 底部黄字描边</div>
          </div>

          <!-- 右侧：发布文案与一键分发工具箱 -->
          <div class="publish-meta-col">
            <div class="meta-section">
              <div class="section-label">
                <span>🔥 爆款发布文案与 SEO 标签</span>
                <button class="btn-copy-small" @click="copyPublishText">
                  {{ copied ? '已复制到剪贴板！' : '📋 一键复制' }}
                </button>
              </div>
              <textarea 
                class="publish-textarea mono-num" 
                readonly 
                :value="publishData.publish_text"
                rows="6"
              ></textarea>
            </div>

            <div class="meta-section">
              <div class="section-label">
                <span>🏷️ 热门标签云</span>
              </div>
              <div class="tags-cloud">
                <span v-for="tag in publishData.tags" :key="tag" class="tag-pill">{{ tag }}</span>
              </div>
            </div>

            <div class="meta-section">
              <div class="section-label">
                <span>📁 物理文件路径</span>
              </div>
              <div class="path-display mono-num">{{ publishData.mp4_path }}</div>
            </div>

            <!-- 一键直传/下载操作组 -->
            <div class="direct-action-group">
              <a 
                :href="publishData.mp4_url" 
                :download="publishData.title + '.mp4'"
                class="btn btn-primary btn-direct-download"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                下载直发视频 (拖入抖音/快手)
              </a>
              <button class="btn btn-secondary" @click="copyPublishText">
                📋 复制文案与标签
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

const props = defineProps({
  candidates: {
    type: Array,
    default: () => []
  },
  currentVideo: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['start-analyze', 'seek-to', 'select-candidate', 'show-toast', 'update-candidates'])

// 当前选中的切片 ID
const selectedCandidateId = ref(null)

const isCardActive = (cand) => {
  const id = cand.id || cand.segment_id
  return selectedCandidateId.value !== null && selectedCandidateId.value === id
}

// 选项卡：candidates (切片池) | stream (流式推理控制台)
const activeTab = ref('candidates')
const analyzing = ref(false)
const exporting = ref(false)

// 终端查看模式：pretty (带缩进语法高亮代码) | raw (流式打字机)
const terminalMode = ref('pretty')

// 本地流式提炼切片列表与结构化结果
const localCandidates = ref([])
const lastResult = ref(null)

// 合并后的候选列表
const allCandidates = computed(() => {
  if (localCandidates.value.length > 0) {
    return localCandidates.value
  }
  return props.candidates || []
})

// 流式相关状态
const currentStepText = ref('就绪')
const humanMessage = ref('')
const streamOutput = ref('')
const streamTokensCount = ref(0)
const showHumanMsg = ref(false)
const terminalBodyRef = ref(null)

// 格式化后的 JSON 字符串
const formattedJson = computed(() => {
  if (lastResult.value) {
    try {
      return JSON.stringify(lastResult.value, null, 2)
    } catch (e) {
      return streamOutput.value
    }
  }
  // 若流式文本已能解析为 JSON
  try {
    const parsed = JSON.parse(streamOutput.value.trim())
    return JSON.stringify(parsed, null, 2)
  } catch (e) {
    return ''
  }
})

// 对 JSON 进行漂亮的色彩语法高亮
const highlightedJson = computed(() => {
  const jsonStr = formattedJson.value || streamOutput.value
  if (!jsonStr) return ''

  // 简单的 JSON 语法着色：键名黄色，字符串值绿色，数字青色
  return jsonStr
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'json-number'
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'json-key'
        } else {
          cls = 'json-string'
        }
      } else if (/true|false/.test(match)) {
        cls = 'json-boolean'
      } else if (/null/.test(match)) {
        cls = 'json-null'
      }
      return `<span class="${cls}">${match}</span>`
    })
})

// 滚动打字机到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (terminalBodyRef.value) {
      terminalBodyRef.value.scrollTop = terminalBodyRef.value.scrollHeight
    }
  })
}

// 清空日志
const clearLog = () => {
  humanMessage.value = ''
  streamOutput.value = ''
  streamTokensCount.value = 0
  lastResult.value = null
  currentStepText.value = '就绪'
}

// 触发基于 SSE 流式接口的 AI 识别
const triggerAnalyze = async () => {
  if (!props.currentVideo) {
    emit('show-toast', '请先在左侧选择一个待分析的录像素材！')
    return
  }

  // 自动切换到流式推理视图
  activeTab.value = 'stream'
  terminalMode.value = 'raw' // 流式过程中使用打字流
  analyzing.value = true
  localCandidates.value = []
  clearLog()
  currentStepText.value = '⚡ 正在建立 LangChain LCEL 流式推理连接...'

  try {
    const response = await fetch('/api/analyze/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: props.currentVideo.file_path })
    })

    if (!response.ok) throw new Error('流式分析服务响应失败')

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.replace('data: ', '').trim()
        if (!jsonStr) continue

        try {
          const payload = JSON.parse(jsonStr)

          if (payload.type === 'step') {
            currentStepText.value = payload.content
          } else if (payload.type === 'human_message') {
            humanMessage.value = payload.content
          } else if (payload.type === 'token') {
            streamOutput.value += payload.content
            streamTokensCount.value += payload.content.length
            scrollToBottom()
          } else if (payload.type === 'candidate_ready') {
            const currentRec = props.currentVideo
            const enriched = {
              ...payload.candidate,
              source_video: payload.candidate.source_video || (currentRec ? currentRec.filename : ''),
              source_filename: payload.candidate.source_filename || (currentRec ? currentRec.filename : ''),
              source_path: payload.candidate.source_path || (currentRec ? currentRec.file_path : ''),
              source_url: payload.candidate.source_url || (currentRec ? currentRec.url : '')
            }
            localCandidates.value.push(enriched)
            lastResult.value = {
              highlight_theme: enriched.theme,
              core_quote: enriched.core_quote,
              recommended_cut_start: enriched.precise_start,
              recommended_cut_end: enriched.precise_end,
              duration: enriched.duration,
              trigger_reason: enriched.trigger_reason,
              generated_titles: enriched.titles
            }
            emit('show-toast', `⚡ 成功提炼切片: ${enriched.theme}`)
          } else if (payload.type === 'finish') {
            currentStepText.value = '✅ 全流程流式分析完毕！'
            terminalMode.value = 'pretty' // 分析完成后自动切为格式化代码与结构卡片
            if (payload.candidates && payload.candidates.length > 0) {
              const currentRec = props.currentVideo
              localCandidates.value = payload.candidates.map(c => ({
                ...c,
                source_video: c.source_video || (currentRec ? currentRec.filename : ''),
                source_filename: c.source_filename || (currentRec ? currentRec.filename : ''),
                source_path: c.source_path || (currentRec ? currentRec.file_path : ''),
                source_url: c.source_url || (currentRec ? currentRec.url : '')
              }))
              const first = localCandidates.value[0]
              lastResult.value = {
                highlight_theme: first.theme,
                core_quote: first.core_quote,
                recommended_cut_start: first.precise_start,
                recommended_cut_end: first.precise_end,
                duration: first.duration,
                trigger_reason: first.trigger_reason,
                generated_titles: first.titles
              }
            }
            emit('update-candidates', {
              ...payload,
              candidates: localCandidates.value
            })
            emit('show-toast', `AI 识别完毕！成功生成 ${localCandidates.value.length} 个高能切片！`)
          } else if (payload.type === 'error') {
            emit('show-toast', `分析异常: ${payload.content}`)
          }
        } catch (e) {
          console.error('解析 SSE 数据包失败:', e, jsonStr)
        }
      }
    }
  } catch (err) {
    emit('show-toast', `流式分析失败: ${err.message}`)
    currentStepText.value = `❌ 分析异常: ${err.message}`
  } finally {
    analyzing.value = false
  }
}

// 点播切片试看与联动定位素材库
const previewClip = (cand) => {
  if (!cand) return
  selectedCandidateId.value = cand.id || cand.segment_id
  
  // 确保来源素材属性一定存在
  if (!cand.source_video && props.currentVideo) {
    cand.source_video = props.currentVideo.filename
    cand.source_filename = props.currentVideo.filename
    cand.source_path = props.currentVideo.file_path
    cand.source_url = props.currentVideo.url
  }

  const startSec = cand.precise_start !== undefined ? cand.precise_start : (cand.start_time || 0)
  
  // 联动发出切片选中事件，通知 App.vue 切换素材库中对应的视频并调用播放器定位
  emit('select-candidate', cand)
  emit('seek-to', startSec)
}

// 直发级交付弹窗状态
const showPublishModal = ref(false)
const copied = ref(false)
const publishData = ref({
  mp4_url: '',
  mp4_path: '',
  title: '',
  publish_text: '',
  tags: []
})

const copyPublishText = async () => {
  if (!publishData.value.publish_text) return
  try {
    await navigator.clipboard.writeText(publishData.value.publish_text)
    copied.value = true
    emit('show-toast', '📋 文案与标签已复制到剪贴板！可直接粘贴至发布后台')
    setTimeout(() => { copied.value = false }, 2500)
  } catch (e) {
    emit('show-toast', '复制失败，请手动选取复制')
  }
}

// 执行导出操作
const exportMedia = async (cand, mode) => {
  exporting.value = true
  emit('show-toast', mode === 'mp4' ? '⚡ 正在启用硬件加速压制 9:16 动态虚化背景与黄色花字...' : '正在写入剪映原生工程 draft_content.json...')

  const videoPath = props.currentVideo ? props.currentVideo.file_path : ''
  const startT = cand.precise_start !== undefined ? cand.precise_start : (cand.start_time || 0)
  const endT = cand.precise_end !== undefined ? cand.precise_end : (cand.end_time || 10)
  const titleText = (cand.titles && cand.titles[0]) || cand.title || cand.theme || '精彩切片'

  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_path: videoPath,
        start_time: startT,
        end_time: endT,
        title: titleText,
        subtitles: cand.subtitles || []
      })
    })

    if (!res.ok) throw new Error('导出服务返回错误')
    const data = await res.json()

    if (mode === 'mp4') {
      publishData.value = {
        mp4_url: data.mp4_url,
        mp4_path: data.mp4_path,
        title: data.title || titleText,
        publish_text: data.publish_text || `${titleText}\n#直播名场面 #高能时刻`,
        tags: data.tags || ['#直播名场面', '#高能时刻']
      }
      showPublishModal.value = true
      emit('show-toast', `🎉 直发级 9:16 成品短视频已渲染就绪！`)
    } else {
      emit('show-toast', `✅ 剪映草稿工程已就绪: ${data.draft_dir}`)
    }
  } catch (err) {
    emit('show-toast', `导出失败: ${err.message}`)
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.board-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.header-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(0, 0, 0, 0.4);
  padding: 3px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.tab-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 0.76rem;
  font-weight: 700;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: var(--transition);
}
.tab-btn:hover {
  color: #FFF;
}
.tab-btn.active {
  background: rgba(99, 102, 241, 0.25);
  color: #A5B4FC;
}

.stream-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}
.stream-dot.pulsing {
  background: #10B981;
  box-shadow: 0 0 8px #10B981;
  animation: pulse 1.2s infinite;
}

.tokens-badge {
  font-size: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent);
  background: rgba(56, 189, 248, 0.15);
  padding: 1px 4px;
  border-radius: 4px;
}

.btn-ai-run {
  background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%);
  color: #FFF;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
  padding: 6px 14px;
  box-shadow: 0 4px 14px rgba(168, 85, 247, 0.35);
}
.btn-ai-run:hover {
  box-shadow: 0 6px 18px rgba(168, 85, 247, 0.5);
  transform: translateY(-1px);
}

/* 流式推理与格式化控制台容器 */
.stream-console-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.stream-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.7);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.step-badge {
  font-size: 0.78rem;
  font-weight: 600;
  color: #38BDF8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-view-cards {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #34D399;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.btn-view-cards:hover {
  background: rgba(16, 185, 129, 0.25);
}

.btn-clear-log {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-muted);
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
}
.btn-clear-log:hover {
  color: #FFF;
  background: rgba(255, 255, 255, 0.08);
}

/* Prompt折叠卡片 */
.prompt-box {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.prompt-box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.02);
  transition: var(--transition);
}
.prompt-box-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.box-tag {
  font-size: 0.74rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
}
.human-tag {
  color: #38BDF8;
}

.arrow-toggle {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.prompt-content {
  padding: 10px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(0, 0, 0, 0.5);
}
.prompt-content pre {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #E2E8F0;
  white-space: pre-wrap;
  line-height: 1.45;
  max-height: 120px;
  overflow-y: auto;
}

/* 🌟 格式化结构解析卡片 */
.formatted-output-card {
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: var(--radius-sm);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.formatted-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 6px;
}

.formatted-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: #38BDF8;
  display: flex;
  align-items: center;
  gap: 6px;
}

.format-badge {
  font-size: 0.68rem;
  color: #34D399;
  background: rgba(16, 185, 129, 0.15);
  padding: 2px 6px;
  border-radius: 4px;
}

.formatted-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.format-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.format-item.full-width {
  grid-column: 1 / -1;
}

.item-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-muted);
}

.item-value {
  font-size: 0.82rem;
  color: #FFF;
  line-height: 1.4;
}
.theme-val {
  color: #FBBF24;
  font-weight: 700;
}
.time-val {
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent);
}
.quote-val {
  font-weight: 700;
  color: #F1F5F9;
}

.trigger-item {
  background: rgba(245, 158, 11, 0.08);
  border-left: 3px solid var(--gold);
  padding: 6px 8px;
  border-radius: 2px 4px 4px 2px;
}
.trigger-item .item-label {
  color: var(--gold);
}
.trigger-val {
  color: #FDE68A;
  font-size: 0.78rem;
}

.titles-column {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 3px;
}
.formatted-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.76rem;
}
.title-idx {
  color: var(--accent);
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}
.title-txt {
  color: #E2E8F0;
}

/* 终端输出卡片 */
.terminal-card {
  background: #090D16;
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.terminal-dots {
  display: flex;
  gap: 5px;
}
.terminal-dots .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
.terminal-dots .red { background: #EF4444; }
.terminal-dots .yellow { background: #F59E0B; }
.terminal-dots .green { background: #10B981; }

.terminal-title {
  font-size: 0.72rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: #A5B4FC;
}

.terminal-view-switch {
  display: flex;
  gap: 4px;
}
.switch-btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-muted);
  font-size: 0.68rem;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: var(--transition);
}
.switch-btn.active {
  background: rgba(99, 102, 241, 0.3);
  border-color: #6366F1;
  color: #FFF;
}

.terminal-body {
  padding: 12px;
  min-height: 160px;
  max-height: 240px;
  overflow-y: auto;
  background: #06090F;
}

.terminal-empty {
  color: var(--text-muted);
  font-size: 0.78rem;
  text-align: center;
  padding: 50px 20px;
  line-height: 1.5;
}

.terminal-text {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.76rem;
  color: #34D399;
  white-space: pre-wrap;
  line-height: 1.45;
}

/* JSON 语法着色样式 */
:deep(.json-key) {
  color: #FBBF24; /* 黄色属性键名 */
  font-weight: 600;
}
:deep(.json-string) {
  color: #34D399; /* 绿色文本值 */
}
:deep(.json-number) {
  color: #38BDF8; /* 青色数值 */
}
:deep(.json-boolean) {
  color: #A78BFA; /* 紫色布尔 */
}
:deep(.json-null) {
  color: #94A3B8;
}

.cursor-blink {
  color: #10B981;
  animation: blink 0.8s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 切片列表展示 */
.candidates-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 50px 20px;
  color: var(--text-muted);
}
.empty-state svg {
  margin-bottom: 12px;
  opacity: 0.3;
}
.empty-state p {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: 4px;
}
.empty-state span {
  font-size: 0.75rem;
}

.cand-card {
  background: rgba(5, 7, 11, 0.56);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 15px;
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  flex-direction: column;
  gap: 9px;
  position: relative;
}

.cand-card:hover {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(20, 27, 45, 0.72);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}

.cand-card.active {
  border-color: var(--primary);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.18) 0%, rgba(15, 23, 42, 0.85) 100%);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

/* 来源素材条 */
.cand-source-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(56, 189, 248, 0.2);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  margin-top: 1px;
}

.source-icon {
  font-size: 0.75rem;
}

.source-label {
  color: var(--text-muted);
  font-weight: 600;
}

.source-name {
  color: #38BDF8;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.source-jump-hint {
  font-size: 0.65rem;
  color: #A5B4FC;
  opacity: 0.8;
  white-space: nowrap;
}

.cand-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-pill {
  font-size: 0.75rem;
  font-weight: 800;
  color: var(--gold);
  background: rgba(245, 158, 11, 0.15);
  padding: 2px 8px;
  border-radius: 12px;
}

.time-range {
  font-size: 0.78rem;
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent);
}

.trigger-reason-box {
  background: rgba(245, 158, 11, 0.08);
  border-left: 3px solid var(--gold);
  padding: 6px 10px;
  border-radius: 2px 6px 6px 2px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 0.78rem;
}

.lightning-icon {
  color: var(--gold);
  font-weight: 800;
}

.reason-text {
  color: #FDE68A;
  line-height: 1.35;
}

.vision-action-box {
  background: rgba(6, 182, 212, 0.08);
  border-left: 3px solid var(--accent);
  padding: 6px 10px;
  border-radius: 2px 6px 6px 2px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 0.76rem;
}

.vision-icon {
  flex-shrink: 0;
}

.vision-text {
  color: #A5F3FC;
  line-height: 1.35;
}

.cand-quote {
  font-size: 0.88rem;
  font-weight: 700;
  color: #FFF;
  line-height: 1.4;
}

.titles-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title-item {
  font-size: 0.76rem;
  color: var(--text-sub);
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 8px;
  border-radius: 4px;
}

.cand-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 4px;
}

.btn-export-mp4 {
  background: rgba(16, 185, 129, 0.15);
  color: #34D399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}
.btn-export-mp4:hover {
  background: rgba(16, 185, 129, 0.25);
}

.btn-export-jy {
  background: rgba(245, 158, 11, 0.15);
  color: #FBBF24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.btn-export-jy:hover {
  background: rgba(245, 158, 11, 0.25);
}

/* 直发级成品交付弹窗 */
.publish-modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(12px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.publish-modal-card {
  width: 900px;
  max-width: 95vw;
  max-height: 90vh;
  background: #0E1320;
  border: 1px solid rgba(99, 102, 241, 0.4);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.8), 0 0 32px rgba(99, 102, 241, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 22px 26px;
  gap: 18px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 14px;
}

.modal-title-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge-direct {
  background: linear-gradient(135deg, #10B981, #06B6D4);
  color: #FFFFFF;
  font-size: 0.7rem;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 999px;
  letter-spacing: 0.5px;
}

.modal-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #F8FAFC;
}

.btn-close {
  background: rgba(255, 255, 255, 0.06);
  border: none;
  color: var(--text-muted);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition: var(--transition);
}
.btn-close:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #F87171;
}

.modal-body-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  min-height: 440px;
  align-items: stretch;
}

.preview-player-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.phone-frame {
  width: 240px;
  height: 426px;
  background: #000;
  border-radius: 16px;
  overflow: hidden;
  border: 2px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
  display: flex;
}

.direct-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.format-tag {
  font-size: 0.66rem;
  color: var(--accent-light);
  text-align: center;
  line-height: 1.4;
  padding: 0 8px;
}

.publish-meta-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
  justify-content: space-between;
}

.meta-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #E2E8F0;
}

.btn-copy-small {
  background: rgba(99, 102, 241, 0.18);
  border: 1px solid rgba(99, 102, 241, 0.4);
  color: #C7D2FE;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
}
.btn-copy-small:hover {
  background: rgba(99, 102, 241, 0.32);
}

.publish-textarea {
  width: 100%;
  background: rgba(5, 7, 11, 0.7);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  color: #F8FAFC;
  padding: 10px 12px;
  font-size: 0.84rem;
  line-height: 1.5;
  resize: none;
  outline: none;
}

.tags-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-pill {
  font-size: 0.72rem;
  font-weight: 600;
  color: #38BDF8;
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.25);
  padding: 2px 8px;
  border-radius: 999px;
}

.path-display {
  font-size: 0.72rem;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  border-radius: 4px;
  word-break: break-all;
}

.direct-action-group {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.btn-direct-download {
  flex: 1;
  text-decoration: none;
  font-weight: 700;
}
</style>
