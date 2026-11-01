#!/bin/bash
#SBATCH --job-name=glimmer-q4
#SBATCH --partition=rtx
#SBATCH --gres=gpu:1g.24gb:1
#SBATCH --qos=general
#SBATCH --time=__SET_FROM_BILLING_POOL__
#SBATCH --output=%x-%j.log
# Rung 2 (hpc24): Glimmer 30B UD-Q4_K_XL (about 17 GB), 0.50 credits per hour, faster queue.
# Set --time above from the remaining billing pool before submitting. The API key is read at runtime.
M=/scratch/parth.rait.pg26/models/glimmer
exec ~/src/llama.cpp/build/bin/llama-server -m "$M/Muse-Glimmer-30B-UD-Q4_K_XL.gguf" --mmproj "$M/mmproj-Muse-Glimmer-30B-BF16.gguf" --alias glimmer-q4 -ngl 99 -c 16384 --jinja --host 0.0.0.0 --port 18080 --api-key-file "$HOME/.glimmer_key"
