import random, math
import numpy as np
from fastapi import FastAPI
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
    volume: list = []
    rois: list = []


def _roi_error(roi_id, label, center, radius, code, message):
    return {
        "id": roi_id,
        "label": label,
        "center": center,
        "radius": radius,
        "status": "error",
        "errorCode": code,
        "message": message,
        "retryable": code in ("OUT_OF_IMAGE", "PARTIAL_OVERLAP", "RADIUS_INVALID"),
    }


@app.post("/api/roi")
def analyze_roi(req: ROIAnalyzeRequest):
    # ---- Validate volume payload ----
    if not req.volume:
        return {
            "status": "error",
            "errorCode": "NO_VOLUME",
            "message": "尚未载入影像数据，请先点击“载入影像”后再测量",
            "rois": [],
        }
    try:
        vol = np.array(req.volume, dtype=np.float32)
    except Exception:
        return {
            "status": "error",
            "errorCode": "VOLUME_PARSE_ERROR",
            "message": "影像数据格式异常，无法解析，请重新载入影像",
            "rois": [],
        }
    if vol.ndim != 3 or 0 in vol.shape:
        return {
            "status": "error",
            "errorCode": "VOLUME_INVALID",
            "message": f"影像体数据异常（维度不合法: {list(vol.shape)}），请重新载入影像",
            "rois": [],
        }
    if vol.size == 0 or not np.isfinite(vol).all():
        return {
            "status": "error",
            "errorCode": "VOLUME_CORRUPT",
            "message": "影像数据缺失或包含非法值（NaN/Infinity），请重新载入影像",
            "rois": [],
        }

    d, h, w = vol.shape
    results = []

    for roi in req.rois:
        roi_id = roi.get("id")
        center = roi.get("center", [w // 2, h // 2, d // 2])
        radius = roi.get("radius", 8)
        label = roi.get("label", "roi") or "roi"

        if (not isinstance(center, (list, tuple)) or len(center) != 3
                or any(not isinstance(c, (int, float)) for c in center)):
            results.append(_roi_error(roi_id, label, center, radius,
                                      "CENTER_INVALID", "ROI中心点参数不合法"))
            continue

        cx, cy, cz = center
        if not isinstance(radius, (int, float)) or radius <= 0:
            results.append(_roi_error(roi_id, label, center, radius,
                                      "RADIUS_INVALID", "ROI半径必须为大于0的数值"))
            continue

        # Bounds check (voxel indices: x in [0,w), y in [0,h), z in [0,d))
        if (cx + radius < 0 or cx - radius >= w or
                cy + radius < 0 or cy - radius >= h or
                cz + radius < 0 or cz - radius >= d):
            results.append(_roi_error(
                roi_id, label, center, radius, "OUT_OF_IMAGE",
                f"区域完全落在影像之外（影像范围 0~{w-1}, 0~{h-1}, 0~{d-1}），请调整中心点后重试"))
            continue

        x0, x1 = max(0, int(cx - radius)), min(w, int(cx + radius) + 1)
        y0, y1 = max(0, int(cy - radius)), min(h, int(cy + radius) + 1)
        z0, z1 = max(0, int(cz - radius)), min(d, int(cz + radius) + 1)

        voxels = vol[z0:z1, y0:y1, x0:x1]
        zz, yy, xx = np.ogrid[z0:z1, y0:y1, x0:x1]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 + (zz - cz) ** 2 <= radius ** 2
        arr = voxels[mask].astype(np.float64)

        if arr.size == 0:
            results.append(_roi_error(
                roi_id, label, center, radius, "NO_VOXEL",
                "ROI内未覆盖任何体素，请增大半径或调整中心点"))
            continue

        clipped = (cx - radius < 0 or cx + radius >= w or
                   cy - radius < 0 or cy + radius >= h or
                   cz - radius < 0 or cz + radius >= d)
        if not np.isfinite(arr).all():
            results.append(_roi_error(
                roi_id, label, center, radius, "DATA_NONFINITE",
                "ROI内存在非法体素值（NaN/Infinity），数据源可能已损坏"))
            continue

        vmin, vmax = float(np.min(arr)), float(np.max(arr))
        if vmax > vmin:
            counts, edges = np.histogram(arr, bins=10, range=(vmin, vmax))
            counts, edges = counts.tolist(), edges.tolist()
        else:
            # Degenerate case: every voxel has the same value
            counts = [int(arr.size)] + [0] * 9
            half = max(abs(vmin) * 0.05, 0.5)
            edges = list(np.linspace(vmin - half, vmin + half, 11))

        results.append({
            "id": roi_id,
            "label": label,
            "center": [cx, cy, cz],
            "radius": radius,
            "status": "partial" if clipped else "ok",
            "message": "区域部分超出影像边界，统计结果仅包含影像内体素" if clipped else "ok",
            "mean": round(float(np.mean(arr)), 2),
            "std": round(float(np.std(arr)), 2),
            "min": round(vmin, 2),
            "max": round(vmax, 2),
            "voxelCount": int(arr.size),
            "histogram": counts,
            "histogramEdges": [round(float(e), 2) for e in edges],
        })

    return {"status": "ok", "rois": results}


@app.get("/api/windows")
def get_windows():
    return {"presets": WINDOW_PRESETS}