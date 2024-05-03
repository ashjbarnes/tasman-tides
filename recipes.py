#!/usr/bin/env python3
import argparse
import ttidelib as tt
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


#### LAGRANGE FILTERING
    
def lagrange_filter(expt,zl,t0,time_window = 100,filter_window = 50,filter_cutoff = 2*np.pi/(16*3600)):
    print("START LAGRANGE FILTERING")
    print("import filtering package:")
    import filtering

    """
    Apply the Lagrange filter to the input data. This is a wrapper around the LagrangeFilter class in filtering.py
    Saves the outputs to `postprocessing/expt/lfiltered/t0-<t0>/filtered_<zl>.nc` with a separate file for each z level.
    Inputs:
        expt: str, the experiment to process
        zl: int, the z level(s) to process
        t0: int, the middle time of the time slice we care about
    """
    HighFilterCutoff = 2*np.pi/(9.8*3600)  ## Same as tolerences for bandpass in Waterhouse 2018
    LowFilterCutoff = 2*np.pi/(15*3600)

    client = tt.startdask()
    dask.config.set(scheduler="single-threaded")
    tmpstorage = os.getenv('PBS_JOBFS')

    rawdata = tt.collect_data(
        expt,
        rawdata = ["u","v","ahh"],
        timerange=(t0 - time_window,t0 + time_window)).isel(zl = [zl])

    # Save attributes to re-add later
    attrs = {
        "u": rawdata.u.attrs,
        "v": rawdata.v.attrs,
        "time": rawdata.time.attrs,
        "xb": rawdata.xb.attrs,
        "yb": rawdata.yb.attrs,
        "zl": rawdata.zl.attrs,
        "base" : rawdata.attrs
    }

    ## Save z level to re-add later
    zl_value = rawdata.zl.values[0]

    ## Remove zl to make data properly 2D
    _rawdata = rawdata.isel(zl = 0) # Make a copy to modify the metadata to keep lagrange filter happy
    # We'll keep rawdata for use later.

    # Strip attrs since lagrange filter complains about them
    _rawdata.u.attrs = {}
    _rawdata.v.attrs = {}
    _rawdata.zl.attrs = {}
    _rawdata.time.attrs = {}
    _rawdata.yb.attrs = {}
    _rawdata.xb.attrs = {}
    _rawdata = _rawdata.assign_coords({
        "time":_rawdata.time * 3600,
        "xb":_rawdata.xb * 1000,
        "yb":_rawdata.yb * 1000})
    _rawdata = _rawdata.drop_vars(["bathy","lat","lon"]) 

    print("Saving data to temporary storage")
    _rawdata.u.to_netcdf(tmpstorage + f"/u.nc",mode="w")
    _rawdata.v.to_netcdf(tmpstorage + f"/v.nc",mode="w")
    (_rawdata.v**2).rename("vv").to_netcdf(tmpstorage + f"/vv.nc",mode="w")
    (_rawdata.u**2).rename("uu").to_netcdf(tmpstorage + f"/uu.nc",mode="w")
    (_rawdata.u*_rawdata.v).rename("uv").to_netcdf(tmpstorage + f"/uv.nc",mode="w")
    print("done")
    client.close() ## Have to close dask client or it messes up the filtering package

    f_high = filtering.LagrangeFilter(
        tmpstorage + "/lowpass", ## Save intermediate output to temporary storage
        {
            "U":tmpstorage + "/u.nc",
            "V":tmpstorage + "/v.nc",
            "uu":tmpstorage + "/uu.nc",
            "vv":tmpstorage + "/vv.nc",
            "uv":tmpstorage + "/uv.nc"
        }, 
        {"U":"u","V":"v","uu":"uu","vv":"vv","uv":"uv"}, 
        {"lon":"xb","lat":"yb","time":"time"},
        sample_variables=["U","V","vv","uu","uv"], mesh="flat",highpass_frequency = HighFilterCutoff,
        advection_dt =timedelta(minutes=5).total_seconds(),
        window_size = timedelta(hours=48).total_seconds(),
    )
    f_low = filtering.LagrangeFilter(
        tmpstorage + "/highpass", ## Save intermediate output to temporary storage
        {
            "U":tmpstorage + "/u.nc",
            "V":tmpstorage + "/v.nc",
            "uu":tmpstorage + "/uu.nc",
            "vv":tmpstorage + "/vv.nc",
            "uv":tmpstorage + "/uv.nc"
        }, 
        {"U":"u","V":"v","uu":"uu","vv":"vv","uv":"uv"}, 
        {"lon":"xb","lat":"yb","time":"time"},
        sample_variables=["U","V","vv","uu","uv"], mesh="flat",highpass_frequency = LowFilterCutoff,
        advection_dt =timedelta(minutes=5).total_seconds(),
        window_size = timedelta(hours=48).total_seconds()
    )
    print("lowpass filter")
    ## Ensure we take times either side of the point of interest
    f_low(times = range(3600 * (time_window - filter_window),3600 * (time_window + filter_window),3600)) 
    print("Highpass filter")
    f_high(times = range(3600 * (time_window - filter_window),3600 * (time_window + filter_window),3600)) ## Ensure we take 

    

    ## Remove stored data to save space on disk
    for i in ["u","v","uu","vv","uv"]:
        os.remove(tmpstorage + f"/{i}.nc")

    client = tt.startdask()
    print(os.listdir(tmpstorage))
    ## Load the filtered data
    highpass = xr.open_dataset(tmpstorage + "/highpass.nc",chunks = "auto")
    lowpass = xr.open_dataset(tmpstorage + "/lowpass.nc",chunks = "auto")


    def tidyup(filtered):
        """Necessary tidying up of metadata and units for filtered outputs"""
    ## Re-add zl as a dimension. Expand dims, then add zl
        filtered = filtered.expand_dims({"zl":[zl_value]})

        ## Restore scale and attributes of rawdata
        filtered = filtered.assign_coords({
            "time":filtered.time / 3600,
            "xb":filtered.xb / 1000,
            "yb":filtered.yb / 1000})

        ## Fix up names of filtered variables:
        for i in filtered.data_vars:
            filtered = filtered.rename({i:i.split("_")[1].lower()})

        filtered.attrs = attrs["base"]
        filtered.u.attrs = attrs["u"]
        filtered.v.attrs = attrs["v"]
        filtered.zl.attrs = attrs["zl"]
        filtered.time.attrs = attrs["time"]
        filtered.yb.attrs = attrs["yb"]
        filtered.xb.attrs = attrs["xb"]

        filtered.attrs["long_name"] = "Filtered velocity data"
        return filtered

    highpass = tidyup(highpass)
    lowpass = tidyup(lowpass)
    outfolder = Path(f"/g/data/nm03/ab8992/postprocessed/{expt}/lfiltered/t0-{t0}")

    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    highpass["cst"] = tt.cross_scale_transfer(highpass)
    lowpass["cst"] = tt.cross_scale_transfer(lowpass) 
    highpass[["u","v","cst"]].to_netcdf(outfolder / f"highpass_{zl}.nc",mode="w")
    lowpass[["u","v","cst"]].to_netcdf(outfolder / f"lowpass_{zl}.nc",mode="w")
    return 






def postprocess(experiment,outputs,recompute = False):
    if outputs == "output*":
        outputs = "all"
    print(startdask())
    tt.postprocessing(outputs,experiment,recompute)
    return

def qsub_lagrange_filter(experiment,zl,t0,windowsize):
    tt.logmsg(f"Submitting lagrange filter for {experiment}, {zl}, {t0}, {windowsize} to qsub")
    text = f"""
#!/bin/bash
#PBS -N lf-{experiment}-{zl}-{t0}
#PBS -P x77
#PBS -q normalbw
#PBS -l mem=112gb
#PBS -l walltime=4:00:00
#PBS -l ncpus=28
#PBS -l jobfs=100gb
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
PYTHONNOUSERSITE=1
cd /scratch/v45/ab8992/tmp
source /home/149/ab8992/libraries/conda/filtering_env/bin/activate
python3 /home/149/ab8992/tasman-tides/recipes.py -r lagrange_filter -e {experiment}  -q 0 -t {t0} -z {zl} -w {windowsize}"""
    with open(f"/home/149/ab8992/tasman-tides/logs/lfilter/lfilter-{experiment}-{zl}.pbs", "w") as f:
        f.write(text)

    result = subprocess.run(
        f"qsub /home/149/ab8992/tasman-tides/logs/lfilter/lfilter-{experiment}-{zl}.pbs",
        shell=True,
        capture_output=True,
        text=True,
        cwd = f"/home/149/ab8992/tasman-tides/logs/lfilter",
    )
    pbs_error = f"lfilter-{experiment}-{zl}.e{result.stdout.split('.')[0]}"
    pbs_log = f"lfilter-{experiment}-{zl}.o{result.stdout.split('.')[0]}"


    # Wait until the PBS logfile appears in the log folder
    while not os.path.exists(f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_error}"):
        time.sleep(10)

    ## Rename the logfile to be recipe--experiment--current_date
    current_date = time.strftime("%b_%d_%H-%M-%S").lower()
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_error}",
        f"/home/149/ab8992/tasman-tides/logs/lfilter/{experiment}-{zl}_{current_date}.err",
    )
    os.rename(
        f"/home/149/ab8992/tasman-tides/logs/lfilter/{pbs_log}",
        f"/home/149/ab8992/tasman-tides/logs/lfilter/{experiment}-{zl}_{current_date}.out",
    )

def qsub(recipe, experiment, outputs,recompute):
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
#PBS -q normalbw
#PBS -l mem=112gb
#PBS -l walltime=12:00:00
#PBS -l ncpus=28
#PBS -l jobfs=100gb
#PBS -l storage=gdata/v45+scratch/v45+scratch/x77+gdata/v45+gdata/nm03+gdata/hh5+scratch/nm03
PYTHONNOUSERSITE=1
module use /g/data/hh5/public/modules
module load conda/analysis3-unstable
module list
python3 /home/149/ab8992/tasman-tides/recipes.py -r {recipe} -e {experiment} -o {outputs} -q 0 {recompute} """

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
        "full-20","full-40","full-80","notide-20","notide-40","notide-80","blank-20","blank-40","blank-80"
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
    parser.add_argument("-q", "--qsub", default=1,type=int, help="Choose whether to execute directly or as qsub job")
    parser.add_argument("-c", "--recompute", action="store_true", help="Recompute completed calculations or not")
    parser.add_argument("-t", "--t0", type=int, help="For lagrange filter: choose the midpoint of the time slice to filter")
    parser.add_argument("-z", "--zl", default = 0,type=int,help="For lagrange filter: choose which z levels to include. eg 0-20 or 5")
    parser.add_argument("-w", "--windowsize", default = 200,type=int,help="For lagrange filter: choose hours either side of t0 to include")
    args = parser.parse_args()


    if args.recipe == None:
        print("Available recipes:\nsurface_speed_movie\nsave_vorticity\nsave_filtered_vels\nspinup_timeseries\nke_movie\ndissipation_movie\nvorticity_movie")
        	
    elif args.recipe == "stocktake":
        stocktake()
        

    elif args.qsub == 1:
        if args.recipe == "lagrange_filter":
            qsub_lagrange_filter(args.experiment,args.zl,args.t0,args.windowsize)

        qsub(args.recipe, args.experiment, args.outputs,args.recompute)


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

    elif args.recipe == "postprocess":
        postprocess(args.experiment,args.outputs,args.recompute)

    elif args.recipe == "lagrange_filter":
        lagrange_filter(args.experiment,args.zl,args.t0,args.windowsize)