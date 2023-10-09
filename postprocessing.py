# Script to be run after mom6 has finished. Payu should call, hopefully able to run locally in new output directory otherwise will need to pass it arguments to know which output to run on / where to save processed data
import numpy as np
import subprocess
import xarray as xr
from pathlib import Path

def get_transect_data(path,vector = np.array([[150,-49.8],[165,-43.3]])):
    """
    Returns a dataset containing 4D hourly transect data along beam path

    Parameters
    ----------
    output_path : Path object
        Path to output directory containing MOM6 output
    vector : np.array
        Array containing two points in longitude, latitude space that define the beam path
    """

    ## Need to modify longitude to ensure we're comparing distances correctly
    longitude_factor = np.cos(-47.5 * np.pi / 180)

    dist = 1352 #! Hardcoded length of the transect. Pending decision of how to handle non-uniformality of the distnaces along transect

    ## Angle from horizontal to the beam path
    theta = np.arctan(
        (vector[0,1] - vector[1,1]) / (longitude_factor * (vector[0,0] - vector[1,0]))
    )



    h = xr.open_mfdataset(path / "hourly_h.nc",decode_times = False, parallel = True,chunks = "auto").sel(xh = slice(145,175),yh = slice(-52,-30))
    v = xr.open_mfdataset(path / "hourly_v.nc",decode_times = False, parallel = True,chunks = "auto").sel(xh = slice(145,175),yq = slice(-52,-30))
    u = xr.open_mfdataset(path / "hourly_u.nc",decode_times = False, parallel = True,chunks = "auto").sel(xq = slice(145,175),yh = slice(-52,-30))
    isop = xr.open_mfdataset(path / "hourly_e.nc",decode_times = False, parallel = True,chunks = "auto").sel(xh = slice(145,175),yh = slice(-52,-30))

    ## Construct transect
    x = xr.DataArray(np.arange(150,165,0.2),dims="l")
    y = xr.DataArray(np.linspace(-43.3,-49.8,x.shape[0]),dims="l")
    # fig,ax = plt.subplots(1,figsize = (10,10))

    u_transect = u.interp(xq = x,yh = y)
    v_transect = v.interp(xh = x,yq = y)
    h_transect = h.interp(xh = x,yh = y)
    isop_transect = isop.interp(xh = x,yh = y)

    ## Calculate velocity along transect
    ul = u_transect.u * np.cos(theta)  + v_transect.v * np.sin(theta)
    ul = ul.assign_coords({"l":('l',np.linspace(0,dist,ul.l.shape[0]))})
    h_transect = h_transect.assign_coords({"l":('l',np.linspace(0,dist,h_transect.l.shape[0]))})
    ul = ul.load()
    h_transect = h_transect.h.load()
    isop_transect = isop_transect.load()
    depth = h_transect.cumsum(dim='zl')
    u_newz = xr.DataArray(data=ul.values,dims=["time","zl", "l"],
            coords=dict(l=(["l"], ul.l.values),depth=(["time","zl", "l"], depth.values)),
            attrs= ul.attrs)

    data = xr.Dataset(
        data_vars = {"h_transect":h_transect,
            "isop_transect":isop_transect.e,
            "depth":depth,
            "u_newz":u_newz})
    data = data.chunk({"time":1})

    return data

