<template>
  <div class="panel">
    <h4>📐 ROI感兴趣区域分析</h4>
    <el-button size="small" @click="store.addROI()" style="margin-bottom:8px">+ 添加ROI</el-button>

    <div v-for="(roi,i) in store.rois" :key="roi.id" class="roi-config">
      <div class="roi-row">
        <span class="roi-index">#{{ i+1 }}</span>
        <el-input v-model="roi.label" size="small" placeholder="标签" style="width:80px"/>
        <el-tooltip v-if="labelCounts.get(roi.label)! > 1" content="存在同名区域，结果将按编号区分，不会互相覆盖" placement="top">
          <el-tag size="small" type="warning" effect="dark" class="dup-tag">同名×{{ labelCounts.get(roi.label) }}</el-tag>
        </el-tooltip>
        <el-input-number v-model="roi.center[0]" size="small" :min="0" :max="maxXYZ[0]-1" style="width:62px" controls-position="right"/>
        <el-input-number v-model="roi.center[1]" size="small" :min="0" :max="maxXYZ[1]-1" style="width:62px" controls-position="right"/>
        <el-input-number v-model="roi.center[2]" size="small" :min="0" :max="maxXYZ[2]-1" style="width:62px" controls-position="right"/>
        <el-input-number v-model="roi.radius" size="small" :min="1" :max="20" style="width:58px" controls-position="right"/>
        <el-button size="small" type="danger" @click="store.removeROI(roi.id)" circle>×</el-button>
      </div>
    </div>

    <el-button type="success" size="small" @click="store.analyzeROI()"
      :loading="store.loading || allAnalyzing"
      :disabled="!store.volumeData || !store.rois.length"
      style="margin-top:8px">📊 分析ROI</el-button>

    <!-- 整体失败（数据源异常 / 请求失败）：保留历史结果并提示原因 -->
    <el-alert v-if="store.analyzeError" type="error" :closable="false" show-icon
      :title="store.analyzeError" class="analyze-error">
      <el-button size="small" type="primary" @click="store.analyzeROI()">重试测量</el-button>
    </el-alert>

    <div v-if="orderedResults.length" class="results">
      <div v-for="(r, idx) in orderedResults" :key="r.id" class="roi-result" :class="{ 'is-error': r.status === 'error' }">
        <div class="r-head">
          <span class="r-label">{{ r.label }}</span>
          <el-tag v-if="labelCounts.get(r.label)! > 1" size="small" type="warning" effect="plain" class="dup-badge">
            #{{ duplicateOrdinal(r.id, r.label) }}
          </el-tag>
          <span v-if="r.measuredAt" class="r-time">{{ formatTime(r.measuredAt) }}</span>
          <el-button v-if="r.status === 'error'" size="small" type="primary" plain
            :loading="store.analyzingIds.has(r.id!)" @click="store.analyzeROI([r.id!])">重试</el-button>
        </div>

        <!-- 测不到 / 数据异常：明确说明原因，而不是留空白 -->
        <template v-if="r.status === 'error'">
          <el-alert type="warning" :closable="false" show-icon class="reason">
            <div class="reason-title">{{ r.errorMessage || '测量失败' }}</div>
            <div class="reason-code" v-if="r.errorCode">原因码：{{ r.errorCode }}</div>
          </el-alert>
        </template>

        <template v-else>
          <el-alert v-if="r.warning" type="info" :closable="false" show-icon
            :title="r.warning" class="clip-warn"/>
          <div class="r-stats">
            <div class="stat"><span>均值</span><b>{{ r.mean }}</b> HU</div>
            <div class="stat"><span>标准差</span><b>{{ r.std }}</b></div>
            <div class="stat"><span>范围</span><b>{{ r.min }}~{{ r.max }}</b></div>
            <div class="stat"><span>体素</span><b>{{ r.voxelCount }}</b></div>
          </div>
          <div class="hist-title">体素值分布 (HU)</div>
          <ROIHistogram :counts="r.histogram || []" :edges="r.histogramEdges || []" />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useImagingStore } from '../store/imaging'
import ROIHistogram from './ROIHistogram.vue'
import type { ROIResult } from '../types'

const store = useImagingStore()

const maxXYZ = computed<[number, number, number]>(() => {
  const dims = store.volumeData?.dimensions
  // dimensions 来自后端，顺序为 [z(depth), y(height), x(width)]
  return dims ? [dims[2], dims[1], dims[0]] : [64, 64, 64]
})

/** 同名标签出现次数，用于标注重复命名 */
const labelCounts = computed(() => {
  const m = new Map<string, number>()
  for (const r of store.rois) m.set(r.label, (m.get(r.label) || 0) + 1)
  return m
})

/** 同名区域在列表中的序号（从 1 开始），让重名结果也能一一对应 */
function duplicateOrdinal(id: string | undefined, label: string) {
  return store.rois.filter(r => r.label === label).findIndex(r => r.id === id) + 1
}

/** 结果按当前 ROI 定义顺序展示（id 对齐，绝不因同名合并） */
const orderedResults = computed(() =>
  store.rois
    .map(def => store.roiResults.find(r => r.id === def.id))
    .filter((r): r is ROIResult => !!r)
)

const allAnalyzing = computed(() =>
  store.rois.length > 0 && store.rois.every(r => store.analyzingIds.has(r.id)))

function formatTime(ts: number) {
  const d = new Date(ts)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.panel { background:#161b22; border-radius:6px; padding:10px; border:1px solid #30363d }
.panel h4 { color:#58a6ff; font-size:12px; margin-bottom:8px }
.roi-row { display:flex; gap:3px; align-items:center; padding:4px 0; font-size:11px; flex-wrap:wrap }
.roi-index { color:#8b949e; min-width:22px }
.dup-tag { transform:scale(0.85); transform-origin:left center }
.results { margin-top:10px; display:flex; flex-direction:column; gap:8px }
.roi-result { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:6px 8px }
.roi-result.is-error { border-color:#9e6a03 }
.r-head { display:flex; align-items:center; gap:6px; margin-bottom:4px }
.r-label { font-size:12px; color:#e6edf3; font-weight:600 }
.dup-badge { transform:scale(0.9); transform-origin:left center }
.r-time { margin-left:auto; font-size:9px; color:#6e7681 }
.r-stats { display:grid; grid-template-columns:1fr 1fr; gap:4px }
.stat { font-size:10px; color:#8b949e; padding:3px 4px; background:#161b22; border-radius:3px }
.stat b { color:#e6edf3; margin-left:4px }
.hist-title { font-size:9px; color:#8b949e; margin-top:6px }
.analyze-error { margin-top:8px }
.analyze-error :deep(.el-alert__content) { display:flex; flex-direction:column; align-items:flex-start; gap:4px }
.clip-warn { margin:2px 0 6px }
.clip-warn :deep(.el-alert__title) { font-size:10px; line-height:1.4 }
.reason { background:#1c1506; border:none }
.reason :deep(.el-alert__title) { font-size:10px; line-height:1.4; color:#e3b341 }
.reason-title { color:#e3b341 }
.reason-code { color:#8b949e; font-size:9px; margin-top:2px }
</style>
