
import argparse
import ttidelib as tt
import os
import subprocess
import time
from dask.distributed import Client,default_client
from matplotlib import pyplot as plt
from pathlib import Path
home = Path("/home/149/ab8992/tasman-tides")
gdata = Path("/g/data/nm03/ab8992")

def startdask():
    try:
    # Try to get the existing Dask client
        client = default_client()
    except ValueError:
        # If there's no existing client, create a new one
        client = Client()

def surfacespeed_movie(experiment, outputs):
    """
    Make a movie of the surface speed for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,surface_data=["speed"],chunks = {"time":1},outputs=outputs,bathy=True)
    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(15, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_surfacespeed,
                experiment,
                "surface_speed",
                framerate=10,
                parallel=True)

    return

def vorticity_movie(experiment, outputs):
    """
    Make a movie of the surface speed for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,data=["vorticity_surface","vorticity_transect"],chunks = {"time":1},outputs=outputs,bathy=True)
    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_vorticity,
                experiment,
                "surface_speed",
                framerate=10,
                parallel=True)

    return


def save_vorticity(experiment,outputs):
    """
    Save the potential vorticity for the given experiment and outputs
    """

    startdask()
    outpath = gdata / "postprocessed" / experiment
    if not os.path.exists(outpath):
        os.makedirs(outpath)

    rawdata = tt.collect_data(
        experiment,
        outputs=outputs,
        rawdata = ["u","v"],
        bathy=True,
        chunks = {"time": -1,"xb":-1,"zl":10}
        )

    vorticity = tt.calculate_vorticity(rawdata).coarsen(time = 149,boundary = "trim").mean().drop("lat").drop("lon").rename("vorticity")
    print("Computing voricity transect")
    vorticity_transect = vorticity.sel(yb = 0,method = "nearest")
    print("Computing vorticity surface")
    vorticity_surface = vorticity.isel(zl = 2)

    vorticity_surface.to_netcdf(outpath / "vorticity_surface.nc")
    vorticity_transect.to_netcdf(outpath / "vorticity_transect.nc")
    return vorticity



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
python3 /home/149/ab8992/tasman-tides/recipes.py -r {recipe} -e {experiment} -o {outputs} -q 0"""

    with open(f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}.pbs", "w") as f:
        f.write(text)

    result = subprocess.run(
        f"qsub /home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}.pbs",
        shell=True,
        capture_output=True,
        text=True,
        cwd = f"/home/149/ab8992/tasman-tides/logs/{recipe}",
    )
    pbs_error = f"{recipe}-{experiment}.e{result.stdout.split('.')[0]}"
    pbs_log = f"{recipe}-{experiment}.o{result.stdout.split('.')[0]}"

    # Wait until the PBS logfile appears in the log folder
    while not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}"):
        time.sleep(10)

    ## Rename the logfile to be recipe--experiment--current_date
    current_date = time.strftime("%b_%d_%H-%M-%S").lower()
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}",
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{experiment}_{current_date}.err",
    )
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_log}",
        f"/home/149/ab8992/tasman-tides/logs/{recipe}/{experiment}_{current_date}.out",
    )

    return
    
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to execute plotting functions from ttidelib")
    parser.add_argument("-r", "--recipe", choices=["surfacespeed", "save_vorticity", "recipe3"], help="Select the recipe to execute")
    parser.add_argument("-e", "--experiment", help="Specify the experiment to apply the recipe to")
    parser.add_argument("-o", "--outputs", help="Specify the outputs to use",default = "output*")
    parser.add_argument("-q", "--qsub", default=1,type=int, help="Choose whether to execute directly or as qsub job")
    args = parser.parse_args()

    print(args)

    if args.qsub == 1:
        print(f"qsub {args.recipe}")
        qsub(args.recipe, args.experiment, args.outputs)
    elif args.recipe == "surfacespeed":
        surfacespeed_movie(args.experiment, args.outputs)
    elif args.recipe == "save_vorticity":
        save_vorticity(args.experiment, args.outputs)
