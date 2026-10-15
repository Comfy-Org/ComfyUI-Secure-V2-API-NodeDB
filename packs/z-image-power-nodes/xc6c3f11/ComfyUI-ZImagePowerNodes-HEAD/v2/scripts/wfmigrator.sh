#!/usr/bin/env bash
# File    : wfmigrator.sh
# Purpose : Wrapper for `wfmigrator.py` to launch the python script
# Author  : Martin Rizzo | <martinrizzo@gmail.com>
# Date    : Apr 2, 2026
# Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
# License : MIT
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                          ComfyUI-ZImagePowerNodes
#         ComfyUI nodes designed specifically for the "Z-Image" model.
#_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
SCRIPT_NAME=$(basename "${BASH_SOURCE[0]}" .sh)           # script name without extension
SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")   # script directory
PYTHON_SCRIPT="${SCRIPT_DIR}/${SCRIPT_NAME}.py"           # path to python script to run

# Environment variables
# PYTHON  : specifies the path to the Python interpreter; default is `python3`
[[ "$PYTHON" ]] || PYTHON=python3

#===========================================================================#
#////////////////////////////////// MAIN ///////////////////////////////////#
#===========================================================================#

"$PYTHON" "$PYTHON_SCRIPT" "$@"
