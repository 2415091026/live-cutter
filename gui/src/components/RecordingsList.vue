<template>
  <div class="glass-card recordings-card">
    <!-- 头部工具栏 -->
    <div class="card-header-row">
      <div class="card-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="23 7 16 12 23 17 23 7"></polygon>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
        </svg>
        <span>录像素材资产库</span>
      </div>
      <div class="header-right-tools">
        <span class="count-pill mono-num">{{ recordings.length }} 项</span>
        <button 
          class="btn-icon-tool" 
          :class="{ 'is-spinning': isOrganizing }"
          @click.stop="handleOrganizeByDate"
          title="将根目录录像按日期整理归档到各日期文件夹"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>
        <button 
          class="btn-icon-tool btn-icon-refresh" 
          :class="{ 'is-spinning': isRefreshing }"
          @click.stop="handleManualRefresh"
          title="刷新录像素材列表"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- 目录展开与控制提示 -->
    <div class="tree-controls-bar" v-if="dateGroups.length > 1">
      <span class="tree-hint">📁 已按日期归整为 {{ dateGroups.length }} 个文件夹</span>
      <div class="tree-toggle-btns">
        <button class="btn-text-toggle" @click="expandAll">全部展开</button>
        <span class="divider">/</span>
        <button class="btn-text-toggle" @click="collapseAll">全部收起</button>
      </div>
    </div>

    <!-- 日期文件夹目录列表 (Folder Accordion Tree) -->
    <div class="list-wrapper">
      <div v-if="recordings.length === 0" class="empty-hint">
        <div class="empty-icon">📼</div>
        <p>暂无本地录像素材</p>
        <span>在上方输入直播间开启监听后将自动按日期入库</span>
      </div>

      <!-- 按日期文件夹节点循环 -->
      <div 
        v-for="group in dateGroups" 
        :key="group.date" 
        class="date-folder-group"
      >
        <!-- 日期文件夹头部 -->
        <div 
          class="folder-header-row" 
          :class="{ 'is-open': isExpanded(group.date) }"
          @click="toggleDate(group.date)"
        >
          <div class="folder-title-left">
            <span class="folder-arrow">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </span>
            <span class="folder-icon">📁</span>
            <span class="folder-date-name">{{ group.date_display }}</span>
          </div>

          <div class="folder-meta-right" @click.stop>
            <span class="folder-count-badge mono-num">{{ group.items.length }} 个视频</span>
            <!-- 批量清空本日所有视频按钮 -->
            <button 
              class="btn-folder-delete"
              :class="{ 'confirming': pendingDeleteDate === group.date }"
              @click.stop="handleDeleteDateGroup(group)"
              :title="pendingDeleteDate === group.date ? '点击确认删除整日视频' : '清空本日全部录像'"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span v-if="pendingDeleteDate === group.date" class="confirm-txt">确认清空?</span>
            </button>
          </div>
        </div>

        <!-- 文件夹展开内容：具体视频列表 -->
        <div v-show="isExpanded(group.date)" class="folder-children-list">
          <div 
            v-for="rec in group.items" 
            :key="rec.filename" 
            class="rec-item"
            :class="{ active: currentVideo && currentVideo.filename === rec.filename }"
            @click="selectRec(rec)"
          >
            <div class="rec-info">
              <div class="rec-header-row">
                <span class="time-tag mono-num">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 16 14"></polyline>
                  </svg>
                  {{ rec.time_display || '未知时间' }}
                </span>
                <span class="anchor-badge" v-if="rec.anchor_label && rec.anchor_label !== '-'">
                  {{ rec.anchor_label }}
                </span>
              </div>

              <div class="rec-name mono-num" :title="rec.filename">{{ rec.filename }}</div>
              <div class="rec-meta mono-num">
                <span>{{ rec.size_mb }} MB</span>
                <span class="meta-dot">•</span>
                <span>H.264 1080P</span>
              </div>
            </div>

            <!-- 右侧状态与操作栏 -->
            <div class="rec-action-col" @click.stop>
              <span class="active-tag" v-if="currentVideo && currentVideo.filename === rec.filename">
                <span class="mini-dot"></span>
                监视中
              </span>

              <!-- 独立单条视频删除按钮 -->
              <button 
                class="btn-item-delete"
                :class="{ 'confirming': pendingDeleteFilename === rec.filename }"
                @click.stop="handleDeleteSingle(rec)"
                :title="pendingDeleteFilename === rec.filename ? '点击确认删除此视频' : '删除该视频文件'"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                <span v-if="pendingDeleteFilename === rec.filename" class="confirm-txt">确认?</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  recordings: {
    type: Array,
    default: () => []
  },
  currentVideo: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['select-video', 'refresh', 'video-deleted', 'show-toast'])
const isRefreshing = ref(false)
const isOrganizing = ref(false)

// 防误触待确认状态
const pendingDeleteFilename = ref('')
const pendingDeleteDate = ref('')
let deleteResetTimer = null

// 响应式展开的日期数组（避免 Set 在部分 Vue 版本中的 reactivity 陷阱）
const expandedDatesList = ref([])

const isExpanded = (date) => expandedDatesList.value.includes(date)

// 按日期对录像进行目录分组
const dateGroups = computed(() => {
  const map = {}
  props.recordings.forEach(rec => {
    const d = rec.date || '未分类日期'
    const display = rec.date_display || d
    if (!map[d]) {
      map[d] = {
        date: d,
        date_display: display,
        items: []
      }
    }
    map[d].items.push(rec)
  })

  const groups = Object.values(map)
  groups.sort((a, b) => (b.date > a.date ? 1 : -1))
  return groups
})

// 默认展开最新一天的文件夹
watch(() => dateGroups.value, (groups) => {
  if (groups.length > 0 && expandedDatesList.value.length === 0) {
    expandedDatesList.value = [groups[0].date]
  }
}, { immediate: true })

const toggleDate = (date) => {
  const idx = expandedDatesList.value.indexOf(date)
  if (idx > -1) {
    expandedDatesList.value.splice(idx, 1)
  } else {
    expandedDatesList.value.push(date)
  }
}

const expandAll = () => {
  expandedDatesList.value = dateGroups.value.map(g => g.date)
}

const collapseAll = () => {
  expandedDatesList.value = []
}

// 手动刷新
const handleManualRefresh = () => {
  isRefreshing.value = true
  emit('refresh')
  setTimeout(() => {
    isRefreshing.value = false
  }, 700)
}

// 一键按日期整理物理磁盘目录
const handleOrganizeByDate = async () => {
  isOrganizing.value = true
  try {
    const res = await fetch('/api/recordings/organize-by-date', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      emit('show-toast', `📁 ${data.message || '已成功按日期整理归档录像目录！'}`)
      emit('refresh')
    }
  } catch (e) {
    emit('show-toast', `归档失败: ${e.message}`)
  } finally {
    setTimeout(() => {
      isOrganizing.value = false
    }, 600)
  }
}

// 单条删除逻辑（二次点击防误触）
const handleDeleteSingle = async (rec) => {
  if (pendingDeleteFilename.value !== rec.filename) {
    pendingDeleteFilename.value = rec.filename
    if (deleteResetTimer) clearTimeout(deleteResetTimer)
    deleteResetTimer = setTimeout(() => {
      pendingDeleteFilename.value = ''
    }, 3500)
    return
  }

  pendingDeleteFilename.value = ''
  try {
    const res = await fetch('/api/recordings/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: rec.filename })
    })

    if (res.ok) {
      emit('show-toast', `🗑️ 已删除视频: ${rec.filename}`)
      emit('video-deleted', rec.filename)
      emit('refresh')
    } else {
      const err = await res.json()
      emit('show-toast', `删除失败: ${err.detail || '未知错误'}`)
    }
  } catch (e) {
    emit('show-toast', `删除请求异常: ${e.message}`)
  }
}

// 整日批量删除逻辑
const handleDeleteDateGroup = async (group) => {
  if (pendingDeleteDate.value !== group.date) {
    pendingDeleteDate.value = group.date
    if (deleteResetTimer) clearTimeout(deleteResetTimer)
    deleteResetTimer = setTimeout(() => {
      pendingDeleteDate.value = ''
    }, 4000)
    return
  }

  pendingDeleteDate.value = ''
  try {
    const filenames = group.items.map(i => i.filename)
    const res = await fetch('/api/recordings/delete-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames, date: group.date })
    })

    if (res.ok) {
      const data = await res.json()
      emit('show-toast', `🗑️ 已清空【${group.date_display}】共 ${data.deleted_count} 个视频`)
      filenames.forEach(fn => emit('video-deleted', fn))
      emit('refresh')
    } else {
      const err = await res.json()
      emit('show-toast', `整日清空失败: ${err.detail || '未知错误'}`)
    }
  } catch (e) {
    emit('show-toast', `整日清空请求异常: ${e.message}`)
  }
}

const selectRec = (rec) => {
  emit('select-video', rec)
}
</script>

<style scoped>
.recordings-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-right-tools {
  display: flex;
  align-items: center;
  gap: 7px;
}

.count-pill {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-sub);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  padding: 2px 9px;
  border-radius: 999px;
}

.btn-icon-tool {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: var(--transition);
}

.btn-icon-tool:hover {
  background: rgba(99, 102, 241, 0.16);
  border-color: rgba(99, 102, 241, 0.4);
  color: #C7D2FE;
}

.btn-icon-tool.is-spinning svg {
  animation: spinTool 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes spinTool {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 目录控制条 */
.tree-controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  padding: 0 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  padding-bottom: 6px;
  flex-shrink: 0;
}

.tree-hint {
  font-weight: 600;
}

.tree-toggle-btns {
  display: flex;
  align-items: center;
  gap: 4px;
}

.btn-text-toggle {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 0.68rem;
  cursor: pointer;
  padding: 1px 3px;
  transition: var(--transition);
}
.btn-text-toggle:hover {
  color: #C7D2FE;
}
.divider {
  opacity: 0.3;
}

/* 列表滚动容器 - 撑满左栏剩余高度并纵向无障碍滚动 */
.list-wrapper {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: 0;
  overflow-y: auto !important;
  overflow-x: hidden;
  overscroll-behavior: contain;
  padding-right: 4px;
}

/* 定制易于滚动与交互的微滚动条 */
.list-wrapper::-webkit-scrollbar {
  width: 6px;
}
.list-wrapper::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 999px;
}
.list-wrapper::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 999px;
}
.list-wrapper::-webkit-scrollbar-thumb:hover {
  background: var(--primary-light);
}

.empty-hint {
  text-align: center;
  padding: 36px 14px;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.empty-icon {
  font-size: 1.6rem;
  opacity: 0.5;
}
.empty-hint p {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-sub);
}
.empty-hint span {
  font-size: 0.72rem;
}

/* 日期文件夹组卡片 */
.date-folder-group {
  display: flex;
  flex-direction: column;
  background: rgba(5, 7, 11, 0.45);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  transition: var(--transition);
  flex-shrink: 0;
}

.folder-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  user-select: none;
  transition: var(--transition);
  flex-shrink: 0;
}

.folder-header-row:hover {
  background: rgba(255, 255, 255, 0.06);
}

.folder-header-row.is-open {
  background: rgba(99, 102, 241, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.folder-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.folder-arrow {
  color: var(--text-muted);
  display: flex;
  align-items: center;
  transition: transform 0.22s ease;
}
.folder-header-row.is-open .folder-arrow {
  transform: rotate(90deg);
  color: var(--accent-light);
}

.folder-icon {
  font-size: 0.9rem;
}

.folder-date-name {
  font-size: 0.78rem;
  font-weight: 700;
  color: #F1F5F9;
  letter-spacing: 0.2px;
}

.folder-meta-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.folder-count-badge {
  font-size: 0.66rem;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  padding: 1px 6px;
  border-radius: 4px;
}

.btn-folder-delete {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.65rem;
  transition: var(--transition);
}

.btn-folder-delete:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
  color: #F87171;
}

.btn-folder-delete.confirming {
  background: rgba(239, 68, 68, 0.28);
  border-color: rgba(239, 68, 68, 0.6);
  color: #FFFFFF;
}

/* 文件夹子条目列表 */
.folder-children-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
}

.rec-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(14, 19, 32, 0.6);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  padding: 9px 11px;
  cursor: pointer;
  transition: var(--transition);
  position: relative;
}

.rec-item:hover {
  background: rgba(30, 41, 59, 0.6);
  border-color: rgba(99, 102, 241, 0.35);
  transform: translateX(2px);
}

.rec-item.active {
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.22) 0%, rgba(15, 23, 42, 0.8) 100%);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.22);
}

.rec-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  gap: 3px;
}

.rec-header-row {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.time-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  color: #38BDF8;
  background: rgba(56, 189, 248, 0.12);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid rgba(56, 189, 248, 0.22);
}

.anchor-badge {
  font-size: 0.66rem;
  font-weight: 700;
  color: var(--gold-light);
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.28);
  padding: 1px 6px;
  border-radius: 4px;
  max-width: 105px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rec-name {
  font-size: 0.74rem;
  font-weight: 600;
  color: #E2E8F0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 195px;
}

.rec-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.66rem;
  color: var(--text-muted);
}
.meta-dot {
  opacity: 0.5;
}

.rec-action-col {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 8px;
}

.active-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.66rem;
  color: var(--accent-light);
  background: rgba(6, 182, 212, 0.16);
  border: 1px solid rgba(6, 182, 212, 0.35);
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 700;
}
.mini-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent-light);
  box-shadow: 0 0 6px var(--accent-light);
}

/* 单条删除按钮 */
.btn-item-delete {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  padding: 3px 6px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.68rem;
  transition: var(--transition);
  opacity: 0.6;
}

.rec-item:hover .btn-item-delete {
  opacity: 1;
}

.btn-item-delete:hover {
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.4);
  color: #F87171;
}

.btn-item-delete.confirming {
  opacity: 1;
  background: rgba(239, 68, 68, 0.32);
  border-color: rgba(239, 68, 68, 0.65);
  color: #FFFFFF;
}

.confirm-txt {
  font-weight: 700;
  font-size: 0.66rem;
}
</style>
