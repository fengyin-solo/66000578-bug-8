export interface WindowPreset { window: number; level: number; desc: string }
export interface VolumeData {
  volume: number[][][]
  dimensions: [number, number, number]
  mpr: { axial: number[][]; coronal: number[][]; sagittal: number[][] }
  preset: string
  windowPresets: Record<string, WindowPreset>
}

export interface ROIDef {
  id: string
  label: string
  center: number[]
  radius: number
}

export type ROIResultStatus = 'ok' | 'partial' | 'error'

export interface ROIResult {
  id: string
  label: string
  center: number[]
  radius: number
  status: ROIResultStatus
  message?: string
  errorCode?: string
  retryable?: boolean
  mean: number
  std: number
  min: number
  max: number
  voxelCount: number
  histogram: number[]
  histogramEdges?: number[]
  /** client-side metadata */
  preset?: string
  measuredAt?: number
}

export interface ROIAnalyzeResponse {
  status: 'ok' | 'error'
  errorCode?: string
  message?: string
  rois: ROIResult[]
}
