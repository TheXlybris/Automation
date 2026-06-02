# ComfyUI Workflow JSON vs API Prompt — Full Debug Notes

## The Bug (session 2026-05-11)

All three pipeline scripts failed silently when submitting jobs to ComfyUI. Error: **`'77'`** in logs.

Root cause: workflow JSON has nodes as a **list** (`wf["nodes"]` is `[{id: 77, ...}, ...]`), but scripts accessed it as a **dict** (`wf["77"]`).

```python
# WRONG — This fails with KeyError: '77'
wf = json.load(open(workflow_path))
wf["77"]["inputs"]["width"] = 1024

# CORRECT
wf = json.load(open(workflow_path))
nodes = {n["id"]: n for n in wf["nodes"]}  # list → dict by id
nodes[77]["widgets_values"][0]            # but still broken — see below
```

Second issue: `nodes[77]["inputs"]` is a **list** of `{name, type, link}` objects, NOT a dict. You can't do `nodes[77]["inputs"]["width"]`.

```python
# WRONG — TypeError: list indices must be integers
nodes[77]["inputs"]["width"] = 1024

# CORRECT — Extract from widgets_values, then build proper input dict
wv = nodes[77]["widgets_values"]  # [1024, 576, 153, 1, 0.1]
width = wv[0]  # 1024
```

## LTXVImgToVideo Node IDs (Image2Video_LTXV.json)

| Node ID | Type | Notes |
|---------|------|-------|
| 77 | LTXVImgToVideo | `widgets_values = [width, height, length, batch_size, strength]` |
| 6 | CLIPTextEncode | positive prompt — `text` embedded in input list entry |
| 7 | CLIPTextEncode | negative prompt |
| 71 | LTXVScheduler | `widgets_values = [steps, denoise, max_shift, base_shift, continuous]` |
| 72 | SamplerCustom | `widgets_values = [add_noise, seed, returns, cfg]` |
| 80 | CreateVideo | `widgets_values = [fps]` |
| 69 | LTXVConditioning | `widgets_values = [frame_rate]` |
| 78 | LoadImage | image filename — NOT in widgets_values, set via API upload |
| 44 | CheckpointLoaderSimple | `ckpt_name` in widgets_values |
| 38 | CLIPLoader | `clip_name` in widgets_values |
| 81 | SaveVideo | `widgets_values = [format, filename_prefix, codec]` |

## Complete Working Pattern

```python
import json

WORKFLOW_PATH = "/mnt/d/AI_Ecosystem/03_Workflows/Image2Video_LTXV.json"

def build_inputs_dict(node):
    """Convert workflow node to ComfyUI API input dict."""
    inputs = {}
    for inp in node.get("inputs", []):
        inputs[inp["name"]] = None  # linked inputs have no direct value
    
    wv = node.get("widgets_values", [])
    if node["type"] == "LTXVImgToVideo":
        inputs["width"] = wv[0] if len(wv) > 0 else 1024
        inputs["height"] = wv[1] if len(wv) > 1 else 576
        inputs["length"] = wv[2] if len(wv) > 2 else 153
        inputs["batch_size"] = wv[3] if len(wv) > 3 else 1
        inputs["strength"] = wv[4] if len(wv) > 4 else 0.1
    elif node["type"] == "LTXVScheduler":
        inputs["steps"] = wv[0] if len(wv) > 0 else 50
        inputs["denoise"] = wv[1] if len(wv) > 1 else 1.0
    elif node["type"] == "SamplerCustom":
        inputs["cfg"] = wv[3] if len(wv) > 3 else 3.0
    elif node["type"] == "CreateVideo":
        inputs["fps"] = wv[0] if len(wv) > 0 else 24
    elif node["type"] == "LTXVConditioning":
        inputs["frame_rate"] = wv[0] if len(wv) > 0 else 25
    elif node["type"] == "KSamplerSelect":
        inputs["sampler_name"] = wv[0] if len(wv) > 0 else "euler"
    elif node["type"] == "SaveVideo":
        inputs["format"] = wv[0] if len(wv) > 0 else "mp4"
        inputs["filename_prefix"] = wv[1] if len(wv) > 1 else "ComfyUI"
        inputs["codec"] = wv[2] if len(wv) > 2 else "h264"
    elif node["type"] == "CLIPTextEncode":
        for inp in node.get("inputs", []):
            if inp.get("name") == "text":
                inputs["text"] = inp.get("text", "")
                break
    elif node["type"] == "LoadImage":
        pass  # image set from API upload
    elif node["type"] == "CheckpointLoaderSimple":
        pass  # ckpt_name set from API
    elif node["type"] == "CLIPLoader":
        pass  # clip_name set from API
    return inputs


def load_workflow():
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        wf = json.load(f)
    nodes = {n["id"]: n for n in wf["nodes"]}
    return wf, nodes


def build_prompt_dict(wf_raw, nodes):
    """Build ComfyUI API prompt dict from workflow JSON."""
    prompt_dict = {}
    for n in wf_raw["nodes"]:
        nid = str(n["id"])
        prompt_dict[nid] = {
            "class_type": n["type"],
            "inputs": build_inputs_dict(nodes[n["id"]])
        }
    return prompt_dict


# Usage:
wf_raw, nodes = load_workflow()

# Override parameters with _input_dict (not mutating original nodes)
nodes[77]["_input_dict"] = build_inputs_dict(nodes[77])
nodes[77]["_input_dict"]["width"] = 1024
nodes[77]["_input_dict"]["height"] = 576
nodes[77]["_input_dict"]["length"] = 144
nodes[77]["_input_dict"]["strength"] = 0.1

nodes[6]["_input_dict"] = build_inputs_dict(nodes[6])
nodes[6]["_input_dict"]["text"] = "gentle ambient motion, soft natural movement"

# Build final API prompt dict
prompt_dict = {}
for n in wf_raw["nodes"]:
    nid = str(n["id"])
    input_dict = nodes[n["id"]].get("_input_dict") or build_inputs_dict(nodes[n["id"]])
    prompt_dict[nid] = {
        "class_type": n["type"],
        "inputs": input_dict
    }

# Submit
resp = requests.post(f"{COMFYUI_HOST}/prompt", json={"prompt": prompt_dict})
```

## Error Logs from the Session

```
Job submetido: job_1778519719417
A carregar workflow...
Config: 1024x576 | 6.0s (144 frames) | strength=0.1
'77'
```

`'77'` is Python's KeyError printed as the exception string — the script printed `wf["77"]` which failed.

## Scripts Fixed

1. `run_video.py` — CLI pipeline
2. `run_video_ui.py` — UI pipeline (progress JSON)
3. `UI/server.py` — Flask + SSE + WebSocket backend

All three had the same dual bug: `wf["77"]` KeyError + `nodes[6]["inputs"]["text"]` TypeError on list.

## Key Structural Differences

| Aspect | Workflow JSON | API Prompt |
|--------|--------------|-----------|
| Top-level | `{id, revision, nodes: [...], links: [...]}` | `{prompt: {}}` |
| Node access | `nodes = {n["id"]: n for n in wf["nodes"]}` | `prompt_dict["77"]["inputs"]["width"] = 1024` |
| Node inputs | List: `[{name: "width", link: null}]` | Dict: `{"width": 1024, "height": 576}` |
| Widget values | `node["widgets_values"][0]` → first slider value | Must map to named inputs |