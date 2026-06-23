"""
DXF MCP Server — 让 AI 智能体直接操控 CAD 生成 DXF 图纸。

通过 MCP 协议暴露 CAD 绘图工具，支持：
- 创建/管理图层
- 绘制线段、圆、矩形、弧线
- 添加文字标注（含中文）
- 尺寸标注
- 保存 DXF 文件（R2007+，AutoCAD 兼容）
"""

import json
import sys
import os

import ezdxf
from ezdxf import units

# ============================================================
# 全局状态：当前打开的图纸
# ============================================================
_doc = None
_msp = None
_output_path = "output.dxf"

# ============================================================
# 工具函数
# ============================================================
def _ensure_doc():
    """确保有打开的图纸，没有则自动创建"""
    global _doc, _msp
    if _doc is None:
        _doc = ezdxf.new(dxfversion="AC1021", units=units.MM)
        _msp = _doc.modelspace()
        # 默认文字样式支持中文
        _doc.styles.add("CN_STYLE", font="SimSun.ttf")
        std = _doc.styles.get("STANDARD")
        std.dxf.font = "SimSun.ttf"
    return _doc, _msp


def _azimuth(v):
    """容错取值"""
    return float(v) if v is not None else 0.0


# ============================================================
# MCP 协议处理
# ============================================================
async def handle_request(request: dict) -> dict:
    """处理 MCP JSON-RPC 请求"""
    method = request.get("method", "")
    req_id = request.get("id")

    # 初始化
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "dxf-mcp",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    # 列出工具
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _TOOLS}}

    # 调用工具
    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = _dispatch(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"❌ 错误: {e}"}],
                    "isError": True,
                },
            }

    # 未实现
    if req_id is not None:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}
    return {}


def _dispatch(name: str, args: dict) -> dict:
    """分发工具调用"""
    global _doc, _msp, _output_path
    doc, msp = _ensure_doc()
    layer = args.get("layer", "0")

    # ---- 图纸管理 ----
    if name == "new_drawing":
        _doc = ezdxf.new(dxfversion="AC1021", units=units.MM)
        _msp = _doc.modelspace()
        _doc.styles.add("CN_STYLE", font="SimSun.ttf")
        _doc.styles.get("STANDARD").dxf.font = "SimSun.ttf"
        _output_path = args.get("filename", "output.dxf")
        return {"status": "ok", "message": f"新建图纸: {_output_path}"}

    if name == "save":
        _output_path = args.get("filename", _output_path)
        if not _output_path.endswith(".dxf"):
            _output_path += ".dxf"
        _doc.saveas(_output_path)
        path = os.path.abspath(_output_path)
        return {"status": "ok", "file": path, "message": f"已保存: {path}"}

    # ---- 图层 ----
    if name == "add_layer":
        ln = args.get("name", "0")
        color = args.get("color", 7)
        if ln not in _doc.layers:
            _doc.layers.add(ln, color=color)
        return {"status": "ok", "layer": ln, "color": color}

    # ---- 线段 ----
    if name == "add_line":
        x1, y1 = float(args["x1"]), float(args["y1"])
        x2, y2 = float(args["x2"]), float(args["y2"])
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})
        return {"status": "ok", "entity": "LINE", "layer": layer}

    # ---- 圆 ----
    if name == "add_circle":
        cx, cy = float(args["cx"]), float(args["cy"])
        r = float(args["radius"])
        msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})
        return {"status": "ok", "entity": "CIRCLE", "layer": layer, "radius": r}

    # ---- 矩形 ----
    if name == "add_rect":
        x1, y1 = float(args["x1"]), float(args["y1"])
        x2, y2 = float(args["x2"]), float(args["y2"])
        pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        for i in range(4):
            msp.add_line(pts[i], pts[i + 1], dxfattribs={"layer": layer})
        w, h = abs(x2 - x1), abs(y2 - y1)
        return {"status": "ok", "entity": "RECT", "layer": layer, "width": w, "height": h}

    # ---- 文字 ----
    if name == "add_text":
        x, y = float(args["x"]), float(args["y"])
        content = args["text"]
        height = float(args.get("height", 300))
        msp.add_text(content, dxfattribs={
            "layer": layer,
            "style": "CN_STYLE",
            "height": height,
            "insert": (x, y),
        })
        return {"status": "ok", "entity": "TEXT", "layer": layer, "text": content}

    # ---- 尺寸 ----
    if name == "add_dimension":
        x1, y1 = float(args["x1"]), float(args["y1"])
        x2, y2 = float(args["x2"]), float(args["y2"])
        offset = float(args.get("offset", 500))
        txt = args.get("text", f"{abs(x2-x1) if abs(x2-x1) > abs(y2-y1) else abs(y2-y1)}")
        h = float(args.get("height", 250))

        # 判断水平/垂直
        if abs(x2 - x1) >= abs(y2 - y1):  # 水平标注
            direction = "horizontal"
            mid_x, mid_y = (x1 + x2) / 2, y1 + offset
            # 起止标记
            msp.add_line((x1, y1), (x1, y1 + offset), dxfattribs={"layer": layer})
            msp.add_line((x2, y2), (x2, y2 + offset), dxfattribs={"layer": layer})
            msp.add_line((x1, y1 + offset), (x2, y2 + offset), dxfattribs={"layer": layer})
        else:  # 垂直标注
            direction = "vertical"
            mid_x, mid_y = x1 + offset, (y1 + y2) / 2
            msp.add_line((x1, y1), (x1 + offset, y1), dxfattribs={"layer": layer})
            msp.add_line((x2, y2), (x2 + offset, y2), dxfattribs={"layer": layer})
            msp.add_line((x1 + offset, y1), (x2 + offset, y2), dxfattribs={"layer": layer})

        msp.add_text(txt, dxfattribs={
            "layer": layer,
            "style": "CN_STYLE",
            "height": h,
            "insert": (mid_x, mid_y),
        })
        return {"status": "ok", "entity": "DIMENSION", "direction": direction, "text": txt}

    raise ValueError(f"未知工具: {name}")


# ============================================================
# 工具清单 (MCP 声明)
# ============================================================
_TOOLS = [
    {
        "name": "new_drawing",
        "description": "创建一张新图纸，设置单位(mm/cm/m)和文件名",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "输出文件名，如 floorplan.dxf"},
                "units": {"type": "string", "enum": ["mm", "cm", "m"], "description": "图纸单位，默认 mm"},
            },
            "required": [],
        },
    },
    {
        "name": "save",
        "description": "保存当前图纸到 DXF 文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "保存路径，如 C:/output.dxf"},
            },
            "required": [],
        },
    },
    {
        "name": "add_layer",
        "description": "创建新图层（如墙体、标注、文字等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "图层名称"},
                "color": {"type": "integer", "description": "ACI 颜色码: 1红 2黄 3绿 4青 5蓝 6紫 7白"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "add_line",
        "description": "绘制线段 (x1,y1)→(x2,y2)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "layer": {"type": "string", "description": "图层名"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "add_circle",
        "description": "绘制圆，指定圆心和半径",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cx": {"type": "number"}, "cy": {"type": "number"},
                "radius": {"type": "number"},
                "layer": {"type": "string"},
            },
            "required": ["cx", "cy", "radius"],
        },
    },
    {
        "name": "add_rect",
        "description": "绘制矩形，指定左下角和右上角坐标",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "layer": {"type": "string"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "add_text",
        "description": "添加文字标注（支持中文，自动使用宋体）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "number"}, "y": {"type": "number"},
                "text": {"type": "string", "description": "文字内容"},
                "height": {"type": "number", "description": "字高，默认 300(mm)"},
                "layer": {"type": "string"},
            },
            "required": ["x", "y", "text"],
        },
    },
    {
        "name": "add_dimension",
        "description": "添加尺寸标注（两点间距离）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "offset": {"type": "number", "description": "标注线偏移距离，默认 500"},
                "text": {"type": "string", "description": "标注文字，默认自动计算"},
                "height": {"type": "number", "description": "文字高度，默认 250"},
                "layer": {"type": "string"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
]


# ============================================================
# stdio 运行入口
# ============================================================
def main():
    """MCP stdio 主循环"""
    import asyncio

    async def _run():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = await handle_request(req)
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                continue

    asyncio.run(_run())


if __name__ == "__main__":
    main()
