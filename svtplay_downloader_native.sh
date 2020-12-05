#!/usr/bin/env bash

cd -- "${BASH_SOURCE[0]%/*}"
pipenv run python ./svtplay_downloader_native.py
