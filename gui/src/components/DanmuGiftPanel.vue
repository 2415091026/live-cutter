<template>
  <div class="glass-card danmu-gift-card">
    <!-- 顶部导播状态与操作栏 -->
    <div class="panel-header">
      <div class="header-left-group">
        <div class="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <span>实时弹幕与礼物雷达</span>
        </div>

        <!-- 连接状态胶囊 -->
        <span class="conn-badge" :class="connStatusClass">
          <span class="conn-dot"></span>
          <span>{{ connStatusText }}</span>
        </span>

        <!-- 传输通道标识 -->
        <span v-if="stateInfo.is_running && stateInfo.transport_mode && stateInfo.transport_mode !== '-'" class="mode-badge mono-num">
          {{ stateInfo.transport_mode }} 通道
        </span>
      </div>

      <!-- 右侧快捷连接与工具组 -->
      <div class="header-controls">
        <div class="mini-room-input">
          <input
            v-model="roomInput"
            type="text"
            placeholder="房间号/直播链接"
            @keyup.enter="handleStartConnect"
          />
          <button
            v-if="!stateInfo.is_running || isDifferentRoom"
            class="btn-mini btn-connect"
            :disabled="operating"
            @click="handleStartConnect"
          >
            {{ operating ? '连接中...' : (stateInfo.is_running ? '切换房间' : '连接弹幕') }}
          </button>
          <button
            v-else
            class="btn-mini btn-disconnect"
            :disabled="operating"
            @click="handleStopConnect"
          >
            断开
          </button>
        </div>

        <button
          class="btn-tool"
          :class="{ active: autoScroll }"
          title="开启或锁定自动滚屏"
          @click="toggleAutoScroll"
        >
          {{ autoScroll ? '⬇ 自动滚屏' : '⏸ 已锁屏' }}
        </button>

        <button
          class="btn-tool"
          title="清空当前屏幕弹幕与礼物记录"
          @click="handleClearScreen"
        >
          清屏
        </button>
      </div>
    </div>

    <!-- 当前锁定直播间横幅（仅在运行或已解析到主播时展示） -->
    <div v-if="stateInfo.is_running || stateInfo.error_message" class="room-banner" :class="{ 'is-error': stateInfo.connection_state === 'error' }">
      <div class="banner-left">
        <span class="banner-label">当前房间:</span>
        <span class="banner-anchor">{{ stateInfo.anchor_name && stateInfo.anchor_name !== '-' ? stateInfo.anchor_name : '-' }}</span>
        <span v-if="stateInfo.room_title && stateInfo.room_title !== '-'" class="banner-title">{{ stateInfo.room_title }}</span>
      </div>
      <div class="banner-right mono-num">
        <span v-if="stateInfo.connection_state === 'error'" class="err-txt">{{ stateInfo.error_message }}</span>
        <span v-else>RID: {{ stateInfo.web_rid || '-' }}</span>
      </div>
    </div>

    <!-- 四维实时遥测指标条 (无数据时严格使用 "-" 占位) -->
    <div class="kpi-strip mono-num">
      <div class="kpi-item">
        <span class="kpi-label">在线观众 / 点赞</span>
        <span class="kpi-value">{{ onlineDisplay }}</span>
      </div>
      <div class="kpi-item">
        <span class="kpi-label">累计弹幕 / 速率</span>
        <span class="kpi-value accent">
          {{ hasActiveSession || metrics.total_chats > 0 ? `${metrics.total_chats} 条` : '-' }}
          <small v-if="hasActiveSession">({{ metrics.chats_per_10s }}/10s)</small>
        </span>
      </div>
      <div class="kpi-item">
        <span class="kpi-label">礼物打赏次数</span>
        <span class="kpi-value gold">
          {{ hasActiveSession || metrics.total_gifts > 0 ? `${metrics.total_gifts} 份` : '-' }}
        </span>
      </div>
      <div class="kpi-item highlight-kpi">
        <span class="kpi-label">礼物钻石热度</span>
        <span class="kpi-value diamond">
          {{ hasActiveSession || metrics.total_diamonds > 0 ? `💎 ${formatNumber(metrics.total_diamonds)}` : '-' }}
        </span>
      </div>
    </div>

    <!-- 双舱主监控区：左舱实时弹幕瀑布流 + 右舱实时礼物高光台 -->
    <div class="dual-cockpit">
      <!-- 左舱：实时弹幕瀑布流 -->
      <div class="cockpit-pane chat-pane">
        <div class="pane-toolbar">
          <div class="pane-title">
            <span class="pane-icon">💬</span>
            <span>实时弹幕流</span>
            <span class="pane-count mono-num">{{ filteredChats.length }}</span>
          </div>

          <div class="pane-filters">
            <button
              class="filter-chip"
              :class="{ active: onlyHotWords }"
              @click="onlyHotWords = !onlyHotWords"
            >
              🔥 仅看热词
            </button>
            <input
              v-model="keywordFilter"
              type="text"
              class="search-mini"
              placeholder="筛选弹幕/用户..."
            />
          </div>
        </div>

        <div
          ref="chatScrollRef"
          class="stream-list chat-list"
          @scroll="onChatManualScroll"
        >
          <div v-if="filteredChats.length === 0" class="pane-empty">
            <div class="empty-glyph">💬</div>
            <p>{{ stateInfo.is_running ? '弹幕通道监听中，等待观众发言...' : '尚未连接直播间弹幕流' }}</p>
            <span>{{ stateInfo.is_running ? '观众发送的实时弹幕与高频热词将毫秒级呈现于此' : '在左侧解析直播间或上方输入房间号点击【连接弹幕】' }}</span>
          </div>

          <div
            v-for="item in filteredChats"
            :key="item.msg_id"
            class="chat-row"
            :class="{ 'is-hot': item.is_hot }"
          >
            <span class="chat-time mono-num">{{ item.time_str || '-' }}</span>

            <img
              v-if="item.avatar && !brokenImages[item.msg_id]"
              :src="item.avatar"
              referrerpolicy="no-referrer"
              class="user-avatar"
              alt=""
              @error="markImageBroken(item.msg_id)"
            />

            <span class="chat-user">{{ item.nickname || '-' }}:</span>
            <span class="chat-text">{{ item.content || '-' }}</span>

            <span
              v-for="kw in (item.hit_keywords || [])"
              :key="kw"
              class="hot-kw-tag"
            >
              🔥 {{ kw }}
            </span>
          </div>
        </div>

        <!-- 新弹幕未读回底悬浮提示 -->
        <button
          v-if="!autoScroll && unreadChatCount > 0"
          class="unread-float-btn"
          @click="resumeAutoScroll"
        >
          ↓ 底部有 {{ unreadChatCount }} 条新弹幕
        </button>
      </div>

      <!-- 右舱：实时礼物打赏与连击舞台 -->
      <div class="cockpit-pane gift-pane">
        <div class="pane-toolbar">
          <div class="pane-title">
            <span class="pane-icon">🎁</span>
            <span>实时礼物榜</span>
            <span class="pane-count mono-num">{{ gifts.length }}</span>
          </div>

          <div class="pane-filters">
            <button
              v-if="!stateInfo.is_logged_in"
              class="filter-chip login-chip"
              :disabled="loginOpening"
              title="抖音游客态会限制礼物消息下发，点击打开浏览器扫码登录一次即可永久解锁完整实时礼物"
              @click="handleOpenDouyinLogin"
            >
              {{ loginOpening ? '等待扫码...' : '🔑 扫码解锁礼物' }}
            </button>
            <span v-else class="logged-in-tag" title="已加载抖音登录凭证，可接收完整礼物与连击">
              ✓ 已解锁礼物
            </span>

            <button
              class="filter-chip gold-chip"
              :class="{ active: onlyHighValueGifts }"
              @click="onlyHighValueGifts = !onlyHighValueGifts"
            >
              💎 大额高光
            </button>
          </div>
        </div>

        <!-- 顶部最新高光连击横幅 (仅当存在真实礼物记录时渲染) -->
        <div
          v-if="featuredGift"
          class="featured-gift-stage"
          :class="[`tier-${featuredGift.tier || 'normal'}`, { 'combo-flash': comboFlashId === featuredGift.combo_key }]"
        >
          <div class="stage-left">
            <div class="gift-icon-box">
              <img
                v-if="featuredGift.gift_icon && !brokenImages['feat_' + featuredGift.msg_id]"
                :src="featuredGift.gift_icon"
                referrerpolicy="no-referrer"
                class="gift-img"
                alt=""
                @error="markImageBroken('feat_' + featuredGift.msg_id)"
              />
              <span v-else class="gift-fallback-emoji">🎁</span>
            </div>
            <div class="stage-meta">
              <div class="stage-sender">{{ featuredGift.nickname || '-' }}</div>
              <div class="stage-action">
                送出 <strong>{{ featuredGift.gift_name || '-' }}</strong>
                <span v-if="featuredGift.total_diamonds > 0" class="stage-diamond mono-num">
                  💎{{ featuredGift.total_diamonds }}
                </span>
              </div>
            </div>
          </div>

          <div class="stage-combo mono-num">
            <span class="combo-x">x</span>
            <span class="combo-num">{{ featuredGift.count || 1 }}</span>
          </div>
        </div>

        <!-- 礼物打赏明细流列表 -->
        <div ref="giftScrollRef" class="stream-list gift-list">
          <div v-if="filteredGifts.length === 0" class="pane-empty">
            <div class="empty-glyph">🎁</div>
            <p>{{ stateInfo.is_running ? '礼物雷达已就绪，等待观众打赏...' : '暂无实时礼物记录' }}</p>
            <span v-if="!stateInfo.is_logged_in">
              提示：抖音对未登录游客会限制礼物消息下发，点击右上角【🔑 扫码解锁礼物】登录一次即可接收完整礼物与连击
            </span>
            <span v-else>{{ stateInfo.is_running ? '连击礼物将自动合并计次并实时计算钻石热度' : '-' }}</span>
          </div>

          <div
            v-for="gift in filteredGifts"
            :key="gift.combo_key || gift.msg_id"
            class="gift-row"
            :class="[`tier-${gift.tier || 'normal'}`, { 'combo-flash': comboFlashId === gift.combo_key }]"
          >
            <div class="gift-row-left">
              <img
                v-if="gift.gift_icon && !brokenImages[gift.msg_id]"
                :src="gift.gift_icon"
                referrerpolicy="no-referrer"
                class="gift-mini-img"
                alt=""
                @error="markImageBroken(gift.msg_id)"
              />
              <span v-else class="gift-mini-emoji">🎁</span>

              <div class="gift-row-info">
                <div class="gift-user-line">
                  <span class="gift-sender">{{ gift.nickname || '-' }}</span>
                  <span class="gift-time mono-num">{{ gift.time_str || '-' }}</span>
                </div>
                <div class="gift-name-line">
                  <span>送出</span>
                  <span class="gift-name-txt">{{ gift.gift_name || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="gift-row-right mono-num">
              <span class="gift-count-badge">x{{ gift.count || 1 }}</span>
              <span v-if="gift.total_diamonds > 0" class="gift-diamond-tag">
                💎 {{ gift.total_diamonds }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  activeTarget: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['show-toast', 'status-change'])

// 房间输入与交互状态
const roomInput = ref('')
const operating = ref(false)
const loginOpening = ref(false)
const autoScroll = ref(true)
const unreadChatCount = ref(0)
const onlyHotWords = ref(false)
const onlyHighValueGifts = ref(false)
const keywordFilter = ref('')
const comboFlashId = ref('')
const brokenImages = reactive({})

// 滚动容器引用
const chatScrollRef = ref(null)
const giftScrollRef = ref(null)

// 后端实时状态与遥测指标
const stateInfo = ref({
  is_running: false,
  connection_state: 'idle',
  transport_mode: '-',
  is_logged_in: false,
  error_message: '',
  target: '',
  web_rid: '',
  anchor_name: '-',
  room_title: '-'
})

const metrics = ref({
  total_chats: 0,
  chats_per_10s: 0,
  total_gifts: 0,
  total_diamonds: 0,
  online_count: 0,
  total_user_str: '-',
  like_total: 0
})

const chats = ref([])
const gifts = ref([])

let sseSource = null
let reconnectTimer = null
let flashResetTimer = null

// 同步外部传入的房间号到输入框
watch(() => props.activeTarget, (newVal) => {
  if (newVal && newVal.trim()) {
    roomInput.value = newVal.trim()
  }
}, { immediate: true })

// 判断输入框房间是否与当前正在采集的房间不同
const isDifferentRoom = computed(() => {
  const inp = roomInput.value.trim()
  if (!inp || !stateInfo.value.is_running) return false
  return inp !== stateInfo.value.target && inp !== stateInfo.value.web_rid
})

const hasActiveSession = computed(() => {
  return stateInfo.value.is_running && stateInfo.value.connection_state === 'connected'
})

// 连接状态展示文案与样式
const connStatusClass = computed(() => {
  const st = stateInfo.value.connection_state
  if (st === 'connected') return 'is-connected'
  if (st === 'connecting') return 'is-connecting'
  if (st === 'error') return 'is-error'
  return 'is-idle'
})

const connStatusText = computed(() => {
  const st = stateInfo.value.connection_state
  if (st === 'connected') return '实时接收中'
  if (st === 'connecting') return '正在握手连接...'
  if (st === 'error') return '连接受限'
  return '待机中'
})

// 在线观众与点赞格式化展示（无数据返回 "-"）
const onlineDisplay = computed(() => {
  const online = metrics.value.online_count
  const likes = metrics.value.like_total
  if (!online && !likes) return '-'
  const onlinePart = online > 0 ? `${formatNumber(online)} 人` : '-'
  const likePart = likes > 0 ? `♥ ${formatNumber(likes)}` : '-'
  return `${onlinePart} / ${likePart}`
})

// 过滤后的弹幕列表
const filteredChats = computed(() => {
  const kw = keywordFilter.value.trim().toLowerCase()
  return chats.value.filter(c => {
    if (onlyHotWords.value && !c.is_hot) return false
    if (kw) {
      const textMatch = (c.content || '').toLowerCase().includes(kw)
      const userMatch = (c.nickname || '').toLowerCase().includes(kw)
      return textMatch || userMatch
    }
    return true
  })
})

// 过滤后的礼物列表（倒序展示最新打赏在最上方）
const filteredGifts = computed(() => {
  const list = [...gifts.value].reverse()
  if (onlyHighValueGifts.value) {
    return list.filter(g => (g.total_diamonds || 0) >= 99)
  }
  return list
})

// 顶部主打展示礼物（取最新一条礼物）
const featuredGift = computed(() => {
  if (gifts.value.length === 0) return null
  return gifts.value[gifts.value.length - 1]
})

// 数字人性化缩略格式化
const formatNumber = (num) => {
  if (!num || num <= 0) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toLocaleString()
}

// 标记加载失败的图片以平滑隐藏或降级为图标
const markImageBroken = (key) => {
  brokenImages[key] = true
}

// 滚动弹幕列表至底部
const scrollChatToBottom = () => {
  if (!autoScroll.value) return
  nextTick(() => {
    const el = chatScrollRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// 监听用户手动上滑阅读历史弹幕
const onChatManualScroll = () => {
  const el = chatScrollRef.value
  if (!el) return
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  if (distanceToBottom > 48) {
    autoScroll.value = false
  } else {
    autoScroll.value = true
    unreadChatCount.value = 0
  }
}

const toggleAutoScroll = () => {
  autoScroll.value = !autoScroll.value
  if (autoScroll.value) {
    unreadChatCount.value = 0
    scrollChatToBottom()
  }
}

const resumeAutoScroll = () => {
  autoScroll.value = true
  unreadChatCount.value = 0
  scrollChatToBottom()
}

// 触发连击高光闪烁动画
const triggerComboFlash = (comboKey) => {
  comboFlashId.value = comboKey
  if (flashResetTimer) clearTimeout(flashResetTimer)
  flashResetTimer = setTimeout(() => {
    comboFlashId.value = ''
  }, 650)
}

// 同步状态信息并通知父组件
const applyStateSnapshot = (data) => {
  if (!data) return
  const wasLoggedIn = stateInfo.value.is_logged_in
  stateInfo.value = {
    is_running: !!data.is_running,
    connection_state: data.connection_state || 'idle',
    transport_mode: data.transport_mode || '-',
    is_logged_in: !!data.is_logged_in,
    error_message: data.error_message || '',
    target: data.target || '',
    web_rid: data.web_rid || '',
    anchor_name: data.anchor_name || '-',
    room_title: data.room_title || '-'
  }
  if (!wasLoggedIn && stateInfo.value.is_logged_in) {
    loginOpening.value = false
    emit('show-toast', '🎉 抖音登录成功！完整实时礼物通道已解锁，重新连接当前房间即可生效')
  }
  if (data.web_rid && !roomInput.value) {
    roomInput.value = data.web_rid
  }
  if (data.metrics) {
    metrics.value = { ...metrics.value, ...data.metrics }
  }
  emit('status-change', {
    isRunning: stateInfo.value.is_running,
    connectionState: stateInfo.value.connection_state,
    anchorName: stateInfo.value.anchor_name,
    totalChats: metrics.value.total_chats,
    totalGifts: metrics.value.total_gifts
  })
}

// 建立 SSE 实时流订阅连接
const connectSSEStream = () => {
  closeSSEStream()
  try {
    sseSource = new EventSource('/api/danmu/stream')

    sseSource.onmessage = (event) => {
      if (!event.data) return
      try {
        const payload = JSON.parse(event.data)
        const evtType = payload.type

        if (evtType === 'snapshot' && payload.data) {
          applyStateSnapshot(payload.data)
          chats.value = Array.isArray(payload.data.chats) ? payload.data.chats : []
          gifts.value = Array.isArray(payload.data.gifts) ? payload.data.gifts : []
          scrollChatToBottom()
        } else if (evtType === 'state' && payload.data) {
          applyStateSnapshot(payload.data)
        } else if (evtType === 'chat' && payload.data) {
          chats.value.push(payload.data)
          if (chats.value.length > 250) {
            chats.value.shift()
          }
          if (autoScroll.value) {
            scrollChatToBottom()
          } else {
            unreadChatCount.value += 1
          }
        } else if (evtType === 'gift' && payload.data) {
          const newGift = payload.data
          if (payload.is_combo_update) {
            const idx = gifts.value.findIndex(g => g.combo_key === newGift.combo_key)
            if (idx > -1) {
              gifts.value[idx] = newGift
            } else {
              gifts.value.push(newGift)
            }
          } else {
            gifts.value.push(newGift)
            if (gifts.value.length > 120) {
              gifts.value.shift()
            }
          }
          triggerComboFlash(newGift.combo_key)
        } else if (evtType === 'metrics' && payload.data) {
          metrics.value = { ...metrics.value, ...payload.data }
          emit('status-change', {
            isRunning: stateInfo.value.is_running,
            connectionState: stateInfo.value.connection_state,
            anchorName: stateInfo.value.anchor_name,
            totalChats: metrics.value.total_chats,
            totalGifts: metrics.value.total_gifts
          })
        } else if (evtType === 'cleared') {
          chats.value = []
          gifts.value = []
          unreadChatCount.value = 0
        }
      } catch (err) {
        console.warn('解析弹幕 SSE 消息失败:', err)
      }
    }

    sseSource.onerror = () => {
      closeSSEStream()
      reconnectTimer = setTimeout(() => {
        connectSSEStream()
      }, 3000)
    }
  } catch (e) {
    console.warn('建立弹幕 SSE 连接失败:', e)
  }
}

const closeSSEStream = () => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (sseSource) {
    sseSource.close()
    sseSource = null
  }
}

// 启动指定直播间的弹幕与礼物采集（支持透传已解析元数据实现秒切）
const startForTarget = async (targetVal, resolvedMeta = null) => {
  const target = (targetVal || roomInput.value || '').trim()
  if (!target) {
    emit('show-toast', '请先输入抖音房间号或直播间链接')
    return
  }

  roomInput.value = target
  operating.value = true

  // 切换新房间时立即重置本地旧房间显示与历史弹幕，避免残留上一主播信息
  if (target !== stateInfo.value.target && target !== stateInfo.value.web_rid) {
    chats.value = []
    gifts.value = []
    unreadChatCount.value = 0
    metrics.value = {
      total_chats: 0,
      chats_per_10s: 0,
      total_gifts: 0,
      total_diamonds: 0,
      online_count: 0,
      total_user_str: '-',
      like_total: 0
    }
    stateInfo.value = {
      ...stateInfo.value,
      is_running: true,
      connection_state: 'connecting',
      transport_mode: '-',
      error_message: '',
      target,
      web_rid: resolvedMeta?.web_rid || target,
      anchor_name: resolvedMeta?.anchor_name || '-',
      room_title: resolvedMeta?.title || '-'
    }
  }

  try {
    const res = await fetch('/api/danmu/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, meta: resolvedMeta || null })
    })
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.detail || '启动弹幕监听失败')
    }
    applyStateSnapshot(data)
    emit('show-toast', `💬 正在连接【${data.anchor_name || target}】实时弹幕与礼物通道...`)
  } catch (err) {
    stateInfo.value.connection_state = 'error'
    stateInfo.value.error_message = err.message
    emit('show-toast', `弹幕连接异常: ${err.message}`)
  } finally {
    operating.value = false
  }
}

const handleStartConnect = () => {
  startForTarget(roomInput.value)
}

// 停止弹幕与礼物采集
const handleStopConnect = async () => {
  operating.value = true
  try {
    const res = await fetch('/api/danmu/stop', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      applyStateSnapshot(data)
      emit('show-toast', '已断开实时弹幕与礼物通道')
    }
  } catch (err) {
    emit('show-toast', `断开异常: ${err.message}`)
  } finally {
    operating.value = false
  }
}

// 触发弹出本机浏览器扫码登录抖音以解锁完整礼物下发
const handleOpenDouyinLogin = async () => {
  loginOpening.value = true
  try {
    const res = await fetch('/api/danmu/login', { method: 'POST' })
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.detail || '无法打开登录窗口')
    }
    emit('show-toast', `🔑 ${data.message || '请在弹出的浏览器窗口中扫码登录抖音'}`)
  } catch (err) {
    loginOpening.value = false
    emit('show-toast', `登录启动失败: ${err.message}`)
  }
}

// 清空屏幕缓存消息
const handleClearScreen = async () => {
  chats.value = []
  gifts.value = []
  unreadChatCount.value = 0
  try {
    await fetch('/api/danmu/clear', { method: 'POST' })
  } catch (e) {
    // 忽略清屏接口瞬态异常
  }
}

defineExpose({
  startForTarget,
  stopConnect: handleStopConnect
})

onMounted(() => {
  connectSSEStream()
})

onUnmounted(() => {
  closeSSEStream()
  if (flashResetTimer) clearTimeout(flashResetTimer)
})
</script>

<style scoped>
.danmu-gift-card {
  display: flex;
  flex-direction: column;
  gap: 11px;
  flex: 1;
  min-height: 0;
}

/* 顶部状态与快捷控制栏 */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.header-left-group {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
}

.conn-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 999px;
  border: 1px solid var(--border-subtle);
}

.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}

.conn-badge.is-connected {
  background: rgba(16, 185, 129, 0.14);
  border-color: rgba(16, 185, 129, 0.38);
  color: #34D399;
}
.conn-badge.is-connected .conn-dot {
  background: #10B981;
  box-shadow: 0 0 8px #10B981;
}

.conn-badge.is-connecting {
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.38);
  color: #FBBF24;
}
.conn-badge.is-connecting .conn-dot {
  background: #F59E0B;
  animation: dotBlink 1s infinite;
}

.conn-badge.is-error {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
  color: #F87171;
}
.conn-badge.is-error .conn-dot {
  background: #EF4444;
}

.conn-badge.is-idle {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
}

@keyframes dotBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

.mode-badge {
  font-size: 0.64rem;
  font-weight: 700;
  color: var(--accent-light);
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.28);
  padding: 2px 7px;
  border-radius: 4px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.mini-room-input {
  display: flex;
  align-items: center;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  padding: 2px 3px 2px 8px;
  gap: 5px;
}

.mini-room-input input {
  background: transparent;
  border: none;
  outline: none;
  color: #FFFFFF;
  font-size: 0.74rem;
  font-family: 'JetBrains Mono', 'Inter', sans-serif;
  width: 145px;
}

.mini-room-input input::placeholder {
  color: var(--text-muted);
  font-family: 'Inter', sans-serif;
}

.btn-mini {
  border: none;
  border-radius: 4px;
  padding: 4px 9px;
  font-size: 0.7rem;
  font-weight: 700;
  cursor: pointer;
  transition: var(--transition);
  white-space: nowrap;
}

.btn-connect {
  background: linear-gradient(135deg, #06B6D4 0%, #4F46E5 100%);
  color: #FFFFFF;
}
.btn-connect:hover:not(:disabled) {
  filter: brightness(1.12);
}

.btn-disconnect {
  background: rgba(239, 68, 68, 0.2);
  color: #FCA5A5;
  border: 1px solid rgba(239, 68, 68, 0.38);
}
.btn-disconnect:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.34);
  color: #FFFFFF;
}

.btn-tool {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-sub);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 5px 9px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: var(--transition);
}
.btn-tool:hover {
  background: rgba(255, 255, 255, 0.09);
  color: #FFFFFF;
}
.btn-tool.active {
  background: rgba(99, 102, 241, 0.16);
  border-color: rgba(99, 102, 241, 0.42);
  color: #C7D2FE;
}

/* 当前房间提示条 */
.room-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 6px 11px;
  background: rgba(6, 182, 212, 0.07);
  border: 1px solid rgba(6, 182, 212, 0.22);
  border-radius: var(--radius-xs);
  font-size: 0.73rem;
}

.room-banner.is-error {
  background: rgba(239, 68, 68, 0.09);
  border-color: rgba(239, 68, 68, 0.3);
}

.banner-left {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.banner-label {
  color: var(--text-muted);
  flex-shrink: 0;
}

.banner-anchor {
  color: #FFFFFF;
  font-weight: 700;
  flex-shrink: 0;
}

.banner-title {
  color: var(--text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.banner-right {
  font-size: 0.7rem;
  color: var(--accent-light);
  flex-shrink: 0;
}

.err-txt {
  color: #FCA5A5;
}

/* 四维 KPI 指标带 */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.kpi-item {
  background: rgba(5, 7, 12, 0.6);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  padding: 7px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.kpi-item.highlight-kpi {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.09) 0%, rgba(168, 85, 247, 0.09) 100%);
  border-color: rgba(245, 158, 11, 0.28);
}

.kpi-label {
  font-size: 0.66rem;
  color: var(--text-muted);
}

.kpi-value {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-value small {
  font-size: 0.66rem;
  color: var(--text-sub);
  font-weight: 500;
  margin-left: 3px;
}

.kpi-value.accent {
  color: var(--accent-light);
}

.kpi-value.gold {
  color: var(--gold-light);
}

.kpi-value.diamond {
  color: #FDE68A;
}

/* 双舱并列主体容器：自适应撑满中栏剩余高度 */
.dual-cockpit {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.cockpit-pane {
  background: rgba(4, 6, 11, 0.72);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  height: 100%;
  min-height: 220px;
}

.pane-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  background: rgba(255, 255, 255, 0.025);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.pane-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.76rem;
  font-weight: 700;
  color: #E2E8F0;
  white-space: nowrap;
}

.pane-count {
  font-size: 0.66rem;
  color: var(--text-sub);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 999px;
}

.pane-filters {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.filter-chip {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  font-size: 0.66rem;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
  cursor: pointer;
  white-space: nowrap;
  transition: var(--transition);
}
.filter-chip:hover {
  color: #FFFFFF;
}
.filter-chip.active {
  background: rgba(245, 158, 11, 0.18);
  border-color: rgba(245, 158, 11, 0.45);
  color: #FCD34D;
}
.filter-chip.gold-chip.active {
  background: rgba(168, 85, 247, 0.22);
  border-color: rgba(192, 132, 252, 0.5);
  color: #E9D5FF;
}

.filter-chip.login-chip {
  background: rgba(245, 158, 11, 0.16);
  border-color: rgba(245, 158, 11, 0.45);
  color: #FDE68A;
}
.filter-chip.login-chip:hover:not(:disabled) {
  background: rgba(245, 158, 11, 0.28);
  color: #FFFFFF;
}

.logged-in-tag {
  font-size: 0.64rem;
  font-weight: 700;
  color: #34D399;
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.35);
  padding: 2px 7px;
  border-radius: 999px;
  white-space: nowrap;
}

.search-mini {
  width: 108px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: #FFFFFF;
  font-size: 0.68rem;
  padding: 3px 7px;
  outline: none;
}
.search-mini:focus {
  border-color: var(--primary-light);
}

/* 滚动流通用容器 */
.stream-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  overscroll-behavior: contain;
}

.pane-empty {
  margin: auto 0;
  text-align: center;
  padding: 24px 12px;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.empty-glyph {
  font-size: 1.45rem;
  opacity: 0.45;
}

.pane-empty p {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-sub);
}

.pane-empty span {
  font-size: 0.68rem;
  line-height: 1.4;
  max-width: 240px;
}

/* 左舱单条弹幕样式 */
.chat-row {
  font-size: 0.75rem;
  line-height: 1.45;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid transparent;
  word-break: break-word;
  transition: background 0.18s ease;
}

.chat-row:hover {
  background: rgba(255, 255, 255, 0.055);
}

.chat-row.is-hot {
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.14) 0%, rgba(239, 68, 68, 0.06) 100%);
  border-color: rgba(245, 158, 11, 0.35);
}

.chat-time {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-right: 6px;
}

.user-avatar {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  vertical-align: -3px;
  margin-right: 5px;
  object-fit: cover;
}

.chat-user {
  color: #38BDF8;
  font-weight: 600;
  margin-right: 5px;
}

.chat-text {
  color: #F1F5F9;
}

.hot-kw-tag {
  display: inline-block;
  margin-left: 6px;
  font-size: 0.62rem;
  font-weight: 700;
  color: #FDE68A;
  background: rgba(245, 158, 11, 0.22);
  border: 1px solid rgba(245, 158, 11, 0.4);
  padding: 0 5px;
  border-radius: 4px;
}

.unread-float-btn {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(79, 70, 229, 0.92);
  border: 1px solid rgba(165, 180, 252, 0.5);
  color: #FFFFFF;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
  z-index: 5;
}

/* 右舱顶部连击高光横幅 */
.featured-gift-stage {
  margin: 8px 10px 0;
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.16) 0%, rgba(99, 102, 241, 0.16) 100%);
  border: 1px solid rgba(56, 189, 248, 0.35);
  flex-shrink: 0;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.featured-gift-stage.tier-epic {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(217, 119, 6, 0.14) 100%);
  border-color: rgba(251, 191, 36, 0.5);
}

.featured-gift-stage.tier-legend {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.28) 0%, rgba(245, 158, 11, 0.25) 100%);
  border-color: rgba(253, 224, 71, 0.65);
  box-shadow: 0 0 18px rgba(245, 158, 11, 0.25);
}

.stage-left {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.gift-icon-box {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.gift-img {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.gift-fallback-emoji {
  font-size: 1.15rem;
}

.stage-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.stage-sender {
  font-size: 0.74rem;
  font-weight: 700;
  color: #FFFFFF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-action {
  font-size: 0.7rem;
  color: #E2E8F0;
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}

.stage-action strong {
  color: #FDE68A;
}

.stage-diamond {
  font-size: 0.64rem;
  color: #FCD34D;
  background: rgba(0, 0, 0, 0.35);
  padding: 0 5px;
  border-radius: 4px;
}

.stage-combo {
  display: flex;
  align-items: baseline;
  gap: 1px;
  color: #FBBF24;
  text-shadow: 0 2px 10px rgba(245, 158, 11, 0.55);
  flex-shrink: 0;
}

.combo-x {
  font-size: 0.8rem;
  font-weight: 800;
  font-style: italic;
}

.combo-num {
  font-size: 1.25rem;
  font-weight: 900;
  font-style: italic;
}

/* 礼物明细列表行 */
.gift-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 6px 9px;
  border-radius: 6px;
  background: rgba(14, 22, 38, 0.65);
  border: 1px solid rgba(56, 189, 248, 0.16);
  transition: var(--transition);
}

.gift-row.tier-epic {
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.14) 0%, rgba(14, 22, 38, 0.7) 100%);
  border-color: rgba(245, 158, 11, 0.38);
}

.gift-row.tier-legend {
  background: linear-gradient(90deg, rgba(168, 85, 247, 0.22) 0%, rgba(245, 158, 11, 0.18) 100%);
  border-color: rgba(251, 191, 36, 0.55);
}

.combo-flash {
  animation: giftPulse 0.55s ease;
}

@keyframes giftPulse {
  0% { transform: scale(1); }
  40% { transform: scale(1.03); box-shadow: 0 0 16px rgba(251, 191, 36, 0.4); }
  100% { transform: scale(1); }
}

.gift-row-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.gift-mini-img {
  width: 24px;
  height: 24px;
  object-fit: contain;
  flex-shrink: 0;
}

.gift-mini-emoji {
  font-size: 1rem;
  flex-shrink: 0;
}

.gift-row-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.gift-user-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gift-sender {
  font-size: 0.72rem;
  font-weight: 700;
  color: #E2E8F0;
  max-width: 110px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gift-time {
  font-size: 0.62rem;
  color: var(--text-muted);
}

.gift-name-line {
  font-size: 0.68rem;
  color: var(--text-sub);
  display: flex;
  align-items: center;
  gap: 4px;
}

.gift-name-txt {
  color: #FDE68A;
  font-weight: 600;
}

.gift-row-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.gift-count-badge {
  font-size: 0.78rem;
  font-weight: 800;
  color: #38BDF8;
}

.gift-row.tier-epic .gift-count-badge,
.gift-row.tier-legend .gift-count-badge {
  color: #FBBF24;
}

.gift-diamond-tag {
  font-size: 0.62rem;
  color: #FCD34D;
}

@media (max-width: 900px) {
  .kpi-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .dual-cockpit {
    grid-template-columns: 1fr;
  }
}
</style>
