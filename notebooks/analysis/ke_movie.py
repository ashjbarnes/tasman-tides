import xarray as xr
import matplotlib.pyplot as plt
import sys
sys.path.append("/home/149/ab8992/tasman-tides/")
import ttidelib as tt
from importlib import reload
from dask.distributed import Client

if __name__ == "__main__":
    client = Client(threads_per_worker = 2)

    output = "012"
    # eta = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/surface.nc",decode_times = False).zos)
    speed = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/surface.nc",decode_times = False).speed)
    u = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/u/*",decode_times = False).u
    v = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/v/*",decode_times = False).v
    e = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/e/*",decode_times = False).e
    rho = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/rho/*",decode_times = False).rho
    bathy = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/ttide-inputs/full-20/topog_raw.nc",decode_times = False).elevation,xname = "lon",yname = "lat")



    data = xr.Dataset(
        {"speed":speed.rename({"time":"TIME"}), ## Rename since this dimension is on 6hrs
                "u":u,
                "v":v,
                "bathy":bathy
        }
    )

    data

    fig = plt.figure(figsize=(15, 12))

    tt.make_movie(data,tt.plot_ke,fig,"full-20","output012_ke")