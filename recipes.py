
#!/g/data/hh5/public/apps/miniconda3/envs/analysis3-23.04/bin/python python3
import argparse
import ttidelib as tt
import os
import subprocess
import time
from dask.distributed import Client
from matplotlib import pyplot as plt
def surfacespeed(experiment, outputs):
    """
    Make a movie of the surface speed for the given experiment and outputs
    """
    client = Client(threads_per_worker = 2)

    data = tt.collect_data(experiment,surface_data=["speed"],chunks = {"time":1})

    fig = plt.figure(figsize=(15, 12))

    tt.make_movie(data,tt.plot_surfacespeed,fig,"plot_surfacespeed","speed",parallel=True)

    return 

def recipe_2(experiment, outputs):
    # Implement recipe 2 logic here
    pass

def recipe_3(experiment, outputs):
    # Implement recipe 3 logic here
    pass

def qsub(recipe, experiment, outputs):
    tt.logmsg(f"Submitting {recipe} for {experiment}, {outputs} to qsub")
    if not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/{recipe}"):
        os.makedirs(f"/home/149/ab8992/tasman-tides/logs/{recipe}")
    text = f"""
#!/bin/bash
#PBS -N {recipe}-{experiment}
#PBS -P v45
#PBS -q normalbw
#PBS -l mem=112gb
#PBS -l walltime=6:00:00
#PBS -l ncpus=28
#PBS -l jobfs=2gb
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5
PYTHONNOUSERSITE=1
module use /g/data/hh5/public/modules
module load conda/analysis3-unstable
module list
python3 /home/149/ab8992/tasman-tides/recipes.py -r {recipe} -e {experiment} -o {outputs}"""

    with open(f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}.pbs", "w") as f:
        f.write(text)

    result = subprocess.run(
        f"qsub /home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}.pbs",
        shell=True,
        capture_output=True,
        text=True,
    )
    pbs_error = f"{recipe}-{experiment}.e{result.stdout.split('.')[0]}"
    pbs_log = f"{recipe}-{experiment}.o{result.stdout.split('.')[0]}"

    # Wait until the PBS logfile appears in the log folder
    while not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}"):
        time.sleep(10)

    ## Rename the logfile to be recipe--experiment--current_date
    current_date = time.strftime("%Y%m%d-%H%M%S")
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}",
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}-{current_date}.err",
    )
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_log}",
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}-{current_date}.out",
    )

    return
    
        




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to execute plotting functions from ttidelib")
    parser.add_argument("-r", "--recipe", choices=["recipe1", "recipe2", "recipe3"], help="Select the recipe to execute")
    parser.add_argument("-e", "--experiment", help="Specify the experiment to apply the recipe to")
    parser.add_argument("-o", "--outputs", help="Specify the outputs to use")
    parser.add_argument("-q", "--qsub", default=False, help="Choose whether to execute directly or as qsub job")
    args = parser.parse_args()



    if args.recipe == "recipe1":
        recipe_1(args.experiment, args.outputs)
    elif args.recipe == "recipe2":
        recipe_2(args.experiment, args.outputs)
    elif args.recipe == "recipe3":
        recipe_3(args.experiment, args.outputs)
