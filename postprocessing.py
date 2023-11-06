from pathlib import Path
import numpy as np
import os
import shutil
import xarray as xr
from dask.distributed import Client
import haversine
from pathlib import Path
import sys
sys.path.append("/home/149/ab8992/tasman-tides/")
import ttidelib as tt
import json

#TODO Have postprocessing script read the diag table to figure out which variables to process?

#TODO Allow python file to take arguments for chunking?

hourly_diags = {
    "u":
    {"x":"xh","y":"yh","z":"zl"},
    "h":
    {"x":"xh","y":"yh","z":"zl"},
    "v":
    {"x":"xh","y":"yh","z":"zl"},
    "rho":
    {"x":"xh","y":"yh","z":"zi"},
    "e":
    {"x":"xh","y":"yh","z":"rho2_i"},
    "u_ISOP":
    {"x":"xh","y":"yh","z":"rho2_l"},
    "v_ISOP":
    {"x":"xh","y":"yh","z":"rho2_l"},
    "daily_mixing":
    {"x":"xh","y":"yh","z":"zl"}
}

daily_diags = [
    "KE_stress",
    "KE_visc",
    "KE_horvisc",
    "PE_to_KE",
    "dKE_dt"
]



if __name__ == "__main__":
    client = Client()
    rundir = Path.cwd()
    # Get the name of folder from Path object
    expt = rundir.name
    print(f"Running postprocessing for experiment {expt}")
    # Find most recent output folder
    i = 0
    while (rundir / f"archive/output{i:03d}").exists():
        i += 1
    i -=1
    output = f"output{i:03d}"

    # Set up the run and output directories
    mom6out = rundir /  f"archive/{output}"
    gdataout = Path("/g/data/nm03/ab8992/") / expt / f"{output}"
    if not gdataout.exists():
        gdataout.mkdir(parents=True)

    ## Simply move the surface variables to gdata. These are unchunked and for the entire domain

    try:
        surface_filename = list(mom6out.glob('*.surface.nc'))[0].name
        shutil.move(str(mom6out / surface_filename),str(gdataout / "surface.nc"))
    except Exception as e:
        print("Could not find surface file!")
        print(e)

    ## Now process the 3D Daily diagnostics. These are cut down to the transect but unchunked. They all have the same dimension names
 

    for diag in daily_diags:
        try:
            
            ds = xr.open_dataset(
                str(mom6out / f"*{diag}.nc"),
                decode_times=False,
            )
            out = tt.beamgrid(ds[diag],xname = "xh",yname = "yh")
            out.to_netcdf(gdataout / f"{diag}.nc")
        except Exception as e:        
            print(f"Failed to open 3d daily diags")
            print(e)



    # Now we do the biggest ones, the hourly diagnostics. These are output in their own folder, chunked along y dimension
    for diag in hourly_diags:
        print(f"processing {diag}")
        if not (gdataout / f"{diag}").exists():
            (gdataout / f"{diag}").mkdir(parents=True)
        try:
            ds = xr.open_mfdataset(
                str(mom6out / f"*{diag}.nc"),
                chunks={hourly_diags[diag]["z"]: 10,"time":50},
                decode_times=False,
            )
        except Exception as e:
            print(f"Failed to open {diag}")
            print(e)
            continue

        out = tt.beamgrid(ds,xname = hourly_diags[diag]["x"],yname = hourly_diags[diag]["y"])
        out = out.chunk({"yb": 12}).persist()

        ## Now split the data up into different y levels
        ## Try split in 4 parts in yh direction

        i = 0
        while i * 12 < out["yb"].shape[0]:
            out.isel(
                {
                    "yb" : slice(i*10,(i+1)*10)
                    }
                    ).to_netcdf(gdataout / f"{diag}" / f"{diag}_y{i:02d}.nc")


            i += 1
