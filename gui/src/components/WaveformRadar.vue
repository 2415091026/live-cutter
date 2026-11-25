<template>
  <div class="glass-card waveform-card">
    <div class="card-title waveform-header">
      <div class="title-left">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
        </svg>
        <span>声学能量图谱与爆发波峰 (Acoustic Telemetry)</span>
      </div>
      <div class="legend-row">
        <span class="legend-item"><span class="dot base"></span> 声强基线</span>
        <span class="legend-item"><span class="dot peak"></span> 高能脉冲阈值区</span>
      </div>
    </div>

    <div class="canvas-box">
      <canvas ref="canvasRef" width="840" height="124"></canvas>
    </div>

    <div class="stats-bar mono-num">
      <div class="stat-chip">
        <span class="stat-label">采样总长</span>
        <span class="stat-val">{{ stats.duration }}s</span>
      </div>
      <div class="stat-chip">
        <span class="stat-label">平均声强能量</span>
        <span class="stat-val">{{ stats.avgEnergy }}</span>
      </div>
      <div class="stat-chip highlight">
        <span class="stat-label">高潮波峰</span>
        <span class="stat-val">{{ stats.peaksCount }} 处</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  peaks: {
    type: Array,
    default: () => []
  },
  totalDuration: {
    type: Number,
    default: 10
  },
  avgEnergy: {
    type: Number,
    default: 1800
  }
})

const canvasRef = ref(null)
const stats = ref({
  duration: '-',
  avgEnergy: '-',
  peaksCount: '-'
})

const renderCanvas = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height

  ctx.clearRect(0, 0, w, h)

  // 绘制精密示波器背景网格
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)'
  ctx.lineWidth = 1
  for (let x = 0; x < w; x += 40) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y < h; y += 31) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }

  // 绘制高潮爆发金色光晕区
  const totalSec = props.totalDuration || 10
  props.peaks.forEach(p => {
    const x1 = (p.start_time / totalSec) * w
    const x2 = (p.end_time / totalSec) * w
    const pw = Math.max(x2 - x1, 16)

    const peakGrad = ctx.createLinearGradient(0, 0, 0, h)
    peakGrad.addColorStop(0, 'rgba(245, 158, 11, 0.32)')
    peakGrad.addColorStop(1, 'rgba(245, 158, 11, 0.06)')
    ctx.fillStyle = peakGrad
    ctx.fillRect(x1, 0, pw, h)

    ctx.strokeStyle = 'rgba(251, 191, 36, 0.85)'
    ctx.lineWidth = 1.5
    ctx.strokeRect(x1, 1, pw, h - 2)
  })

  // 绘制渐变填充与能量折线
  const points = 130
  const coords = []
  for (let i = 0; i < points; i++) {
    const x = (i / (points - 1)) * w
    const timeAtX = (i / (points - 1)) * totalSec
    const inPeak = props.peaks.some(p => timeAtX >= p.start_time && timeAtX <= p.end_time)
    const wave = Math.sin(i * 0.45) * 0.08 + Math.cos(i * 0.9) * 0.06
    const ratio = inPeak ? (0.68 + Math.abs(wave) * 1.6) : (0.24 + Math.abs(wave))
    const y = Math.max(10, Math.min(h - 10, h - ratio * h * 0.85 - 6))
    coords.push({ x, y })
  }

  // 底部面积渐变着色
  const areaGrad = ctx.createLinearGradient(0, 0, 0, h)
  areaGrad.addColorStop(0, 'rgba(99, 102, 241, 0.35)')
  areaGrad.addColorStop(1, 'rgba(6, 182, 212, 0.0)')

  ctx.beginPath()
  ctx.moveTo(0, h)
  coords.forEach(pt => ctx.lineTo(pt.x, pt.y))
  ctx.lineTo(w, h)
  ctx.closePath()
  ctx.fillStyle = areaGrad
  ctx.fill()

  // 顶部能量主包络线
  const lineGrad = ctx.createLinearGradient(0, 0, w, 0)
  lineGrad.addColorStop(0, '#6366F1')
  lineGrad.addColorStop(0.5, '#38BDF8')
  lineGrad.addColorStop(1, '#818CF8')

  ctx.beginPath()
  coords.forEach((pt, idx) => {
    if (idx === 0) ctx.moveTo(pt.x, pt.y)
    else ctx.lineTo(pt.x, pt.y)
  })
  ctx.strokeStyle = lineGrad
  ctx.lineWidth = 2
  ctx.stroke()
}

watch(() => props.peaks, () => {
  stats.value.duration = props.totalDuration ? props.totalDuration.toFixed(1) : '-'
  stats.value.avgEnergy = props.avgEnergy ? props.avgEnergy.toFixed(0) : '-'
  stats.value.peaksCount = props.peaks.length
  renderCanvas()
}, { deep: true })

onMounted(() => {
  renderCanvas()
})
</script>

<style scoped>
.waveform-card {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.waveform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-row {
  display: flex;
  gap: 14px;
  font-size: 0.72rem;
  color: var(--text-sub);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.dot.base {
  background: linear-gradient(135deg, #6366F1, #38BDF8);
}
.dot.peak {
  background: #F59E0B;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.8);
}

.canvas-box {
  background: rgba(4, 6, 11, 0.75);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-subtle);
  overflow: hidden;
  height: 124px;
  box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.6);
}

canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.stats-bar {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.stat-chip {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  padding: 6px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.72rem;
}

.stat-chip.highlight {
  background: rgba(245, 158, 11, 0.07);
  border-color: rgba(245, 158, 11, 0.25);
}

.stat-label {
  color: var(--text-muted);
}

.stat-val {
  color: var(--text-main);
  font-weight: 700;
}

.stat-chip.highlight .stat-val {
  color: var(--gold-light);
}
</style>
