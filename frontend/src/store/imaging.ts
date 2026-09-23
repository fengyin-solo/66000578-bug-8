import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from 'axios'
import type { VolumeData, ROIResult, ROIDef } from '@/types'

const STORAGE_KEY = 'miv-roi-state-v1'

interface PersistedState {
  version: 1
  /** 数据键：预设+体数据尺寸，尺寸变化后旧结果不再展示（避免与新数据错位） */
  dataKey: string
  preset: string
  rois: ROIDef[]
  results: ROIResult[]
}

function makeDataKey(preset: string, dims?: number[]) {
  return dims ? `${preset}:${dims.join('x')}` : preset
}

function loadPersisted(): PersistedState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedState
    if (parsed.version !== 1 || !Array.isArray(parsed.rois)) return null
    return parsed
  } catch {
    return null
  }
}

let idSeq = 0
export function newROIId() {
  idSeq += 1
  return `roi-${Date.now().toString(36)}-${idSeq}`
}

export const useImagingStore = defineStore('imaging', () => {
  const loading = ref(false)
  const volumeData = ref<VolumeData | null>(null)
  const preset = ref('brain')
  const windowVal = ref(80)
  const levelVal = ref(40)
  const roiResults = ref<ROIResult[]>([])
  const mprSlice = ref({ axial: 32, coronal: 32, sagittal: 32 })

  const rois = ref<ROIDef[]>([{ id: newROIId(), label: 'lesion1', center: [30, 28, 32], radius: 6 }])

  /** 数据级错误（载入失败 / 测量请求整体失败），页面展示重试入口 */
  const volumeError = ref('')
  const analyzeError = ref('')
  /** 正在测量中的 ROI id（单个重试时只转对应那一张卡片） */
  const analyzingIds = ref<Set<string>>(new Set())

  const persisted = loadPersisted()

  function persist() {
    if (!volumeData.value) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        version: 1,
        dataKey: makeDataKey(preset.value, volumeData.value.dimensions),
        preset: preset.value,
        rois: rois.value,
        results: roiResults.value,
      } satisfies PersistedState))
    } catch {
      /* 存储满 / 隐私模式等：持久化失败不影响本次使用 */
    }
  }

  async function loadVolume() {
    loading.value = true
    volumeError.value = ''
    try {
      const { data } = await axios.post('/api/volume', {
        preset: preset.value, width: 64, height: 64, depth: 64
      })
      volumeData.value = data
      mprSlice.value = { axial: 32, coronal: 32, sagittal: 32 }

      // 恢复同一份数据上的 ROI 配置与历史测量结果；不同数据则从干净状态开始
      const key = makeDataKey(preset.value, data.dimensions)
      const saved = loadPersisted()
      if (saved && saved.dataKey === key) {
        rois.value = saved.rois
        roiResults.value = saved.results
      } else {
        rois.value = [{ id: newROIId(), label: 'lesion1', center: [30, 28, 32], radius: 6 }]
        roiResults.value = []
      }
    } catch (e: any) {
      volumeError.value = e?.response?.data?.detail
        || e?.message
        || '影像载入失败，请检查后端服务后重试'
    } finally {
      loading.value = false
    }
  }

  async function analyzeROI(targetIds?: string[]) {
    if (!volumeData.value) {
      analyzeError.value = '尚未载入影像，请先载入影像后再测量'
      return
    }
    const targets = targetIds
      ? rois.value.filter(r => targetIds.includes(r.id))
      : rois.value
    if (!targets.length) return

    analyzeError.value = ''
    targets.forEach(r => analyzingIds.value.add(r.id))
    try {
      const { data } = await axios.post('/api/roi', {
        volume: volumeData.value.volume,
        rois: targets.map(r => ({ ...r })),
      })

      // 按 id 合并：只更新本次测量的 ROI，其余历史结果原样保留
      const incoming = new Map<string, ROIResult>()
      for (const r of (data.rois || []) as ROIResult[]) {
        if (r.id) incoming.set(r.id, { ...r, measuredAt: Date.now() })
      }
      const next: ROIResult[] = []
      const seen = new Set<string>()
      for (const def of rois.value) {
        seen.add(def.id)
        const fresh = incoming.get(def.id)
        if (fresh) next.push(fresh)
        else {
          const prev = roiResults.value.find(p => p.id === def.id)
          if (prev) next.push(prev)
        }
      }
      roiResults.value = next
      persist()
    } catch (e: any) {
      // 整体失败（如数据源异常）：不覆盖已有结果，给出原因与重试入口
      analyzeError.value = e?.response?.data?.detail
        || e?.message
        || '测量请求失败，请稍后重试'
    } finally {
      targets.forEach(r => analyzingIds.value.delete(r.id))
    }
  }

  function addROI() {
    rois.value.push({
      id: newROIId(),
      label: `roi-${rois.value.length + 1}`,
      center: [32, 32, 32],
      radius: 8,
    })
  }

  function removeROI(id: string) {
    rois.value = rois.value.filter(r => r.id !== id)
    roiResults.value = roiResults.value.filter(r => r.id !== id)
    analyzingIds.value.delete(id)
    persist()
  }

  function applyWindow(w: number, l: number) { windowVal.value = w; levelVal.value = l }

  // 刷新前已完成恢复；之后配置/结果变化随时落盘
  watch([rois, roiResults], persist, { deep: true })

  // 存在历史会话时：自动重新拉取对应预设的体数据，并从本地还原 ROI 配置与结果；
  // 无历史会话则停留在首屏占位，由用户手动载入。
  if (persisted) {
    preset.value = persisted.preset
    loadVolume()
  }

  return {
    loading, volumeData, preset, windowVal, levelVal, roiResults, mprSlice,
    rois, volumeError, analyzeError, analyzingIds,
    loadVolume, analyzeROI, addROI, removeROI, applyWindow,
  }
})
