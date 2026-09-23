<template>
  <div class="panel">
    <h4>📐 ROI感兴趣区域分析</h4>
    <el-button size="small" @click="store.addROI()" style="margin-bottom:8px">+ 添加ROI</el-button>

    <div v-for="(roi, i) in store.rois" :key="roi.id" class="roi-config">
      <div class="roi-row">
        <span class="roi-no">ROI #{{ i + 1 }}</span>
        <el-input v-model="roi.label" size="small" placeholder="标签" style="width:90px"/>
        <el-tag v-if="labelDupCount(roi.label) > 1" size="small" type="warning" effect="dark" class="dup-tag">
          同名 {{dupIndex(roi)}}/{{labelDupCount(roi.label)}}
        </el-tag>
      </div>
      <div class="roi-row">
        <span class="coord-hint">x,y,z</span>
        <el-input-number v-for="(c, ci) in roi.center" :key="ci" v-model="roi.center[ci]" size="small"
          :min="0" :max="dim - 1" style="width:72px" controls-position="right"/>
        <el-input-number v-model="roi.radius" size="small" :min="1" :max="30" style="width:70px" controls-position="right"/>
        <el-button size="small" type="danger" @click="store.removeROI(roi.id)" circle>×</el-button>
      </div>
    </div>

    <div class="action-row">
      <el-button type="success" size="small" @click="store.analyzeROI()"
        :loading="store.loading" :disabled="!store.rois.length">📊 测量全部ROI</el-button>
      <el-button size="small" @click="store.clearResults()" :disabled="!store.roiResults.length">清空结果</el-button>
    </div>

    <div v-if="store.roiResults.length" class="results">
      <div v-for="(r, i) in orderedResults" :key="r.id" class="roi-result" :class="`is-${r.status}`">
        <div class="r-head">
          <span class="r-label">{{ displayLabel(r) }}</span>
          <span class="r-id">#{{ r.id.slice(0, 6) }}</span>
          <el-tag v-if="r.status === 'error'" size="small" type="danger" effect="dark">测量失败</el-tag>
          <el-tag v-else-if="r.status === 'partial'" size="small" type="warning" effect="dark">部分出界</el-tag>
          <el-tag v-else size="small" type="success" effect="dark">成功</el-tag>
        </div>

        <div v-if="isStale(r)" class="stale-hint">
          ⚠ 参数已修改或影像预设不同，结果可能已失效，建议重新测量
        </div>

        <div v-if="r.status === 'error'" class="error-box">
          <div class="error-msg">{{ r.message || '测量失败，请重试' }}</div>
          <el-button size="small" type="warning" plain :loading="store.loading" @click="store.retryROI(r.id)">
            🔄 重试该区域
          </el-button>
        </div>

        <template v-else>
          <div v-if="r.status === 'partial'" class="partial-hint">{{ r.message }}</div>
          <div class="r-stats">
            <div class="stat"><span>均值</span><b>{{ r.mean }}</b> HU</div>
            <div class="stat"><span>标准差</span><b>{{ r.std }}</b></div>
            <div class="stat"><span>范围</span><b>{{ r.min }}~{{ r.max }}</b></div>
            <div class="stat"><span>体素</span><b>{{ r.voxelCount }}</b></div>
          </div>
          <div class="hist-title">体素值分布</div>
          <HistogramChart :counts="r.histogram" :edges="r.histogramEdges" />
          <div class="meta-row">
            <span>{{ r.preset ? presetName(r.preset) : '' }} · {{ formatTime(r.measuredAt) }}</span>
            <el-button size="small" link type="primary" :loading="store.loading" @click="store.retryROI(r.id)">重新测量</el-button>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="empty-hint">
      暂无测量结果。配置好ROI中心点与半径后点击「测量全部ROI」。
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useImagingStore } from '../store/imaging'
import HistogramChart from './HistogramChart.vue'
import type { ROIResult, ROIDef } from '../types'

const store = useImagingStore()
const dim = computed(() => store.volumeData?.dimensions?.[0] ?? 64)

/** Results shown in the same order as the current ROI definitions; orphans appended. */
const orderedResults = computed(() => {
  const byId = new Map(store.roiResults.map(r => [r.id, r]))
  const ordered: ROIResult[] = []
  store.rois.forEach(roi => { const r = byId.get(roi.id); if (r) { ordered.push(r); byId.delete(roi.id) } })
  return ordered.concat(...byId.values())
})

const PRESET_NAMES: Record<string, string> = { brain: '头部CT', chest: '胸部CT', abdomen: '腹部CT' }
function presetName(p: string) { return PRESET_NAMES[p] ?? p }
function formatTime(t?: number) {
  if (!t) return ''
  const d = new Date(t)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function labelDupCount(label: string) {
  return store.rois.filter(r => r.label === label).length
}
function dupIndex(roi: ROIDef) {
  return store.rois.filter(r => r.label === roi.label).findIndex(r => r.id === roi.id) + 1
}

function displayLabel(r: ROIResult) {
  const sameLabel = orderedResults.value.filter(x => x.label === r.label)
  if (sameLabel.length > 1) {
    const idx = sameLabel.findIndex(x => x.id === r.id) + 1
    return `${r.label}（第${idx}个）`
  }
  return r.label
}

function isStale(r: ROIResult) {
  if (r.status === 'error') return false
  if (r.preset && r.preset !== store.preset) return true
  const def = store.rois.find(x => x.id === r.id)
  if (!def) return false
  if (def.label !== r.label || def.radius !== r.radius) return true
  return def.center.some((c, ci) => c !== r.center[ci])
}
</script>

<style scoped>
.panel { background:#161b22; border-radius:6px; padding:10px; border:1px solid #30363d }
.panel h4 { color:#58a6ff; font-size:12px; margin-bottom:8px }
.roi-config { padding:4px 0; border-bottom:1px dashed #21262d }
.roi-row { display:flex; gap:3px; align-items:center; padding:3px 0; font-size:11px; flex-wrap:wrap }
.roi-no { color:#c9d1d9; min-width:52px }
.coord-hint { color:#8b949e; font-size:10px; width:26px }
.dup-tag { margin-left:2px }
.action-row { display:flex; gap:8px; margin-top:8px }
.results { margin-top:10px; display:flex; flex-direction:column; gap:8px }
.roi-result { background:#0d1117; border-radius:4px; padding:8px; border:1px solid #30363d }
.roi-result.is-error { border-color:#6e2332 }
.roi-result.is-partial { border-color:#7d5c10 }
.r-head { display:flex; align-items:center; gap:6px; margin-bottom:4px }
.r-label { font-size:12px; color:#e6edf3; font-weight:600 }
.r-id { font-size:9px; color:#6e7681; font-family:monospace }
.r-stats { display:grid; grid-template-columns:1fr 1fr; gap:4px }
.stat { font-size:10px; color:#8b949e; padding:3px 4px; background:#161b22; border-radius:3px }
.stat b { color:#e6edf3; margin-left:4px }
.hist-title { font-size:10px; color:#8b949e; margin-top:6px }
.meta-row { display:flex; justify-content:space-between; align-items:center; margin-top:2px; font-size:9px; color:#6e7681 }
.error-box { display:flex; flex-direction:column; gap:6px; padding:4px 0 }
.error-msg { font-size:11px; color:#ff7b72; line-height:1.5 }
.partial-hint { font-size:10px; color:#d29922; margin-bottom:4px }
.stale-hint { font-size:10px; color:#d29922; background:#2d2410; border-radius:3px; padding:4px 6px; margin-bottom:4px }
.empty-hint { margin-top:10px; font-size:11px; color:#6e7681; text-align:center; padding:10px; border:1px dashed #30363d; border-radius:4px }
</style>
