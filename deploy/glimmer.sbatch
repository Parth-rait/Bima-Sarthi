#!/bin/bash
#SBATCH --job-name=glimmer
#SBATCH --partition=rtx
#SBATCH --gres=gpu:2g.48gb:1
#SBATCH --qos=general
#SBATCH --time=__SET_FROM_BILLING_POOL__
#SBATCH --output=%x-%j.log
# Rung 1 (hpc48): Glimmer 30B Q8_K_XL with vision. Set --time above from the remaining billing pool
# (HH:MM:SS, at most the QOS limit of 12 h) before submitting. The API key is read at runtime from the key file (--api-key-file keeps it out of the process list), never stored here.
M=/scratch/parth.rait.pg26/models/glimmer
exec ~/src/llama.cpp/build/bin/llama-server -m "$M/Muse-Glimmer-30B-UD-Q8_K_XL.gguf" --mmproj "$M/mmproj-Muse-Glimmer-30B-BF16.gguf" --alias glimmer -ngl 99 -c 32768 --jinja --host 0.0.0.0 --port 18080 --api-key-file "$HOME/.glimmer_key"
