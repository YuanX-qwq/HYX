#!/usr/bin/env python3
"""methods-experiments-writing · 方法与实验章节要素抽取/对齐/缺口检查引擎（纯标准库）。

子命令：
  parse      解析材料包：配置、日志、步骤记录、草稿章节 → 归一化要素
  params     生成参数表（名称/取值/单位/作用对象/来源）并与草稿数值对齐
  steps      从材料还原有序步骤（输入/操作/输出/判断）
  check      六要素齐全性与一致性检查（步骤/设置/参数/数据集/对照/复现/限制）
  assemble   生成可编辑章节草稿（Markdown）
  run        跑完整流程并产出 result 草稿（供 serialize_result.py 序列化）
"""

import argparse
import json
import re
import sys
from pathlib import Path

NUM_RE = re.compile(r"(?<![\w.\-/])(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?:\s?(%|‰|mg|g|kg|mL|ml|L|s|ms|min|h|GB|MB|°C|K|epochs?|steps?))?(?![:：]\d)")
ALIAS = {"学习率": "lr", "批量": "batch_size", "batch size": "batch_size", "迭代轮": "epochs", "epoch": "epochs", "训练轮": "epochs", "权重衰减": "weight_decay", "weight decay": "weight_decay", "warmup": "warmup_epochs", "随机种子": "seed", "种子": "seed", "验证集比例": "split_ratio_val", "训练集比例": "split_ratio_train"}
CUE = ("学习率", "batch", "epoch", "准确率", "精度", "提升", "达到", "loss", "weight decay", "种子", "seed", "warmup", "率", "%")
UNIT_HINT = {"_ms": "ms", "_s": "s", "_h": "h", "_gb": "GB", "_mb": "MB", "_pct": "%",
             "_ratio": "ratio", "_c": "°C", "_celsius": "°C", "_k": "K"}
UNIT_STANDARD = {"s": "s", "sec": "s", "second": "s", "seconds": "s", "min": "min", "minute": "min",
                 "minutes": "min", "h": "h", "hour": "h", "hours": "h", "ms": "ms", "msec": "ms",
                 "gb": "GB", "mb": "MB", "ml": "mL", "l": "L", "epoch": "epochs", "epochs": "epochs",
                 "step": "steps", "steps": "steps", "%": "%", "°c": "°C", "k": "K", "mg": "mg", "g": "g",
                 "kg": "kg", "‰": "‰"}
STEP_MARK = re.compile(r"^\s*(?:\[step\s*(\d+)\]|step\s*(\d+)\s*[:：]|(\d+)[.)]\s+)(.+)$", re.I)
SPLIT_KEY = re.compile(r"(split|ratio|_size$|^train$|^val$|^valid$|^test$|^dev$|比例|划分)", re.I)


# ------------------------------------------------------------------ YAML 迷你解析
def parse_yaml_min(text):
    """两层缩进的 key: value / list 解析；返回 (嵌套 dict, 每行归属的行号)。"""
    root = {}
    stack = [(-1, root)]
    lines = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key_val = raw.strip()
        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        parent = stack[-1][1]
        if key_val.startswith("- "):
            if isinstance(parent, list):
                parent.append(_coerce(key_val[2:].strip()))
            continue
        if ":" not in key_val:
            continue
        k, v = key_val.split(":", 1)
        k, v = k.strip(), v.strip()
        if not v:
            container = {}
            parent[k] = container
            stack.append((indent, container))
            lines[k] = lineno
            continue
        if v.startswith("[") and v.endswith("]"):
            parent[k] = [_coerce(x.strip()) for x in v[1:-1].split(",") if x.strip()]
        else:
            parent[k] = _coerce(v)
        lines[k] = lineno
    return root, lines


def _coerce(v):
    v = v.strip().strip('"').strip("'")
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def flatten(d, prefix="", out=None):
    out = {} if out is None else out
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            flatten(v, key, out)
        else:
            out[key] = v
    return out


def is_split_key(key):
    return bool(SPLIT_KEY.search(key.split('.')[-1]))


def unit_of(key):
    low = key.lower()
    for suffix, unit in UNIT_HINT.items():
        if low.endswith(suffix):
            return unit
    tail = low.rsplit(".", 1)[-1]
    if tail in UNIT_STANDARD:
        return UNIT_STANDARD[tail]
    # 复合键（warmup_epochs / num_steps / lr_ratio）按后缀识别，最短 3 字符避免误判
    for k, unit in UNIT_STANDARD.items():
        if len(k) >= 3 and tail.endswith(k):
            return unit
    return "—"


def target_of(key):
    """参数作用对象：由键名前缀推断（train/val/test/model/opt/data）。"""
    seg = key.lower().split(".")
    for s in seg[:-1]:
        if s in ("train", "training"):
            return "训练"
        if s in ("val", "valid", "validation", "dev"):
            return "验证"
        if s in ("test", "eval", "evaluation"):
            return "测试"
        if s in ("model", "net", "arch"):
            return "模型"
        if s in ("opt", "optim", "optimizer"):
            return "优化器"
        if s in ("data", "dataset"):
            return "数据"
    return "全局"


# ------------------------------------------------------------------ 材料解析
def load_materials(case_path, config_path, log_path, steps_path, draft_path):
    cfg, cfg_lines = {}, {}
    if config_path and Path(config_path).exists():
        text = Path(config_path).read_text(encoding="utf-8")
        if config_path.lower().endswith(".json"):
            cfg = flatten(json.loads(text))
            cfg_lines = {k: 0 for k in cfg}
        else:
            nested, lines = parse_yaml_min(text)
            cfg, _ = flatten(nested), None
            # 行号按末级键名匹配
            flat_lines = {}
            for k in cfg:
                tail = k.split(".")[-1]
                flat_lines[k] = lines.get(tail, 0)
            cfg_lines = flat_lines
    log = Path(log_path).read_text(encoding="utf-8") if log_path and Path(log_path).exists() else ""
    steps_text = Path(steps_path).read_text(encoding="utf-8") if steps_path and Path(steps_path).exists() else ""
    draft = Path(draft_path).read_text(encoding="utf-8") if draft_path and Path(draft_path).exists() else ""
    return {"config": cfg, "config_lines": cfg_lines, "config_path": config_path or "",
            "log": log, "steps_text": steps_text, "draft": draft, "draft_path": draft_path or ""}


def params_from_config(m):
    out = []
    for k, v in m["config"].items():
        if isinstance(v, (list, bool)) or k.lower().startswith(("baseline", "baselines")):
            continue
        out.append({"name": k, "value": v, "unit": unit_of(k), "target": target_of(k),
                    "source": "%s:%s" % (Path(m["config_path"]).name, m["config_lines"].get(k, 0)),
                    "source_type": "config"})
    # 日志里显式 key=value 且配置没有的，补成"日志来源"
    for mt in re.finditer(r"^([A-Za-z_][\w.]*)\s*=\s*([^\s#]+)", m["log"], re.M):
        k, v = mt.group(1), mt.group(2)
        if k in m["config"] or any(p["name"] == k for p in out):
            continue
        out.append({"name": k, "value": _coerce(v), "unit": unit_of(k), "target": target_of(k),
                    "source": "log 中的 %s=%s" % (k, v), "source_type": "log"})
    return out


def setup_from(m):
    log = m["log"]
    hw = ""
    for pat in (r"(NVIDIA|AMD|Intel)[^\n]{0,60}", r"GPU[^\n]{0,40}"):
        mt = re.search(pat, log, re.I)
        if mt:
            hw = mt.group(0).strip()
            break
    vers = re.findall(r"(python|torch|pytorch|tensorflow|cuda|cudnn)\s*[=: ]\s*([0-9][\w.]*)", log, re.I)
    software = ", ".join("%s %s" % (a.lower(), b) for a, b in vers) or ""
    seed = ""
    for k in ("seed", "random_seed", "seeds"):
        if k in m["config"]:
            seed = str(m["config"][k])
            break
    if not seed:
        mt = re.search(r"seed\s*[=:]\s*(\d+)", log, re.I)
        seed = mt.group(1) if mt else ""
    reps = ""
    mt = re.search(r"(?:repeat|repetition|runs?|n_runs)\s*[=:]\s*(\d+)", log + json.dumps(m["config"]), re.I)
    if mt:
        reps = mt.group(1)
    split = ""
    keys = [k for k in m["config"] if is_split_key(k) and "batch" not in k.lower()]
    if keys:
        split = ", ".join("%s=%s" % (k, m["config"][k]) for k in keys)
    return {"hardware": hw, "software_versions": software, "seed": seed,
            "repetitions": reps, "train_val_test": split}


def dataset_from(m):
    cfg = m["config"]

    def pick(*names, prefix=None):
        # 优先 dataset.* 前缀，其次全键；不做模糊猜测
        for k, v in cfg.items():
            tail = k.split(".")[-1].lower()
            if tail in names and (prefix is None or k.lower().startswith(prefix)):
                return str(v)
        return ""

    name = pick("name", "dataset_name", "dataset", prefix="dataset") or \
        next((str(cfg[k]) for k in cfg if k.split(".")[-1].lower() in ("dataset", "dataset_name")), "")
    version = pick("version", "dataset_version", prefix="dataset") or pick("dataset_version")
    scale = pick("n_train", "train_size", "n_samples", "num_samples") or pick("size", prefix="dataset")
    split_ratio_keys = [k for k in cfg if is_split_key(k) and "batch" not in k.lower()]
    split = ", ".join("%s=%s" % (k.split(".")[-1], cfg[k]) for k in split_ratio_keys)
    pre = pick("preprocess", "augment", "normalize", "tokenizer")
    purpose = "训练/验证/测试按上述比例划分" if split_ratio_keys else ""
    return {"name": name, "version": version, "scale": scale, "preprocess": pre,
            "split": split, "purpose": purpose}


def baselines_from(m):
    out = []
    cfg = m["config"]
    for k, v in cfg.items():
        if "baseline" in k.lower():
            vals = v if isinstance(v, list) else [v]
            for item in vals:
                out.append({"name": str(item), "version": "", "budget_matched": "未说明",
                            "source": "%s:%s" % (Path(m["config_path"]).name, m["config_lines"].get(k, 0))})
    for mt in re.finditer(r"baseline[s]?\s*[=:]\s*([A-Za-z0-9_\-\., ]+?)(?=\s+(?:top1|acc|accuracy|score|loss|$))", m["log"], re.I):
        for item in re.split(r"[,，]", mt.group(1)):
            item = item.strip()
            if item and not any(b["name"] == item for b in out):
                out.append({"name": item, "version": "", "budget_matched": "未说明",
                            "source": "log 中的 baseline 行"})
    for mt in re.finditer(r"(与|对比|compared with|baseline[s]? (?:include|are))\s*([A-Za-z0-9_\-\., ]{2,60})", m["draft"], re.I):
        for item in re.split(r"[,，、]", mt.group(2)):
            item = item.strip().rstrip("。.")
            if item and len(item) < 40 and not any(b["name"] == item for b in out):
                out.append({"name": item, "version": "", "budget_matched": "未说明", "source": "草稿正文提及"})
    return out


def steps_from(m):
    src = m["steps_text"] or m["log"]
    out = []
    for line in src.splitlines():
        mt = STEP_MARK.match(line)
        if not mt:
            continue
        body = mt.group(4).strip()
        num = mt.group(1) or mt.group(2) or mt.group(3)
        inputs = _grab(body, ("输入", "input", "in:"))
        oper = _grab(body, ("操作", "operation", "do:", "执行"))
        outputs = _grab(body, ("输出", "output", "out:"))
        cond = _grab(body, ("判断", "condition", "if:", "若"))
        head = re.split(r"[；;]\s*(?:输入|输出|判断|input|output|condition)", body, maxsplit=1)[0]
        out.append({"order": int(num) if num and num.isdigit() else len(out) + 1,
                    "action": (oper or head).strip().rstrip("；;，,"),
                    "inputs": inputs, "outputs": outputs, "condition": cond,
                    "source": ("steps" if m["steps_text"] else "log") + " 第 %s 步" % num})
    out.sort(key=lambda s: s["order"])
    return out


def _grab(body, keys):
    for k in keys:
        mt = re.search(k + r"\s*[:：]\s*([^；;|]+)", body, re.I)
        if mt:
            return mt.group(1).strip()
    return ""


def numbers_in(text):
    out = []
    for mt in NUM_RE.finditer(text):
        raw = mt.group(0).strip()
        unit = UNIT_STANDARD.get((mt.group(2) or "").lower(), mt.group(2) or "")
        try:
            val = float(mt.group(1))
        except ValueError:
            continue
        out.append({"raw": raw, "value": val, "unit": unit, "pos": mt.start()})
    return out


def _same(a, b):
    try:
        return abs(float(a) - float(b)) <= max(1e-12, abs(float(b)) * 1e-6)
    except (TypeError, ValueError):
        return False


def align(m, params):
    """草稿数值 vs 参数表：unsourced / conflict / matched"""
    cfg_vals = {p["name"]: p["value"] for p in params}
    nums = numbers_in(m["draft"])
    res = {"sourced": [], "conflict": [], "unsourced": []}
    for n in nums:
        hit = None
        for name, val in cfg_vals.items():
            if _same(n["value"], val):
                hit = name
                break
        if hit:
            res["sourced"].append({"name": hit, "value": n["raw"]})
            continue
        # 只在本句/本分句内找参数线索，避免跨句误配
        cut = -1
        for ch in "。\n；;，,、：:":
            cut = max(cut, m["draft"].rfind(ch, 0, n["pos"]))
        clause = m["draft"][cut + 1:n["pos"]].lower()
        alias_hit = None
        for k, v in ALIAS.items():
            idx = clause.rfind(k.lower())
            if idx >= 0 and (alias_hit is None or idx > alias_hit[0]):
                alias_hit = (idx, v)
        key_hit = None
        for k in cfg_vals:
            tail = k.split(".")[-1].lower()
            idx = clause.rfind(tail) if len(tail) > 1 else -1
            if idx >= 0 and (key_hit is None or idx > key_hit[0]):
                key_hit = (idx, k)
        guess = None
        best = key_hit
        if alias_hit and (best is None or alias_hit[0] > best[0]):
            cand = next((k for k in cfg_vals if k.split(".")[-1].lower() == alias_hit[1]), None)
            best = (alias_hit[0], cand) if cand else best
        guess = best[1] if best else None
        if guess:
            res["conflict"].append({"name": guess, "config_value": cfg_vals[guess],
                                    "draft_value": n["raw"],
                                    "context": clause.strip()[-40:]})
        elif any(cue in clause for cue in CUE):
            res["unsourced"].append({"value": n["raw"], "context": clause.strip()[-40:]})
    return res


def check_elements(m, params, steps, setup, data, bases, align_res):
    items = []

    def add(name, ok, detail):
        items.append({"element": name, "status": "complete" if ok else ("partial" if detail else "missing"),
                      "detail": detail})

    add("steps", len(steps) >= 2 and all(s["inputs"] and s["outputs"] for s in steps),
        "%d 步，带输入/输出的 %d 步" % (len(steps), sum(1 for s in steps if s["inputs"] and s["outputs"])))
    add("setup", bool(setup["hardware"] and setup["software_versions"] and setup["seed"]),
        "硬件=%s；软件=%s；seed=%s" % (setup["hardware"] or "缺", setup["software_versions"] or "缺", setup["seed"] or "缺"))
    add("params", len(params) >= 5 and all(p["source"] for p in params),
        "%d 个参数，全部带来源" % len(params))
    add("dataset", bool(data["name"] and data["split"]),
        "名称=%s；划分=%s" % (data["name"] or "缺", data["split"] or "缺"))
    add("baselines", bool(bases) and all(b["budget_matched"] != "未说明" for b in bases),
        "%d 个基线，同预算说明 %d 个" % (len(bases), sum(1 for b in bases if b["budget_matched"] != "未说明")))
    return items


def repro_from(m, setup):
    log = m["log"]
    code = ""
    mt = re.search(r"(git (?:commit|rev)[^\n]{0,60}|commit[=: ]\s*([0-9a-f]{7,40}))", log, re.I)
    if mt:
        code = mt.group(0).strip()
    env = setup["software_versions"] or ""
    cmds = "\n".join(l.strip() for l in log.splitlines() if re.match(r"^\s*(\$|>|cmd[:>]|python |bash |sh )", l, re.I))[:300]
    access = ""
    mt = re.search(r"(/data/[^\s]+|s3://[^\s]+|huggingface[^\s]+|https?://[^\s]+)", m["log"] + m["draft"])
    if mt:
        access = mt.group(0)
    return {"code_version": code, "environment": env, "seed": setup["seed"],
            "commands": cmds, "data_access": access}


def limitations_from(align_res, data, bases, steps):
    out = []
    for c in align_res["conflict"]:
        out.append({"limitation": "正文数值与配置不一致：%s" % c["name"],
                    "failure_scenario": "按正文 %s 复现会得到与记录不同的结果" % c["draft_value"],
                    "requires_confirmation": True})
    for u in align_res["unsourced"]:
        out.append({"limitation": "正文数值无材料来源：%s" % u["value"],
                    "failure_scenario": "该数值可能来自未提供的材料，复现时无法核对",
                    "requires_confirmation": True})
    if not data["version"]:
        out.append({"limitation": "数据集版本未在材料中给出",
                    "failure_scenario": "换版本后划分与指标会变化，复现结果不可比",
                    "requires_confirmation": True})
    if bases and all(b["budget_matched"] == "未说明" for b in bases):
        out.append({"limitation": "基线未说明是否同预算",
                    "failure_scenario": "不同训练预算下的对比结论不成立", "requires_confirmation": True})
    gaps = [s["order"] for s in steps if not (s["inputs"] and s["outputs"])]
    if gaps:
        out.append({"limitation": "步骤 %s 缺输入或输出" % gaps,
                    "failure_scenario": "读者无法判断该步的进入条件与产物", "requires_confirmation": False})
    return out


def assemble_section(m, steps, setup, params, data, bases, repro, limitations):
    lines = ["## 方法", ""]
    for s in steps:
        bits = ["%d. %s" % (s["order"], s["action"].rstrip("。"))]
        if s["inputs"]:
            bits.append("输入：%s" % s["inputs"])
        if s["outputs"]:
            bits.append("输出：%s" % s["outputs"])
        if s["condition"]:
            bits.append("判断：%s" % s["condition"])
        lines.append("；".join(bits) + "。")
    lines += ["", "## 实验设置", "",
              "- 硬件：%s" % (setup["hardware"] or "（材料未给出）"),
              "- 软件：%s" % (setup["software_versions"] or "（材料未给出）"),
              "- 随机种子：%s；重复次数：%s" % (setup["seed"] or "（材料未给出）", setup["repetitions"] or "（材料未给出）"),
              "- 训练/验证/测试：%s" % (setup["train_val_test"] or "（材料未给出）"),
              "", "## 参数", "", "| 名称 | 取值 | 单位 | 作用对象 | 来源 |", "|---|---|---|---|---|"]
    for p in params:
        lines.append("| %s | %s | %s | %s | %s |" % (p["name"], p["value"], p["unit"], p["target"], p["source"]))
    lines += ["", "## 数据集", "",
              "- 名称：%s；版本：%s；规模：%s" % (data["name"] or "（未给出）", data["version"] or "（未给出）", data["scale"] or "（未给出）"),
              "- 预处理：%s；划分：%s" % (data["preprocess"] or "（未给出）", data["split"] or "（未给出）")]
    if bases:
        lines += ["", "## 对照实验", ""]
        for b in bases:
            lines.append("- 基线 %s（版本 %s，同预算：%s）" % (b["name"], b["version"] or "未给出", b["budget_matched"]))
    lines += ["", "## 可复现性", "",
              "- 代码版本：%s" % (repro["code_version"] or "（材料未给出）"),
              "- 环境：%s" % (repro["environment"] or "（材料未给出）"),
              "- 数据获取：%s" % (repro["data_access"] or "（材料未给出）")]
    if repro["commands"]:
        lines += ["- 命令：", "", "```bash", repro["commands"], "```"]
    lines += ["", "## 限制", ""]
    for lim in limitations:
        lines.append("- %s（失效场景：%s%s）" % (lim["limitation"], lim["failure_scenario"],
                                             "；需作者确认" if lim["requires_confirmation"] else ""))
    return "\n".join(lines) + "\n"


def run_case(case_path, cfg, log, steps_path, draft):
    case = json.loads(Path(case_path).read_text(encoding="utf-8")) if case_path and Path(case_path).exists() else {}
    m = load_materials(case_path, cfg, log, steps_path, draft)
    params = params_from_config(m)
    setup = setup_from(m)
    data = dataset_from(m)
    bases = baselines_from(m)
    steps = steps_from(m)
    al = align(m, params)
    elems = check_elements(m, params, steps, setup, data, bases, al)
    repro = repro_from(m, setup)
    lims = limitations_from(al, data, bases, steps)

    sources = []
    for p in params[:10]:
        sources.append({"source_id": "param:%s" % p["name"], "locator": p["source"],
                        "locator_type": "config_or_log_line", "quote": "%s = %s" % (p["name"], p["value"]),
                        "note": "参数与来源绑定"})
    for s in steps[:6]:
        sources.append({"source_id": "step:%d" % s["order"], "locator": s["source"],
                        "locator_type": "step_record", "quote": s["action"][:120], "note": "步骤原文"})
    for b in bases[:4]:
        sources.append({"source_id": "baseline:%s" % b["name"], "locator": b["source"],
                        "locator_type": "material_line", "quote": b["name"], "note": "基线来源"})

    unc = []
    for c in al["conflict"]:
        unc.append({"item": "参数 %s 取值冲突（配置 %s vs 正文 %s）" % (c["name"], c["config_value"], c["draft_value"]),
                    "reason": "正文与配置文件不一致，无法判断以哪个为准",
                    "action_required": "由作者确认并统一正文或配置"})
    for u in al["unsourced"]:
        unc.append({"item": "正文数值 %s 无来源" % u["value"],
                    "reason": "配置与日志中均未出现该数值",
                    "action_required": "补充来源或删除该数值"})
    if not steps:
        unc.append({"item": "步骤记录缺失", "reason": "材料中没有可解析的步骤记录",
                    "action_required": "提供实验步骤记录或日志片段"})
    if not setup["hardware"]:
        unc.append({"item": "硬件信息缺失", "reason": "日志中未出现 GPU/CPU 型号",
                    "action_required": "补充运行环境信息"})
    if not data["version"]:
        unc.append({"item": "数据集版本缺失", "reason": "配置中未给出 version 字段",
                    "action_required": "确认数据集版本与获取方式"})

    complete = sum(1 for e in elems if e["status"] == "complete")
    status = "success" if complete == len(elems) and not al["conflict"] and not al["unsourced"] else "partial"
    return {"case_id": case.get("case_id", ""), "task_id": case.get("task_id", ""), "status": status,
            "results": {"method_steps": [{"order": s["order"], "action": s["action"],
                                          "inputs": s["inputs"], "outputs": s["outputs"],
                                          "condition": s["condition"]} for s in steps],
                        "experimental_setup": setup,
                        "parameters": params,
                        "dataset": data,
                        "baselines": [{"name": b["name"], "version": b["version"],
                                       "budget_matched": b["budget_matched"], "source": b["source"]} for b in bases],
                        "reproducibility": repro,
                        "limitations": lims},
            "sources": sources, "uncertainty": unc,
            "changes": [{"step": "1", "action": "解析配置/日志/步骤记录", "note": "参数 %d 个，步骤 %d 步，日志 %d 字符" % (len(params), len(steps), len(m["log"]))},
                        {"step": "2", "action": "参数与草稿数值对齐", "note": "命中 %d，冲突 %d，无来源 %d" % (len(al["sourced"]), len(al["conflict"]), len(al["unsourced"]))},
                        {"step": "3", "action": "六要素齐全性检查", "note": "complete %d/%d" % (complete, len(elems))},
                        {"step": "4", "action": "生成章节草稿与限制清单", "note": "限制 %d 条" % len(lims)}],
            "artifacts": [], "elements": elems, "alignment": al,
            "section_md": assemble_section(m, steps, setup, params, data, bases, repro, lims)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="methods & experiments writing engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("parse", "params", "steps", "check", "assemble", "run"):
        sp = sub.add_parser(name)
        sp.add_argument("--case", default="")
        sp.add_argument("--config", default="")
        sp.add_argument("--log", default="")
        sp.add_argument("--steps", default="")
        sp.add_argument("--draft", default="")
        sp.add_argument("--out", default="")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        res = run_case(a.case, a.config, a.log, a.steps, a.draft)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(a.out).with_name("section.md").write_text(res["section_md"], encoding="utf-8")
        print("status=%s params=%d steps=%d baselines=%d conflict=%d unsourced=%d limits=%d"
              % (res["status"], len(res["results"]["parameters"]), len(res["results"]["method_steps"]),
                 len(res["results"]["baselines"]), len(res["alignment"]["conflict"]),
                 len(res["alignment"]["unsourced"]), len(res["results"]["limitations"])))
        return 0

    m = load_materials(a.case, a.config, a.log, a.steps, a.draft)
    params = params_from_config(m)
    if a.cmd == "parse":
        out = {"config": m["config"], "params": params, "setup": setup_from(m),
               "dataset": dataset_from(m), "baselines": baselines_from(m), "steps": steps_from(m)}
    elif a.cmd == "params":
        out = {"parameters": params, "alignment": align(m, params), "count": len(params)}
    elif a.cmd == "steps":
        out = {"steps": steps_from(m), "count": len(steps_from(m))}
    elif a.cmd == "check":
        al = align(m, params)
        out = {"elements": check_elements(m, params, steps_from(m), setup_from(m),
                                          dataset_from(m), baselines_from(m), al),
               "alignment": al}
    else:
        setup, data, bases = setup_from(m), dataset_from(m), baselines_from(m)
        out = {"markdown": assemble_section(m, steps_from(m), setup, params, data, bases,
                                            repro_from(m, setup),
                                            limitations_from(align(m, params), data, bases, steps_from(m)))}
    txt = json.dumps(out, ensure_ascii=False, indent=2) if a.cmd != "assemble" else out["markdown"]
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    else:
        print(txt[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
