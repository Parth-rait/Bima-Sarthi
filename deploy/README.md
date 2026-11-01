# Deploy

Fallback ladder (`models.yaml`, used via `<ROLE>_FALLBACKS=hpc48,hpc24,kaggle,baseten,ollama_dev`):

| Rung | Model | Served by | Runbook |
|---|---|---|---|
| 1 `hpc48` | Glimmer Q8 + mmproj, vision | `glimmer.sbatch` (rtx, gpu:2g.48gb:1) | runbook 19a (kept outside the repo) |
| 2 `hpc24` | Glimmer UD-Q4_K_XL, vision | `glimmer_q4.sbatch` (rtx, gpu:1g.24gb:1) | runbook 19a (kept outside the repo) |
| 3 `kaggle` | Glimmer Q4 on 2 T4 | `kaggle_glimmer.ipynb` | runbook 19b (kept outside the repo) |
| 4 `baseten` | Spark Open | hosted (no file) | `.env`: `BASETEN_API_KEY` |
| 5 `ollama_dev` | Llama 3.2 3B, text only, dev | local Ollama | runbook 19c (kept outside the repo) |

Public demo: `Dockerfile.space` (+ `.dockerignore`), reader and writer on Baseten; see runbook 19d (kept outside the repo).
The sbatch files hold a `--time` placeholder to set from the billing pool; API keys are never stored in any file here.
