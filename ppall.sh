#!/bin/bash

# Run all postprocessing for each experiment


# Add an optional command line argument called recompute that defaults to false

recompute=${1:-False}

for i in full-20 notide-20 blank-20 full-40 notide-40 blank-40 full-80 notide-80 blank-80;
do
  echo $i
  python3 recipes.py -r save_filtered_vels -c $recompute -e $i &
  python3 recipes.py -r save_vorticity -c $recompute -e $i &
done

