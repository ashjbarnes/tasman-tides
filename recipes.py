#!/usr/bin/env python3
import argparse
import ttidelib as tt
import glob
import os
import subprocess
import time
from datetime import timedelta
import dask
from dask.distributed import Client,default_client
from matplotlib import pyplot as plt
from pathlib import Path
home = Path("/home/149/ab8992/tasman-tides")
gdata = Path("/g/data/nm03/ab8992")
import numpy as np
import xarray as xr
from cftime import date2num,DatetimeJulian

def startdask():
    try:
    # Try to get the existing Dask client
        client = default_client()
        print("Startdask: found existing client")
        print(client)
    except ValueError:
        # If there's no existing client, create a new one
        print("Startdask: no client found. Creating a new one")
        client = Client()
        print(client)

    return client

def surface_speed_movie(experiment):
    """
    Make a movie of the surface speed
    """
    resolution = experiment.split("-")[-1]
    startdask()

    speed = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/{experiment}/**/surface.nc",decode_times=False,parallel = True,decode_cf = False).speed.isel(time=slice(None, None, 10))

    speed = speed.chunk({"time":1,"xh":-1,"yh":-1})

    # interpolate the xq and yq onto xh and yh using xarray built in method
    bathy = xr.open_mfdataset(f"/g/data/nm03/ab8992/ttide-inputs/full-{resolution}/topog_raw.nc",decode_times = False).elevation
    bathy = bathy.rename({"lat":"yh","lon":"xh"})
    bathy = bathy.where(bathy > 0).persist()

    print(speed)
    data = xr.Dataset(
        {
            "speed":speed,
            "bathy":bathy
        }
    )


    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_surfacespeed,
                experiment,
                "surface_speed",
                framerate=30,
                parallel=True)

    return


def vorticity_movie(experiment, outputs):
    """
    Make a movie of the vorticity for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,ppdata=["vorticity"],chunks = {"time":1})
    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_vorticity,
                experiment,
                "vorticity",
                framerate=5,
                parallel=True)

    return

def ekman_pumping_movie(experiment):
    """
    Make a movie of the ekman pumping
    """
    resolution = experiment.split("-")[-1]
    startdask()

    tau = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/{experiment}/**/surface.nc",decode_times=False,chunks = {"time":1})[["taux","tauy"]]
    # interpolate the xq and yq onto xh and yh using xarray built in method
    tau = tau.interp(xq = tau.xh,yq = tau.yh)
    bathy = xr.open_mfdataset(f"/g/data/nm03/ab8992/ttide-inputs/full-{resolution}/topog_raw.nc",decode_times = False).elevation
    bathy = bathy.rename({"lat":"yh","lon":"xh"})
    bathy = bathy.where(bathy > 0).persist()

    curl = tau.tauy.differentiate("xh") - tau.taux.differentiate("yh")

    data = xr.Dataset(
        {
            "curl":curl,
            "bathy":bathy
        }
    )


    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_ekman_pumping,
                experiment,
                "ekman_pumping",
                framerate=5,
                parallel=False)

    return

def ke_movie(experiment, outputs):
    """
    Make a movie of the vorticity for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data("full-20",ppdata = ["vorticity","UU","VV"])

    print("loaded data")
    print(data)
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_ke,
                experiment,
                "M2_Kinetic_Energy",
                framerate=5,
                parallel=True)

    return

def dissipation_movie(experiment, outputs):
    """
    Make a movie of the m2 dissipation anomalies for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,ppdata = ["vorticity","dissipation"],chunks = {"time":1})

    print("loaded data")
    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_dissipation,
                experiment,
                "M2_dissipation",
                framerate=5,
                parallel=True)



    return

def dissipation_anomaly_movie(experiment, outputs):
    """
    Make a movie of the m2 dissipation anomalies for the given experiment and outputs
    """
    startdask()

    data = tt.collect_data(experiment,ppdata = ["vorticity","dissipation"],chunks = {"time":1})

    print("loaded data")
    print("Make dissipation anomaly movie")

    data["dissipation_topdown_mean"] = data["dissipation_topdown"].mean("time").compute()
    data["dissipation_transect_mean"] = data["dissipation_transect"].mean("time").compute()

    fig = plt.figure(figsize=(20, 12))

    print("Start making movie...")
    tt.make_movie(data,
                tt.plot_dissipation,
                experiment,
                "M2_dissipation_anomaly",
                framerate=5,
                parallel=True,
                plot_kwargs = {"anomaly":True}
    )

    return



def save_vorticity(experiment,outputs,recompute = False):
    """
    Save the relative vorticity for the given experiment and outputs
    """
    basepath = gdata / "postprocessed" / experiment / "vorticity"
    startdask()


    rawdata = tt.collect_data(
        experiment,
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
        rawdata = ["u","v","ahh"],
        chunks = {"zl":10}
        )
    print("Data loaded")
    for i in range(0,len(data.time) // averaging_window):
        mid_time =  data.time[int(np.floor((i + 0.5) * averaging_window)) ] ## Middle of time window time

        ## Here skip the time slice if it already exists and recompute is False
        if os.path.exists(basepath / "UU" / "topdown" / f"UU_time-{int(mid_time.values)}.nc") and not recompute:
            print("Skipping time",f"{i} = {mid_time}")
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
            m2f).compute()
        V = tt.m2filter(
            v_,
            m2f).compute()
        
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
        f"/g/data/nm03/ab8992/outputs/{experiment}/output*/u/*.nc",decode_times = False,parallel=True
    ).fillna(0)
    v = xr.open_mfdataset(
        f"/g/data/nm03/ab8992/outputs/{experiment}/output*/v/*.nc",decode_times = False,parallel=True
    ).fillna(0)
    print("Calculate ke")
    ke = (u.u**2 + v.v**2).integrate("xb").integrate("yb").integrate("zl")
    if not os.path.exists(f"/g/data/nm03/ab8992/postprocessed/{experiment}"):
        os.makedirs(f"/g/data/nm03/ab8992/postprocessed/{experiment}")
    ke.to_netcdf(f"/g/data/nm03/ab8992/postprocessed/{experiment}/ke_timeseries.nc")


   

def vmodes(expt,t0 = 10000):
    client = tt.startdask(nthreads = 1)
    print(client)
    tt.logmsg(f"Starting vertical modes calculation for {expt} {t0}")
    data = tt.collect_data(
            exptname=expt,
            rawdata = ["rho"],
            timerange = (t0 - 233,t0 + 233 )
        ).sel(yb = slice(-125,125))
    if "zi" in data:
        data = data.drop_vars("zi")
    H = data.bathy
    if H.mean("xb").mean("yb") <= 0:
        H *= -1
    tt.logmsg("VMODES: data loaded.")
    N = tt.getN(data.rho).mean("time")

    #! OLD! Doesn't work with 80th. Way too much overhead. Modify to coarsen data first
    #! N = tt.getN(data.rho).mean("time").load()
    #! print("Collected N, loading data..")
    #! data = xr.merge([N.rename("N"),H.rename("H")]).load()
    data = xr.merge([N.rename("N"),H.rename("H")]).coarsen(xb = 4,yb = 4,boundary = "trim").mean().load()
    print("coarsened. Now vmodes")
    
    data = data.chunk({"xb":1,"yb":1,"zl":-1})



    tt.logmsg("Calculating vertical modes")
    out = tt.ShootingVmodes_parallel(data,nmodes = 6).load()
    tt.logmsg("success")
    if not os.path.exists(f"/g/data/nm03/ab8992/postprocessed/{expt}/vertical_eigenfunctions"):
        os.makedirs(f"/g/data/nm03/ab8992/postprocessed/{expt}/vertical_eigenfunctions")
    out.to_netcdf(f"/g/data/nm03/ab8992/postprocessed/{expt}/vertical_eigenfunctions/vmode-t0-{t0}.nc")

    return
    
def check_outputs(expt,rerun = True):
    print(expt,end = "\n\n")
    if "40" in expt:
        no = 34
    elif "10" in expt:
        no = 10
    else:
        no = 17

    dirs = os.listdir(f"/g/data/nm03/ab8992/outputs/{expt}")
    vars = ["ahh","v","u","e","rho"]
    # tell me how many files in each directory
    # print(dirs)
    for dir in dirs:
        if dir[0] != "o":
            continue

        bad = False
        for var in vars:
            # print(len(os.listdir(f"/g/data/nm03/ab8992/outputs/{expt}/" + dir + "/" + var)))
            if not os.path.exists(f"/g/data/nm03/ab8992/outputs/{expt}/" + dir + "/" + var):

                bad = True
            if os.path.exists(f"/g/data/nm03/ab8992/outputs/{expt}/" + dir + "/" + var) and len(glob.glob(f"/g/data/nm03/ab8992/outputs/{expt}/" + dir + "/" + var + "/*.nc")) != no:
                
                bad = True

                
        if bad:
            print("\t" + dir,end = "\n")
            if rerun:
                subprocess.run(
                        f"python3 recipes.py -r postprocess -e {expt} -o {int(dir.split('output')[-1])} & ",
                        shell=True,
                        text=True,
                        cwd = f"/home/149/ab8992/tasman-tides",
                        )


def postprocess(experiment,outputs,recompute = False):
    if outputs == "output*":
        outputs = "all"
    print(startdask())
    tt.postprocessing(outputs,experiment,recompute)
    return

def qsub_lagrange_filter(experiment,t0,windowsize,offset):
    tt.logmsg(f"Submitting lagrange filter for {experiment}, {t0}, {windowsize} to qsub")
    text = f"""
#!/bin/bash
#PBS -N lf-{experiment}-{t0}-{offset}
#PBS -P x77
#PBS -q normalsr
#PBS -l mem=512gb
#PBS -l walltime=6:00:00
#PBS -l ncpus=104
#PBS -l jobfs=400gb
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
PYTHONNOUSERSITE=1
cd /scratch/v45/ab8992/tmp
source /g/data/hh5/public/apps/miniconda3/envs/analysis3-24.04/bin/activate
python3 /home/149/ab8992/tasman-tides/lfilter.py -e {experiment} -t {t0} -w {windowsize} -o {offset}
"""
    with open(f"/home/149/ab8992/tasman-tides/logs/lfilter/lfilter-{experiment}-{t0}-{offset}.pbs", "w") as f:
        f.write(text)

    result = subprocess.run(
        f"qsub /home/149/ab8992/tasman-tides/logs/lfilter/lfilter-{experiment}-{t0}-{offset}.pbs",
        shell=True,
        capture_output=True,
        text=True,
        cwd = f"/home/149/ab8992/tasman-tides/logs/lfilter",
    )
    pbs_error = f"lf-{experiment}-{t0}-{offset}.e{result.stdout.split('.')[0]}"
    pbs_log = f"lf-{experiment}-{t0}-{offset}.o{result.stdout.split('.')[0]}"


    # # Wait until the PBS logfile appears in the log folder
    # while not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_error}"):
    #     time.sleep(10)

    # ## Rename the logfile to be recipe--experiment--current_date
    # current_date = time.strftime("%b_%d_%H-%M-%S").lower()
    # os.rename(
    #     f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_error}",
    #     f"/home/149/ab8992/tasman-tides/logs/lfilter/{experiment}-{offset}_{current_date}.err",
    # )
    # os.rename(
    #     f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_log}",
    #     f"/home/149/ab8992/tasman-tides/logs/lfilter/{experiment}-{offset}_{current_date}.out",
    # )

def qsub(recipe, experiment, outputs,recompute,t0):
    tt.logmsg(f"Submitting {recipe} for {experiment}, {outputs} to qsub")
    if not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/{recipe}"):
        os.makedirs(f"/home/149/ab8992/tasman-tides/logs/{recipe}")
    if recompute:
        recompute = "-c "
    else:
        recompute = ""
    text = f"""
#!/bin/bash
#PBS -N {recipe}-{experiment}
#PBS -P x77
#PBS -q normalsr
#PBS -l mem=512gb
#PBS -l walltime=6:00:00
#PBS -l ncpus=104
#PBS -l jobfs=400gb
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
PYTHONNOUSERSITE=1
source /g/data/hh5/public/apps/miniconda3/envs/analysis3-24.04/bin/activate
python3 /home/149/ab8992/tasman-tides/recipes.py -r {recipe} -e {experiment} -o {outputs} -q 0 {recompute} -t {t0}"""
    filename = f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}-{outputs}.pbs"
    if recipe == "vmodes":
        filename = f"/home/149/ab8992/tasman-tides/logs/{recipe}/{recipe}-{experiment}-{t0}.pbs"
    with open(filename, "w") as f:
        f.write(text)

    result = subprocess.run(
        f"qsub {filename}",
        shell=True,
        capture_output=True,
        text=True,
        cwd = f"/home/149/ab8992/tasman-tides/logs/{recipe}",
    )
    pbs_error = f"{recipe}-{experiment}.e{result.stdout.split('.')[0]}"
    pbs_log = f"{recipe}-{experiment}.o{result.stdout.split('.')[0]}"

    # Wait until the PBS logfile appears in the log folder
    # while not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}"):
    #     time.sleep(10)

    # ## Rename the logfile to be recipe--experiment--current_date
    # current_date = time.strftime("%b_%d_%H-%M-%S").lower()
    # os.rename(
    #     f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_error}",
    #     f"/home/149/ab8992/tasman-tides/logs/{recipe}/{experiment}_{current_date}.err",
    # )
    # os.rename(
    #     f"/home/149/ab8992/tasman-tides/logs/{recipe}/{pbs_log}",
    #     f"/home/149/ab8992/tasman-tides/logs/{recipe}/{experiment}_{current_date}.out",
    # )

    return
    
def stocktake():
    """
    Parses all of the experiment folders in the 'gdata' directory and outputs a list of the experiments 
    alongside the timestamp of the last output in both the 'postprocessed' and 'outputs' directories.
    """
    base_dirs = [
        # Path('/g/data/nm03/ab8992/postprocessed'),
        Path('/g/data/nm03/ab8992/outputs')
    ]
    expts = [
        "full-20","full-40","full-80","notide-20","notide-40","notide-80","blank-20","blank-40","blank-80","smooth-20","smooth-40"
    ]
    outstr = "Expt\t\t Last \t End Date \t Total Days\n"
    for expt in expts:
        for base_dir in base_dirs:
            
            # Get a list of all netCDF files in the directory
            files = (base_dir / expt).glob("**/surface.nc")
            lastfile = None
            for file in files:
                if "output" in file.parent.name and (lastfile == None or int(file.parent.name.split("output")[1]) > int(lastfile.parent.name.split("output")[1])):
                    lastfile = file

            ds = xr.open_dataset(lastfile)

            # Get the 'time' variable
            time = ds['time'].values[-1]
            # Convert the 'time' variable to a Julian Day number
            time_julian = date2num(time, 'days since 0001-01-01 00:00:00')

            # Convert the specific date to a Julian Day number
            date_julian = date2num(DatetimeJulian(2015, 1, 1), 'days since 0001-01-01 00:00:00')

            # Find the number of days between the two dates
            total_days = time_julian - date_julian
            
            # Get the last timestamp
            last_timestamp = time
            outstr += f"{expt} \t {lastfile.parent.name.split('output')[-1]} \t {last_timestamp.strftime('%Y-%m-%d')} \t {round(total_days)}\n"
    
    ## Save the output string to a file located in path
    with open("/home/149/ab8992/tasman-tides/stocktake.txt", "w+") as f:
        f.write(outstr)
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to execute plotting functions from ttidelib")
    parser.add_argument("-r", "--recipe", help="Select the recipe to execute",default=None)
    parser.add_argument("-e", "--experiment", help="Specify the experiment to apply the recipe to")
    parser.add_argument("-o", "--outputs", help="Specify the outputs to use",default = "output*")
    parser.add_argument("-n", "--offset", help="Offset from t0. Used by lfilter",default = "output*")
    parser.add_argument("-q", "--qsub", default=1,type=int, help="Choose whether to execute directly or as qsub job")
    parser.add_argument("-c", "--recompute", action="store_true", help="Recompute completed calculations or not")
    parser.add_argument("-t", "--t0", type=int, default = 10000, help="For lagrange filter: choose the midpoint of the time slice to filter")
    parser.add_argument("-z", "--zl", default = 0,type=int,help="For lagrange filter: choose which z levels to include. eg 0-20 or 5")
    parser.add_argument("-w", "--windowsize", default = 149,type=int,help="For lagrange filter: choose hours either side of t0 to include")
    args = parser.parse_args()


    if args.recipe == None:
        print("Available recipes:\nsurface_speed_movie\nsave_vorticity\nsave_filtered_vels\nspinup_timeseries\nke_movie\ndissipation_movie\nvorticity_movie")
        	
    elif args.recipe == "stocktake":
        stocktake()
        

    elif args.qsub == 1:
        if args.recipe == "lagrange_filter":
            qsub_lagrange_filter(args.experiment,args.t0,args.windowsize,args.offset)
        
        elif args.recipe == "check_outputs":
            for expt in ["smooth-20","smooth-40","smooth-10","beamless-10","beamless-20","beamless-40","full-10"]:
                check_outputs(expt)
        else:
            qsub(args.recipe, args.experiment, args.outputs,args.recompute,args.t0)


    elif args.recipe == "surface_speed_movie":
        surface_speed_movie(args.experiment)

    elif args.recipe == "save_vorticity":
        save_vorticity(args.experiment, args.outputs,args.recompute)

    elif args.recipe == "save_filtered_vels":
        save_filtered_vels(args.experiment, args.outputs,args.recompute)

    elif args.recipe == "spinup_timeseries":
        spinup_timeseries(args.experiment)

    elif args.recipe == "ke_movie":
        ke_movie(args.experiment, args.outputs)

    elif args.recipe == "dissipation_movie":
        dissipation_movie(args.experiment, args.outputs)
    elif args.recipe == "dissipation_anomaly_movie":
        dissipation_anomaly_movie(args.experiment, args.outputs)

    elif args.recipe == "vorticity_movie":
        vorticity_movie(args.experiment, args.outputs)

    elif args.recipe == "ekman_pumping_movie":
        ekman_pumping_movie(args.experiment)

    elif args.recipe == "check_outputs":
        for expt in ["smooth-20","smooth-40","smooth-10","beamless-10","beamless-20","beamless-40","full-10"]:
            check_outputs(expt)

    elif args.recipe == "postprocess":
        postprocess(args.experiment,args.outputs,args.recompute)

    elif args.recipe == "lagrange_filter":
        lagrange_filter(args.experiment,args.zl,args.t0,args.windowsize)

    elif args.recipe == "vmodes":
        vmodes(args.experiment,t0 = args.t0)

