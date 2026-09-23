"""端到端验证 /api/roi 的各分支。运行: python3 test_roi.py"""
import sys, math, json
sys.path.insert(0, '/workspace/backend')
import numpy as np
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

def post_roi(payload):
    # allow_nan=True：模拟真实客户端发送 NaN 令牌（Python json 可解析）
    return client.post('/api/roi',
                       content=json.dumps(payload, allow_nan=True),
                       headers={"Content-Type": "application/json"})

vol = np.zeros((40, 50, 60), dtype=np.float32)
# 内部球：值随 x 渐变，保证直方图非退化
zz, yy, xx = np.mgrid[0:40, 0:50, 0:60]
inside = (xx-30)**2 + (yy-25)**2 + (zz-20)**2 <= 18**2
vol[inside] = 40 + (xx[inside]-20) * 1.5
VOL = vol.tolist()

passed, failed = [], []
def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + (f" :: {detail}" if detail and not cond else ""))

# 1) 正常 ROI：返回均值/标准差/分布图(含桶边界)
r = post_roi({"volume": VOL, "rois": [
    {"id": "a", "label": "lesion", "center": [30, 25, 20], "radius": 6}]})
d = r.json()["rois"][0]
check("正常: status=ok", d["status"] == "ok")
check("正常: 均值/标准差存在", isinstance(d["mean"], (int, float)) and d["std"] is not None)
check("正常: 直方图10桶", len(d["histogram"]) == 10 and sum(d["histogram"]) == d["voxelCount"],
      f"{d.get('histogram')} count={d.get('voxelCount')}")
check("正常: 桶边界11个", len(d["histogramEdges"]) == 11)
check("正常: 无裁剪警告", not d.get("warning"))

# 2) 同名 ROI 两条：id 区分，互不覆盖
r = post_roi({"volume": VOL, "rois": [
    {"id": "a", "label": "same", "center": [30, 25, 20], "radius": 6},
    {"id": "b", "label": "same", "center": [26, 25, 20], "radius": 4},
]})
rs = r.json()["rois"]
check("同名: 返回两条", len(rs) == 2)
check("同名: id 分别保留", [x["id"] for x in rs] == ["a", "b"])
check("同名: 标签相同但结果不同", rs[0]["label"] == rs[1]["label"] == "same" and rs[0]["mean"] != rs[1]["mean"],
      f"{rs[0]['mean']} vs {rs[1]['mean']}")

# 3) 区域完全落在影像之外
r = post_roi({"volume": VOL, "rois": [
    {"id": "out", "label": "far", "center": [200, 200, 200], "radius": 3}]})
d = r.json()["rois"][0]
check("越界: status=error", d["status"] == "error")
check("越界: 原因码 outside_volume", d["errorCode"] == "outside_volume")
check("越界: 有中文原因说明", "影像之外" in (d["errorMessage"] or ""), d.get("errorMessage"))

# 4) 部分超出边界：成功但带裁剪警告
r = post_roi({"volume": VOL, "rois": [
    {"id": "clip", "label": "edge", "center": [2, 25, 20], "radius": 8}]})
d = r.json()["rois"][0]
check("裁剪: status=ok", d["status"] == "ok")
check("裁剪: 警告含体素数说明", d.get("warning") and "超出影像边界" in d["warning"], d.get("warning"))

# 5) 参数非法：球心格式错 / 半径非法
r = post_roi({"volume": VOL, "rois": [
    {"id": "bad1", "label": "x", "center": [1, 2], "radius": 5},
    {"id": "bad2", "label": "x", "center": [1, 2, 3], "radius": -2},
    {"id": "bad3", "label": "x", "center": ["a", 2, 3], "radius": 5},
]})
rs = r.json()["rois"]
check("非法参数: 每条都返回错误", [x["status"] for x in rs] == ["error"]*3)
check("非法参数: 原因码区分", [x["errorCode"] for x in rs] ==
      ["invalid_center", "invalid_radius", "invalid_center"])

# 6) ROI 内含 null（前端 JSON.stringify(NaN) 实际发出 null，pydantic 转为 NaN）：跳过并警告
vol_nan = np.array(VOL, dtype=np.float64)
vol_nan[20, 25, 30] = np.nan
payload = vol_nan.tolist()
payload[20][25][30] = None  # 模拟浏览器真实发出的 JSON null
r = post_roi({"volume": payload, "rois": [
    {"id": "nan1", "label": "n", "center": [30, 25, 20], "radius": 3}]})
d = r.json()["rois"][0]
check("局部NaN: 测量成功", d["status"] == "ok")
check("局部NaN: 警告已跳过", d.get("warning") and "缺失值" in d["warning"], d.get("warning"))

# 7) ROI 全部是缺失值（null -> NaN）
vol_allnan = np.full((10, 10, 10), np.nan).tolist()
vol_allnan[5][5][5] = None
r = post_roi({"volume": vol_allnan, "rois": [
    {"id": "nan2", "label": "n", "center": [5, 5, 5], "radius": 2}]})
d = r.json()["rois"][0]
check("全NaN: 错误且原因明确", d["status"] == "error" and d["errorCode"] == "data_anomaly")

# 8) 数据源整体（结构）异常
r1 = post_roi({"volume": [], "rois": []})
check("空体数据: 400 + 中文detail", r1.status_code == 400 and "为空" in r1.json()["detail"])
r2 = post_roi({"volume": [[1, 2], [3, 4]], "rois": []})
check("维度异常: 400 + 说明维数", r2.status_code == 400 and "维" in r2.json()["detail"])
r3 = post_roi({"volume": [[[1, 2], [3]], [[1], [3, 4]]], "rois": []})  # 参差不齐，无法构三维
check("畸形数据: 400 + 格式异常说明", r3.status_code == 400 and "格式异常" in r3.json()["detail"],
      f"{r3.status_code} {r3.text[:120]}")

# 9) 所有体素取值相同：单桶直方图，不报错
vol_flat = np.full((20, 20, 20), 33.0)
r = post_roi({"volume": vol_flat.tolist(), "rois": [
    {"id": "flat", "label": "f", "center": [10, 10, 10], "radius": 3}]})
d = r.json()["rois"][0]
check("恒定值: 成功", d["status"] == "ok")
check("恒定值: 单桶直方图", d["histogram"] == [d["voxelCount"]] and len(d["histogramEdges"]) == 2,
      f"{d.get('histogram')} {d.get('histogramEdges')}")

# 10) 混合批次：一条成功、一条越界，互不影响
r = post_roi({"volume": VOL, "rois": [
    {"id": "ok1", "label": "mix", "center": [30, 25, 20], "radius": 5},
    {"id": "err1", "label": "mix", "center": [-50, -50, -50], "radius": 2},
]})
rs = r.json()["rois"]
check("混合批次: 仍返回两条", len(rs) == 2)
check("混合批次: 状态分别为 ok/error", [x["status"] for x in rs] == ["ok", "error"])

print(f"\n==== {len(passed)} passed, {len(failed)} failed ====")
sys.exit(1 if failed else 0)
