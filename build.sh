#!/usr/bin/env bash
cd ../data/incoming
cp -r /opt/gravis/data/cases/to_copy/input .
cd /opt/gravis/app
cd processing/mra
docker build -t gravis-processing .
cd ../..