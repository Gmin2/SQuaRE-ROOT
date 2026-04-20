# SQuaRE MVP scope (narrative lock)

This page states **what the current MVP is** and **what it is not**, so stakeholders interpret reports correctly. For JSON field definitions see [`output-contract.md`](output-contract.md). For paper-by-paper honesty lists see [`validation_index.yaml`](validation_index.yaml) and [`validation_overview.md`](validation_overview.md).

## Flagship scenarios (in scope for MVP demos)

| Scenario file | Role |
|---------------|------|
| [`../Configs/oratomic_gold_path.yaml`](../Configs/oratomic_gold_path.yaml) | **Default demo:** neutral-atom (Cain et al.) + QLDPC + ECDLP secp256k1 envelope (Babbush algorithm YAML). Stable id `oratomic_gold_path`. |
| [`../Configs/rsa2048_gidney_ekera_2021_parallel.yaml`](../Configs/rsa2048_gidney_ekera_2021_parallel.yaml) | RSA-2048 stack with Gidney & Ekerå (2021) assumptions and **Table 2–style** pinned references in magic YAML. |
| [`../Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml`](../Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml) | Same ECDLP logical envelope on **superconducting + surface** (Babbush et al. 2026 headline comparison). |

## What we claim vs what we ship

- **Transparent accounting:** Every bundled default is traceable to YAML (`source`, `confidence`, `date`, optional DOI). The engine **does not invent citations**.
- **Not full paper replication:** Unless a validation section explicitly says otherwise, SQuaRE numbers are **stacked proxies** (heuristic code distance, Toffoli→depth rules, naive data-plane products, coarse schedules). They are **not** a byte-for-byte reproduction of each paper’s internal compiler or layout optimizer.
- **Not a product UI:** There is **no** browser app or slider UI in this MVP; the stakeholder path is **CLI** (Markdown or JSON).

## One command to show a stakeholder

From the `SQUARE/` directory after a normal install:

```bash
python -m pip install -e .
square-mvp-demo
```

JSON instead of Markdown:

```bash
square-mvp-demo --json
```

RSA-2048 flagship instead of Oratomic:

```bash
square-mvp-demo Configs/rsa2048_gidney_ekera_2021_parallel.yaml
```

Windows (if `python` is not on `PATH`): use `py -3 -m pip install -e .` then `square-mvp-demo` from the same environment.

## Reporting issues with numbers

Open an issue describing **(1)** the scenario file, **(2)** `report_contract_version` from the JSON root, **(3)** the YAML parameter keys you believe are wrong or missing a source, and **(4)** the paper section you expected to match. See also [CONTRIBUTING.md](../../CONTRIBUTING.md) at the repository root.
