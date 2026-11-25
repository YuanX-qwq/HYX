#!/usr/bin/env python3
"""30 项自测：要素抽取、参数对齐、步骤、六要素检查、成稿与契约序列化。"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import mew  # noqa: E402

CFG = """model: resnet18
seed: 42
train:
  batch_size: 64
  lr: 0.001
  epochs: 20
opt:
  warmup_epochs: 3
dataset:
  name: CIFAR-10
  n_train: 50000
  split_ratio_train: 0.9
  split_ratio_val: 0.1
baselines: [vanilla resnet18, mixup resnet18]
"""
LOG = """python=3.10.12 torch=2.1.0 cuda=12.1
device: NVIDIA A100-SXM4-40GB
git commit: 4f7c2ab
seed=42
dataset root: /data/cifar10
$ python train.py --config config.yaml
baseline: vanilla resnet18 top1=0.918
baseline: mixup resnet18 top1=0.947
"""
STEPS = """[step 1] 读取数据并增强；输入：原图；输出：增强训练集
[step 2] 训练 ResNet-18；输入：增强训练集；输出：权重
[step 3] 验证集评估 top-1；输入：验证集与权重；输出：指标
"""
DRAFT = "学习率为 0.01，共 20 个 epoch。最终 top-1 准确率达到 87.3%。随机种子为 42。"
ROOFCASE = {"case_id": "T-CASE-09", "task_id": "t"}
PASSED = []


def run(name, fn):
    try:
        ok = bool(fn())
        err = ""
    except Exception as exc:  # noqa: BLE001
        ok, err = False, "%s: %s" % (type(exc).__name__, exc)
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + err) if err else ""))
    PASSED.append(ok)


def fixture(tmp):
    d = Path(tmp)
    (d / "config.yaml").write_text(CFG, encoding="utf-8")
    (d / "run.log").write_text(LOG, encoding="utf-8")
    (d / "steps.md").write_text(STEPS, encoding="utf-8")
    (d / "draft.md").write_text(DRAFT, encoding="utf-8")
    (d / "case.json").write_text(json.dumps(ROOFCASE, ensure_ascii=False), encoding="utf-8")
    return mew.load_materials(str(d / "case.json"), str(d / "config.yaml"), str(d / "run.log"),
                              str(d / "steps.md"), str(d / "draft.md"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        ok = fixture(td)
        (td / "case.json").write_text(json.dumps(ROOFCASE), encoding="utf-8")

        params = mew.params_from_config(ok)
        names = {p["name"] for p in params}
        al = mew.align(ok, params)
        steps = mew.steps_from(ok)
        setup = mew.setup_from(ok)
        data = mew.dataset_from(ok)
        bases = mew.baselines_from(ok)

        run("yaml_nested_flatten", lambda: "train.lr" in ok["config"] and ok["config"]["train.lr"] == 0.001)
        run("unit_from_suffix", lambda: next(p for p in params if p["name"] == "opt.warmup_epochs")["unit"] == "epochs")
        run("target_train", lambda: next(p for p in params if p["name"] == "train.batch_size")["target"] == "训练")
        run("params_have_source", lambda: all(p["source"] for p in params))
        run("baseline_excluded_from_params", lambda: not any("baseline" in n for n in names))
        run("setup_hardware", lambda: "A100" in setup["hardware"])
        run("setup_software", lambda: "torch 2.1.0" in setup["software_versions"])
        run("seed_from_config", lambda: setup["seed"] == "42")
        run("split_ratio_only", lambda: "0.9" in setup["train_val_test"] and "batch_size" not in setup["train_val_test"])
        run("dataset_name", lambda: data["name"] == "CIFAR-10")
        run("dataset_scale", lambda: data["scale"] == "50000")
        run("dataset_version_blank", lambda: data["version"] == "")
        run("steps_count", lambda: len(steps) == 3)
        run("steps_have_io", lambda: all(s["inputs"] and s["outputs"] for s in steps))
        run("steps_action_trimmed", lambda: all("输入" not in s["action"] for s in steps))
        run("conflict_detected", lambda: any(c["name"] == "train.lr" for c in al["conflict"]))
        run("conflict_values", lambda: all(c["config_value"] != c["draft_value"] for c in al["conflict"]))
        run("unsourced_detected", lambda: any(u["value"].startswith("87.3") for u in al["unsourced"]))
        run("seed_not_false_conflict", lambda: not any(c["name"] == "seed" for c in al["conflict"]))
        run("no_bogus_unsourced", lambda: len(al["unsourced"]) == 1)
        run("baselines_dedup", lambda: [b["name"] for b in bases] == ["vanilla resnet18", "mixup resnet18"])
        run("baseline_budget_unknown", lambda: all(b["budget_matched"] == "未说明" for b in bases))
        elems = mew.check_elements(ok, params, steps, setup, data, bases, al)
        run("elements_five", lambda: [e["element"] for e in elems] == ["steps", "setup", "params", "dataset", "baselines"])
        run("element_status_mixed", lambda: any(e["status"] == "complete" for e in elems))
        lims = mew.limitations_from(al, data, bases, steps)
        run("limitation_has_conflict", lambda: any("不一致" in l["limitation"] for l in lims))
        run("limitation_requires_confirm", lambda: any(l["requires_confirm"] if False else l["requires_confirmation"] for l in lims))
        md = mew.assemble_section(ok, steps, setup, params, data, bases,
                                  mew.repro_from(ok, setup), lims)
        run("section_has_table", lambda: "| 名称 | 取值 | 单位 | 作用对象 | 来源 |" in md and "train.lr" in md)

        # 一键流程 + 契约
        code = mew.main(["run", "--case", str(td / "case.json"), "--config", str(td / "config.yaml"),
                         "--log", str(td / "run.log"), "--steps", str(td / "steps.md"),
                         "--draft", str(td / "draft.md"), "--out", str(td / "draft_result.json")])
        run("run_exit_zero", lambda: code == 0 and (td / "draft_result.json").exists())
        draft = json.loads((td / "draft_result.json").read_text(encoding="utf-8"))
        run("run_status_partial", lambda: draft["status"] == "partial")

        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                            "--input", str(td / "case.json"), "--draft", str(td / "draft_result.json"),
                            "--out", str(td / "out.json")], capture_output=True, text=True)
        doc = json.loads((td / "out.json").read_text(encoding="utf-8")) if p.returncode == 0 else {}
        run("serializer_runs", lambda: p.returncode == 0)
        run("contract_nine_fields", lambda: set(doc) == {
            "case_id", "task_id", "status", "results", "sources", "uncertainty",
            "changes", "artifacts", "metadata"})
        run("case_id_passthrough", lambda: doc.get("case_id") == "T-CASE-09")

        bad = json.loads((td / "draft_result.json").read_text(encoding="utf-8"))
        bad["status"] = "success"
        (td / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        p2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                             "--input", str(td / "case.json"), "--draft", str(td / "bad.json"),
                             "--out", str(td / "out2.json")], capture_output=True, text=True)
        run("success_rejects_confirm", lambda: p2.returncode == 1 and "确认" in p2.stderr)

        nosrc = json.loads((td / "draft_result.json").read_text(encoding="utf-8"))
        nosrc["results"]["parameters"][0]["source"] = ""
        (td / "nosrc.json").write_text(json.dumps(nosrc, ensure_ascii=False), encoding="utf-8")
        p3 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                             "--input", str(td / "case.json"), "--draft", str(td / "nosrc.json"),
                             "--out", str(td / "out3.json")], capture_output=True, text=True)
        run("rejects_missing_source", lambda: p3.returncode == 1 and "来源" in p3.stderr)

    print("%d/%d assertions passed" % (sum(PASSED), len(PASSED)))
    return 0 if all(PASSED) else 1


if __name__ == "__main__":
    sys.exit(main())
