#!/usr/bin/env bash

../scripts/wfmigrator.sh GGUF --fp8  --output-dir FP8
../scripts/wfmigrator.sh GGUF --bf16 --output-dir BF16
