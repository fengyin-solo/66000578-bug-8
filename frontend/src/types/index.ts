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

export type ROIStatus = 'ok' | 'error'

export interface ROIResult {
  id?: string
  label: string
  center: number[]
  radius: number
  status: ROIStatus
  /** 成功时的提示（区域被边界裁剪 / 跳过了异常体素） */
  warning?: string | null
  /** 失败原因码，如 outside_volume / data_anomaly / invalid_center ... */
  errorCode?: string
  /** 失败原因说明 */
  errorMessage?: string
  mean?: number
  std?: number
  min?: number
  max?: number
  voxelCount?: number
  histogram?: number[]
  /** 直方图各桶边界（长度 = histogram.length + 1） */
  histogramEdges?: number[]
  /** 测量时间戳（本地持久化用） */
  measuredAt?: number
}
