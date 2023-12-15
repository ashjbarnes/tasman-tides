#!/bin/bash
#PBS -N notide40-pprocess
#PBS -P v45
#PBS -q normalbw
#PBS -l mem=224gb
#PBS -l walltime=24:00:00
#PBS -l ncpus=56
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
#PBS -l jobfs=10gb
cd $PBS_O_WORKDIR
PYTHONNOUSERSITE=1
module use /g/data/hh5/public/modules
module load conda/analysis3-unstable
module list
python3 /home/149/ab8992/tasman-tides/postprocessing.py -p "28-30" -c 6
