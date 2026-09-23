import random, math
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Medical Imaging Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class VolumeRequest(BaseModel):
    preset: str = "brain"  # brain / chest / abdomen
    width: int = 64
    height: int = 64
    depth: int = 64


class ROIRequest(BaseModel):
    center: list = [32, 32, 32]
    radius: int = 10
    label: str = "lesion"


class WindowLevelRequest(BaseModel):
    window: float = 400.0
    level: float = 40.0
    preset: str = "brain"


WINDOW_PRESETS = {
    "lung":     {"window": 1500, "level": -600, "desc": "肺窗 (W1500/L-600)"},
    "mediastinum": {"window": 350, "level": 50, "desc": "纵隔窗 (W350/L50)"},
    "bone":     {"window": 2000, "level": 300, "desc": "骨窗 (W2000/L300)"},
    "brain":    {"window": 80, "level": 40, "desc": "脑窗 (W80/L40)"},
    "abdomen":  {"window": 400, "level": 40, "desc": "腹窗 (W400/L40)"},
}


def generate_volume(preset: str, w: int, h: int, d: int):
    """Generate synthetic CT-like volume"""
    np.random.seed(42)
    vol = np.zeros((d, h, w), dtype=np.float32)

    center_x, center_y, center_z = w//2, h//2, d//2
    for z in range(d):
        for y in range(h):
            for x in range(w):
                # Head-like shape
                rx = (x - center_x - 5) / (w * 0.4)
                ry = (y - center_y) / (h * 0.45)
                rz = (z - center_z + 3) / (d * 0.4)
                dist = math.sqrt(rx**2 + ry**2 + rz**2)

                if preset == "brain":
                    if dist < 0.85:
                        # Brain tissue
                        base = 35
                        # Sulci pattern
                        noise = (np.sin(x * 0.4) * np.cos(y * 0.3) + np.sin(z * 0.35)) * 8
                        # Ventricles (CSF)
                        vent_dist = math.sqrt(((x-center_x+2)/(w*0.15))**2 + ((y-center_y)/(h*0.12))**2 + ((z-center_z)/(d*0.1))**2)
                        if vent_dist < 0.6:
                            base = 10 + noise * 0.3
                        # Skull
                        if dist > 0.7 and dist < 0.85:
                            base = 200 + random.uniform(-20, 20)
                        vol[z, y, x] = base + noise
                    elif dist < 0.9:
                        vol[z, y, x] = 100  # Scalp
                elif preset == "chest":
                    # Body oval
                    bx = (x - center_x) / (w * 0.35)
                    by = (y - center_y) / (h * 0.4)
                    body = math.sqrt(bx**2 + by**2)
                    if body < 1.0:
                        # Lungs (dark)
                        lung_dist1 = math.sqrt(((x-center_x+8)/(w*0.12))**2 + ((y-center_y)/(h*0.13))**2)
                        lung_dist2 = math.sqrt(((x-center_x-8)/(w*0.12))**2 + ((y-center_y)/(h*0.13))**2)
                        if lung_dist1 < 0.7 or lung_dist2 < 0.7:
                            vol[z, y, x] = -650 + np.sin(z*0.3)*30
                        else:
                            vol[z, y, x] = 30 + np.random.uniform(-5, 5)
                        # Spine
                        if abs(x - center_x) < 3 and abs(y - center_y + 8) < 4:
                            vol[z, y, x] = 250
                    vol[z, y, x] += np.random.uniform(-3, 3)
                elif preset == "abdomen":
                    bx = (x - center_x) / (w * 0.33)
                    by = (y - center_y) / (h * 0.4)
                    body = math.sqrt(bx**2 + by**2)
                    if body < 1.0:
                        base = 35
                        # Liver (right upper)
                        lv = math.sqrt(((x-center_x-6)/(w*0.08))**2 + ((y-center_y+4)/(h*0.07))**2)
                        if lv < 0.6:
                            base = 55 + np.random.uniform(-5, 5)
                        # Kidneys
                        kd1 = math.sqrt(((x-center_x-5)/(w*0.04))**2 + ((y-center_y-5)/(h*0.04))**2)
                        kd2 = math.sqrt(((x-center_x+5)/(w*0.04))**2 + ((y-center_y-5)/(h*0.04))**2)
                        if kd1 < 0.4 or kd2 < 0.4:
                            base = 45
                        # Spine
                        if abs(x - center_x) < 3 and abs(y - center_y + 7) < 4:
                            base = 250 + np.random.uniform(-10, 10)
                        vol[z, y, x] = base + np.random.uniform(-9, 9)

    return vol.tolist()


@app.post("/api/volume")
def get_volume(req: VolumeRequest):
    vol = generate_volume(req.preset, req.width, req.height, req.depth)

    # Extract mid slices for MPR
    mid_axial = int(req.depth // 2)
    mid_coronal = int(req.height // 2)
    mid_sagittal = int(req.width // 2)

    # Return: 3D volume + 3 MPR slices
    return {
        "volume": vol,
        "dimensions": [req.depth, req.height, req.width],
        "mpr": {
            "axial": vol[mid_axial],
            "coronal": [[vol[z][mid_coronal][x] for x in range(req.width)] for z in range(req.depth)],
            "sagittal": [[vol[z][y][mid_sagittal] for y in range(req.height)] for z in range(req.depth)]
        },
        "preset": req.preset,
        "windowPresets": WINDOW_PRESETS
    }


class ROIAnalyzeRequest(BaseModel):
    volume: list
    rois: list = []


def _fail(roi: dict, code: str, message: str) -> dict:
    return {
        "id": roi.get("id"),
        "label": str(roi.get("label") or "roi"),
        "center": roi.get("center"),
        "radius": roi.get("radius"),
        "status": "error",
        "errorCode": code,
        "errorMessage": message,
    }


@app.post("/api/roi")
def analyze_roi(req: ROIAnalyzeRequest):
    # ---- 数据源级校验：数据缺失 / 结构异常时直接返回明确错误 ----
    if req.volume is None:
        raise HTTPException(status_code=400, detail="未收到体数据，请先载入影像后再测量")
    try:
        vol = np.array(req.volume, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=400, detail="体数据格式异常，无法解析为三维数组")
    if vol.size == 0:
        raise HTTPException(status_code=400, detail="体数据为空，没有可测量的影像内容")
    if vol.ndim != 3:
        raise HTTPException(status_code=400, detail=f"体数据维度异常：期望三维数组，实际为 {vol.ndim} 维")
    d, h, w = vol.shape
    # 注：体数据中的缺失值(NaN/Inf)在各 ROI 内逐区域处理——部分异常跳过并警告，
    # 全部异常才判该区域失败，避免个别坏体素让整次测量不可用。

    results = []
    for roi in req.rois:
        if not isinstance(roi, dict):
            results.append(_fail(roi if isinstance(roi, dict) else {},
                                 "invalid_roi", "该区域参数格式异常"))
            continue

        center = roi.get("center")
        radius = roi.get("radius")

        # ---- 参数校验 ----
        if not isinstance(center, list) or len(center) != 3:
            results.append(_fail(roi, "invalid_center", "球心坐标缺失或格式错误，需要 [x, y, z] 三个值"))
            continue
        try:
            cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        except (TypeError, ValueError):
            results.append(_fail(roi, "invalid_center", "球心坐标不是有效数值"))
            continue
        if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(cz)):
            results.append(_fail(roi, "invalid_center", "球心坐标包含空值或非数值"))
            continue

        try:
            radius = float(radius)
        except (TypeError, ValueError):
            results.append(_fail(roi, "invalid_radius", "半径不是有效数值"))
            continue
        if not math.isfinite(radius) or radius <= 0:
            results.append(_fail(roi, "invalid_radius", "半径必须为大于 0 的数值"))
            continue
        if radius > 10000:
            results.append(_fail(roi, "invalid_radius", f"半径 {radius:g} 过大，请检查是否填错单位"))
            continue

        r = int(math.ceil(radius))

        # ---- 区域是否完全落在影像之外 ----
        if (cx + radius < 0 or cy + radius < 0 or cz + radius < 0
                or cx - radius > w - 1 or cy - radius > h - 1 or cz - radius > d - 1):
            results.append(_fail(
                roi, "outside_volume",
                f"球形区域完全位于影像之外（影像范围 x:0~{w-1}, y:0~{h-1}, z:0~{d-1}），未测到任何体素。"
                "请调整球心坐标后重试"
            ))
            continue

        x0, x1 = max(0, int(cx) - r), min(w, int(cx) + r + 1)
        y0, y1 = max(0, int(cy) - r), min(h, int(cy) + r + 1)
        z0, z1 = max(0, int(cz) - r), min(d, int(cz) + r + 1)

        # 完整球（未被边界裁剪时）的理论体素数，用于判断是否被裁剪
        gx, gy, gz = np.mgrid[-r:r+1, -r:r+1, -r:r+1]
        full_sphere_count = int(np.count_nonzero(gx**2 + gy**2 + gz**2 <= radius**2))

        zz, yy, xx = np.mgrid[z0:z1, y0:y1, x0:x1]
        mask = (xx - cx)**2 + (yy - cy)**2 + (zz - cz)**2 <= radius**2
        voxels = vol[z0:z1, y0:y1, x0:x1][mask]
        voxel_count = int(voxels.size)

        if voxel_count == 0:
            results.append(_fail(
                roi, "empty_region",
                "区域与影像没有交集，未测到任何体素，请调整球心或半径后重试"
            ))
            continue

        finite = voxels[np.isfinite(voxels)]
        bad_count = voxel_count - int(finite.size)
        if finite.size == 0:
            results.append(_fail(
                roi, "data_anomaly",
                f"区域内 {voxel_count} 个体素全部为缺失值(NaN)或无穷值(Inf)，无法计算统计量"
            ))
            continue

        vmin, vmax = float(finite.min()), float(finite.max())
        if vmax > vmin:
            counts, edges = np.histogram(finite, bins=10, range=(vmin, vmax))
            histogram = counts.tolist()
            bin_edges = [round(float(e), 2) for e in edges]
        else:
            # 所有体素取值相同：单桶直方图，避免 range 相等导致的空桶问题
            histogram = [int(finite.size)]
            bin_edges = [round(vmin, 2), round(vmax, 2)]

        clipped = voxel_count < full_sphere_count
        warning = None
        if clipped:
            warning = ("区域部分超出影像边界，统计结果仅基于影像内的 "
                       f"{voxel_count} 个体素（完整球形约 {full_sphere_count} 个）")
        if bad_count:
            anomaly_warning = f"区域内有 {bad_count} 个体素为缺失值/无穷值，统计时已跳过"
            warning = f"{warning}；{anomaly_warning}" if warning else anomaly_warning

        results.append({
            "id": roi.get("id"),
            "label": str(roi.get("label") or "roi"),
            "center": [cx, cy, cz],
            "radius": radius,
            "status": "ok",
            "warning": warning,
            "mean": round(float(np.mean(finite)), 2),
            "std": round(float(np.std(finite)), 2),
            "min": round(vmin, 2),
            "max": round(vmax, 2),
            "voxelCount": int(finite.size),
            "histogram": histogram,
            "histogramEdges": bin_edges,
        })

    return {"rois": results}


@app.get("/api/windows")
def get_windows():
    return {"presets": WINDOW_PRESETS}