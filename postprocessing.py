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
    "rho":
    {"x":"xh","y":"yh","z":"zi"},
    "e":
    {"x":"xh","y":"yh","z":"rho2_i"},
    "Khh":
    {"x":"xh","y":"yh","z":"zl"},
}

daily_diags = [
    "KE_stress"
    "KE_visc"
    "KE_horvisc"
    "PE_to_KE"
    "dKE_dt"
]

def save_chunked(data,name,chunks = 12):
        data = data.chunk({"yb": chunks}).persist()

        i = 0
        while i * chunks < data["yb"].shape[0]:
            data.isel(
                {
                    "yb" : slice(i*10,(i+1)*10)
                    }
                    ).to_netcdf(gdataout / f"{name}" / f"{name}_y{i:02d}.nc")
            i += 1


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
    if (mom6out / "surface.nc").exists():
        shutil.move(str(mom6out / "surface.nc"),str(gdataout / "surface.nc"))


    ## Now we do the biggest ones, the hourly diagnostics. These are output in their own folder, chunked along y dimension

    ## First do the velocities together, as these need to be summed along and against the beam

    theta = np.arctan((-43.3 + 49.8) / -17) # This is the angle of rotation
    u = xr.open_mfdataset(
        str(mom6out / f"u.nc"),
        chunks={"zl": 10,"time":50},
        decode_times=False,
    )
    v = xr.open_mfdataset(
        str(mom6out / f"v.nc"),
        chunks={"zl": 10,"time":50},
        decode_times=False,
    )

    u = tt.beamgrid(u,xname = "xq")
    v = tt.beamgrid(v,yname = "yq")

    # Rotate the velocities
    u_rot = u["u"] * np.cos(theta) - v["v"] * np.sin(theta)
    v_rot = u["u"] * np.sin(theta) + v["v"] * np.cos(theta)

    # Set the name of u to "u" and description to "velocity along beam"
    u_rot.name = "u"
    u_rot.attrs["long_name"] = "Velocity along beam (Eastward positive)"
    v_rot.name = "v"
    v_rot.attrs["long_name"] = "Velocity across beam (Northward positive)"

    save_chunked(u_rot,"u",chunks = 12)
    save_chunked(v_rot,"v",chunks = 12)

    ## Now do the rest of the hourly diagnostics
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

        save_chunked(out,diag,chunks = 12)

