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
import subprocess
#TODO Allow python file to take arguments for chunking?

#! THIS IS A MODIFIED VERSION TO USE WITH THE NEW DISSIPATION EXPERIMENTS
# Only difference is accounting for thew new diags and saving in a separate folder. Changes marked with #! in comments

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--to_process', type=str, help='outputs to process. If 0, runs all, if -1 runs only last',default = "last")
parser.add_argument('-c', '--yb-chunksize', type=str, help='size of chunks across beam',default=6)
args = parser.parse_args()

to_process = args.to_process

def postprocessing(to_process,expt = "full-20",recompute = False):
    """
    This is called after each run. Calls beamgrid to interpolate everything and save to gdata
    """
    hourly_diags = {
    "ahh":
    {"x":"xh","y":"yh","z":"z_l"},
    "kvu":
    {"x":"xq","y":"yh","z":"z_l"},
    "rho":
    {"x":"xh","y":"yh","z":"z_l"}}


    daily_diags = [
        "KE_visc",
        "KE_horvisc",
        "Kd_interface",
    ]

    yb_chunksize = 6
    rundir = Path("/home/149/ab8992/tasman-tides/rundirs/DE") / expt

    if to_process == "last":
        # Find most recent output folder
        outputs = (rundir / f"archive").glob("output*")
        temp = 0
        for i in outputs:
            s = int(i.name.split("output")[-1])
            if s > temp:
                temp = s

        outputs = [f"output{temp:03d}"]

        print(f"Processing last output ({outputs[0]})")


    elif to_process == "all" and recompute == True:
        print("Processing all outputs...")
        # Find all output folders
        i = 0
        outputs = []
        while (rundir / f"archive/output{i:03d}").exists():
            outputs.append(f"output{i:03d}")
            i += 1

        print(outputs)

    elif to_process == "all" and recompute == False:
        print("Postprocess all outputs, excluding those which are done")
        # Find all output folders
        i = 0
        outputs = []
        while (rundir / f"archive/output{i:03d}").exists():
            ## now check whether /g/data/nm03/ab8992/outputs/DissipationExperiment/expt/output/topdown/VAR exists for var in ahh e rho u v
            done = True
            for var in ["rho","u","v","ahh"]:
                if not (Path("/g/data/nm03/ab8992/outputs/DissipationExperiment") / expt / f"output{i:03d}" / var  / f"{var}_y01.nc").exists():
                    done = False

            if done == False:
                outputs.append(f"output{i:03d}")
            i += 1

        print("Outputs that need recomputing: ",outputs,sep = "\n")

    elif "-" in to_process:
        outputs = [f"output{int(i):03d}" for i in range(int(to_process.split("-")[0]),int(to_process.split("-")[1]) + 1)]
        print(f"Processing outputs ({outputs})")
    else:
        outputs = [f"output{int(to_process):03d}"]
        print(f"Processing specified output ({outputs})")

    # Iterate over all outputs
    for output in outputs:
        print(f"\t\t Processing {output}")
        # Set up the run and output directories
        mom6out = rundir /  f"archive/{output}"
        print(f"Processing {mom6out}")
        gdataout = Path("/g/data/nm03/ab8992/outputs/DissipationExperiment") / expt / f"{output}"
        if gdataout.exists():
            shutil.rmtree(gdataout)
            gdataout.mkdir(parents=True)
        else:
            gdataout.mkdir(parents=True)


        ## Simply move the surface variables to gdata. These are unchunked and for the entire domain

        try:
            surface_filename = list(mom6out.glob('*surface.nc'))[0].name
            shutil.copy(str(mom6out / surface_filename),str(gdataout / "surface.nc"))
        except Exception as e:
            print("Couldn't move surface.nc")
            print(e)
            continue
        ## Finally copy across ocean stats
        print("Copying ocean.stats")
        try:
            shutil.copy(str(mom6out / 'ocean.stats.nc'),str(gdataout / "ocean_stats.nc"))        
        except Exception as e:
            print("Couldn't move ocean.stats")
            print(e)
            continue
        # Now we do the biggest ones, the hourly diagnostics. These are output in their own folder, chunked along y dimension
        # First do the velocities together, as these need to be summed along and against the beam

        theta = np.arctan((-43.3 + 49.8) / -17) # This is the angle of rotation
        u = xr.open_mfdataset(
            str(mom6out / f"*u.nc"),
            chunks={"z_l": 10,"time":10,"xq":-1,"yh":-1},
            decode_times=False,
        ).u.sel(xq = slice(144,170),yh = slice(-55,-40))
        v = xr.open_mfdataset(
            str(mom6out / f"*v.nc"),
            chunks={"z_l": 10,"time":10,"xh":-1,"yq":-1},
            decode_times=False,
        ).v.sel(xh = slice(144,170),yq = slice(-55,-40))

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

        tt.save_chunked(u_rot,"u",yb_chunksize,gdataout)
        tt.save_chunked(v_rot,"v",yb_chunksize,gdataout)

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
                    chunks={hourly_diags[diag]["z"]: 10,"time":10,"xh":-1,"yh":-1},
                    decode_times=False,
                )[diag].sel({hourly_diags[diag]["x"] : slice(144,170), hourly_diags[diag]["y"] : slice(-55,-40)})
            except Exception as e:
                print(f"Failed to open {diag}")
                print(e)

            out = tt.beamgrid(ds,xname = hourly_diags[diag]["x"],yname = hourly_diags[diag]["y"]).persist()

            tt.save_chunked(out,diag,yb_chunksize,gdataout)
            del out

        #! New for the daily diags
        for diag in daily_diags:
            print(f"processing {diag}")
            try:
                ds = xr.open_mfdataset(
                    str(mom6out / f"*{diag}.nc"),
                    chunks="auto",
                    decode_times=False,
                )[diag].sel({"xh" : slice(144,170), "yh" : slice(-55,-40)})
            except Exception as e:
                print(f"Failed to open {diag}")
                print(e)

            out = tt.beamgrid(ds,xname = "xh",yname = "yh").persist()
            out.to_netcdf(gdataout / f"{diag}.nc")
            # tt.save_chunked(out,diag,yb_chunksize,gdataout)
            del out


        ## Now do 2D surface diagnostics
        print(f"processing surface diagnostics over transect")
        try:
            if "blank" in expt: 
                ds = xr.open_mfdataset(
                    str(mom6out / f"*surface.nc"),
                    chunks={"time":10},
                    decode_times=False,
                ).sel({
                    "xh" : slice(144,170), "yh" : slice(-55,-40)
                    })
            else:
                ds = xr.open_mfdataset(
                    str(mom6out / f"*surface.nc"),
                    chunks={"time":10},
                    decode_times=False,
                ).sel({
                    "xh" : slice(144,170), "yh" : slice(-55,-40),
                    "xq" : slice(144,170), "yq" : slice(-55,-40),
                    })
        except Exception as e:
            print(f"Failed to open surface!")
            print(e)
            continue
        eta = tt.beamgrid(ds.zos)
        speed = tt.beamgrid(ds.speed)
        if not "blank" in expt:
            taux = tt.beamgrid(ds.taux,xname = "xq")
            tauy = tt.beamgrid(ds.tauy,yname = "yq")
            surface_transect = xr.merge([eta,speed,taux,tauy])
        else:
            surface_transect = xr.merge([eta,speed])
        surface_transect.load().to_netcdf(gdataout / "surface_transect.nc")
        del eta
        del speed
        if not "blank" in expt:
            del taux
            del tauy
        del surface_transect

        for i in ["u","v","ahh","e","rho"]:
            subprocess.run(
            f"rm {str(mom6out)}/*{i}.nc",
            shell=True
            )






if __name__ == "__main__":
    client = Client(threads_per_worker = 1,n_workers = 24)
    print(client)
    rundir = Path.cwd()
    # Get the name of folder from Path object
    expt = rundir.name
    print(f"Running postprocessing for experiment {expt}")


    postprocessing(to_process,expt,recompute = True)
