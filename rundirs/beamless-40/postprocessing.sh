#!/bin/bash
#PBS -N beamless40-pprocess
#PBS -P nm03
#PBS -q normal
#PBS -l mem=112gb
#PBS -l walltime=6:00:00
#PBS -l ncpus=48
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
cd $PBS_O_WORKDIR
PYTHONNOUSERSITE=1
source /g/data/hh5/public/apps/miniconda3/envs/analysis3-24.04/bin/activate

python3 /home/149/ab8992/tasman-tides/postprocessing.py -p "last" -c 6
cp MOM_override_largestep MOM_override