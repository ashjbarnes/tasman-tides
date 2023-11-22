#!/bin/bash

arg=${1:-"syncing local to gadi"}
git pull
git add --all
git commit -m "$arg"
git push


ssh ab8992@gadi.nci.org.au "cd tasman-tides; git pull; exit"
