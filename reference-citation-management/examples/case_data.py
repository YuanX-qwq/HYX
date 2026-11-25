# -*- coding: utf-8 -*-
"""参考文献与引用管理：示例稿件 + 文献库 + 草稿结果（示例，非正式案例答案）。"""

# 示例稿件：编号有重复、缺连续、指向错误（[4] 无对应条目），并有一句该引却未引
manuscript = """本研究考察掺杂对催化活性的影响[1]。在 25 °C 条件下，掺杂样品的产率提升到 42%[1]。
对照组在相同条件下产率仅为 18%[1]。该结果证明掺杂总是有效[1]。X 射线衍射表明晶格常数随掺杂量增大而减小[2]。
掺杂样品在连续 10 小时反应后仍保持稳定[2]，这一点与文献报道一致[6]。
此外，掺杂样品的比表面积达到 210 m2/g，明显高于未掺杂样品。
"""

# 示例文献库（BibTeX）：含预印本与正式版重复、同一 DOI 重复、以及一条编造条目
library_bib = """
@article{wang2021doping,
  author = {Wang, Li and Zhang, Hui and Chen, Ming},
  title = {Doping-induced lattice contraction and catalytic activity in oxide catalysts},
  journal = {Journal of Catalysis},
  year = {2021}, volume = {398}, number = {2}, pages = {112--121},
  doi = {10.1016/j.jcat.2021.03.014}
}
@article{wang2021preprint,
  author = {Wang, Li and Zhang, Hui},
  title = {Doping induced lattice contraction and catalytic activity in oxide catalysts},
  journal = {arXiv preprint arXiv:2101.04567},
  year = {2021}, doi = {10.48550/arXiv.2101.04567}
}
@article{wang2021dup,
  author = {Wang, Li and Zhang, Hui and Chen, Ming},
  title = {Doping-Induced Lattice Contraction and Catalytic Activity in Oxide Catalysts},
  journal = {Journal of Catalysis},
  year = {2021}, volume = {398}, number = {2}, pages = {112-121},
  doi = {10.1016/J.CAT.2021.03.014}
}
@article{chen2020xrd,
  author = {Chen, Ming},
  title = {X-ray diffraction study of lattice constants in doped oxides},
  journal = {Materials Letters},
  year = {2020}, volume = {271}, pages = {127--134},
  doi = {10.1016/j.matlet.2020.11.009}
}
@article{liu2019stability,
  author = {Liu, Qiang and Zhao, Yan},
  title = {Long-term hydrothermal stability of doped oxide catalysts under reaction conditions},
  journal = {Applied Catalysis B},
  year = {2019}, volume = {245}, pages = {55--63},
  doi = {10.1016/j.apcatb.2019.01.007}
}
@article{fake2022ghost,
  author = {Smith, John},
  title = {Unpublished placeholder results on doping},
  journal = {Journal of Nonexistent Results},
  year = {2022}, doi = {doi:10.9999/fake.2022.001}
}
"""

# 示例草稿结果（结构照 output_contract；内容来自上面的合成材料）
draft = {
    "status": "partial",
    "results": {
        "citations": [
            {"claim_span": "本研究考察掺杂对催化活性的影响[1]。", "ref_keys": "wang2021doping",
             "placement": "sentence-end", "style": "GB/T 7714-2015"},
            {"claim_span": "在 25 °C 条件下，掺杂样品的产率提升到 42%[3]。", "ref_keys": "wang2021doping",
             "placement": "sentence-end", "style": "GB/T 7714-2015"},
            {"claim_span": "X 射线衍射表明晶格常数随掺杂量增大而减小[2]。", "ref_keys": "chen2020xrd",
             "placement": "sentence-end", "style": "GB/T 7714-2015"},
            {"claim_span": "掺杂样品在连续 10 小时反应后仍保持稳定[5]。", "ref_keys": "liu2019stability",
             "placement": "sentence-end", "style": "GB/T 7714-2015"},
        ],
        "reference_list": [
            {"key": "wang2021doping",
             "metadata": "WANG L, ZHANG H, CHEN M. Doping-induced lattice contraction and catalytic activity in oxide catalysts[J]. Journal of Catalysis, 2021, 398(2): 112-121. DOI: 10.1016/j.jcat.2021.03.014.",
             "doi": "10.1016/j.jcat.2021.03.014", "source": "wang2021doping; wang2021preprint; wang2021dup",
             "status": "verified_shape"},
            {"key": "liu2019stability",
             "metadata": "LIU Q, ZHAO Y. Long-term hydrothermal stability of doped oxide catalysts under reaction conditions[J]. Applied Catalysis B, 2019, 245: 55-63. DOI: 10.1016/j.apcatb.2019.01.007.",
             "doi": "10.1016/j.apcatb.2019.01.007", "source": "liu2019stability", "status": "verified_shape"},
            {"key": "chen2020xrd",
             "metadata": "CHEN M. X-ray diffraction study of lattice constants in doped oxides[J]. Materials Letters, 2020, 271: 127-134. DOI: 10.1016/j.matlet.2020.11.009.",
             "doi": "10.1016/j.matlet.2020.11.009", "source": "chen2020xrd", "status": "verified_shape"},
            {"key": "fake2022ghost",
             "metadata": "SMITH J. Unpublished placeholder results on doping[J]. Journal of Nonexistent Results, 2022. DOI: doi:10.9999/fake.2022.001.",
             "doi": "doi:10.9999/fake.2022.001", "source": "fake2022ghost", "status": "needs_check"},
        ],
        "dedup": [
            {"merged_keys": "wang2021doping, wang2021preprint, wang2021dup",
             "basis": "R-DOI; R-PREPRINT", "kept_key": "wang2021doping"}
        ],
        "consistency_checks": [
            {"claim": "该结果证明掺杂总是有效", "ref_key": "wang2021doping", "match": "weak",
             "evidence": "词重叠得分 0.31 | 题名：Doping-induced lattice contraction and catalytic activity in oxide catalysts"},
            {"claim": "掺杂样品在连续 10 小时反应后仍保持稳定", "ref_key": "liu2019stability",
             "match": "strong", "evidence": "词重叠得分 0.62 | 题名含 stability / hydrothermal"},
            {"claim": "这一点与文献报道一致", "ref_key": "?4", "match": "dangling",
             "evidence": "文献表无第 4 条"},
        ],
        "format_notes": {"target_style": "GB/T 7714-2015", "converted_from": "bibtex",
                         "kept_fields": ["DOI", "volume", "issue", "pages"]},
    },
    "sources": [
        {"source_id": "manuscript", "locator": "paragraph 1-2", "locator_type": "paragraph",
         "quote": "在 25 °C 条件下，掺杂样品的产率提升到 42%", "note": "正文断言原文"},
        {"source_id": "library.bib", "locator": "entry wang2021doping", "locator_type": "record",
         "quote": "doi = {10.1016/j.jcat.2021.03.014}", "note": "DOI 比对依据"},
    ],
    "uncertainty": [
        {"item": "第 4 条正文引用 [4] 无对应文献",
         "reason": "文献库无该编号条目，可能为漏导入或编号错位",
         "action_required": "补录条目或改编号，需作者确认"},
        {"item": "fake2022ghost 真实性",
         "reason": "DOI 形态非法（doi:10.9999/...），题名含 placeholder",
         "action_required": "按 DOI 解析或数据库检索核验，未核验前不得引用"},
    ],
    "changes": [
        {"step": "1", "action": "读取 manuscript 与 library.bib", "note": "确认两处输入与目标规范 GB/T 7714-2015"},
        {"step": "2", "action": "解析 BibTeX 6 条", "note": "字段映射 author/title/journal/year/volume/issue/pages/doi"},
        {"step": "3", "action": "去重合并 3 条为 1 条", "note": "DOI 相同 + 预印本与正式版同题"},
        {"step": "4", "action": "逐句核验论断与文献", "note": "3 条 strong/weak，另 1 条 dangling"},
        {"step": "5", "action": "标记编造条目", "note": "DOI 非法且题名占位，状态 needs_check"},
    ],
    "artifacts": [],
    "metadata": {"model": "doubao-work-agent", "runtime": "python3.13", "example_only": True},
}

case = {"case_id": "EXAMPLE-CASE-W04", "task_id": "product-arena-03-429cc14d",
        "target_style": "GB/T 7714-2015", "library_format": "bibtex"}
