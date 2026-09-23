import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from 'axios'
import type { VolumeData, ROIResult, ROIDef, ROIAnalyzeResponse } from '@/types'

const ROIS_KEY = 'miv-rois'
const RESULTS_KEY = 'miv-roi-results'

function genId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `roi-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function loadPersisted<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch {
    return fallback
  }
}

function errorResult(roi: ROIDef, code: string, message: string): ROIResult {
  return {
    id: roi.id, label: roi.label, center: [...roi.center], radius: roi.radius,
    status: 'error', errorCode: code, message, retryable: true,
    mean: 0, std: 0, min: 0, max: 0, voxelCount: 0, histogram: [],
    preset: undefined, measuredAt: Date.now(),
  }
}

export const useImagingStore = defineStore('imaging', () => {
  const loading = ref(false)
  const volumeData = ref<VolumeData | null>(null)
  const preset = ref(localStorage.getItem('miv-preset') || 'brain')
  const windowVal = ref(80)
  const levelVal = ref(40)
  const mprSlice = ref({ axial: 32, coronal: 32, sagittal: 32 })

  const rois = ref<ROIDef[]>(loadPersisted<ROIDef[]>(ROIS_KEY, [
    { id: genId(), label: 'lesion1', center: [30, 28, 32], radius: 6 }
  ]))
  const roiResults = ref<ROIResult[]>(loadPersisted<ROIResult[]>(RESULTS_KEY, []))

  watch(rois, (v) => localStorage.setItem(ROIS_KEY, JSON.stringify(v)), { deep: true })
  watch(roiResults, (v) => localStorage.setItem(RESULTS_KEY, JSON.stringify(v)), { deep: true })
  watch(preset, (v) => localStorage.setItem('miv-preset', v))

  async function loadVolume() {
    loading.value = true
    try {
      const { data } = await axios.post('/api/volume', {
        preset: preset.value, width: 64, height: 64, depth: 64
      })
      volumeData.value = data
      mprSlice.value = { axial: 32, coronal: 32, sagittal: 32 }
    } finally { loading.value = false }
  }

  /** Merge one ROI's result into the result list (keyed by ROI id). */
  function upsertResult(result: ROIResult) {
    const idx = roiResults.value.findIndex(r => r.id === result.id)
    if (idx >= 0) roiResults.value.splice(idx, 1, result)
    else roiResults.value.push(result)
  }

  async function analyzeROI(ids?: string[]) {
    const targets = rois.value.filter(r => !ids || ids.includes(r.id))
    if (!targets.length) return
    loading.value = true
    try {
      if (!volumeData.value?.volume) {
        targets.forEach(r => upsertResult(errorResult(r, 'NO_VOLUME', '尚未载入影像数据，请先点击“载入影像”后重试')))
        return
      }
      let data: ROIAnalyzeResponse
      try {
        const resp = await axios.post<ROIAnalyzeResponse>('/api/roi', {
          volume: volumeData.value.volume,
          rois: targets.map(({ id, label, center, radius }) => ({ id, label, center, radius }))
        })
        data = resp.data
      } catch {
        targets.forEach(r => upsertResult(errorResult(r, 'NETWORK_ERROR', '测量请求失败（服务不可用或网络异常），请检查服务后重试')))
        return
      }

      // Global-level failure (e.g. corrupt volume): surface it per ROI
      if (data.status === 'error') {
        targets.forEach(r => upsertResult(errorResult(r, data.errorCode ?? 'UNKNOWN', data.message ?? '测量失败，请重试')))
        return
      }

      targets.forEach((target) => {
        const r = data.rois.find(x => x.id === target.id)
        if (!r) {
          upsertResult(errorResult(target, 'NO_RESULT', '服务未返回该区域的测量结果，请重试'))
          return
        }
        // Keep label/geometry in sync with the current definition
        r.label = target.label
        r.center = [...target.center]
        r.radius = target.radius
        r.preset = preset.value
        r.measuredAt = Date.now()
        upsertResult(r)
      })
    } finally { loading.value = false }
  }

  function retryROI(id: string) { return analyzeROI([id]) }

  function addROI() {
    rois.value.push({ id: genId(), label: `roi-${rois.value.length + 1}`, center: [32, 32, 32], radius: 8 })
  }

  function removeROI(id: string) {
    rois.value = rois.value.filter(r => r.id !== id)
    roiResults.value = roiResults.value.filter(r => r.id !== id)
  }

  function clearResults() { roiResults.value = [] }

  function applyWindow(w: number, l: number) { windowVal.value = w; levelVal.value = l }

  return { loading, volumeData, preset, windowVal, levelVal, mprSlice,
    rois, roiResults, loadVolume, analyzeROI, retryROI, addROI, removeROI, clearResults, applyWindow }
})
