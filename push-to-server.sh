#!/usr/bin/env bash

rsync -avz \
    --exclude '.git' \
    --exclude '.env' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude 'apps/backend/storage/' \
    --exclude 'apps/frontend/dist/' \
    -e "ssh -i ~/.ssh/facefit" \
    /Users/valtzmanmagnus/Desktop/facefit/ facefit@34.107.61.101:/opt/facefit/


