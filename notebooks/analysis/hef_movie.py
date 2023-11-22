import xarray as xr
import matplotlib.pyplot as plt
import sys
sys.path.append("/home/149/ab8992/tasman-tides/")
import ttidelib as tt
from importlib import reload
from dask.distributed import Client
client = Client()
client


output = "01*"
# eta = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/surface.nc",decode_times = False).zos)
speed = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/surface.nc",decode_times = False).speed)
u = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/u/*",decode_times = False).u
v = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/v/*",decode_times = False).v
e = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/e/*",decode_times = False).e
rho = xr.open_mfdataset(f"/g/data/nm03/ab8992/outputs/full-20/output{output}/rho/*",decode_times = False).rho
bathy = tt.beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/ttide-inputs/full-20/topog_raw.nc",decode_times = False).elevation,xname = "lon",yname = "lat")



data = xr.Dataset(
    {"speed":speed.rename({"time":"TIME"}), ## Rename since this dimension is on 6hrs
            "u":u.isel(time = slice(20,25)),
            "v":v.isel(time = slice(20,25)),
            "bathy":bathy
    }
)

data

fig = plt.figure(figsize=(15, 12))

tt.make_movie(data,tt.plot_hef,fig,"full-20","runs10on")