#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[migrate] %s\n' "$1"
}

git_mv_if_exists() {
  local src="$1"
  local dst="$2"

  if [ -e "$src" ]; then
    log "git mv $src -> $dst"
    mkdir -p "$(dirname "$dst")"
    git mv "$src" "$dst"
  elif [ -e "$dst" ]; then
    log "skip move; destination already exists: $dst"
  else
    log "skip move; source missing: $src"
  fi
}

git_rm_if_exists() {
  local target="$1"

  if [ -e "$target" ]; then
    log "git rm -r $target"
    git rm -r "$target"
  else
    log "skip remove; missing: $target"
  fi
}

mkdir_if_missing() {
  local target="$1"

  if [ -d "$target" ]; then
    log "directory exists: $target"
  else
    log "mkdir -p $target"
    mkdir -p "$target"
  fi
}

touch_if_missing() {
  local target="$1"

  if [ -e "$target" ]; then
    log "file exists: $target"
  else
    log "touch $target"
    mkdir -p "$(dirname "$target")"
    touch "$target"
  fi
}

log "starting v0 -> v1 file migration"

mkdir_if_missing "config"
mkdir_if_missing ".streamlit"
mkdir_if_missing ".github/workflows"
mkdir_if_missing "src/collectors"
mkdir_if_missing "src/pipeline"
mkdir_if_missing "src/interpretation"
mkdir_if_missing "src/ui"
mkdir_if_missing "scripts"
mkdir_if_missing "data/baseline"
mkdir_if_missing "data/monitoring"
mkdir_if_missing "data/interpretations"
mkdir_if_missing "data/manual"

git_mv_if_exists "src/cleaner.py" "src/pipeline/clean.py"
git_mv_if_exists "src/labeler.py" "src/pipeline/label.py"
git_mv_if_exists "src/evaluate.py" "src/pipeline/evaluate.py"
git_mv_if_exists "src/reddit_collector.py" "src/collectors/reddit.py"
git_mv_if_exists "src/hn_collector.py" "src/collectors/hackernews.py"
git_mv_if_exists "data/labeled/manual_sample_100.csv" "data/manual/manual_sample_100.csv"

git_rm_if_exists "src/collector.py"
git_rm_if_exists "src/weibo_collector.py"
git_rm_if_exists "src/xhs_collector.py"
git_rm_if_exists "src/xhs_post_collector.py"
git_rm_if_exists "src/reddit_post_collector.py"
git_rm_if_exists "src/analyzer.py"
git_rm_if_exists "src/visualizer.py"
git_rm_if_exists "src/extract_examples.py"
git_rm_if_exists "sample.py"
git_rm_if_exists "data/raw"
git_rm_if_exists "data/cleaned"
git_rm_if_exists "output"
git_rm_if_exists "src/__pycache__"
git_rm_if_exists "__pycache__"

touch_if_missing "config/__init__.py"
touch_if_missing "src/__init__.py"
touch_if_missing "src/collectors/__init__.py"
touch_if_missing "src/pipeline/__init__.py"
touch_if_missing "src/interpretation/__init__.py"
touch_if_missing "src/ui/__init__.py"
touch_if_missing "data/monitoring/labeled_monitoring.csv"
touch_if_missing "data/interpretations/interpretations.json"

log "migration script finished"
log "note: consolidate data/labeled/*.csv into data/baseline/labeled_baseline.csv in the next phase before removing data/labeled"
