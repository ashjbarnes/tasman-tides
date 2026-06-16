#!/bin/bash
#PBS -N ttide-pprocess
#PBS -P v45
#PBS -q normal
#PBS -l walltime=5:00:00
#PBS -l ncpus=96
#PBS -l mem=384GB
#PBS -l jobfs=100GB
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5
cd $PBS_O_WORKDIR
PYTHONNOUSERSITE=1
module use /g/data/hh5/public/modules
module load conda/analysis3-23.04
module list
python3 /home/149/ab8992/tasman-tides/postprocessing.py
