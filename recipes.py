
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

    data = tt.collect_data(experiment,ppdata=["vorticity_surface","vorticity_transect"],chunks = {"time":1},outputs=outputs,bathy=True)
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

def save_ppdata(transect_data,topdown_data,basepath,recompute = False):
    """
    Save the postprocessed data to gdata. Takes computed topdown and transect data and saves each time slice to postprocessed folders
    Time index override is used when processing one time slice at a time. That way the index can be used to name the file correctly
    """
    print(basepath)
    print(basepath.name)
    print(str(type(basepath.name)))
    for i in ["topdown","transect"]:
        if not os.path.exists(basepath / i):
            os.makedirs(basepath / i)

    for i in range(len(topdown_data.time.values)):
        time = topdown_data.time.values[i]
        if not os.path.exists(basepath / "topdown" / f"vorticity_time-{str(i).zfill(3)}.nc") or recompute:
            topdown_data.isel(time = i).expand_dims("time").assign_coords(time = [time]).to_netcdf(basepath / "topdown" / str(basepath.name + f"_time-{str(round(time))}.nc"))

        if not os.path.exists(basepath / "transect" / f"vorticity_time-{str(i).zfill(3)}.nc") or recompute:
            transect_data.isel(time = i).expand_dims("time").assign_coords(time = [time]).to_netcdf(basepath / "transect" / str(basepath.name + f"_time-{str(round(time))}.nc"))


    return

def save_vorticity(experiment,outputs,recompute = False):
    """
    Save the relative vorticity for the given experiment and outputs
    """
    basepath = gdata / "postprocessed" / experiment / "vorticity"
    startdask()


    rawdata = tt.collect_data(
        experiment,
        outputs=outputs,
        rawdata = ["u","v"],
        chunks = {"time": -1,"xb":-1,"zl":10}
        )

    vorticity_topdown = tt.calculate_vorticity(rawdata).coarsen(time = 149,boundary = "trim").mean().drop("lat").drop("lon").rename("vorticity").isel(zl = 2)
    vorticity_transect = tt.calculate_vorticity(rawdata).coarsen(time = 149,boundary = "trim").mean().drop("lat").drop("lon").rename("vorticity").sel(yb = 0,method = "nearest")

    save_ppdata(vorticity_transect,vorticity_topdown,basepath,recompute=recompute)

    return 

def save_filtered_vels(experiment,outputs,recompute = False):
    """
    Calculate the filtered velocities over 149 hours and save u'u', v'v', u'v' all averaged over 149 hours as separate files
    """
    startdask()

    m2 = 360 / 28.984104 ## Period of m2 in hours
    averaging_window = int(12 * m2) ## this comes out to be 149.0472 hours, so close enough to a multiple of tidal periods
    m2f = 1/ m2    ## Frequency of m2 in radians per hour

    data = tt.collect_data(
        experiment,
        outputs=outputs,
        rawdata = ["u","v"],
        bathy=False,
        chunks = {"time": -1,"xb":-1,"zl":10}
        )
    for i in range(0,len(data.time) // averaging_window):
        mid_time =  data.time[round((i + 0.5) * averaging_window) ] ## Middle of time window time

        print("Processing time slice",f"{i} = {mid_time}")
        u_ = data.u.isel(
                time = slice(i * averaging_window, (i + 1) * averaging_window)
                ).chunk({"time":-1}).drop(["lat","lon"]).fillna(0)
        v_ = data.v.isel(
                time = slice(i * averaging_window, (i + 1) * averaging_window)
                ).chunk({"time":-1}).drop(["lat","lon"]).fillna(0)
        U = tt.m2filter(
            u_,
            m2f).persist()
        V = tt.m2filter(
            v_,
            m2f).persist()
        
        data_to_save = {
            "UU" : (U * U).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("UU"),
            "VV" : (V * V).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("VV"),
            "UV" : (U * V).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("UV"),
            "laplacian" : (
                U.differentiate("xb").differentiate("xb") + V.differentiate("yb").differentiate("yb")
                ).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("velocity_laplacian")
        }

        for key in data_to_save:
            basepath = gdata / "postprocessed" / experiment / key
            save_ppdata(
                data_to_save[key].sel(yb = 0,method = "nearest"),
                data_to_save[key].integrate("zl"),
                basepath,
                recompute=recompute
            )

    return 


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
    parser.add_argument("-r", "--recipe", choices=["surfacespeed", "save_vorticity", "save_filtered_vels"], help="Select the recipe to execute")
    parser.add_argument("-e", "--experiment", help="Specify the experiment to apply the recipe to")
    parser.add_argument("-o", "--outputs", help="Specify the outputs to use",default = "output*")
    parser.add_argument("-q", "--qsub", default=1,type=int, help="Choose whether to execute directly or as qsub job")
    parser.add_argument("-c", "--recompute", default=False,type=bool, help="Choose whether to execute directly or as qsub job")
    args = parser.parse_args()

    print(args)

    if args.qsub == 1:
        print(f"qsub {args.recipe}")
        qsub(args.recipe, args.experiment, args.outputs)
    elif args.recipe == "surfacespeed":
        surfacespeed_movie(args.experiment, args.outputs)
    elif args.recipe == "save_vorticity":
        save_vorticity(args.experiment, args.outputs,args.recompute)
    elif args.recipe == "save_filtered_vels":
        save_filtered_vels(args.experiment, args.outputs,args.recompute)
