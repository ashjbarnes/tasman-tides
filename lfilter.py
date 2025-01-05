#!/usr/bin/env python3
import os
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
def startdask(nthreads = 4):
    try:
    # Try to get the existing Dask client
        client = default_client()
        print(client)
    except ValueError:
        # If there's no existing client, create a new one
        client = Client(
            threads_per_worker = nthreads)
        print(client)
    return client

def save_data_for_filter(expt,zl,t0,tmpstorage,sample_window = 250):

    client = startdask()

    rawdata = tt.collect_data(
        expt,
        rawdata = ["u","v"],
        timerange=(
            t0 - sample_window // 2,t0 + sample_window // 2 + sample_window % 2
            )).isel(zl = zl).load()
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
            (rawdata.v**2).rename("vv"),
            (rawdata.u**2).rename("uu"),
            (rawdata.u*rawdata.v).rename("uv"),
        ]
    )

    for i in range(0,96):
        out.isel(zl = [i]).to_netcdf(tmpstorage + f"/raw_{i}.nc",mode="w")
    print("done")
    client.close() ## Have to close dask client or it messes up the filtering package
    return attrs


def lagrange_filter(zl,tmpstorage,filter_window = 2,sample_window = 250):

    """
    Apply the Lagrange filter to the input data. This is a wrapper around the LagrangeFilter class in filtering.py
    Saves the outputs to `postprocessing/expt/lfiltered/t0-<t0>/filtered_<zl>.nc` with a separate file for each z level.
    Inputs:
        expt: str, the experiment to process
        zl: int, the z level(s) to process
        t0: int, the middle time of the time slice we care about
    """
    print(f"Filtering zl = {zl} with windowsize {filter_window}")
    os.chdir(tmpstorage)
    FastCutoff = 2*np.pi/(9.8*3600)  ## Same as tolerences for bandpass in Waterhouse 2018
    SlowCutoff = 2*np.pi/(15*3600)


    data_map = {
            "U":tmpstorage + f"/raw_{zl}.nc",
            "V":tmpstorage + f"/raw_{zl}.nc",
            "uu":tmpstorage + f"/raw_{zl}.nc",
            "vv":tmpstorage + f"/raw_{zl}.nc",
            "uv":tmpstorage + f"/raw_{zl}.nc"
        }
    if os.path.exists(tmpstorage + f"/SlowFilter_{zl}.nc"):
        os.remove(tmpstorage + f"/SlowFilter_{zl}.nc")
    if os.path.exists(tmpstorage + f"/FastFilter_{zl}.nc"):
        os.remove(tmpstorage + f"/FastFilter_{zl}.nc")


    FastFilter = filtering.LagrangeFilter(
        tmpstorage + f"/FastFilter_{zl}", ## Save intermediate output to temporary storage
        data_map, 
        {"U":"u","V":"v","uu":"uu","vv":"vv","uv":"uv"}, 
        {"lon":"xb","lat":"yb","time":"time"},
        sample_variables=["U","V","vv","uu","uv"], mesh="flat",highpass_frequency = FastCutoff,
        advection_dt =timedelta(minutes=5).total_seconds(),
        window_size = timedelta(hours=48).total_seconds(),
    )
    SlowFilter = filtering.LagrangeFilter(
        tmpstorage + f"/SlowFilter_{zl}", ## Save intermediate output to temporary storage
        data_map, 
        {"U":"u","V":"v","uu":"uu","vv":"vv","uv":"uv"}, 
        {"lon":"xb","lat":"yb","time":"time"},
        sample_variables=["U","V","vv","uu","uv"], mesh="flat",highpass_frequency = SlowCutoff,
        advection_dt =timedelta(minutes=5).total_seconds(),
        window_size = timedelta(hours=48).total_seconds()
    )
    trange = range(
        3600 * (sample_window // 2 - filter_window // 2),
        3600 * (sample_window // 2 + filter_window // 2 + filter_window % 2),
        3600)
    ## Ensure we take times either side of the point of interest
    # FastFilter(times = trange) 
    print("Highpass filter")
    SlowFilter(times = trange) 
    FastFilter(times = trange) 

    ## Re add zl as dimension
    zl_value = float(xr.open_dataset("/g/data/nm03/ab8992/outputs/zl.nc").isel(zl = zl).zl.values)
    SlowfilterData = xr.open_dataset(tmpstorage + f"/SlowFilter_{zl}.nc").expand_dims({"zl":[zl_value]})
    SlowfilterData = SlowfilterData.assign_coords({
        "time":SlowfilterData.time / 3600,
        "xb":SlowfilterData.xb / 1000,
        "yb":SlowfilterData.yb / 1000})
    for i in SlowfilterData.data_vars:
        SlowfilterData = SlowfilterData.rename({i:i.split("_")[1].lower()})

    # repeat for fast filter
    FastfilterData = xr.open_dataset(tmpstorage + f"/FastFilter_{zl}.nc").expand_dims({"zl":[zl_value]})
    FastfilterData = FastfilterData.assign_coords({
        "time":FastfilterData.time / 3600,
        "xb":FastfilterData.xb / 1000,
        "yb":FastfilterData.yb / 1000})
    for i in FastfilterData.data_vars:
        FastfilterData = FastfilterData.rename({i:i.split("_")[1].lower()})

    # outfolder = Path(f"/g/data/nm03/ab8992/postprocessed/{expt}/lfiltered/t0-{t0}")
    outfolder = Path(tmpstorage) / "output"

    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    SlowfilterData.to_netcdf(outfolder / f"SlowFilter_{zl}.nc",mode="w")
    FastfilterData.to_netcdf(outfolder / f"FastFilter_{zl}.nc",mode="w")
    return 


def lfilter_tidyup(tmpstorage,outputfolder,offset = -1):
    """Necessary tidying up of metadata and units for filtered outputs"""

    if offset == -1:
        offset = ""
    for i in ["Fast","Slow"]:
        data = xr.open_mfdataset(tmpstorage + f"/output/{i}Filter_*.nc",combine="by_coords")
        data.zl.attrs = {'units': 'meters', 'long_name': 'Depth at cell center', 'axis': 'Z', 'positive': 'down', 'edges': 'z_i'}
        data.time.attrs = {'units': 'hours since 2010-01-01 00:00:00', 'long_name': 'time', 'axis': 'T', 'calendar_type': 'JULIAN', 'calendar': 'julian'}
        data.xb.attrs = {'long_name': 'Distance along beam from Tasmania towards Macquarie Ridge', 'units': 'km'}
        data.yb.attrs = {'long_name': 'Distance perpendicular to beam referened from beam centre', 'units': 'km'}
        data.attrs["long_name"] = f"{i}filtered velocity data"
        cst = tt.cross_scale_transfer(data)
        data["cst"] = cst
        data[["u","v","cst"]].to_netcdf(outputfolder / f"{i}Filter{offset}.nc",mode="w")
    return 


if __name__ == "__main__":
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
    # tmpstorage = "/scratch/nm03/ab8992/saphhirerapids"
    tmpstorage = os.getenv('PBS_JOBFS')
    t0_adjusted = t0
    sample_window = 250
    offset = args.offset
    ## If we're splitting into multiple jobs for different offsets, adjust times
    if offset != -1:
        filter_window = 15 #! Hardcoded for 9 lots of 15 hours + 14 hours
        # sample_window = 150
        t0_adjusted = t0 - 75 + offset * 15 + 7
        if offset == 9:
            filter_window = 14

    outputfolder = Path(f"/g/data/nm03/ab8992/postprocessed/{expt}/lfiltered/t0-{t0}")
    if not os.path.exists(tmpstorage):
        os.makedirs(tmpstorage)

    if not os.path.exists(outputfolder):
        os.makedirs(outputfolder)

    save_data_for_filter(expt,slice(0,96),t0_adjusted,tmpstorage,sample_window = sample_window)
    print("Data saved. Starting filtering...")
    client = startdask(nthreads = 1)
    tasks = [delayed(lagrange_filter)(n, tmpstorage,filter_window) for n in range(96)]
    results = compute(*tasks)

    print("Done. Tidying up...")
    lfilter_tidyup(tmpstorage,outputfolder,offset = offset)
