#!/usr/bin/env python3
import os
import warnings
from datetime import timedelta
from dask.distributed import Client,default_client
from dask import delayed, compute
import filtering
from pathlib import Path
home = Path("/home/149/ab8992/tasman-tides")
gdata = Path("/g/data/nm03/ab8992")
import numpy as np
import xarray as xr
os.chdir(home)
import ttidelib as tt
import argparse
def startdask(nthreads = 1):
    try:
    # Try to get the existing Dask client
        client = default_client()
        print(client)
    except ValueError:
        # If there's no existing client, create a new one
        client = Client(
            threads_per_worker = nthreads,n_workers = 96)
        print(client)
    return client

def save_data_for_filter(expt,zl,t0,tmpstorage,sample_window = 250):

    client = startdask()
    retry = 0
    while retry < 5:
        try:
            rawdata = tt.collect_data(
                expt,
                rawdata = ["u","v","rho"],
                timerange=(
                    t0 - sample_window // 2,t0 + sample_window // 2 + sample_window % 2
                    )).isel(zl = zl) # Load tanks the 80th! maybe quicker for lower res, not worth it .load()
            retry = 100
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Retry loading data")
            retry +=1
    print("Done loading data")
    attrs = {
        "u": rawdata.u.attrs,
        "v": rawdata.v.attrs,
        "time": rawdata.time.attrs,
        "xb": rawdata.xb.attrs,
        "yb": rawdata.yb.attrs,
        "zl": rawdata.zl.attrs,
        "base" : rawdata.attrs
    }
    ## Remove zl to make data properly 2D
    rawdata.u.attrs = {}
    rawdata.v.attrs = {}
    rawdata.zl.attrs = {}
    rawdata.time.attrs = {}
    rawdata.yb.attrs = {}
    rawdata.xb.attrs = {}
    rawdata = rawdata.assign_coords({
        "time":rawdata.time * 3600,
        "xb":rawdata.xb * 1000,
        "yb":rawdata.yb * 1000})
    rawdata = rawdata.drop_vars(["bathy","lat","lon"]) 
    if not os.path.exists(tmpstorage):
        os.makedirs(tmpstorage)
    print("Saving data to temporary storage")


    # for i in range(0,rawdata.zl.size):
    out = xr.merge(
        [
            rawdata.u,
            rawdata.v,
            rawdata.rho - rawdata.rho.mean("time"), # density anomaly
        ]
    )
    print("Raw saved data times")
    print(out.time.values[0],out.time.values[-1])
    for i in range(0,96):
        out.isel(zl = [i]).to_netcdf(tmpstorage + f"/raw_{i}.nc",mode="w")
    print("done")
    client.close() ## Have to close dask client or it messes up the filtering package
    return attrs


def lagrange_filter(zl,tmpstorage,filter_range,sample_window = 250):

    """
    Apply the Lagrange filter to the input data. This is a wrapper around the LagrangeFilter class in filtering.py
    Saves the outputs to `postprocessing/expt/lfiltered/t0-<t0>/filtered_<zl>.nc` with a separate file for each z level.
    Inputs:
        expt: str, the experiment to process
        zl: int, the z level(s) to process
        t0: int, the middle time of the time slice we care about
    """
    os.chdir(tmpstorage)
    FastCutoff = 2*np.pi/(9.8*3600)  ## Same as tolerences for bandpass in Waterhouse 2018
    SlowCutoff = 2*np.pi/(15*3600)


    data_map = {
            "U":tmpstorage + f"/raw_{zl}.nc",
            "V":tmpstorage + f"/raw_{zl}.nc",
            "rho":tmpstorage + f"/raw_{zl}.nc",
        }
    if os.path.exists(tmpstorage + f"/Filtered_{zl}.nc"):
        os.remove(tmpstorage + f"/Filtered_{zl}.nc")


    BandpassFilter = filtering.LagrangeFilter(
        tmpstorage + f"/Filtered_{zl}", ## Save intermediate output to temporary storage
        data_map, 
        {"U":"u","V":"v","rho":"rho"}, 
        {"lon":"xb","lat":"yb","time":"time"},
        sample_variables=["U","V","rho"], mesh="flat",frequency = np.array([SlowCutoff,FastCutoff]),filter_type = "bandpass",
        advection_dt =timedelta(minutes=5).total_seconds(),
        window_size = timedelta(hours=48).total_seconds(),
    )

    ## Ensure we take times either side of the point of interest
    BandpassFilter(times = filter_range) 

    ## Re add zl as dimension
    zl_value = float(xr.open_dataset("/g/data/nm03/ab8992/outputs/zl.nc").isel(zl = zl).zl.values)
    FilteredData = xr.open_dataset(tmpstorage + f"/Filtered_{zl}.nc").expand_dims({"zl":[zl_value]})
    FilteredData = FilteredData.assign_coords({
        "time":FilteredData.time / 3600,
        "xb":FilteredData.xb / 1000,
        "yb":FilteredData.yb / 1000})
    for i in FilteredData.data_vars:
        FilteredData = FilteredData.rename({i:i.split("_")[1].lower()})

    # outfolder = Path(f"/g/data/nm03/ab8992/postprocessed/{expt}/lfiltered/t0-{t0}")
    outfolder = Path(tmpstorage) / "output"

    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    FilteredData.to_netcdf(outfolder / f"Filtered_{zl}.nc",mode="w")
    return 


def lfilter_tidyup(tmpstorage,outputfolder,offset = -1):
    """Necessary tidying up of metadata and units for filtered outputs"""

    if offset == -1:
        offset = ""
    data = xr.open_mfdataset(tmpstorage + f"/output/Filtered_*.nc",combine="by_coords")
    data.zl.attrs = {'units': 'meters', 'long_name': 'Depth at cell center', 'axis': 'Z', 'positive': 'down', 'edges': 'z_i'}
    data.time.attrs = {'units': 'hours since 2010-01-01 00:00:00', 'long_name': 'time', 'axis': 'T', 'calendar_type': 'JULIAN', 'calendar': 'julian'}
    data.xb.attrs = {'long_name': 'Distance along beam from Tasmania towards Macquarie Ridge', 'units': 'km'}
    data.yb.attrs = {'long_name': 'Distance perpendicular to beam referened from beam centre', 'units': 'km'}
    data.attrs["long_name"] = f"filtered velocity data"
    data[["u","v","rho"]].to_netcdf(outputfolder / f"Filtered{offset}.nc",mode="w")
    return 


if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--expt', type=str, help='Experiment name', default="full-20")
    parser.add_argument('-t', '--t0', type=int, help='Start time')
    parser.add_argument('-o', '--offset', type=int, help='Offset from start time',default=-1)
    parser.add_argument('-w', '--window', type=int, help='Window', default=149)
    args = parser.parse_args()
    expt = args.expt

    ## Defaults if we're just doing all times in one hit
    t0 = args.t0
    filter_window = args.window
    filter_window = 233 #! UPDATE IN MAY to be more efficient for 80th degree
    # tmpstorage = "/scratch/nm03/ab8992/saphhirerapids"
    tmpstorage = os.getenv('PBS_JOBFS')
    # tmpstorage = "/scratch/nm03/ab8992/qsub_lfilter80"

    t0_adjusted = t0
    sample_window = 333 # 48hrs advection either side of sample window
    offset = args.offset
    ## If we're splitting into multiple jobs for different offsets, adjust times
    if offset != -1:
        filter_window = 17 #! Hardcoded for 12 lots of 17 hours + 12 hours
        # sample_window = 150
        start = sample_window // 2 - 117 + offset * filter_window
        if offset == 13:
            filter_window = 12
        stop = start + filter_window

    tt.logmsg(f"Filtering from {start} to {stop}")
    adjusted_t0 = t0 + (stop + start) // 2 - 117 # This gets the middle of the range being filtered
    tt.logmsg(f"Adjusted t0: {adjusted_t0}")

    outputfolder = Path(f"/g/data/nm03/ab8992/postprocessed/{expt}/bandpassed/t0-{t0}")
    if not os.path.exists(tmpstorage):
        os.makedirs(tmpstorage)

    if not os.path.exists(outputfolder):
        os.makedirs(outputfolder)

    # save_data_for_filter(expt,slice(0,96),t0,tmpstorage,sample_window = sample_window)
    tt.logmsg(f"Starting to pre-save for filtering of {expt} at t0 = {adjusted_t0}")
    save_data_for_filter(expt,slice(0,96),adjusted_t0,tmpstorage,sample_window = (stop - start + 100)) #! Alternative: Set sample window to stop - start + 100. Set t0 to the middle of the range. Load less data
    tt.logmsg(f"Done pre saving for filtering of {expt} at t0 = {adjusted_t0}")

    filter_range = range(
        3600 * 50,
        3600 * (50 + filter_window),
        3600)

    print("Data saved. Starting filtering...")
    client = startdask(nthreads = 1)
    tasks = [delayed(lagrange_filter)(n, tmpstorage,filter_range,filter_window) for n in range(96)]
    results = compute(*tasks)

    print("Done. Tidying up...")
    lfilter_tidyup(tmpstorage,outputfolder,offset = offset)
