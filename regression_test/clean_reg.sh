#!/bin/bash

# Safety check: ensure we're in the regression_test directory
current_dir=$(basename "$(pwd)")
if [[ "$current_dir" != "regression_test" ]]; then
    echo "Error: This script must be executed from the regression_test directory."
    echo "Current directory: $(pwd)"
    exit 1
fi

rm -rf *.log
rm -rf compare_version_list

# Clean directories except .empty files
find run -mindepth 1 ! -name '.empty' -delete
find references/local -mindepth 1 ! -name '.empty' -delete
find references/cloud -mindepth 1 ! -name '.empty' -delete
