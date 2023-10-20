#!/bin/bash
#PBS -N python-test
#PBS -P <project code>
#PBS -q normal
#PBS -l walltime=5:00:00
#PBS -l ncpus=96
#PBS -l mem=384GB
#PBS -l jobfs=100GB
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03
module use /g/data/hh5/public/apps/miniconda3/envs/
module load analysis3-23.04

python3 /home/149/ab8992/tasman-tides/postprocessing.py
