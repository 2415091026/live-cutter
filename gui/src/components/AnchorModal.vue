<template>
  <div v-if="visible" class="modal-backdrop" @click="close">
    <div class="modal-dialog" @click.stop>
      <div class="modal-header">
        <div class="modal-title">
          <div class="title-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
          <div>
            <div class="title-main">主播专属性格档案库 (Anchor Persona Profiles)</div>
            <div class="title-sub">驱动专属弹幕黑话匹配、定制化 Prompt 与画幅分割模板</div>
          </div>
        </div>
        <button class="btn-close" @click="close">&times;</button>
      </div>

      <div class="modal-body">
        <div v-for="a in anchors" :key="a.anchor_id" class="anchor-item-card">
          <div class="anchor-header">
            <div class="anchor-name-wrap">
              <span class="anchor-title-text">{{ a.anchor_name }}</span>
              <span class="rid-pill mono-num" v-if="a.web_rid">RID: {{ a.web_rid }}</span>
            </div>
            <span class="category-badge">{{ a.category }}</span>
          </div>

          <div class="meta-row mono-num">
            <span class="meta-tag">画幅模板: <strong>{{ a.layout_template }}</strong></span>
            <span class="meta-tag">触发灵敏度: <strong>{{ a.heat_sensitivity }}</strong></span>
          </div>

          <div class="prompt-text">
            <span class="sec-label">人设认知指导:</span>
            <p>{{ a.persona_prompt }}</p>
          </div>

          <div class="keywords-box">
            <span class="kw-label">专属触发词典:</span>
            <div class="kw-tags">
              <span v-for="kw in (a.exclusive_keywords || [])" :key="kw" class="kw-chip">{{ kw }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  anchors: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close'])

const close = () => {
  emit('close')
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(3, 5, 10, 0.78);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fade-in 0.2s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-dialog {
  background: #0B0F1C;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  width: 680px;
  max-width: 92vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-float);
}

.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.16);
  border: 1px solid rgba(99, 102, 241, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818CF8;
}

.title-main {
  font-family: 'Outfit', sans-serif;
  font-size: 1.02rem;
  font-weight: 700;
  color: var(--text-main);
}

.title-sub {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.btn-close {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-sub);
  width: 30px;
  height: 30px;
  border-radius: 6px;
  font-size: 1.3rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
}
.btn-close:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #FFF;
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.anchor-item-card {
  background: rgba(5, 7, 11, 0.55);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: var(--transition);
}

.anchor-item-card:hover {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(15, 23, 42, 0.6);
}

.anchor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.anchor-name-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anchor-title-text {
  font-size: 0.98rem;
  font-weight: 800;
  color: #FFFFFF;
}

.rid-pill {
  font-size: 0.68rem;
  color: var(--accent-light);
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.28);
  padding: 2px 7px;
  border-radius: 4px;
}

.category-badge {
  font-size: 0.72rem;
  background: rgba(99, 102, 241, 0.16);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #C7D2FE;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
}

.meta-row {
  display: flex;
  gap: 12px;
  font-size: 0.74rem;
  color: var(--text-sub);
}

.meta-tag {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-subtle);
  padding: 3px 8px;
  border-radius: 4px;
}

.meta-tag strong {
  color: #E2E8F0;
}

.prompt-text {
  font-size: 0.78rem;
  color: var(--text-sub);
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.02);
  padding: 9px 11px;
  border-radius: 6px;
  border-left: 3px solid var(--primary);
}

.sec-label {
  font-weight: 700;
  color: #C7D2FE;
  display: block;
  margin-bottom: 3px;
  font-size: 0.72rem;
}

.keywords-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kw-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--gold-light);
}

.kw-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kw-chip {
  font-size: 0.7rem;
  color: #FDE68A;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.25);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
</style>
