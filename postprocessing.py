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
import argparse

#TODO Allow python file to take arguments for chunking?



parser = argparse.ArgumentParser()
parser.add_argument('-p', '--to_process', type=str, help='outputs to process. If 0, runs all, if -1 runs only last')
parser.add_argument('-c', '--yb-chunksize', type=str, help='size of chunks across beam',default=12)
args = parser.parse_args()

to_process = args.to_process
yb_chunksize = args.yb_chunksize


hourly_diags = {
    "rho":
    {"x":"xh","y":"yh","z":"z_l"},
    "khh":
    {"x":"xh","y":"yh","z":"z_l"},
    "e":
    {"x":"xh","y":"yh","z":"rho2_i"}
}

daily_diags = [
    "KE_stress"
    "KE_visc"
    "KE_horvisc"
    "PE_to_KE"
    "dKE_dt"
]

def save_chunked(data,name,chunks = yb_chunksize):
    if not (gdataout / f"{name}").exists():
        (gdataout / f"{name}").mkdir(parents=True)
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
    # print(client)
    rundir = Path.cwd()
    # Get the name of folder from Path object
    expt = rundir.name
    print(f"Running postprocessing for experiment {expt}")

    if to_process == "-1":
        # Find most recent output folder
        i = 0
        while (rundir / f"archive/output{i:03d}").exists():
            i += 1
        i -=1
        outputs = [f"output{i:03d}"]

    if to_process == "0":
        print("Processing all outputs...")
        # Find all output folders
        i = 0
        outputs = []
        while (rundir / f"archive/output{i:03d}").exists():
            outputs.append(f"output{i:03d}")
            i += 1

        print(outputs)
    else:
        outputs = [f"output{int(to_process):03d}"]

    for output in outputs:
        print(f"\t\t Processing {output}")
        # Set up the run and output directories
        mom6out = rundir /  f"archive/{output}"
        print(f"Processing {mom6out}")
        gdataout = Path("/g/data/nm03/ab8992/outputs") / expt / f"{output}"
        if not gdataout.exists():
            gdataout.mkdir(parents=True)

        ## Simply move the surface variables to gdata. These are unchunked and for the entire domain

        try:
            surface_filename = list(mom6out.glob('*.surface.nc'))[0].name
            shutil.copy(str(mom6out / surface_filename),str(gdataout / "surface.nc"))
        except Exception as e:
            print("Couldn't move surface.nc")
            print(e)

        # Now we do the biggest ones, the hourly diagnostics. These are output in their own folder, chunked along y dimension
        # First do the velocities together, as these need to be summed along and against the beam

        theta = np.arctan((-43.3 + 49.8) / -17) # This is the angle of rotation
        u = xr.open_mfdataset(
            str(mom6out / f"*u.nc"),
            chunks={"z_l": 10,"time":10},
            decode_times=False,
        ).sel(xq = slice(145,170),yh = slice(-55,-40)).u
        v = xr.open_mfdataset(
            str(mom6out / f"*v.nc"),
            chunks={"z_l": 10,"time":10},
            decode_times=False,
        ).sel(xh = slice(145,170),yq = slice(-55,-40)).v

        u = tt.beamgrid(u,xname = "xq",chunks = yb_chunksize).persist()
        v = tt.beamgrid(v,yname = "yq",chunks = yb_chunksize).persist()

        # Rotate the velocities
        u_rot = u * np.cos(theta) - v * np.sin(theta)
        v_rot = u * np.sin(theta) + v * np.cos(theta)

        # Set the name of u to "u" and description to "velocity along beam"
        u_rot.name = "u"
        u_rot.attrs["long_name"] = "Velocity along beam (Eastward positive)"
        v_rot.name = "v"
        v_rot.attrs["long_name"] = "Velocity across beam (Northward positive)"

        save_chunked(u_rot,"u",chunks = yb_chunksize)
        save_chunked(v_rot,"v",chunks = yb_chunksize)

        del u
        del v
        del u_rot
        del v_rot
        ## Now do the rest of the hourly diagnostics
        for diag in hourly_diags:
            print(f"processing {diag}")
            try:
                ds = xr.open_mfdataset(
                    str(mom6out / f"*{diag}.nc"),
                    chunks={hourly_diags[diag]["z"]: 10,"time":10},
                    decode_times=False,
                )[diag].sel({hourly_diags[diag]["x"] : slice(145,170), hourly_diags[diag]["y"] : slice(-55,-40)})
            except Exception as e:
                print(f"Failed to open {diag}")
                print(e)
                continue

            out = tt.beamgrid(ds,xname = hourly_diags[diag]["x"],yname = hourly_diags[diag]["y"])
            out = out.chunk({"yb": yb_chunksize}).persist()

            save_chunked(out,diag,chunks = yb_chunksize)
            del out