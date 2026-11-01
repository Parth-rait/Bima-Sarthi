# Ground truth

Every fact the code depends on. Never change a value without Parth confirming. Record disagreements under "Open conflicts".

| Fact | Value | Source | Verified on | Status |
|---|---|---|---|---|
| Submission deadline | 9:00 PM EST 4 Nov 2026 = 7:30 AM IST 5 Nov 2026 | Plan brief | 30 Oct 2026 (plan) | Confirmed |
| Spark Open model ID | `meta-models/muse-spark-open` | Baseten (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Baseten base URL | `https://inference.baseten.co/v1` | Baseten (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Spark Open `-1026` ID | Returned 404; do not use | Baseten (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Glimmer weights file | `Muse-Glimmer-30B-UD-Q8_K_XL.gguf` (31 GB) | Cluster scratch (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Glimmer mmproj file | `mmproj-Muse-Glimmer-30B-BF16.gguf` (3.6 GB) | Cluster scratch (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Glimmer model directory | `/scratch/parth.rait.pg26/models/glimmer/` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Glimmer smaller quant | `UD-Q4_K_XL`, about 17 GB | Plan brief | 30 Oct 2026 (plan) | Confirmed |
| Cluster user | `parth.rait.pg26` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Cluster login host | `10.1.45.201` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Cluster partitions | `rtx` and `h200` only | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| QOS `general` | 12 h, 1 GPU, 4 jobs | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| H200 access | Closed to QOS `general` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| GPU node software | CUDA at `/usr/local/cuda`; no working `module load python` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| llama-server path | `~/src/llama.cpp/build/bin/llama-server` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| llama.cpp build flags | `GGML_NATIVE=OFF`, `CMAKE_CUDA_ARCHITECTURES=120` | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Model download method | `hf` xet downloader fails on scratch; use curl | Cluster (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Spark Open price | $1.25/M input tokens, $4.25/M output tokens | Baseten (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Kimi K3 fallback model and price | `moonshotai/Kimi-K3`; $3.00/M input tokens, $15.00/M output tokens (cached input ignored) | Baseten dashboard, pasted by Parth | 1 Nov 2026 | Confirmed |
| Nemotron Ultra fallback model and price | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B`; $0.60/M input tokens, $2.40/M output tokens (cached input ignored) | Baseten dashboard, pasted by Parth | 1 Nov 2026 | Confirmed |
| DeepSeek V4 Flash fallback model and price | `deepseek-ai/DeepSeek-V4-Flash-0731`; $0.13/M input tokens, $0.26/M output tokens (cached input ignored) | Baseten dashboard, pasted by Parth | 1 Nov 2026 | Confirmed |
| Firecrawl free tier | 1,000 credits a month | Firecrawl (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| Tavily free tier | 1,000 credits a month | Tavily (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| OpenAlex | $1 a day with a free key | OpenAlex (plan brief) | 30 Oct 2026 (plan) | Confirmed |
| CIO 2023-24 health complaints | 31,490 | CIO Annual Report 2023-24 (secondary) | 27 Oct 2026 | Confirmed |
| CIO 2023-24 awards to complainants | 6,235 | CIO Annual Report 2023-24 (secondary) | 27 Oct 2026 | Confirmed |
| CIO 2023-24 awards to insurers | 4,125 | CIO Annual Report 2023-24 (secondary) | 27 Oct 2026 | Confirmed |
| CIO 2023-24 mediated | 10,140 | CIO Annual Report 2023-24 (secondary) | 27 Oct 2026 | Confirmed |
| Ombudsman awards | Not public (OTP download only) | Plan brief | 27 Oct 2026 | Confirmed |
| Moratorium period | 60 months | Secondary source; primary fill in Task 6 Step 5 | 30 Oct 2026 (plan) | UNVERIFIED |
| Pre-existing disease wait cap | 36 months | Secondary source; primary fill in Task 6 Step 5 | 30 Oct 2026 (plan) | UNVERIFIED |
| Cashless authorisation time | 1 hour | Secondary source; primary fill in Task 6 Step 5 | 30 Oct 2026 (plan) | UNVERIFIED |
| Discharge authorisation time | 3 hours | Secondary source; primary fill in Task 6 Step 5 | 30 Oct 2026 (plan) | UNVERIFIED |
| Ombudsman wait before approaching | 1 month | ombudsman_rules_2017 p10, rule 14(3) | Verified on 1 Nov 2026 (confirmed by Parth) | Confirmed |
| Ombudsman claim-amount limit | ₹50 lakh (₹50,00,000) | irdai_ppi_master_2024 p135 | Verified on 1 Nov 2026 (confirmed by Parth) | Confirmed |
| Ombudsman award cap | ₹30 lakh (₹30,00,000) | ombudsman_rules_2017 p12, rule 17(3) | Verified on 1 Nov 2026 (confirmed by Parth) | Confirmed |
| Ombudsman filing window | 1 year | ombudsman_rules_2017 p10 | Verified on 1 Nov 2026 (confirmed by Parth) | Confirmed |
| Insurer reply deadline | 14 days | irdai_ppi_master_2024 p111 (also p123, p135) | Verified on 1 Nov 2026 (confirmed by Parth) | Confirmed |
| Indian Kanoon API price | Search ₹0.50, Document ₹0.20 per request (Original Document ₹0.50, Fragment ₹0.05, Metainfo ₹0.02); ₹500 free on signup; ₹10,000/month free for verified non-commercial use | https://api.indiankanoon.org/pricing/ | 1 Nov 2026 | Confirmed (official pricing page) |

## Open conflicts


| Fact | Value in use | Primary text says | Where | Raised | Status |
|---|---|---|---|---|---|
| Insurer reply deadline | 15 days | "Insurers should provide resolution to the complaint within 14 days" | irdai_ppi_master_2024 p111, p123, p135 | 1 Nov 2026 (rule-card quote check) | Resolved 1 Nov 2026: corrected to primary text, Parth confirmed |
| Wait before Ombudsman | 30 days | "within a period of one month after the insurer … received his representation" | ombudsman_rules_2017 p10, rule 14(3) | 1 Nov 2026 | Resolved 1 Nov 2026: corrected to primary text, Parth confirmed |
| Ombudsman ₹50 lakh cap | ₹50 lakh | ₹50 lakh appears as a claim-amount limit ("in case the claim amount is up to Rs. 50 lakhs"); the Rules cap awards at "rupees thirty lakhs" | irdai_ppi_master_2024 p135; ombudsman_rules_2017 p12, rule 17(3) | 1 Nov 2026 | Resolved 1 Nov 2026: corrected to primary text, Parth confirmed |
