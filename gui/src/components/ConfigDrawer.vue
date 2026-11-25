<template>
  <div class="drawer-overlay" :class="{ 'open': visible }" @click.self="handleClose">
    <aside class="config-drawer" :class="{ 'open': visible }">
      <!-- 抽屉头部 -->
      <div class="drawer-header">
        <div class="header-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
          <span>系统与双模大模型参数配置</span>
        </div>
        <button class="btn-close" @click="handleClose" title="关闭抽屉">✕</button>
      </div>

      <!-- 抽屉滚动内容区 -->
      <div class="drawer-body">
        <!-- 模块 1：双模认知引擎切换与大模型配置 -->
        <div class="config-section">
          <div class="section-title">
            <span class="icon-tag">🧠</span>
            <span>AI 切片认知方案选择 (双引擎可配置)</span>
            <span class="badge-langchain">LangChain LCEL</span>
          </div>

          <!-- 核心双模式切换卡片 -->
          <div class="mode-selector-grid">
            <div 
              class="mode-card" 
              :class="{ active: configForm.llm.engine_mode === 'multimodal' }"
              @click="selectEngineMode('multimodal')"
            >
              <div class="mode-card-top">
                <span class="mode-icon">👁️</span>
                <span class="mode-badge omni">推荐 • 音画全感知</span>
              </div>
              <div class="mode-title">多模态视觉方案</div>
              <div class="mode-model mono-num">{{ configForm.llm.multimodal_model || 'qwen3.8-omni-flash' }}</div>
              <div class="mode-desc">自动抽样视频关键帧+台词+声波，看懂极限操作、沉默破防表情并过滤大厅假高能</div>
            </div>

            <div 
              class="mode-card" 
              :class="{ active: configForm.llm.engine_mode === 'text' }"
              @click="selectEngineMode('text')"
            >
              <div class="mode-card-top">
                <span class="mode-icon">⚡</span>
                <span class="mode-badge fast">经典 • 极速低耗</span>
              </div>
              <div class="mode-title">经典声文方案</div>
              <div class="mode-model mono-num">{{ configForm.llm.text_model || 'qwen3.8-flash' }}</div>
              <div class="mode-desc">保留原有声强波峰 + Whisper 语音转写 + 纯文本语义断句方案，响应极快</div>
            </div>
          </div>

          <!-- 多模态专属参数：关键帧采样数与模型代号 -->
          <div v-if="configForm.llm.engine_mode === 'multimodal'" class="sub-mode-box omni-box">
            <div class="form-group">
              <label class="form-label">多模态模型代号 (Multimodal Model)</label>
              <input 
                v-model="configForm.llm.multimodal_model" 
                type="text" 
                class="form-input mono-num" 
                placeholder="默认: qwen3.8-omni-flash"
                @input="configForm.llm.model = configForm.llm.multimodal_model"
              />
            </div>

            <div class="form-group">
              <div class="label-with-val">
                <label class="form-label">每个候选片段抽样关键帧数</label>
                <span class="range-val highlight-val">{{ configForm.llm.frame_sample_count }} 帧 / 片段</span>
              </div>
              <input 
                v-model.number="configForm.llm.frame_sample_count" 
                type="range" 
                min="3" 
                max="9" 
                step="1" 
                class="form-range"
              />
              <span class="field-tip">在声能爆发区间均匀抽取视频帧注入 qwen3.8-omni-flash，推荐 6 帧兼顾动作连续性与速度。</span>
            </div>
          </div>

          <!-- 经典声文专属参数 -->
          <div v-else class="sub-mode-box text-box">
            <div class="form-group">
              <label class="form-label">纯文本模型代号 (Text Model)</label>
              <input 
                v-model="configForm.llm.text_model" 
                type="text" 
                class="form-input mono-num" 
                placeholder="默认: qwen3.8-flash"
                @input="configForm.llm.model = configForm.llm.text_model"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">模型服务商预设 (Provider)</label>
            <div class="provider-grid">
              <button 
                type="button" 
                class="provider-btn" 
                :class="{ active: configForm.llm.provider === 'qwen' }"
                @click="applyProviderPreset('qwen')"
              >
                阿里百炼 (Qwen / Omni)
              </button>
              <button 
                type="button" 
                class="provider-btn" 
                :class="{ active: configForm.llm.provider === 'deepseek' }"
                @click="applyProviderPreset('deepseek')"
              >
                DeepSeek
              </button>
              <button 
                type="button" 
                class="provider-btn" 
                :class="{ active: configForm.llm.provider === 'zhipu' }"
                @click="applyProviderPreset('zhipu')"
              >
                智谱 GLM
              </button>
              <button 
                type="button" 
                class="provider-btn" 
                :class="{ active: configForm.llm.provider === 'custom' }"
                @click="configForm.llm.provider = 'custom'"
              >
                OpenAI 兼容/本地
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">API 访问密钥 (API Key)</label>
            <div class="input-password-wrapper">
              <input 
                v-model="configForm.llm.api_key" 
                :type="showApiKey ? 'text' : 'password'" 
                class="form-input mono-num" 
                placeholder="sk-..."
              />
              <button type="button" class="btn-toggle-eye" @click="showApiKey = !showApiKey">
                {{ showApiKey ? '隐藏' : '显示' }}
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">API 基础端点 (Base URL)</label>
            <input 
              v-model="configForm.llm.base_url" 
              type="text" 
              class="form-input mono-num" 
              placeholder="https://..."
            />
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <div class="label-with-val">
                <label class="form-label">采样温度 (Temperature)</label>
                <span class="range-val">{{ configForm.llm.temperature }}</span>
              </div>
              <input 
                v-model.number="configForm.llm.temperature" 
                type="range" 
                min="0.0" 
                max="1.0" 
                step="0.05" 
                class="form-range"
              />
            </div>

            <div class="form-group" style="width: 120px;">
              <label class="form-label">超时时间 (秒)</label>
              <input 
                v-model.number="configForm.llm.timeout_seconds" 
                type="number" 
                class="form-input mono-num" 
                min="5" 
                max="120"
              />
            </div>
          </div>
        </div>

        <!-- 模块 2：切片视频时长与灵敏度策略 -->
        <div class="config-section">
          <div class="section-title">
            <span class="icon-tag">✂️</span>
            <span>高能切片与视频时长策略</span>
          </div>

          <div class="form-group">
            <div class="label-with-val">
              <label class="form-label">录像分片采样时长 (秒)</label>
              <span class="range-val highlight-val">{{ configForm.system.segment_duration }} 秒</span>
            </div>
            <input 
              v-model.number="configForm.system.segment_duration" 
              type="range" 
              min="15" 
              max="60" 
              step="5" 
              class="form-range"
            />
            <span class="field-tip">建议设为 25~45 秒。采样时长越大，切片包含的前因铺垫与完整上下文越充分。</span>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">切片期望最短时长 (秒)</label>
              <input 
                v-model.number="configForm.system.target_slice_min" 
                type="number" 
                class="form-input mono-num" 
                min="10" 
                max="30"
              />
            </div>
            <div class="form-group flex-1">
              <label class="form-label">切片期望最长时长 (秒)</label>
              <input 
                v-model.number="configForm.system.target_slice_max" 
                type="number" 
                class="form-input mono-num" 
                min="20" 
                max="90"
              />
            </div>
          </div>

          <div class="form-group">
            <div class="label-with-val">
              <label class="form-label">声量激增触发灵敏度 (倍数)</label>
              <span class="range-val">{{ configForm.system.intensity_threshold }}x</span>
            </div>
            <input 
              v-model.number="configForm.system.intensity_threshold" 
              type="range" 
              min="1.1" 
              max="2.5" 
              step="0.1" 
              class="form-range"
            />
            <span class="field-tip">越低越灵敏（更易捕捉说话情绪）；越高越挑剔（仅捕捉强烈咆哮/爆笑）。</span>
          </div>
        </div>

        <!-- 模块 3：自动成片与双轨交付 -->
        <div class="config-section">
          <div class="section-title">
            <span class="icon-tag">🎬</span>
            <span>自动化导出与双轨交付</span>
          </div>

          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-label">自动压制 9:16 短视频成片</span>
              <span class="toggle-desc">捕获高能时自动通过 FFmpeg 渲染花字字幕成片</span>
            </div>
            <label class="switch">
              <input type="checkbox" v-model="configForm.system.auto_short_enabled" />
              <span class="slider"></span>
            </label>
          </div>

          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-label">自动生成剪映工程草稿</span>
              <span class="toggle-desc">自动写入 draft_content.json，可直接在剪映打开精修</span>
            </div>
            <label class="switch">
              <input type="checkbox" v-model="configForm.system.auto_draft_enabled" />
              <span class="slider"></span>
            </label>
          </div>
        </div>
      </div>

      <!-- 抽屉底部操作栏 -->
      <div class="drawer-footer">
        <button class="btn btn-secondary" @click="handleClose">取消</button>
        <button class="btn btn-primary btn-save" :disabled="saving" @click="handleSave">
          {{ saving ? '正在保存与热重载...' : '保存配置并立即生效' }}
        </button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'show-toast', 'config-saved'])

const saving = ref(false)
const showApiKey = ref(false)

const configForm = reactive({
  llm: {
    engine_mode: 'multimodal',
    provider: 'qwen',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key: '',
    model: 'qwen3.8-omni-flash',
    text_model: 'qwen3.8-flash',
    multimodal_model: 'qwen3.8-omni-flash',
    frame_sample_count: 6,
    temperature: 0.3,
    timeout_seconds: 35,
    max_tokens: 2000
  },
  system: {
    segment_duration: 25,
    default_record_duration: 20,
    target_slice_min: 15,
    target_slice_max: 35,
    intensity_threshold: 1.3,
    min_energy: 180,
    auto_short_enabled: true,
    auto_draft_enabled: true
  }
})

const presets = {
  qwen: {
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    text_model: 'qwen3.8-flash',
    multimodal_model: 'qwen3.8-omni-flash'
  },
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    text_model: 'deepseek-chat',
    multimodal_model: 'deepseek-chat'
  },
  zhipu: {
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    text_model: 'glm-4-flash',
    multimodal_model: 'glm-4v-flash'
  }
}

const selectEngineMode = (mode) => {
  configForm.llm.engine_mode = mode
  if (mode === 'multimodal') {
    configForm.llm.model = configForm.llm.multimodal_model || 'qwen3.8-omni-flash'
  } else {
    configForm.llm.model = configForm.llm.text_model || 'qwen3.8-flash'
  }
}

const applyProviderPreset = (provider) => {
  configForm.llm.provider = provider
  if (presets[provider]) {
    configForm.llm.base_url = presets[provider].base_url
    configForm.llm.text_model = presets[provider].text_model
    configForm.llm.multimodal_model = presets[provider].multimodal_model
    selectEngineMode(configForm.llm.engine_mode)
  }
}

const fetchConfig = async () => {
  try {
    const res = await fetch('/api/config')
    if (res.ok) {
      const data = await res.json()
      if (data.llm) Object.assign(configForm.llm, data.llm)
      if (data.system) Object.assign(configForm.system, data.system)
    }
  } catch (err) {
    console.error('获取系统配置失败:', err)
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    fetchConfig()
  }
})

const handleClose = () => {
  emit('close')
}

const handleSave = async () => {
  saving.value = true
  try {
    selectEngineMode(configForm.llm.engine_mode)
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        llm: configForm.llm,
        system: configForm.system
      })
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }

    const result = await res.json()
    emit('show-toast', `✅ ${result.message || '配置已保存并热重载生效！'}`)
    emit('config-saved')
    handleClose()
  } catch (e) {
    emit('show-toast', `❌ 保存配置失败: ${e.message}`)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(3, 5, 10, 0.72);
  backdrop-filter: blur(10px);
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}
.drawer-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.config-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 540px;
  max-width: 92vw;
  height: 100vh;
  background: rgba(11, 15, 28, 0.97);
  backdrop-filter: blur(24px);
  border-left: 1px solid var(--border-strong);
  box-shadow: -12px 0 45px rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1001;
}
.config-drawer.open {
  transform: translateX(0);
}

.drawer-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.02rem;
  font-weight: 700;
  color: #FFF;
}
.header-title svg {
  color: var(--accent-light);
}

.btn-close {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-sub);
  font-size: 1rem;
  cursor: pointer;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  transition: var(--transition);
}
.btn-close:hover {
  color: #FFF;
  background: rgba(255, 255, 255, 0.12);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-section {
  background: rgba(16, 22, 38, 0.65);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 700;
  color: #F1F5F9;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 10px;
}

.badge-langchain {
  font-size: 0.65rem;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #C7D2FE;
  padding: 2px 7px;
  border-radius: 999px;
  margin-left: auto;
}

/* 双模式选择卡片网格 */
.mode-selector-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.mode-card {
  background: rgba(5, 7, 11, 0.55);
  border: 1.5px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 12px;
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.mode-card:hover {
  border-color: rgba(255, 255, 255, 0.22);
  background: rgba(20, 27, 45, 0.65);
}

.mode-card.active {
  background: linear-gradient(145deg, rgba(99, 102, 241, 0.22) 0%, rgba(6, 182, 212, 0.12) 100%);
  border-color: var(--primary);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.25);
}

.mode-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mode-icon {
  font-size: 1.15rem;
}

.mode-badge {
  font-size: 0.62rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 999px;
}
.mode-badge.omni {
  background: rgba(6, 182, 212, 0.18);
  color: var(--accent-light);
  border: 1px solid rgba(6, 182, 212, 0.35);
}
.mode-badge.fast {
  background: rgba(245, 158, 11, 0.16);
  color: var(--gold-light);
  border: 1px solid rgba(245, 158, 11, 0.32);
}

.mode-title {
  font-size: 0.86rem;
  font-weight: 800;
  color: #FFFFFF;
  margin-top: 2px;
}

.mode-model {
  font-size: 0.72rem;
  color: #A5B4FC;
  font-weight: 600;
}

.mode-desc {
  font-size: 0.68rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.sub-mode-box {
  background: rgba(0, 0, 0, 0.32);
  border: 1px dashed rgba(99, 102, 241, 0.35);
  border-radius: var(--radius-xs);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.form-label {
  font-size: 0.75rem;
  color: var(--text-sub);
  font-weight: 600;
}

.label-with-val {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.range-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--accent-light);
}
.highlight-val {
  color: var(--gold-light);
  font-weight: 700;
}

.field-tip {
  font-size: 0.68rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.form-input {
  background: rgba(5, 7, 11, 0.65);
  border: 1px solid var(--border-subtle);
  color: #FFF;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  outline: none;
  transition: var(--transition);
}
.form-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-glow);
}

.provider-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.provider-btn {
  background: rgba(5, 7, 11, 0.5);
  border: 1px solid var(--border-subtle);
  color: var(--text-sub);
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: var(--transition);
}
.provider-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #FFF;
}
.provider-btn.active {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--primary);
  color: #C7D2FE;
  font-weight: 700;
}

.input-password-wrapper {
  position: relative;
  display: flex;
}
.input-password-wrapper input {
  flex: 1;
  padding-right: 50px;
}
.btn-toggle-eye {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 0.7rem;
  cursor: pointer;
}
.btn-toggle-eye:hover {
  color: #FFF;
}

.form-range {
  accent-color: var(--accent);
  cursor: pointer;
}

.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toggle-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #F1F5F9;
}

.toggle-desc {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: rgba(255, 255, 255, 0.15);
  transition: 0.3s;
  border-radius: 22px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}
input:checked + .slider {
  background-color: #10B981;
}
input:checked + .slider:before {
  transform: translateX(18px);
}

.drawer-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.btn-save {
  background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%);
  color: #FFF;
  font-weight: 700;
  box-shadow: 0 4px 14px rgba(168, 85, 247, 0.35);
}
</style>
