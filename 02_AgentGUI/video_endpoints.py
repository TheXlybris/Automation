#!/usr/bin/env python3
"""Video generation endpoints for AgentGUI server.py.

Provides: storyboard, generate, status, fetch, extend, postprocess.
Appended to server.py before the Video Analyzer section.
"""
import json, os, copy, subprocess, re, requests, uuid, shutil, time
from pathlib import Path
from flask import request, jsonify

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.0.187:11434")
COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "http://192.168.0.187:8188")
VIDEO_WF_DIR = Path("/media/sf_AI_Ecosystem/03_Workflows")
COMFYUI_OUTPUT_DIR = Path("/media/sf_AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output")
MEDIA_DIR = Path("/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI/media")
COMFYUI_INPUT_DIR = Path("/media/sf_AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/input")

NEGATIVE_FANTASY = "static, still, motionless, blurry details, worst quality, low quality, JPEG artifacts, deformed, disfigured, morphological aberrations, messy background, overall gray, overexposed, realistic, photographic, live-action, real world, text, watermark, subtitle"
NEGATIVE_REALISTIC = "static, still, motionless, blurry details, worst quality, low quality, JPEG artifacts, deformed, disfigured, morphological aberrations, messy background, overexposed, cartoon, anime, illustration, painting, 3d render, text, watermark, subtitle"

# Subgraph chain order (chunk 2-8)
CHAIN_IDS = [
    "698e36df-48d4-4287-b2d0-dcc52b061095",
    "5dc78ce5-bcf7-420a-8267-dd4609141233",
    "d55f381a-0bf3-40ca-af4a-d2c85f09c24c",
    "8009d707-0820-4728-b874-90885deab238",
    "6faa0958-0a15-459d-ad2b-944768ada35a",
    "b6720a03-b3c2-4792-9e32-c2addcd5c9d4",
    "a4727103-5706-4168-b05b-00c73effa805",
]


def _wf_to_api(ui_wf):
    """Convert ComfyUI UI-format WF to API format (node_id -> {class_type, inputs}).
    Resolves GetNode/SetNode (frontend-only) into direct node references.
    Uses ComfyUI /object_info to map widget_values to input names by position."""
    api = {}
    nodes = ui_wf.get("nodes", [])
    links = ui_wf.get("links", [])
    subgraphs = ui_wf.get("definitions", {}).get("subgraphs", [])

    # Fetch object_info from ComfyUI for input name mapping
    try:
        oi_resp = requests.get(f"{COMFYUI_HOST}/object_info", timeout=15)
        object_info = oi_resp.json()
    except Exception:
        object_info = {}

    # Build link lookup: link_id -> [from_node, from_slot, to_node, to_slot, type]
    link_map = {}
    for link in links:
        if isinstance(link, list) and len(link) >= 5:
            link_map[link[0]] = link

    # Map subgraph instance IDs to their definitions
    sg_def_map = {}
    for sg in subgraphs:
        sg_def_map[sg.get("id", "")] = sg

    # Map instance node_id -> definition id
    _inst_to_def = {}
    for n in nodes:
        nt = n.get("type", "")
        if len(nt) == 36 and "-" in nt:
            _inst_to_def[str(n.get("id", ""))] = nt

    # Build SetNode map: var_name -> [source_node_id, output_slot]
    # GetNode/SetNode are frontend-only (comfyui-easy-use), not valid in API format.
    set_map = {}
    for n in nodes:
        if n.get("type") == "SetNode":
            wv = n.get("widgets_values", [])
            var_name = wv[0] if wv else n.get("title", "").replace("Set_", "")
            for inp in n.get("inputs", []):
                link_id = inp.get("link")
                if link_id is not None and link_id in link_map:
                    link = link_map[link_id]
                    set_map[var_name] = [str(link[1]), link[2]]
                    break

    # Build GetNode map: node_id -> var_name (so we can resolve links from GetNodes)
    get_var_map = {}  # node_id -> var_name
    for n in nodes:
        if n.get("type") == "GetNode":
            wv = n.get("widgets_values", [])
            var_name = wv[0] if wv else ""
            get_var_map[str(n.get("id", ""))] = var_name

    # Build subgraph output map: sg_def_id -> {output_slot: [inner_node_id, inner_slot]}
    sg_output_map = {}
    for sg in subgraphs:
        sg_id = sg.get("id", "")
        sg_links = sg.get("links", [])
        sg_link_map = {}
        for l in sg_links:
            if isinstance(l, dict):
                sg_link_map[l["id"]] = l
        out_map = {}
        for out_idx, out in enumerate(sg.get("outputs", [])):
            for lid in out.get("linkIds", []):
                if lid in sg_link_map:
                    l = sg_link_map[lid]
                    if l.get("target_id") == -20:  # output target marker
                        out_map[out_idx] = [str(l["origin_id"]), l["origin_slot"]]
                        break
        sg_output_map[sg_id] = out_map

    def _resolve_link(link_id):
        """Resolve a link to [node_id, slot], following GetNode -> SetNode source."""
        if link_id not in link_map:
            return None
        link = link_map[link_id]
        src_node_id = str(link[1])
        src_slot = link[2]
        # If source is a GetNode, resolve to the actual source via set_map
        if src_node_id in get_var_map:
            var_name = get_var_map[src_node_id]
            if var_name in set_map:
                return set_map[var_name]
        # Find source node
        src_node = None
        for n in nodes:
            if str(n.get("id", "")) == src_node_id:
                src_node = n
                break
        # If source is a subgraph instance, resolve to inner node via sg_output_map
        if src_node and len(src_node.get("type", "")) == 36 and "-" in src_node["type"]:
            sg_id = src_node["type"]
            if sg_id in sg_output_map and src_slot in sg_output_map[sg_id]:
                inner = sg_output_map[sg_id][src_slot]
                return [f"{src_node_id}_{inner[0]}", inner[1]]
        # If source is a skipped node (frontend-only, uninstalled, or bypassed), bypass it
        SKIP_TYPES = ("GetNode", "SetNode", "Note", "MarkdownNote", "Reroute", "RIFE VFI", "PreviewImage")
        if src_node and (src_node.get("type") in SKIP_TYPES or src_node.get("mode", 0) == 4):
            # Find the input that feeds this output slot
            for inp in src_node.get("inputs", []):
                inp_link_id = inp.get("link")
                if inp_link_id is not None:
                    return _resolve_link(inp_link_id)
        return [src_node_id, src_slot]

    # Build subgraph input map for each instance: instance_node_id -> {input_slot: resolved_source}
    # Subgraph inner nodes reference origin_id=-10 with origin_slot=N to read parent input N
    sg_input_map = {}  # instance_id -> {slot_index: [resolved_node_id, slot]}
    for n in nodes:
        nt = n.get("type", "")
        if len(nt) == 36 and "-" in nt:  # subgraph instance
            inst_id = str(n.get("id", ""))
            inp_map = {}
            for i, inp in enumerate(n.get("inputs", [])):
                link_id = inp.get("link")
                if link_id is not None:
                    resolved = _resolve_link(link_id)
                    if resolved:
                        inp_map[i] = resolved
            sg_input_map[inst_id] = inp_map

    def _get_node_inputs(node, all_nodes, link_map, sg_defs, inst_id=None, sg_links=None):
        """Extract inputs dict from a UI node, resolving links to node references.
        If inst_id is set, this node is inside a subgraph — resolve via sg_links."""
        inputs = {}
        node_inputs = node.get("inputs", [])
        wv = node.get("widgets_values", [])
        nt = node.get("type", "")

        # Build subgraph link lookup if inside a subgraph
        sg_link_lookup = {}
        if sg_links:
            for l in sg_links:
                if isinstance(l, dict):
                    sg_link_lookup[l["id"]] = l

        for inp in node_inputs:
            inp_name = inp.get("name", "")
            link_id = inp.get("link")
            if link_id is not None:
                if sg_link_lookup and link_id in sg_link_lookup:
                    # Subgraph-internal link (dict format)
                    l = sg_link_lookup[link_id]
                    src_id = str(l["origin_id"])
                    src_slot = l["origin_slot"]
                    # Resolve -10 (parent input) via sg_input_map
                    if src_id == "-10" and inst_id in sg_input_map:
                        slot = int(src_slot)
                        if slot in sg_input_map[inst_id]:
                            inputs[inp_name] = sg_input_map[inst_id][slot]
                    else:
                        inputs[inp_name] = [f"{inst_id}_{src_id}", src_slot]
                else:
                    # Main graph link (list format)
                    resolved = _resolve_link(link_id)
                    if resolved:
                        inputs[inp_name] = resolved
            elif inp.get("link") is None:
                pass

        # Generic widget_values extraction using object_info input order
        # object_info gives us the required+optional input names in order;
        # widget_values maps by position to inputs that are NOT linked
        if wv:
            # Get the input order for this node type from object_info
            oi = object_info.get(nt, {})
            input_order = oi.get("input_order", {}).get("required", [])
            # Also include optional inputs
            input_order = input_order + oi.get("input_order", {}).get("optional", [])

            if input_order:
                # Determine which inputs are linked (skip those)
                linked_names = set()
                for inp in node_inputs:
                    if inp.get("link") is not None:
                        linked_names.add(inp.get("name", ""))

                # Build set of input names that are data-type (tensor/object) inputs
                # These should never get widget values mapped to them
                data_types = {"IMAGE","MASK","MODEL","CLIP","VAE","LATENT","CONDITIONING","AUDIO","INT","FLOAT","BOOLEAN","VIDEO","VHS_FILENAMES","VHS_BATCHMANAGER","VHS_VIDEOINFO"}
                # Actually INT/FLOAT/BOOLEAN can be widgets, so only skip tensor types
                tensor_types = {"IMAGE","MASK","MODEL","CLIP","VAE","LATENT","CONDITIONING","AUDIO","VIDEO","VHS_FILENAMES","VHS_BATCHMANAGER","VHS_VIDEOINFO","SAMPLER","SIGMAS","GUIDER","NOISE"}
                skip_names = set()
                for sect in ("required","optional"):
                    for inp_name, cfg in oi.get("input",{}).get(sect,{}).items():
                        if isinstance(cfg, list) and cfg and isinstance(cfg[0], str) and cfg[0] in tensor_types:
                            skip_names.add(inp_name)

                # For dict-style widget_values (VHS nodes), map by key directly
                if isinstance(wv, dict):
                    for k, v in wv.items():
                        if k in input_order and k not in linked_names:
                            inputs[k] = v
                # For list-style widget_values, map by position
                elif isinstance(wv, list):
                    # Build set of input names that have control_after_generate
                    cag_inputs = set()
                    oi_req = oi.get("input", {}).get("required", {})
                    for inp_name, cfg in oi_req.items():
                        if isinstance(cfg, list) and len(cfg) >= 2 and isinstance(cfg[1], dict):
                            if cfg[1].get("control_after_generate"):
                                cag_inputs.add(inp_name)

                    widx = 0
                    for inp_name in input_order:
                        # Tensor types don't have widgets — skip entirely
                        if inp_name in skip_names:
                            continue
                        # Linked inputs with widgets still consume a position in wv
                        if inp_name in linked_names:
                            widx += 1
                            if inp_name in cag_inputs and widx < len(wv):
                                widx += 1
                            continue
                        if widx >= len(wv):
                            break
                        inputs[inp_name] = wv[widx]
                        widx += 1
                        if inp_name in cag_inputs and widx < len(wv):
                            widx += 1

        # If inside a subgraph, parent inputs (-10) are already resolved above
        return inputs

    # Process main graph nodes — skip GetNode/SetNode
    all_nodes = nodes
    for node in nodes:
        nid = str(node.get("id", ""))
        nt = node.get("type", "")
        if not nid or not nt:
            continue
        # Skip frontend-only nodes, uninstalled nodes, and bypassed nodes (mode=4)
        if nt in ("GetNode", "SetNode", "Note", "MarkdownNote", "Reroute", "RIFE VFI", "PreviewImage"):
            continue
        if node.get("mode", 0) == 4:
            continue
        # Skip reroute/proxy nodes
        if len(nt) == 36 and "-" in nt:  # UUID = subgraph instance
            sg_def = sg_def_map.get(nt)
            if sg_def:
                for sn in sg_def.get("nodes", []):
                    snid = str(sn.get("id", ""))
                    snt = sn.get("type", "")
                    if not snid or not snt:
                        continue
                    if snt in ("GetNode", "SetNode", "Note", "MarkdownNote", "Reroute", "RIFE VFI", "PreviewImage"):
                        continue
                    if sn.get("mode", 0) == 4:
                        continue
                    combined_id = f"{nid}_{snid}"
                    api[combined_id] = {
                        "class_type": snt,
                        "inputs": _get_node_inputs(sn, sg_def.get("nodes", []), link_map, sg_def_map, inst_id=nid, sg_links=sg_def.get("links", []))
                    }
            continue

        api[nid] = {
            "class_type": nt,
            "inputs": _get_node_inputs(node, all_nodes, link_map, sg_def_map)
        }

    return api


# Chunk node mapping: subgraph instance IDs and VHS nodes per chunk
# Chunk 1 = main graph (KSamplers 35,36, VAEDecode 61, VHS 78)
# Chunks 2-8 = subgraph instances
CHUNK_SG_NODE_IDS = [160, 129, 130, 142, 143, 144, 149]   # chunks 2-8
CHUNK_VHS_NODE_IDS = [90, 104, 131, 145, 146, 147, 148]   # chunks 2-8
IMAGE_BATCH_NODE_IDS = [241, 242, 243, 244, 245, 246, 247] # for n_chunks 2-8
VHS_PREVIEW_NODE_ID = 150
VHS_PREVIEW_LINK_ID = 551  # link from ImageBatch 247 -> VHS 150


def _update_wf_prompts(wf, image_filename, prompts, negative, steps=8, cfg=1.5, seed=-1):
    """Update UI-format WF with new prompts and parameters.
    Bypasses unused chunks based on len(prompts) to avoid OOM."""
    wf = copy.deepcopy(wf)
    n_chunks = len(prompts)

    # LoadImage (ID=85)
    for n in wf["nodes"]:
        if n.get("id") == 85 and n.get("type") == "LoadImage":
            wv = n.get("widgets_values", [])
            if isinstance(wv, list) and wv:
                wv[0] = image_filename

    # Chunk 1 positive (CLIPTextEncode ID=3)
    for n in wf["nodes"]:
        if n.get("id") == 3 and n.get("type") == "CLIPTextEncode":
            wv = n.get("widgets_values", [])
            if isinstance(wv, list) and wv:
                wv[0] = prompts[0] if prompts else ""

    # Chunk 1 negative (ID=4)
    for n in wf["nodes"]:
        if n.get("id") == 4 and n.get("type") == "CLIPTextEncode":
            wv = n.get("widgets_values", [])
            if isinstance(wv, list) and wv:
                wv[0] = negative

    # KSampler params (IDs 35, 36)
    for n in wf["nodes"]:
        if n.get("type") == "KSamplerAdvanced" and n.get("id") in [35, 36]:
            wv = n.get("widgets_values", [])
            if isinstance(wv, list) and len(wv) >= 5:
                if seed != -1:
                    wv[1] = seed
                wv[3] = steps
                wv[4] = cfg

    # Subgraphs (chunks 2-8) — set prompts and bypass unused
    subgraphs = wf.get("definitions", {}).get("subgraphs", [])
    for i, cid in enumerate(CHAIN_IDS):
        chunk_num = i + 2
        should_bypass = chunk_num > n_chunks
        for sg in subgraphs:
            if sg.get("id") == cid:
                for sn in sg.get("nodes", []):
                    if sn.get("type") == "CLIPTextEncode" and not should_bypass:
                        title = sn.get("title", "")
                        wv = sn.get("widgets_values", [])
                        if isinstance(wv, list) and wv:
                            if "Positive" in title:
                                wv[0] = prompts[i + 1]
                            elif "Negative" in title:
                                wv[0] = negative
                    elif sn.get("type") == "KSamplerAdvanced" and not should_bypass:
                        wv = sn.get("widgets_values", [])
                        if isinstance(wv, list) and len(wv) >= 5:
                            if seed != -1:
                                wv[1] = seed
                            wv[3] = steps
                            wv[4] = cfg
                break

    # Bypass unused subgraph instances (mode=4)
    for i, sg_node_id in enumerate(CHUNK_SG_NODE_IDS):
        chunk_num = i + 2
        for n in wf["nodes"]:
            if n.get("id") == sg_node_id:
                n["mode"] = 4 if chunk_num > n_chunks else 0
                break

    # Bypass VHS_VideoCombine nodes for unused chunks
    for i, vhs_node_id in enumerate(CHUNK_VHS_NODE_IDS):
        chunk_num = i + 2
        for n in wf["nodes"]:
            if n.get("id") == vhs_node_id:
                n["mode"] = 4 if chunk_num > n_chunks else 0
                break

    # Bypass ImageBatch nodes that reference unused chunks
    # ImageBatch 241 = chunks 1+2, 242 = chunks 1-3, ..., 247 = chunks 1-8
    # For n_chunks=1: bypass ALL (no merge needed)
    # For n_chunks=N>=2: keep 241..(240+N), bypass (241+N)..247
    for i, ib_node_id in enumerate(IMAGE_BATCH_NODE_IDS):
        needed_chunks = i + 2  # this IB is needed when n_chunks >= needed_chunks
        for n in wf["nodes"]:
            if n.get("id") == ib_node_id:
                n["mode"] = 4 if n_chunks < needed_chunks else 0
                break

    # Reroute VHS 150 (16fpsPreview) to the last active source
    # n_chunks=1: node 61 (VAEDecode)
    # n_chunks>=2: ImageBatch (240 + n_chunks)
    if n_chunks == 1:
        preview_src = 61
    else:
        preview_src = 240 + n_chunks
    for l in wf.get("links", []):
        if isinstance(l, list) and l[0] == VHS_PREVIEW_LINK_ID:
            l[1] = preview_src
            l[2] = 0
            break

    # Update output prefixes and force 16fps (RIFE is bypassed, postprocess handles fps)
    for n in wf["nodes"]:
        if n.get("type") == "VHS_VideoCombine":
            wv = n.get("widgets_values", [])
            if isinstance(wv, dict):
                wv["frame_rate"] = 16
                prefix = wv.get("filename_prefix", "")
                if prefix and not prefix.startswith("VG_"):
                    wv["filename_prefix"] = f"VG_{prefix}"

    return wf


def _storyboard(scene, duration, style):
    """Generate N short movement prompts via Ollama."""
    n_chunks = max(1, duration // 5)
    style_hint = "fantasy style, bioluminescent" if style == "fantasy" else "photorealistic, natural"

    system = (
        f"Generate exactly {n_chunks} camera movement prompts for a video.\n"
        f"Return a JSON array with EXACTLY {n_chunks} strings.\n"
        "Rules: MAX 15 words per prompt. Describe ONLY camera movement. "
        "Do NOT describe objects or colors. Prompts flow continuously. Simple English.\n"
        f"Example: [\"camera slowly pans left\", \"gentle dolly forward\", \"camera tilts up\"]"
    )
    user = f"Scene: {scene}\nGenerate {n_chunks} movement prompts for {duration}s video."

    payload = json.dumps({
        "model": "qwen3:8b",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False, "max_tokens": 1000, "temperature": 0.4
    }).encode()

    resp = requests.post(f"{OLLAMA_HOST}/v1/chat/completions", data=payload,
                         headers={"Content-Type": "application/json"}, timeout=180)
    data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            prompts = json.loads(match.group())
        except json.JSONDecodeError:
            prompts = re.findall(r'"([^"]+)"', text)
    else:
        prompts = re.findall(r'"([^"]+)"', text)

    while len(prompts) < n_chunks:
        prompts.append("camera continues forward, smooth motion")
    prompts = prompts[:n_chunks]

    # Truncate to 15 words
    cleaned = []
    for p in prompts:
        words = p.strip().strip('"').split()
        if len(words) > 15:
            words = words[:15]
        cleaned.append(" ".join(words))

    negative = NEGATIVE_FANTASY if style == "fantasy" else NEGATIVE_REALISTIC
    return {"positive": cleaned, "negative": negative, "n_chunks": n_chunks}


def register_video_endpoints(app):
    """Register all video generation endpoints on the Flask app."""

    @app.route("/api/video/storyboard", methods=["POST"])
    def api_video_storyboard():
        data = request.json or {}
        scene = data.get("scene", "").strip()
        duration = int(data.get("duration", 40))
        style = data.get("style", "fantasy")
        if not scene:
            return jsonify({"error": "Cena vazia"}), 400
        try:
            result = _storyboard(scene, duration, style)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/video/generate", methods=["POST"])
    def api_video_generate():
        data = request.json or {}
        image_filename = data.get("image_filename", "")
        prompts = data.get("prompts", [])
        negative = data.get("negative", NEGATIVE_FANTASY)
        style = data.get("style", "fantasy")
        steps = int(data.get("steps", 8))
        cfg = float(data.get("cfg", 1.5))
        seed = int(data.get("seed", -1))

        if not image_filename or not prompts:
            return jsonify({"error": "Imagem e prompts obrigatórios"}), 400

        # Copy uploaded image to ComfyUI input dir so LoadImage can find it
        media_temp = Path("/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI/temp") / image_filename
        comfy_input = COMFYUI_INPUT_DIR / image_filename
        if media_temp.exists():
            shutil.copy2(str(media_temp), str(comfy_input))

        wf_path = VIDEO_WF_DIR / "Wan2.2-16x9-Clean_motionfix.json"
        if not wf_path.exists():
            return jsonify({"error": f"WF não encontrado: {wf_path}"}), 500

        try:
            wf = json.loads(wf_path.read_text(encoding="utf-8"))
        except Exception as e:
            return jsonify({"error": f"Erro ao ler WF: {e}"}), 500

        # Update WF with prompts and params
        wf = _update_wf_prompts(wf, image_filename, prompts, negative, steps, cfg, seed)

        # Save modified WF for user to load in ComfyUI
        modified_path = COMFYUI_INPUT_DIR / f"vg_workflow_{int(time.time())}.json"
        try:
            modified_path.write_text(json.dumps(wf, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Try to convert to API format and submit
        try:
            api_wf = _wf_to_api(wf)
            client_id = uuid.uuid4().hex
            resp = requests.post(f"{COMFYUI_HOST}/prompt",
                                 json={"prompt": api_wf, "client_id": client_id}, timeout=30)
            result = resp.json()
            if resp.status_code != 200:
                err_msg = result.get("error", {}).get("message", str(result)) if isinstance(result.get("error"), dict) else str(result)
                return jsonify({
                    "error": f"ComfyUI rejeitou o WF: {err_msg}",
                    "wf_path": str(modified_path),
                }), 400
            if result.get("node_errors"):
                return jsonify({
                    "error": "WF tem erros de nodes. Carrega manualmente no ComfyUI.",
                    "wf_path": str(modified_path),
                    "node_errors": result["node_errors"]
                }), 400
            prompt_id = result.get("prompt_id", "")
            return jsonify({"success": True, "prompt_id": prompt_id, "client_id": client_id, "wf_path": str(modified_path)})
        except Exception as e:
            # If API submission fails, return WF path for manual loading
            return jsonify({
                "success": False,
                "wf_path": str(modified_path),
                "error": f"Submissão automática falhou: {e}. Carrega o WF manualmente no ComfyUI."
            }), 200

    @app.route("/api/video/status/<prompt_id>")
    def api_video_status(prompt_id):
        try:
            resp = requests.get(f"{COMFYUI_HOST}/history/{prompt_id}", timeout=10)
            history = resp.json()
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 502

        if prompt_id not in history:
            return jsonify({"status": "queued"})

        entry = history[prompt_id]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            return jsonify({"status": "error", "error": "Erro na execução"})

        if not status.get("completed", False):
            return jsonify({"status": "running"})

        # Extract output videos
        videos = []
        outputs = entry.get("outputs", {})
        for node_id, node_output in outputs.items():
            for vid in node_output.get("gifs", []):  # VHS uses "gifs" for video outputs
                videos.append({
                    "filename": vid.get("filename", ""),
                    "subfolder": vid.get("subfolder", ""),
                    "type": vid.get("type", "output")
                })
            for img in node_output.get("images", []):
                videos.append({
                    "filename": img.get("filename", ""),
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output")
                })

        return jsonify({"status": "done", "videos": videos})

    @app.route("/api/video/fetch", methods=["POST"])
    def api_video_fetch():
        data = request.json or {}
        videos = data.get("videos", [])
        upscale = float(data.get("upscale", 1))
        if not videos:
            return jsonify({"error": "Nenhum vídeo"}), 400

        # Copy first video to media dir
        vid = videos[0]
        filename = vid.get("filename", "")
        subfolder = vid.get("subfolder", "")

        src = COMFYUI_OUTPUT_DIR / subfolder / filename if subfolder else COMFYUI_OUTPUT_DIR / filename
        if not src.exists():
            return jsonify({"error": f"Ficheiro não encontrado: {src}"}), 404

        # Copy to media dir with timestamp
        ts = int(time.time())
        dest_name = f"video_{ts}_{filename}"
        dest = MEDIA_DIR / dest_name
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(src), str(dest))
        except Exception as e:
            return jsonify({"error": f"Cópia falhou: {e}"}), 500

        # ffmpeg upscale (replaces ComfyUI ImageScaleBy — no OOM, streams frame-by-frame)
        if upscale > 1:
            upscaled_name = f"video_{ts}_u{int(upscale)}x_{filename}"
            upscaled_dest = MEDIA_DIR / upscaled_name
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(dest),
                     "-vf", f"scale=iw*{upscale}:ih*{upscale}:flags=lanczos",
                     "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                     "-c:a", "copy", str(upscaled_dest)],
                    capture_output=True, timeout=600)
            except Exception as e:
                return jsonify({"error": f"FFmpeg upscale falhou: {e}"}), 500
            if upscaled_dest.exists() and upscaled_dest.stat().st_size > 0:
                dest.unlink(missing_ok=True)  # remove unupscaled version
                dest_name = upscaled_name
                dest = upscaled_dest

        return jsonify({
            "success": True,
            "filename": dest_name,
            "url": f"/api/media/file/{dest_name}"
        })

    @app.route("/api/video/extend", methods=["POST"])
    def api_video_extend():
        data = request.json or {}
        video_filename = data.get("video_filename", "")
        prompts = data.get("prompts", [])
        negative = data.get("negative", NEGATIVE_FANTASY)

        if not video_filename or not prompts:
            return jsonify({"error": "Vídeo e prompts obrigatórios"}), 400

        # Find the video in media dir
        video_path = MEDIA_DIR / video_filename
        if not video_path.exists():
            # Try ComfyUI output
            video_path = COMFYUI_OUTPUT_DIR / video_filename
        if not video_path.exists():
            return jsonify({"error": f"Vídeo não encontrado: {video_filename}"}), 404

        # Extract last frame
        last_frame_path = COMFYUI_INPUT_DIR / f"vg_lastframe_{int(time.time())}.png"
        COMFYUI_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["ffmpeg", "-y", "-i", str(video_path),
                          "-vf", "select=last", "-frames:v", "1", str(last_frame_path)],
                         capture_output=True, timeout=30)
        except Exception as e:
            return jsonify({"error": f"FFmpeg falhou: {e}"}), 500

        if not last_frame_path.exists():
            return jsonify({"error": "Falha ao extrair última frame"}), 500

        # Generate new WF with last frame
        wf_path = VIDEO_WF_DIR / "Wan2.2-16x9-Clean_motionfix.json"
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
        wf = _update_wf_prompts(wf, last_frame_path.name, prompts, negative)

        # Save modified WF
        modified_path = COMFYUI_INPUT_DIR / f"vg_extend_{int(time.time())}.json"
        modified_path.write_text(json.dumps(wf, indent=2), encoding="utf-8")

        # Try API submission
        try:
            api_wf = _wf_to_api(wf)
            client_id = uuid.uuid4().hex
            resp = requests.post(f"{COMFYUI_HOST}/prompt",
                                 json={"prompt": api_wf, "client_id": client_id}, timeout=30)
            result = resp.json()
            prompt_id = result.get("prompt_id", "")
            return jsonify({"success": True, "prompt_id": prompt_id, "client_id": client_id, "wf_path": str(modified_path)})
        except Exception as e:
            return jsonify({
                "success": False,
                "wf_path": str(modified_path),
                "error": f"Submissão falhou: {e}. Carrega manualmente."
            }), 200

    @app.route("/api/video/postprocess", methods=["POST"])
    def api_video_postprocess():
        data = request.json or {}
        filename = data.get("filename", "")
        fps = int(data.get("fps", 16))
        upscale = int(data.get("upscale", 1))

        if not filename:
            return jsonify({"error": "Filename obrigatório"}), 400

        # Find the source video
        src_path = MEDIA_DIR / filename
        if not src_path.exists():
            src_path = COMFYUI_OUTPUT_DIR / filename
        if not src_path.exists():
            return jsonify({"error": f"Vídeo não encontrado: {filename}"}), 404

        # Copy video to ComfyUI input dir so VHS_LoadVideo can find it
        input_name = f"pp_input_{int(time.time())}.mp4"
        pp_input = COMFYUI_INPUT_DIR / input_name
        COMFYUI_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(src_path), str(pp_input))
        except Exception as e:
            return jsonify({"error": f"Cópia falhou: {e}"}), 500

        # Load PostProcess_Enhance WF and build API-format prompt
        pp_wf_path = VIDEO_WF_DIR / "PostProcess_Enhance.json"
        if not pp_wf_path.exists():
            return jsonify({"error": "PostProcess WF não encontrado"}), 500

        try:
            ui_wf = json.loads(pp_wf_path.read_text(encoding="utf-8"))
        except Exception as e:
            return jsonify({"error": f"Erro ao ler WF: {e}"}), 500

        # Build API format manually — WF has 5 nodes but ImageScaleBy (node 3)
        # is BYPASSED to avoid OOM (it loads all frames into RAM at once).
        # Upscale is handled post-ComfyUI by ffmpeg in api_video_fetch.
        # Link reroute: RIFE output (link 2) → CreateVideo input (was link 3)
        # Node 1: VHS_LoadVideo  → widget[0] = video path
        # Node 2: RIFEInterpolation → widgets [source_fps, target_fps, scale, model, batch, fp16]
        # Node 3: ImageScaleBy → SKIPPED (OOM risk)
        # Node 4: CreateVideo → widget[0] = fps
        # Node 5: SaveVideo → widget[0] = filename_prefix
        SKIP_NODE_TYPES = {"ImageScaleBy"}
        # Map: original link_id from ImageScaleBy output → RIFE output link_id
        # link 2 = RIFE→ImageScaleBy, link 3 = ImageScaleBy→CreateVideo
        # We reroute: CreateVideo's input that pointed to link 3 now points to link 2
        REROUTE_LINKS = {3: 2}  # old_link_id → new_link_id

        api_wf = {}
        for n in ui_wf.get("nodes", []):
            nid = str(n["id"])
            nt = n["type"]
            if nt in SKIP_NODE_TYPES:
                continue  # bypass ImageScaleBy entirely

            wv = n.get("widgets_values", [])
            inputs = {}

            # Resolve linked inputs (with reroute for bypassed nodes)
            for inp in n.get("inputs", []):
                link_id = inp.get("link")
                if link_id is not None:
                    link_id = REROUTE_LINKS.get(link_id, link_id)
                    for l in ui_wf.get("links", []):
                        if isinstance(l, list) and l[0] == link_id:
                            inputs[inp["name"]] = [str(l[1]), l[2]]
                            break

            if nt == "VHS_LoadVideo":
                inputs["video"] = input_name
                # wv order: [video, force_rate, skip_first_frames, select_every_nth, custom_width, custom_height, frame_load_cap]
                if isinstance(wv, list):
                    if len(wv) > 1: inputs["force_rate"] = wv[1]
                    if len(wv) > 2: inputs["skip_first_frames"] = wv[2]
                    if len(wv) > 3: inputs["select_every_nth"] = max(1, wv[3])
                    if len(wv) > 4: inputs["custom_width"] = wv[4]
                    if len(wv) > 5: inputs["custom_height"] = wv[5]
                    if len(wv) > 6: inputs["frame_load_cap"] = 0  # 0 = all frames
            elif nt == "RIFEInterpolation":
                if isinstance(wv, list) and len(wv) >= 6:
                    inputs["source_fps"] = 16
                    inputs["target_fps"] = fps
                    inputs["scale"] = wv[2] if len(wv) > 2 else 1
                    inputs["model_name"] = wv[3] if len(wv) > 3 else "flownet.pkl"
                    inputs["batch_size"] = wv[4] if len(wv) > 4 else 8
                    inputs["use_fp16"] = wv[5] if len(wv) > 5 else True
            elif nt == "CreateVideo":
                if isinstance(wv, list) and len(wv) >= 1:
                    inputs["fps"] = fps
            elif nt == "SaveVideo":
                # wv order: [filename_prefix, format, codec]
                if isinstance(wv, list):
                    inputs["filename_prefix"] = "PP_Enhanced"
                    if len(wv) > 1: inputs["format"] = wv[1]
                    if len(wv) > 2: inputs["codec"] = wv[2]

            api_wf[nid] = {"class_type": nt, "inputs": inputs}

        # Submit to ComfyUI
        try:
            client_id = uuid.uuid4().hex
            resp = requests.post(f"{COMFYUI_HOST}/prompt",
                                 json={"prompt": api_wf, "client_id": client_id}, timeout=30)
            result = resp.json()
            if "node_errors" in result and result["node_errors"]:
                return jsonify({
                    "error": "PostProcess WF tem erros de nodes",
                    "node_errors": result["node_errors"]
                }), 400
            prompt_id = result.get("prompt_id", "")
            return jsonify({
                "success": True,
                "prompt_id": prompt_id,
                "client_id": client_id,
                "source_filename": filename
            })
        except Exception as e:
            return jsonify({"error": f"Submissão falhou: {e}"}), 500