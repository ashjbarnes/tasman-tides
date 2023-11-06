from pathlib import Path
import numpy as np
import os
import xarray as xr
from dask.distributed import Client
import haversine
from pathlib import Path
import sys
sys.path.append("/home/149/ab8992/tasman-tides/")
import ttidelib as tt


#TODO Have postprocessing script read the diag table to figure out which variables to process?

#TODO Allow python file to take arguments for chunking?

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
    gdataout = Path("/g/data/nm03/ab8992/") / expt / f"output{output}"
    if not gdataout.exists():
        gdataout.mkdir(parents=True)

    diags = {
        "hourly_rho":{"x":"xh","y":"yh","z":"zl"},
        "hourly_u":{"x":"xq","y":"yh","z":"zl"},
        "hourly_v":{"x":"xh","y":"yq","z":"zl"},
        "hourly_e":{"x":"xh","y":"yh","z":"zi"}
    }

    for diag in diags:
        print(f"processing {diag}")
        try:
            ds = xr.open_mfdataset(
                str(mom6out / f"*{diag}.nc"),
                chunks={diags[diag]["z"]: 10,"time":50},
                decode_times=False,
            )
        except Exception as e:
            print(f"Failed to open {diag}")
            print(e)
            continue

        print(diags[diag]["x"])
        out = tt.beamgrid(ds,xname = diags[diag]["x"],yname = diags[diag]["y"])
        out = out.chunk({"yb": 12}).persist()

        ## Now split the data up into different y levels
        ## Try split in 4 parts in yh direction

        i = 0
        while i * 12 < out["yb"].shape[0]:
            out.isel(
                {
                    "yb" : slice(i*10,(i+1)*10)
                    }
                    ).to_netcdf(gdataout / f"y{i:02d}_{diag}.nc")


            i += 1
