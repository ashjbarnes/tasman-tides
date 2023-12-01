
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

def save_pv(experiment,outputs):
    """
    Save the potential vorticity for the given experiment and outputs
    """
    startdask()

    outpath = gdata / "postprocessed/" / experiment / "pv"
    if not outpath.exists():
        outpath.mkdir(parents=True)
    print("Loading data")
    data = tt.collect_data(
        experiment,
        outputs=outputs,
        rawdata = ["u","v"],
        bathy=True
        )
    print("Lazily computing pv")
    pv = tt.calculate_pv(data)

    # now need to average over 149hr chunks
    # Spatial chunk was removed from the data, but we've reduced data size by 150. 
    # Originally, time chunk was 15 (5) days for 20th (40th) degree. For 20 deg, this means each time shapshot is a few mb. Perfect for movies in parallel

    # Iterate over time in pv with steps of 149 hours. Average over each step and save as a netcdf file 
    for t in range(0, len(pv.time), 149):
        print("Iteration",t,sep = "\t")
        t_str = str(t).zfill(5)  # Format t as a padded 5-digit string
        pv_chunk = pv.isel(time=slice(t, t + 149)).mean(dim="time").drop("time")
        ## Add the time dimension back in but call it TIME
        data = data.expand_dims("time")
        data = data.assign_coords(time = [400])
        data.TIME.attrs = pv.time.attrs
        pv_chunk.to_netcdf(outpath / f"pv_t{t_str}.nc")

    return pv



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
    parser.add_argument("-r", "--recipe", choices=["surfacespeed", "save_pv", "recipe3"], help="Select the recipe to execute")
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
    elif args.recipe == "save_pv":
        save_pv(args.experiment, args.outputs)
