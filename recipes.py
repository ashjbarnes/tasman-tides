
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
import numpy as np
import xarray as xr

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
    Make a movie of the vorticity for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,ppdata=["vorticity"],chunks = {"time":1},outputs=outputs,bathy=True)
    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_vorticity,
                experiment,
                "surface_speed",
                framerate=5,
                parallel=True)

    return

def ke_movie(experiment, outputs):
    """
    Make a movie of the vorticity for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data("full-20",ppdata = ["vorticity","UU","VV"],outputs = outputs,bathy = True)

    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_ke,
                experiment,
                "M2 Kinetic Energy",
                framerate=5,
                parallel=True)

    return

def dissipation_movie(experiment, outputs):
    """
    Make a movie of the m2 dissipation anomalies for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data("full-20",ppdata = ["vorticity","dissipation"],outputs = outputs,bathy = True)

    data["dissipation"] = data["dissipation"] - data["dissipation"].mean("time")

    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_dissipation,
                experiment,
                "M2 dissipation",
                framerate=5,
                parallel=True)

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

    tt.save_ppdata(vorticity_transect,vorticity_topdown,basepath,recompute=recompute)

    return 

def save_filtered_vels(experiment,outputs,recompute = False):
    """
    Calculate the filtered velocities over 149 hours and save u'u', v'v', u'v' all averaged over 149 hours as separate files
    """
    startdask()
    basepath = gdata / "postprocessed" / experiment

    m2 = 360 / 28.984104 ## Period of m2 in hours
    averaging_window = int(12 * m2) ## this comes out to be 149.0472 hours, so close enough to a multiple of tidal periods
    m2f = 1/ m2    ## Frequency of m2 in radians per hour

    data = tt.collect_data(
        experiment,
        outputs=outputs,
        rawdata = ["u","v","ahh"],
        bathy=False,
        chunks = {"time": -1,"xb":-1,"zl":10}
        )
    
    for i in range(0,len(data.time) // averaging_window):
        mid_time =  data.time[int(np.floor((i + 0.5) * averaging_window)) ] ## Middle of time window time

        ## Here skip the time slice if it already exists and recompute is False
        if os.path.exists(basepath / "dissipation" / "topdown" / f"dissipation_time-{str(i).zfill(3)}.nc") and not recompute:
            continue


        print("Processing time slice",f"{i} = {mid_time}")
        u_ = data.u.isel(
                time = slice(i * averaging_window, (i + 1) * averaging_window)
                ).chunk({"time":-1}).drop(["lat","lon"]).fillna(0)
        v_ = data.v.isel(
                time = slice(i * averaging_window, (i + 1) * averaging_window)
                ).chunk({"time":-1}).drop(["lat","lon"]).fillna(0)
        ahh = data.ahh.isel(
                time = slice(i * averaging_window, (i + 1) * averaging_window)
                ).chunk({"time":-1}).drop(["lat","lon"]).fillna(0)
        U = tt.m2filter(
            u_,
            m2f).persist()
        V = tt.m2filter(
            v_,
            m2f).persist()
        
        # Calculate dissipation as viscosity * laplacian(u)^2 
        laplacian2 = (U.differentiate("xb").differentiate("xb") + V.differentiate("yb").differentiate("yb")
                )**2
        dissipation = (laplacian2.mean("time") * ahh.mean("time")).expand_dims("time").assign_coords(time = [mid_time]).rename("dissipation")

        data_to_save = {
            "UU" : (U * U).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("UU"),
            "VV" : (V * V).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("VV"),
            "UV" : (U * V).mean("time").expand_dims("time").assign_coords(time = [mid_time]).rename("UV"),
            "dissipation" : dissipation
        }

        for key in data_to_save:
            tt.save_ppdata(
                data_to_save[key].sel(yb = 0,method = "nearest"),
                data_to_save[key].integrate("zl"),
                basepath / key,
                recompute=recompute
            )

    return 

def spinup_timeseries(experiment):
    """
    Timeseries of the total integrated kinetic energy in the domain of interest
    """
    u = xr.open_mfdataset(
        f"/g/data/nm03/ab8992/outputs/{experiment}/output*/u/*",decode_times = False,parallel=True
    ).fillna(0)
    v = xr.open_mfdataset(
        f"/g/data/nm03/ab8992/outputs/{experiment}/output*/v/*",decode_times = False,parallel=True
    ).fillna(0)
    print("Calculate ke")
    ke = (u.u**2 * v.v**2).integrate("xb").integrate("yb").integrate("zl")
    if not os.path.exists(f"/g/data/nm03/ab8992/postprocessed/{experiment}"):
        os.makedirs(f"/g/data/nm03/ab8992/postprocessed/{experiment}")
    ke.to_netcdf(f"/g/data/nm03/ab8992/postprocessed/{experiment}/ke_timeseries.nc")


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
    parser.add_argument("-r", "--recipe", help="Select the recipe to execute")
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

    elif args.recipe == "spinup_timeseries":
        spinup_timeseries(args.experiment)