# Validation overview (SQuaRE vs published sources)

Long-form comparisons are **not** split across many small markdown files. Use:

| Artifact | Role |
|----------|------|
| [`validation_index.yaml`](validation_index.yaml) | One row per **primary source / scenario family**: headlines, report JSON paths, discrepancy tags, anchor name. **Add new papers here first.** |
| This file | **Human-readable** detail: framework below, then **one section per index entry** (linked by anchor). |

## How to add a new modality or paper

1. Add assumptions + algorithm + scenario YAML as usual under `Assumptions/`, `Algorithms/`, `Configs/`.
2. Append an `entries[]` block to `validation_index.yaml` (copy the shape of an existing entry).
3. Add a `##` section below with the same `overview_section_anchor` as the heading slug (see existing ECDLP example).
4. Keep tables short; move unstable numbers to “re-run report” language so the doc does not rot.

## How to read comparisons

- **SQuaRE** exposes **transparent stacks** under YAML assumptions. Outputs are **not** automatic proof of a paper’s headline paragraph.
- When a bullet in `discrepancy_categories` applies, treat paper numbers and SQuaRE numbers as **different objects** unless you add pinned YAML rows that match the paper’s accounting.

---

<a id="ecdlp-babbush-et-al-2026"></a>

## ECDLP — Babbush et al. (2026)

**Index:** `entries[].id == ecdlp_secp256k1_babbush_et_al_2026` in [`validation_index.yaml`](validation_index.yaml).

This section compares **numbers emitted by SQuaRE** for `Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` to the **published narrative** in *Securing Elliptic Curve Cryptocurrencies against Quantum Vulnerabilities: Resource Estimates and Mitigations* (Babbush et al., dated March 30, 2026). It is **not** a replication of the paper’s internal compiler or ZK-backed circuit costs.

### What the paper states (abstract / introduction)

- Two logical resource envelopes for **256-bit ECDLP on secp256k1**; the bundled scenario uses **low_toffoli_variant**: **≤1450 logical qubits** and **≤70M Toffoli gates**.
- On **superconducting** hardware with **~10⁻³ physical error** and **planar connectivity**, the paper describes the attack as running in **minutes** and using **fewer than ~half a million physical qubits** (order-of-magnitude headline vs prior estimates).

### What SQuaRE reports (representative run)

Values below come from `build_scenario_report` on that scenario (engine as installed; **no CLI overrides**). See `representative_run_snapshot` in the index entry for a compact summary; **re-run** if defaults change.

| Quantity | Typical report value | Report path |
|----------|----------------------|-------------|
| Heuristic surface-code distance `d` | **~21** | `dashboard.code_distance_d`, `qec_distance_resolution` |
| Physical qubits per logical (patch at `d`) | **968** (`2(d+1)²`) | `qec_overhead.logical_qubit_patch_physical_qubit_count` |
| Naive data-plane physical qubits (`logical × patch`) | **~1.4×10⁶** | `dashboard.approximate_data_plane_physical_qubits` |
| Naive serial time (depth proxy × surface cycle) | **~0.00081 days ≈ 70 s ≈ 1.2 min** | `dashboard.naive_serial_time_days_from_depth_times_cycle`, `timing.naive_serial_from_measurement_depth` |
| Paper narrative upper bound (stored for reference) | **5×10⁵** physical qubits | `algorithm_metrics.ecdlp.paper_headline_physical_qubits_upper_bound_narrative` |

### Why these differ

1. **Different objects.** The paper’s **~500k qubits** and **minutes** refer to a **full resource picture** for a **compiled** architecture (scheduling, distillation footprint, control, etc.). SQuaRE’s **~1.4M** figure is a **naive data-plane proxy** only: **abstract logical qubits × patch qubits per logical** at heuristic `d`. It **excludes** factories, routing, and other overhead that the paper rolls into end-to-end totals, and it uses a **phenomenological distance heuristic**, not the paper’s optimizer.

2. **Depth is a proxy, not a schedule.** `abstract_measurement_depth_layers` is **Toffoli count ×** `ecdlp_measurement_depth_layers_per_toffoli_gate` (default **1.0**). That drives the union-bound distance choice and **naive_serial** time. It is **not** the paper’s layer-accurate fault-tolerant schedule. Naive serial time in the **same order of magnitude as “minutes”** can happen **by coincidence**; that does **not** mean the models are equivalent.

3. **Modality placeholders.** `superconducting_babbush_et_al_2026` uses **documented placeholder** cycle and reaction times where the abstract does not fix microseconds. Changing those values changes naive time and any reaction-aware heuristics.

4. **No Table 2–style pins.** RSA scenarios can align to Gidney & Ekerå **Table 2** pinned wall-clock and qubit totals. The ECDLP path does **not** ingest analogous pinned end-to-end rows for Babbush et al.; comparison is **conceptual** until such pins exist in YAML.

### How to tighten alignment

Replace **placeholder modality timings** from the full paper, refine the **Toffoli→depth** rule, and add **end-to-end** or **pinned** rows to the assumptions database when available.

---

<a id="ecdlp-cain-et-al-2026-neutral-atom-qldpc"></a>

## ECDLP — Cain et al. (2026), neutral atom + QLDPC stack

**Index:** `entries[].id == ecdlp_secp256k1_cain_et_al_2026_neutral_atom_qldpc` in [`validation_index.yaml`](validation_index.yaml).

Scenario [`Configs/ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml`](../Configs/ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml) keeps the **same algorithm document** as the Babbush ECDLP example (`ecdlp_secp256k1_babbush_et_al_2026`) but points `paths.modality` at [`neutral_atom_cain_et_al_2026.yaml`](../Assumptions/Modalities/neutral_atom_cain_et_al_2026.yaml) and `paths.qec_code` at [`qldpc_cain_et_al_2026.yaml`](../Assumptions/QEC_Codes/qldpc_cain_et_al_2026.yaml), per *Shor's algorithm is possible with as few as 10,000 reconfigurable atomic qubits* (arXiv:2603.28627).

### What the paper states (abstract)

- Combines **high-rate quantum error-correcting codes**, **efficient logical instruction sets**, and **circuit design** so Shor-class workloads at cryptographic scales can use **~10k** reconfigurable atomic qubits (headline), with **~26k** physical atoms cited for **P-256 discrete log** in **a few days** under plausible assumptions.
- Positions **neutral-atom** experiments (fault-tolerant ops below threshold, hundreds of qubits, large arrays) as motivation.

### What SQuaRE does here

- **Logical layer:** Unchanged ECDLP envelopes from the Babbush algorithm YAML (e.g. `low_toffoli_variant`).
- **Physical layer:** Neutral-atom modality YAML supplies gate/cycle/reaction **proxies** for report plumbing; QLDPC YAML supplies `code_family: quantum_ldpc` and a **symbolic** `logical_qubit_patch_physical_qubit_count_formula` in `d` (not a full LDPC layout from the paper).
- **Heuristic distance** still uses the phenomenological union-bound path with LDPC-tuned placeholder threshold metadata—**not** Cain et al.’s optimizer.

### How to tighten alignment

Pin **native error**, **syndrome / cycle times**, and **physical footprint** from the paper’s main text into the modality and QEC files; replace the patch formula when you have layout constants that map cleanly into SQuaRE’s `d`-based dashboard hooks or extend the engine for LDPC-specific parameters.
