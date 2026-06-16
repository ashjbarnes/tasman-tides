#!/bin/bash
#PBS -N blank20-pp
#PBS -P x77
#PBS -q normal
#PBS -l mem=112gb
#PBS -l walltime=6:00:00
#PBS -l ncpus=28
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
#PBS -l jobfs=10gb
cd $PBS_O_WORKDIR
PYTHONNOUSERSITE=1
module use /g/data/hh5/public/modules
module load conda/analysis3-24.04
module list
python3 /home/149/ab8992/tasman-tides/debug_postprocessing.py -p "last" -c 6
