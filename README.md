# dxf-mcp 🏗️

**MCP Server — 让 AI 智能体直接操控 CAD，生成 DXF 图纸。**

通过 MCP (Model Context Protocol) 协议暴露 8 个 CAD 绘图工具，智能体可以像人类设计师一样：创建图层、画墙体、画圆、标注尺寸、添加中文文字，最终输出 AutoCAD 兼容的 `.dxf` 文件。

## 功能特性

| 特性 | 说明 |
|------|------|
| 🧠 **AI 操控 CAD** | 通过自然语言描述，智能体自动调用绘图工具生成图纸 |
| 🔤 **中文支持** | 内置 SimSun（宋体）TTF 字体，房间名、尺寸标注等中文完美显示 |
| 📐 **毫米单位** | INSUNITS=4，CAD 中量距即所得，无需换算 |
| 📑 **图层管理** | 墙体/标注/文字/门洞自动分层，便于后续编辑 |
| 📦 **标准 DXF** | R2007 格式，兼容 AutoCAD 2007+、中望 CAD、LibreCAD 等 |
| 🔌 **MCP 协议** | 符合 MCP 2024-11-05 规范，任何支持 MCP 的 AI 客户端均可接入 |

## 可用工具

| 工具 | 功能 | 必填参数 |
|------|------|----------|
| `new_drawing` | 创建新图纸 | `filename` (可选) |
| `save` | 保存为 DXF 文件 | `filename` (可选) |
| `add_layer` | 创建图层 | `name` |
| `add_line` | 画线段 | `x1, y1, x2, y2` |
| `add_circle` | 画圆 | `cx, cy, radius` |
| `add_rect` | 画矩形 | `x1, y1, x2, y2` |
| `add_text` | 添加文字（支持中文） | `x, y, text` |
| `add_dimension` | 尺寸标注 | `x1, y1, x2, y2` |

## 项目结构

```
dxf-mcp/
├── dxf_mcp/
│   ├── __init__.py
│   └── server.py              # MCP Server 主程序
├── examples/
│   └── floorplan_3br.py       # 案例：三居室平面图
├── pyproject.toml
└── README.md
```

---

## 安装

### 1. 克隆仓库

```bash
git clone git@github.com:2016469520/cad-mcp.git
cd cad-mcp
```

### 2. 安装依赖

```bash
pip install -e .
```

唯一依赖是 [ezdxf](https://pypi.org/project/ezdxf/) >= 1.4，会自动安装。

---

## 在 Claude Code 中使用

### 方式一：项目级配置（推荐）

在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "dxf-mcp": {
      "command": "python",
      "args": ["-m", "dxf_mcp.server"],
      "cwd": "/path/to/dxf-mcp"
    }
  }
}
```

### 方式二：全局配置

编辑 `~/.claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "dxf-mcp": {
      "command": "python",
      "args": ["-m", "dxf_mcp.server"],
      "cwd": "/absolute/path/to/dxf-mcp"
    }
  }
}
```

### 方式三：claude.ai 云端使用

在 claude.ai 的 Settings → Integrations → MCP Servers 中添加：

| 字段 | 值 |
|------|-----|
| Name | `dxf-mcp` |
| Command | `python` |
| Args | `-m, dxf_mcp.server` |
| Working Directory | `/absolute/path/to/dxf-mcp` |

### Claude Code 使用示例

配置完成后，直接在对话中用自然语言描述需求：

> 帮我画一个 200x100 的矩形，左下角在 (0,0)，中心放一个半径 20 的圆，保存到桌面

> 帮我设计一个三居室的平面图，主卧 4.2x3.6m，次卧 3.6x3.3m 和 2.4x3.2m，客厅 4.2x5.4m，标注所有尺寸

> 在当前的 DXF 图纸上，给主卧添加一个步入式衣柜，尺寸 2x2m

Claude 会自动调用 dxf-mcp 的工具链：

```
new_drawing → add_layer → add_rect / add_line → add_circle
→ add_text → add_dimension → save
```

---

## 在 Codex (OpenAI) 中使用

### 配置

在 Codex 项目的 `codex.toml` 或 `~/.codex/config.toml` 中添加：

```toml
[mcp_servers.dxf-mcp]
command = "python"
args = ["-m", "dxf_mcp.server"]
cwd = "/absolute/path/to/dxf-mcp"
```

或在 `~/.codex/mcp.json` 中配置：

```json
{
  "mcpServers": {
    "dxf-mcp": {
      "command": "python",
      "args": ["-m", "dxf_mcp.server"],
      "cwd": "/absolute/path/to/dxf-mcp"
    }
  }
}
```

### Codex 使用示例

在 Codex 对话中：

> Draw a 12000x10200mm floor plan with 3 bedrooms, living room, kitchen, and bathroom. Add Chinese labels and dimensions.

> Add a 2000mm diameter circular staircase in the hallway area of the current drawing.

> Create a new layer called "ELECTRICAL" and add electrical symbols to the floor plan.



## 案例：三居室平面图

```bash
python examples/floorplan_3br.py
```

生成 `test_drawing.dxf`，包含完整的 12000×10200mm 三居室户型：

```
        4200            4200            3600
    ┌───────────┬──────────────────┬───────────┐
    │           │                  │           │
    │  主卧室   │    客厅 / 餐厅   │ 次卧室 1  │
    │ 4.2×3.6  │    4.2 × 5.4     │ 3.6×3.3   │
    │           │                  │           │
    ├─────┬─────┤                  ├───────────┤
    │厨房 │     │                  │ 次卧室 2  │
    │2.2× │走道 │                  │ 2.4×3.2   │
    │3.9  │     │                  │           │
    ├──┬──┴──┬──┼─────┬────────────┤    过道   │
    │玄│卫浴 │过│    阳台移门      │           │
    │关│2.2× │道│     (四扇)      │           │
    │  │3.9  │  │                  │           │
    └──┴─────┴──┴──────────────────┴───────────┘
```

| 房间 | 尺寸 | 面积 |
|------|------|------|
| 主卧室 | 4.2m × 3.6m | 15.1m² |
| 次卧室 1 | 3.6m × 3.3m | 11.9m² |
| 次卧室 2 | 2.4m × 3.2m | 7.7m² |
| 客厅/餐厅 | 4.2m × 5.4m | 22.7m² |
| 厨房 | 2.2m × 3.9m | 8.6m² |
| 卫生间 | 2.2m × 3.9m | 8.6m² |

---

## 开发

### 运行 MCP Server

```bash
python -m dxf_mcp.server
```

### 测试

```bash
# 运行示例
python examples/floorplan_3br.py

# 在 CAD 软件中打开生成的 DXF
start test_drawing.dxf
```

### 依赖

- Python >= 3.10
- [ezdxf](https://pypi.org/project/ezdxf/) >= 1.4

## License

MIT
