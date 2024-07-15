# A file to keep all common functions that might be used for postprocessing and analysis fo the ttide experiment
import scipy
from matplotlib import rc
import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import os
import datetime as dt
import haversine
import xarray as xr
import subprocess
import matplotlib.pyplot as plt
import shutil
import dask
import cmocean
from pathlib import Path
from dask.distributed import Client,default_client

home = Path("/home/149/ab8992/tasman-tides")
gdata = Path("/g/data/nm03/ab8992")
m2 = 360 / 28.984104 ## Period of m2 in hours
averaging_window = int(12 * m2) ## this comes out to be 149.0472 hours, so close enough to a multiple of tidal periods
m2f = 1/ m2    ## Frequency of m2 in radians per hour
########################################### Small Utility Functions ###############################################


def logmsg(message,logfile = home / "logs" /"mainlog"):
    """
    Write a message out to the logfile. If message is None, create a new logfile with the current time
    """
    current_time = dt.datetime.now().strftime("%d-%m-%y %H:%M:%S")

    with open(logfile,"a") as f:
        f.write(current_time + ":\t" + message + "\n")
    return 

def startdask():
    try:
    # Try to get the existing Dask client
        client = default_client()
        print(client)
    except ValueError:
        # If there's no existing client, create a new one
        client = Client()
        print(client)
    return client

def save(data,path):
    """
    Save the data to the path. If the path doesn't exist, create it
    """
    path = Path(str(f"/g/data/nm03/postprocessed/" + path))
    if not path.exists():
        path.mkdir(parents=True)
    # Make sure this saves and overwrites existing without throwing error 

    data.to_netcdf(path, mode='w')  # Add mode='w' to overwrite existing files
    return

def xy_to_lonlat(x,y,x0,y0):
    """
    All outputs are in degrees
    """
    lat = np.arcsin((y + y0) / 6371)
    lon = np.arcsin((x + x0) / (6371 * np.cos(lat)))
    #! HARDCODED FOR QUADRANT 2
    lon = np.pi - lon
    return lon * 180 / np.pi,lat * 180 / np.pi

def lonlat_to_xy(lon,lat,lon0,lat0):
    """
    All inputs are in degrees
    """
    R = 6371
    lon /= 180 / np.pi
    lat /= 180 / np.pi
    lon0 /= 180 / np.pi
    lat0 /= 180 / np.pi
    x0,y0 = R * np.cos(lat0) * np.sin(lon0) , R * np.sin(lat0)
    x,y = R * np.cos(lat) * np.sin(lon) - x0, R * np.sin(lat) - y0

    return x,y

def anticlockwise_rotation(x,y):
    theta = np.abs(np.arctan((-43.3 + 49.8) / -17))
    x_rotated = x * np.cos(theta) - y * np.sin(theta)
    y_rotated = x * np.sin(theta) + y * np.cos(theta)
    return x_rotated,y_rotated

def m2filter(field,freq = m2f,tol = 0.015):
    """
    Filter about the m2 frequency. Just pass a field and it will return the real part of the filtered field
    """
    import xrft
    FIELD = xrft.fft(field,dim = "time")
    FIELD_filtered = FIELD.where(np.abs(np.abs(FIELD.freq_time) - freq) < tol,0)
    return np.real(xrft.ifft(FIELD_filtered,dim = "freq_time"))

def filter_velocities(data):
    """
    Given a velocity field
    """
    duy = data.u.differentiate("yb")
    dvx = data.v.differentiate("xb")
    return (dvx - duy)

########################################### More involved postprocessing functions ###############################################

def beamgrid(data,lat0 = -42.1,lon0 = 147.2,beamwidth = 400,beamlength = 1500,plot = False,xname = "xh",yname = "yh",vmin = None,vmax = None,chunks = 12):
    
    """
    Takes data output from MOM6, interpolates onto our small and rotated grid and saves for long term storage
    data : xarray.DataArray
        The data to be gridded
    lat0 : float
        Latitude of the origin of the beam
    lon0 : float
        Longitude of the origin of the beam
    beamwidth : float
        Width of the beam in km
    beamlength : float
        Length of the beam in km
    res : float
        Resolution of the grid in km
    plot : bool
        Whether to plot the grid. If plotting, only pass dataarray
    chunks : int
        Chunk size for dask along the yb axis
    Return a xarray.DataArray cut down to size on to the beam grid. The resolution is automatically determined from the base grid.

    """
    import xesmf

    if plot == True:
        assert isinstance(data,xr.DataArray), "Data must be an xarray.DataArray"

    lon = data[xname].data
    lat = data[yname].data 

    theta = np.arctan((-43.3 + 49.8) / -17) #! Hardcoded. This comes out to -20.9 degrees
    theta *= -1 ## Look, I just did some trial and error until the beam was in the right quadrant. Who needs year 10 maths
    res = haversine.haversine((lat[0],lon[0]),(lat[0],lon[1]))
    res = np.ceil(res)
    LAT , LON = np.meshgrid(lat,lon)

    ## Define target grid on rotated mesh in km
    y_ = np.linspace(
        -0.5 * beamwidth,
        0.5 * beamwidth,
        int(beamwidth // res) + 1)
    x_ = np.linspace(
        0,
        -1 * beamlength,
        int(beamlength // res) + 1)
    
    X_,Y_ = np.meshgrid(x_,y_)
    ## Define the rotated grid as represented on the original grid. I.E, the points on x_ y_ as represented on the x,y coordinate system
    theta_ = theta
    Xrot , Yrot = X_ * np.cos(theta_) - Y_ * np.sin(theta_) , X_ * np.sin(theta_) + Y_ * np.cos(theta_)
    ## Calculate X,Y (the rotated grid points) as lat/lon
    x0,y0 = 6371 * np.cos(lat0 * np.pi/180) * np.sin(lon0 * np.pi/180) , 6371 * np.sin(lat0 * np.pi/180)
    LONrot,LATrot = xy_to_lonlat(Xrot,Yrot,x0,y0)

    ## Create target grid to interpolate onto
    newgrid = xr.DataArray(
        data = X_ * 0,
        dims = ["yb","xb"],
        coords = {
            "xb":(["xb"], - X_[0,:]), ## This sets the coordinate as running from Tasmania -> Mac ridge
            "yb":(["yb"],Y_[:,0]),
            "lon":(["yb","xb"],LONrot),
            "lat":(["yb","xb"],LATrot),
        }
    )
    regridder = xesmf.Regridder(
    data.rename({xname:"lon",yname:"lat"}),newgrid,"bilinear"
    )

    out = regridder(
        data,keep_attrs = True
        )
    # assign attributes to out
    out.attrs = data.attrs
    out.attrs["Description"] = f"Beamwidth {beamwidth}km, Beamlength {beamlength}km, Resolution {res}km, angle {theta} degrees, origin {lat0,lon0}"
    out.xb.attrs = {
            "long_name": "Distance along beam from Tasmania towards Macquarie Ridge",
            "units": "km",
    }
    out.yb.attrs = {
            "long_name": "Distance perpendicular to beam referened from beam centre",
            "units": "km",
    }
    out.lon.attrs = {
            "long_name": "Longitude of grid point",
            "units": "degrees",
    }
    out.lat.attrs = {
            "long_name": "Latitude of grid point",
            "units": "degrees",
    }

    if "z_l" in out.dims:
        out = out.rename({"z_l":"zl"})
    if "z_i" in out.dims:
        out = out.rename({"z_i":"zi"})
    if plot == False:
        return out

    else:
        out = out.assign_coords(
            {"x":(["yb","xb"],Xrot),
             "y":(["yb","xb"],Yrot)}
        )

        ## Define the original grid on cartesian coordinates
        x,y = lonlat_to_xy(LON,LAT,lon0,lat0)


        toplot = data.assign_coords(
            {"x":([xname,yname],x),
            "y":([xname,yname],y)}
        )

        fig,ax = plt.subplots(1,2,figsize = (14,7))

        toplot.plot(x = "x",y = "y",ax = ax[0],add_colorbar = False,cmap = "cubehelix",vmax = vmax,vmin = vmin)

        out.plot(x="x",y = "y",add_colorbar = False,ax = ax[0],cmap = "RdBu",vmax = vmax,vmin = vmin)
        ax[0].invert_xaxis()

        toplot.plot(ax = ax[1],add_colorbar = False,cmap = "cubehelix",vmax = vmax,vmin = vmin)

        out.plot(x="lon",y = "lat",add_colorbar = False,ax = ax[1],cmap = "RdBu",vmax = vmax,vmin = vmin)

        ax[0].set_title("Subgrid in Cartesian")
        ax[1].set_title("Subgrid in latlon")

        return out

import scipy
def calculate_N(rho):
    """
    Calculate the buoyancy frequency given density rho in z* coords"""
    N = np.sqrt(
        ((9.8 / rho) * rho.differentiate("zl"))
        ).rename("N").fillna(0)
    N.attrs = {"units":"s^-1"}
    return N


def save_chunked(data,name,chunks,gdataout):
    """
    Saves data with chunks in cross beam direction
    """
    if not (gdataout / f"{name}").exists():
        (gdataout / f"{name}").mkdir(parents=True)
    i = 0
    while i * chunks < data["yb"].shape[0]:
        data.isel(
            {
                "yb" : slice(i*chunks,(i+1)*chunks)
                }
                ).to_netcdf(gdataout / f"{name}" / f"{name}_y{i:02d}.nc")
        i += 1

def postprocessing(to_process,expt = "full-20",recompute = False):
    """
    This is called after each run. Calls beamgrid to interpolate everything and save to gdata
    """
    hourly_diags = {
    "rho":
    {"x":"xh","y":"yh","z":"z_l"},
    "ahh":
    {"x":"xh","y":"yh","z":"z_l"},
    "e":
    {"x":"xh","y":"yh","z":"rho2_i"}
    }

    yb_chunksize = 6
    rundir = Path("/home/149/ab8992/tasman-tides/rundirs/") / expt

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
            ## now check whether /g/data/nm03/ab8992/outputs/expt/output/topdown/VAR exists for var in ahh e rho u v
            done = True
            for var in ["ahh","e","rho","u","v"]:
                if not (Path("/g/data/nm03/ab8992/outputs") / expt / f"output{i:03d}" / var  / f"{var}_y01.nc").exists():
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
        gdataout = Path("/g/data/nm03/ab8992/outputs") / expt / f"{output}"
        if not gdataout.exists():
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

        u = beamgrid(u,xname = "xq",chunks = yb_chunksize).persist()
        v = beamgrid(v,yname = "yq",chunks = yb_chunksize).persist()

        # Rotate the velocities
        u_rot = u * np.cos(theta) - v * np.sin(theta)
        v_rot = u * np.sin(theta) + v * np.cos(theta)

        # Set the name of u to "u" and description to "velocity along beam"
        u_rot.name = "u"
        u_rot.attrs["long_name"] = "Velocity along beam (Eastward positive)"
        v_rot.name = "v"
        v_rot.attrs["long_name"] = "Velocity across beam (Northward positive)"

        save_chunked(u_rot,"u",yb_chunksize,gdataout)
        save_chunked(v_rot,"v",yb_chunksize,gdataout)

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

            out = beamgrid(ds,xname = hourly_diags[diag]["x"],yname = hourly_diags[diag]["y"]).persist()

            save_chunked(out,diag,yb_chunksize,gdataout)
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
        eta = beamgrid(ds.zos)
        speed = beamgrid(ds.speed)
        if not "blank" in expt:
            taux = beamgrid(ds.taux,xname = "xq")
            tauy = beamgrid(ds.tauy,yname = "yq")
            surface_transect = xr.merge([eta,speed,taux,tauy])
        else:
            surface_transect = xr.merge([eta,speed])
        surface_transect.to_netcdf(gdataout / "surface_transect.nc")
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

def collect_data(exptname,rawdata = None,ppdata = None,lfiltered = None,chunks = None,timerange = (None,None)):
    """
    Collect all data required for analysis into a single xarray.Dataset
    expname : str
        Name of the experiment
    rawdata : list of str
        List of raw data variables to include
    ppdata : list of str
        List of postprocessed data variables to include. Note that thse aren't organised in to "outputs" given that they are often filtered temporally and so don't fit within the same output bins as model runs
    lfiltered : str. eg: "10000-highpass"
    outputs : str
        Glob string to match the output directories
    chunks : dict
        Chunks to use for dask. If "auto", use the default chunking for each variable. Surface variables are only given a time chunk
    timerange : Can choose the times instead of output. If None, use all times
    """
    #! As I've made mistakes in saving data, I've been correcting the mistakes retrospectively here
    res = exptname.split("-")[-1]

    if res == "20" and exptname != "blank-20":
        time_per_output = 15 * 24
    elif res == "40" or exptname == "blank-20":
        time_per_output = 5 * 24

    data = {}
    ## First handle the case of lfiltered data. Here, load the filtered
    ## data first, then extract the timerange information from it. Use
    ## this to load the raw data via a recursive collect_data call
    if type(lfiltered) != type(None):
        prefix = ""
        if "-" in lfiltered:
            prefix = lfiltered.split("-")[1]
            t0 = lfiltered.split("-")[0]
        if prefix == "highpass": #! This is a really lazy fix, but I mixed up lowpass and highpass in the filter script. 
            prefix = "lowpass"   #! This undoes the mistake without having to go back and rename a bunch of stuff
        elif prefix == "lowpass":#! while keeping analysis scripts consistent
            prefix = "highpass"
        
        else:
            t0 = lfiltered
        ldata = xr.open_mfdataset(
            str(Path("/g/data/nm03/ab8992/postprocessed") / exptname / "lfiltered" /  f"bp-t0-{t0}/{prefix}*.nc"),
            decode_times = False,
            decode_cf=False)
        timerange = (ldata.time.values[0],ldata.time.values[-1])
        print(f"Timerange as inferred from lfiltered data: {timerange}")
        # iterate over every data variable in the lfiltered dataset
        for var in ldata:
            if var == "cst":
                data[var] = ldata[var]
            data[f"{var}_lf"] = ldata[var]       

    if None in timerange:
        rawdata_paths = list(
            Path(f"/g/data/nm03/ab8992/outputs/{exptname}/").glob('output*')
            )
    else:
        outputs = np.arange(
            np.floor(timerange[0] /time_per_output),
            np.ceil(timerange[1] / time_per_output)
        ).astype(int)
        # change these outputs to strings with 3 digits
        rawdata_paths = [f"/g/data/nm03/ab8992/outputs/{exptname}/output{i:03d}" for i in outputs]

    ppdata_path = Path("/g/data/nm03/ab8992/postprocessed/") / exptname


    if type(rawdata) != type(None):
        
        for var in rawdata:
            print(f"loading {var}...",end = "\t" )

            # Collect list of files to load
            all_files = []
            # Loop over each path in the paths list
            for path in rawdata_paths:
                # Convert the path to a Path object
                path = Path(path) / var
                # Use glob to find all files that match the pattern
                files = list(path.glob('*.nc'))
                # Add the files to the all_files list
                all_files.extend(files)

            # Now pass all the files instead of a wildcard string
            data[var] = xr.open_mfdataset(all_files, decode_times=False, parallel=True, decode_cf=False).sel(time = slice(timerange[0],timerange[1]))[var]
            
            print("done.")

        #! I messed up the rotation! This fixes the velocity rotation on data load.
        if "u" in rawdata and "v" in rawdata:
            u_rotated_once,v_rotated_once = anticlockwise_rotation(data["u"],data["v"])
            u_rotated_once, v_rotated_once = anticlockwise_rotation(u_rotated_once,v_rotated_once)

            data["u"] = u_rotated_once.rename("u")
            data["v"] = v_rotated_once.rename("v")

    if type(ppdata) != type(None):
        for var in ppdata:
            print(f"loading {var} topdown...",end = "\t" )
            data[var + "_topdown"] = xr.open_mfdataset(
                str(ppdata_path / var / "topdown" / "*.nc"),chunks = chunks,decode_times = False,parallel = True,decode_cf = False).sel(time = slice(timerange[0],timerange[1])
            )[var].rename(f"{var}_topdown")
            print("done. loading transect...",end = "\t")
            data[var + "_transect"] = xr.open_mfdataset(
                str(ppdata_path / var / "transect" / "*.nc"),chunks = chunks,decode_times = False,parallel = True,decode_cf = False).sel(time = slice(timerange[0],timerange[1])
            )[var].rename(f"{var}_transect")
            print("done.")


    data["bathy"] = xr.open_mfdataset(str(Path("/g/data/nm03/ab8992/outputs/") / exptname / "bathy_transect.nc")).rename({"elevation":"bathy"})


    data = xr.merge([data[i] for i in data])

    ## Weird thing with smooth and ideal that ntiles remains a dim
    if "ntiles" in data.dims:
        data = data.isel(ntiles = 0)
    return data

def save_ppdata(transect_data,topdown_data,basepath,recompute = False):
    """
    Save the postprocessed data to gdata. Takes computed topdown and transect data and saves each time slice to postprocessed folders
    Time index override is used when processing one time slice at a time. That way the index can be used to name the file correctly
    """
    print(basepath)
    print(basepath.name)
    print(str(type(basepath.name)))
    for i in ["topdown","transect"]:
        if not os.path.exists(basepath / i):
            os.makedirs(basepath / i)

    for i in range(len(topdown_data.time.values)):
        time = topdown_data.time.values[i]
        if not os.path.exists(basepath / "topdown" / f"vorticity_time-{str(i).zfill(3)}.nc") or recompute:
            topdown_data.isel(time = i).expand_dims("time").assign_coords(time = [time]).to_netcdf(basepath / "topdown" / str(basepath.name + f"_time-{str(round(time))}.nc"))

        if not os.path.exists(basepath / "transect" / f"vorticity_time-{str(i).zfill(3)}.nc") or recompute:
            transect_data.isel(time = i).expand_dims("time").assign_coords(time = [time]).to_netcdf(basepath / "transect" / str(basepath.name + f"_time-{str(round(time))}.nc"))


    return

########################### ANALYSIS #############################################

def cross_scale_transfer(data):
    """Calcualtes the cross scale transfer term given already filtered data. This will work
    whether the data is temporally or spatially filtered"""

    tau_uu = data.uu - data.u**2
    tau_uv = data.uv - data.u*data.v
    tau_vv = data.vv - data.v**2
    u = data.u
    v = data.v

    transfer = (
        tau_uu * u.differentiate("xb") +
        tau_uv * u.differentiate("yb") +
        tau_uv * v.differentiate("xb") +
        tau_vv * v.differentiate("yb")
    ).rename("energy_transfer")

    return transfer

def calculate_vorticity(rawdata):
    """
    Calculate the relative vorticity from the raw data
    """
    u = rawdata["u"]
    v = rawdata["v"]
    u = u.fillna(0)
    v = v.fillna(0)

    dvx = v.differentiate("xb")
    duy = u.differentiate("yb")


    return (dvx - duy)

def calculate_hef(u,v,time,total_only = True):
    """
    Calculate the horizontal energy fluxes from the u and v velocities and ith time index. Time window is 12 m2 periods
    Inputs:
    u,v : xarray.DataArray
        u and v velocities
    i : int
        index of the time window to calculate over
    total_only : bool
        If true, only return the total energy flux. If false, return all components
    """

    u = u.fillna(0)
    v = v.fillna(0)


    ## Actually set it to a midpoint of the time window
    u_ = u.sel(
            time = slice(time -  0.5 * averaging_window, time + 0.5 *  averaging_window)
            ).chunk({"time":-1}).drop(["lat","lon"])
    v_ = v.sel(
            time = slice(time -  0.5 * averaging_window, time + 0.5 *  averaging_window)
            ).chunk({"time":-1}).drop(["lat","lon"])

    uf = m2filter(
        u_,
        m2f)
    vf = m2filter(
        v_,
        m2f)

    dux = u_.mean("time").differentiate("xb")
    dvy = v_.mean("time").differentiate("yb")
    duy = u_.mean("time").differentiate("yb")
    dvx = v_.mean("time").differentiate("xb")

    nstress_u = -1 * (uf * uf).mean("time")
    nstress_v = -1 * (vf * vf).mean("time")
    n_strain = -1 * (dux - dvy)
    shear = -1 * (uf * vf).mean("time")
    shear_strain = -1 * (duy + dvx)

    out = xr.Dataset(
        {
            "nstress_u":nstress_u,
            "nstress_v":nstress_v,
            "n_strain":n_strain,
            "shear":shear,
            "shear_strain":shear_strain,
            "total":0.5 * ((nstress_u - nstress_v) * n_strain - shear * shear_strain)
        }
    )
    # out.expand_dims("TIME").assign_coords(time=('TIME', [t_middle]))
    # out.time.attrs = u.time.attrs

    if total_only == True:
        return out.total ## Do this to reintroduce nans for easy plotting


    return out



########################### PLOTTING #############################################

def plot_ekman_pumping(data):
    """
    Plot the ekman pumping for the given data
    """
    cmap = cmocean.cm.curl
    earth_cmap = matplotlib.cm.get_cmap("gist_earth")
    fig,ax = plt.subplots(1,figsize = (15,12))
    
    data["curl"].plot(vmax = 0.5,vmin = - 0.5,ax = ax,cmap = cmap,add_colorbar = False)
    data["bathy"].plot(cmap = earth_cmap,vmin = -1000,vmax = 1500,ax = ax,add_colorbar = False)
    ax.set_title("Curl of Wind Stress")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return fig


def plot_vorticity(data):
    """
    Plot the vorticity at both surface and a transect. Requires ppdata: vorticity_topdown, vorticity_transect, bathy.
    """
    fig,ax = plt.subplots(2,1,figsize = (20,12))


    data["vorticity_topdown"].plot(vmin = - 0.075,vmax = 0.075,cmap = "RdBu",ax = ax[0])
    data["vorticity_transect"].plot(vmin = - 0.05,vmax = 0.05,cmap = "RdBu",ax = ax[1])

    ax[0].set_title("")
    ax[1].set_title("")
    ax[1].invert_yaxis()
    plot_topo(ax[0],bathy = data["bathy"])
    plot_topo(ax[1],bathy = data["bathy"],transect = 0)
    ax[1].set_xlabel('km from Tas')
    ax[0].set_ylabel('km S to N')
    ax[0].set_xlabel('')
    ax[1].set_ylabel('km S to N')
    ax[1].set_title('Transect along middle of beam')
    ax[0].set_title('Relative Vorticity')
    ax[0].hlines(y = 0,xmin = 100,xmax = 1450,linestyles = "dashed",color = "black")

    # Add text to the top right corner of the figure
    ax[0].text(0.95, 0.95, data.time.values, transform=ax[0].transAxes, fontsize=10, va="top", ha="right")

    return fig


def plot_ke(data):
    fig = plt.figure(figsize=(20, 12))
    ax = fig.subplots(2,1)

    cmap = matplotlib.cm.get_cmap('plasma')

    ## HORIZONTAL PLOTS FIRST

    data["vorticity_topdown"].plot.contour(ax = ax[0],levels = [-0.075,-0.025,0.025,0.075],cmap = "binary",linestyle = "solid")
    (1032*(data["UU_topdown"] + data["VV_topdown"])).plot(ax = ax[0],cmap = cmap,cbar_kwargs={'label': "Kinetic Energy"},vmax = 40)

    ## Add bathymetry plot
    plot_topo(ax[0],data["bathy"])


    ## Second axis: vertical transect
    data["vorticity_transect"].plot.contour(ax = ax[1],levels = [-0.075,-0.025,0.025,0.075],cmap = "binary",linestyle = "solid")
    (data["UU_transect"] + data["VV_transect"]).plot(ax = ax[1],cmap = cmap,cbar_kwargs={'label': "Kinetic Energy"},vmax = 0.02)
    plot_topo(ax[1],data["bathy"],transect=0)

    # fig.suptitle(exptname)
    ax[1].invert_yaxis()
    ax[0].set_xlabel('km from Tas')
    ax[0].set_ylabel('km S to N')
    ax[0].set_title('Kinetic Energy with Surface Speed contours')
    ## put gridlines on plot
    # ax[0].grid(True, which='both')
    ax[0].hlines(y = 0,xmin = 100,xmax = 1450,linestyles = "dashed")
    ax[1].set_xlabel('')
    ax[1].set_ylabel('km S to N')
    ax[1].set_title('Transect along middle of beam')
    ax[0].text(0.95, 0.95, data["UU_transect"].time.values, transform=ax[0].transAxes, fontsize=10, va="top", ha="right")

    return fig

def plot_dissipation(data,vmax_topdown = 5e5,anomaly = False):
    vmax_topdown = 5e5
    vmin_topdown = 0
    vmax_transect = 500
    vmin_transect = 0
    vmin = 0
    cmap1 = matplotlib.cm.get_cmap('plasma')
    cmap2 = cmap = cmocean.cm.dense_r
    if anomaly == True:
        vmax_topdown = 400000
        vmin_topdown = -400000
        vmax_transect = 200
        vmin_transect = -200
        vmin = -5
        cmap = "Rdbu"
        data["dissipation_topdown"] -= data["dissipation_topdown_mean"]
        data["dissipation_transect"] -= data["dissipation_transect_mean"]

        ## Replace all negative values with -log10 of the absolute value
        data["dissipation_topdown"].loc[data["dissipation_topdown"] > 0] =  np.log10(np.abs(data["dissipation_topdown"].loc[data["dissipation_topdown"] > 0]))
        data["dissipation_transect"].loc[data["dissipation_transect"] > 0] =  np.log10(np.abs(data["dissipation_transect"].loc[data["dissipation_transect"] > 0]))

        ## Replace all negative values with -log10 of the absolute value
        data["dissipation_topdown"].loc[data["dissipation_topdown"] < 0] = -1 * np.log10(np.abs(data["dissipation_topdown"].loc[data["dissipation_topdown"] < 0]))
        data["dissipation_transect"].loc[data["dissipation_transect"] < 0] = -1 * np.log10(np.abs(data["dissipation_transect"].loc[data["dissipation_transect"] < 0]))

    else:
        data["dissipation_topdown"] = np.log10(data["dissipation_topdown"])
        data["dissipation_transect"] = np.log10(data["dissipation_transect"])

        # Replace po


    fig = plt.figure(figsize=(20, 12))
    ax = fig.subplots(2,1)


    ## HORIZONTAL PLOTS FIRST

    data["vorticity_topdown"].plot.contour(ax = ax[0],levels = [-0.075,-0.025,0.025,0.075],cmap = cmap1,linestyle = "solid")
    data["dissipation_topdown"].plot(ax = ax[0],cmap = cmap2,cbar_kwargs={'label': "Dissipation"},vmax = 5,vmin = vmin)

    ## Add bathymetry plot
    plot_topo(ax[0],data["bathy"])


    ## Second axis: vertical transect
    data["vorticity_transect"].plot.contour(ax = ax[1],levels = [-0.075,-0.025,0.025,0.075],cmap = cmap1,linestyle = "solid")
    data["dissipation_transect"].plot(ax = ax[1],cmap = cmap2,cbar_kwargs={'label': "Dissipation"})
    plot_topo(ax[1],data["bathy"],transect=0)

    # fig.suptitle(exptname)
    ax[1].invert_yaxis()
    ax[0].set_xlabel('km from Tas')
    ax[0].set_ylabel('km S to N')
    ax[0].set_title('Dissipation of M2 energy with vorticity contours')
    ## put gridlines on plot
    # ax[0].grid(True, which='both')
    ax[0].hlines(y = 0,xmin = 100,xmax = 1450,linestyles = "dashed")
    ax[1].set_xlabel('')
    ax[1].set_ylabel('km S to N')
    ax[1].set_title('Transect along middle of beam')
    ax[0].text(0.95, 0.95, data["vorticity_transect"].time.values, transform=ax[0].transAxes, fontsize=10, va="top", ha="right")

    return fig



def plot_topo(ax,bathy = None,transect = None):
    """
    Plot the topography. If transect is not None, plot a transect at the specified yb value
    """

    earth_cmap = matplotlib.cm.get_cmap("gist_earth")
    earth_cmap.set_bad(color = "white",alpha = 0)
    if type(bathy) == type(None):
        bathy = beamgrid(xr.open_mfdataset(f"/g/data/nm03/ab8992/ttide-inputs/full-20/topog_raw.nc",decode_times = False).elevation,xname = "lon",yname = "lat")



    if type(transect) == type(None):
        bathy.where(bathy > 0).plot(cmap = earth_cmap,vmin = -1000,vmax = 1500,ax = ax,add_colorbar = False)
        return ax
    
    else:
        transect = bathy.sel(yb = transect,method = "nearest")
        ax.fill_between(transect.xb,transect * 0 + 6000,-1 * transect,color = "dimgrey")
        return ax



def make_movie(data,plot_function,runname,plotname,framerate = 5,parallel = False,plot_kwargs = {}):
    """
    Custom function to make a movie of a plot function. Saves to a folder in dropbox. Intermediate frames are saved to /tmp
    data_list : dictionary of dataarrays required by plot function
    plot_function : function to plot data
    runname : name of the run eg full-20
    plotname : name of the plot eg "h_energy_transfer"
    plot_kwargs : kwargs to pass to plot function
    """

    print(f"Making movie {plotname} for {runname}")
    tmppath = Path(f"/g/data/v45/ab8992/movies_tmp/tasman-tides/{runname}/movies/{plotname}/")
    outpath = Path(f"/g/data/v45/ab8992/dropbox/tasman-tides/{runname}/movies/")
    print(tmppath)
    ## Log the start of movie making

    if os.path.exists(tmppath):
        shutil.rmtree(tmppath)
    os.makedirs(tmppath)
    if not os.path.exists(outpath):
        os.makedirs(outpath)
    
    logmsg(f"Making movie {plotname} for {runname}")  


    ## Make each frame of the movie and save to tmpdir
    if parallel == True:
        @dask.delayed
        def process_chunk(_data,i):
            fig = plot_function(_data,**plot_kwargs)
            fig.savefig(tmppath / f"frame_{str(i).zfill(5)}.png")
            plt.close()
            return None
        
        frames = [process_chunk(data.isel(time = i),i) for i in range(len(data.time))]
        dask.compute(*frames)

    ## Do the same thing but in serial
    else:
        for i in range(len(data.time)):
            fig = plot_function(data.isel(time = i))
            fig.savefig(tmppath / f"frame_{str(i).zfill(5)}.png")
            plt.close()


    logmsg(f"Finished making frames")
    print(f"ffmpeg -r {framerate}  -i {tmppath}/frame_%05d.png -s 1920x1080 -c:v libx264 -pix_fmt yuv420p {str(outpath) + plotname}.mp4")
    result = subprocess.run(
            f"ffmpeg -y -r {framerate} -i {tmppath}/frame_%05d.png -s 1920x1080 -c:v libx264 -pix_fmt yuv420p {str(outpath / plotname)}.mp4",
            shell = True,
            capture_output=True,
            text=True,
        )
    print(f"ffmpeg finished with returncode {result.returncode} \n\n and output \n\n{result.stdout}")
    logmsg(
        f"ffmpeg finished with returncode {result.returncode}",
    )
    print(result.stderr)
    print(result.stdout)
    if str(result.returncode) == "1":
        logmsg(f"ffmpeg output: {result.stdout}")
    return

def plot_hef(data,fig,i,framedim = "TIME",**kwargs):

    ax = fig.subplots(2,1)

    time = data["speed"].TIME.values[i]
    hef = calculate_hef(data["u"],data["v"],time = time)
    # exptname = "full-20" #TODO make this a kwarg

    cmap = matplotlib.cm.get_cmap('RdBu')
    data["speed"].isel(TIME = i).plot.contour(ax = ax[0],levels = [0.5,0.75,1,1.25],cmap = "copper",lineweight = 0.5,vmin = 0.25,vmax = 1.25,linewidths = 0.75)
    hef.integrate("zl").plot(ax = ax[0],cmap = cmap,vmin = -0.05,vmax = 0.05,cbar_kwargs={'label': "Energy flux (tide to eddy)"})

    ## Add bathymetry plot
    plot_topo(ax[0],data["bathy"])
    ## Second axis: vertical transect
    hef.sel(yb = 0,method = "nearest").plot(ax = ax[1],cmap = cmap,vmin = -0.00001,vmax = 0.00001,cbar_kwargs={'label': "Energy flux (tide to eddy)"})
    plot_topo(ax[1],data["bathy"],transect = 0)
    # fig.suptitle(exptname)
    ax[1].invert_yaxis()
    ax[0].set_xlabel('km from Tas')
    ax[0].set_ylabel('km S to N')
    ax[0].set_title('M2 Horizontal Energy Transfer with Surface Speed contours')
    ## put gridlines on plot
    # ax[0].grid(True, which='both')
    ax[0].hlines(y = 0,xmin = 100,xmax = 1450,linestyles = "dashed")
    ax[1].set_xlabel('')
    ax[1].set_ylabel('km S to N')
    ax[1].set_title('Transect along middle of beam')
    return




def plot_ke(data,framedim = "TIME",**kwargs):

    ax = fig.subplots(2,1)

    time = data["speed"].TIME.values[i]
    ke = calculate_ke(data["u"],data["v"],time = time)
    exptname = "full-20" #TODO make this a kwarg

    cmap = matplotlib.cm.get_cmap('plasma')
    data["speed"].isel(TIME = i).plot.contour(ax = ax[0],levels = [0.5,0.75,1,1.25],cmap = "copper",lineweight = 0.5,vmin = 0.25,vmax = 1.25,linewidths = 0.75)
    ke.mean("zl").plot(ax = ax[0],cmap = cmap,vmax = 12,cbar_kwargs={'label': "Energy flux (tide to eddy)"})

    ## Add bathymetry plot
    plot_topo(ax[0],data["bathy"])


    ## Second axis: vertical transect
    ke.sel(yb = 0,method = "nearest").plot(ax = ax[1],cmap = cmap,vmax = 12,cbar_kwargs={'label': "Kinetic Energy about M2"})
    plot_topo(ax[1],data["bathy"],transect = 0)
    fig.suptitle(exptname)
    ax[1].invert_yaxis()
    ax[0].set_xlabel('km from Tas')
    ax[0].set_ylabel('km S to N')
    ax[0].set_title('Kinetic Energy with Surface Speed contours')
    ## put gridlines on plot
    # ax[0].grid(True, which='both')
    ax[0].hlines(y = 0,xmin = 100,xmax = 1450,linestyles = "dashed")
    ax[1].set_xlabel('')
    ax[1].set_ylabel('km S to N')
    ax[1].set_title('Transect along middle of beam')
    return

def plot_surfacespeed(data,**kwargs):

    cmap = cmocean.cm.dense_r
    earth_cmap = matplotlib.cm.get_cmap("gist_earth")
    fig,ax = plt.subplots(1,figsize = (15,12))
    # Set the background colour to the plot to the lowest value in the cmap
    ax.set_facecolor(cmap(0))
    
    data["speed"].plot(vmax = 4,vmin = 0,ax = ax,cmap = cmap,add_colorbar = False)
    data["bathy"].plot(cmap = earth_cmap,vmin = -1000,vmax = 1500,ax = ax,add_colorbar = False)
    ax.set_title("Surface Speed")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    ax.text(0.95, 0.95, f"Day {int(data.time.values//24)}", transform=ax.transAxes, fontsize=15, va="top", ha="right",color = "linen")
    return fig


################################    POWER SPECTRA FUNCTIONS #####################################
##
## Added April 24. Originally written for the power spectrum notebook. Made general to be used for spectra in other dimensions hopefully


def PlotKEPS(data,ax,color,label = None,linestyle = "solid",dim = "time"):
    # Make a docstring
    """
    Plot power spectrum onto given axis. Fiddling with axes should be done afterwards! Also assumes you've already converted to SI units.
    data : dataset
        Dataset should already have chunks in transform dimension removed
    ax : axis to plot on
    color : color of line
    label : label for line. Kind of deprecated if you're adding manually anyway
    """
    import xrft
    u = xrft.power_spectrum(data.u, dim=[dim], window='hann',true_phase = True,detrend = "linear")
    v = xrft.power_spectrum(data.v, dim=[dim], window='hann',true_phase = True,detrend = "linear")
    ps = 0.5*(u + v)
    m2 = 1 / (12.45 * 3600)
    f = 1 / (17.89 * 3600)

    if "xb" in ps.dims:
        ps = ps.mean("xb")
    if "yb" in ps.dims:
        ps = ps.mean("yb")
    if "zl" in ps.dims:
        ps = ps.mean("zl")
    if "time" in ps.dims:
        ps = ps.mean("time")

    if label != None:
        (ps.freq_time * ps).plot(xscale = "log",yscale = "log",ax = ax,color = color,label = label,linestyle = linestyle)
    else:
        (ps.freq_time * ps).plot(xscale = "log",yscale = "log",ax = ax,color = color,linestyle = linestyle)

    return 

def FetchForKEPS(s,timeslice =200,zrange = (10,30),lfiltered = False,chunks = {"time":-1,"zl":1}):
    """
    This function belongs with plotting spectra. It reads in and calculates the data needed to plot power spectra. Originally in the plot_spectra notebook.
    Given a dictionary s of experiment names, such that 
    s[i] = {"expt":"full-20","time":t0}
    return a dictionary of data for each of these combinations
    This can later be split up into the regions of interest
    """
    data = {}
    for i in s:
        if lfiltered == False:
            vels = collect_data(
                s[i]["expt"],
                rawdata = ["u","v"],timerange = (s[i]["time"] - timeslice,s[i]["time"] + timeslice)).sel(yb = slice(-50,50))
        else:
            vels = xr.open_mfdataset(
                f"/g/data/nm03/ab8992/postprocessed/{s[i]['expt']}/lfiltered/t0-{s[i]['time']}/*.nc",
                decode_times = False,
                decode_cf = False,
                parallel = True)
        vels = vels.assign_coords({"time":vels.time * 3600}).chunk(chunks)
        
        data[i] = vels.fillna(0) #! Fillna necessary for detrend to work in shelf region where there's shallow bathy. This might mess up averages though!

    return data


def TemporalPSTidyup(ax,title):
    """
    Add M2 and f lines to a power spectrum plot as well as axis title.
    """
    m2 = 1 / (12.45 * 3600)
    f = 1 / (17.89 * 3600)
    maxi = 1e-2
    ax.vlines(m2,0,maxi,color = "grey",linestyle = "dotted",alpha = 0.3)
    ax.vlines(m2 + f,0,maxi,color = "grey",linestyle = "dotted",alpha = 0.3)
    ax.vlines(2 * m2,0,maxi,color = "grey",linestyle = "dotted",alpha = 0.3)
    ax.vlines(f,0,maxi,color = "grey",linestyle = "dotted",alpha = 0.3)
    ax.vlines(2 * f,0,maxi,color = "grey",linestyle = "dotted",alpha = 0.3)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(r"$\omega$KE per frequency")
    # Instead of using labels, put the text of M2 f ect on the plot near the x axis
    ax.text(1.01 * m2,1.1 * 1e-10,"M2")
    ax.text(0.99 * m2 + f,1.1 * 1e-10,"M2+f")
    ax.text(1.01 * f,1.1 * 1e-10,"f")
    ax.text(1.01 * 2 * f,1.1 * 1e-10,"2f")
    ax.text(1.01 * 2 * m2,1.1 * 1e-10," 2M2")
    ax.set_title(title)
    return 

def SelectRegion(data,region):
    """
    Slices about a region of interest given longitude extent tuples
    """
    data = data.sel(xb = slice(regions[region][0],regions[region][1]))
    return data

regions = {"gen": [1300,None],"prop": [700,800],"eddy": [200,250],"shelf": [100,150]}



#################  STURM LIOUVILLE SOLVER FUNCTIONS #############################

def ApproxVerticalModes(data,zrange = slice(None,None),nmodes = 5):
    """
    Use approximate Sturm-Liouville theory to calculate the vertical modes of the data. You can feed it 4D (xyzt). or 3D (xyz) data,
    if 4D it will return a timeseries of the horizontal coefficients. Currently only does horizontal velocities! Will add vertical later.
    
    input:
    data : xarray.Dataset
        dataset needs to contain u,v,rho and H. Time dimension must be "time" and vertical dimension must be "zl"
    zrange : slice(min,max) 
        The range (in metres) over which to integrate the velocities. The vertical eigenfunctions always use the entire depth, but velocities can be chosen to avoid the mixed layer.
    nmodes : int
        Number of modes to calculate

    returns:
        Dataset with u(nxyt),v(nxyt) and phi(nxyz) where phi is the eigenfunction of the vertical mode
    
    """
    data["H"] = np.abs(data.bathy)
    if "time" in data.rho.dims:
        data["N"] = calculate_N(data.rho).rename("N").mean("time")
    else:
        data["N"] = calculate_N(data.rho).rename("N")

    # data["N"] = np.linspace(data.N[0],data.N[-1],len(data["N"]))
    zl = data.zl.values
    ## Later we need to do a cumulative integral along the z axis. This is a pain in xarray, so we'll use scipy and pass this to xarray's 'apply_along_axis' method. 
    def scipy_integrate(data):
        full_integral = scipy.integrate.trapz(data,x = zl)
        return (data * 0) + full_integral - scipy.integrate.cumulative_trapezoid(
            data,
            x = zl,
            initial = 0
            )


    # Use np.apply_along_axis to prevent averaging over N and H!
    eigenvectors = (data["rho"].isel(time = 0) * 0).expand_dims({"mode":nmodes})

    ## Construct empty arrays of the right dimensions to store the output
    uout = (data["rho"].isel(zl = 0) * 0).expand_dims({"mode":nmodes})
    vout = (data["rho"].isel(zl = 0) * 0).expand_dims({"mode":nmodes}) 
    Nbar = data.N.integrate("zl") / data.H

    for n in range(1,nmodes + 1): ## Start from 1 or else your first eigenfunction only depends on N!
        
        to_integrate = (n * data["N"] * np.pi) / (data.H * Nbar) ## This is the bit in the Approx Sturm-Liouville eqn under the integral sign within the cos term
        # This next line is a convuluted (but computationally efficient!) way of doing the cumulative sum along the z axis.
        integrated =  np.apply_along_axis(scipy_integrate,to_integrate.get_axis_num('zl'),to_integrate) 

        # This is just the rest of the eigenfunction. Fill NANs with 0s so that integrating over bathymetry doesn't cause problems.
        phi_n = (np.sqrt(
            2 * data.N / (data.H * Nbar)
        ) * np.cos(
            integrated
        )).fillna(0)

        eigenvectors[n-1,:,:,:] = phi_n
        # Handle the 3D or 3D data inputs.
        if "time" in data.u.dims:
            uout[n - 1,:,:,:] = (data.u.fillna(0) * phi_n).sel(zl = zrange).integrate("zl")
            vout[n - 1,:,:,:] = (data.v.fillna(0) * phi_n).sel(zl = zrange).integrate("zl")
        else:
            uout[n - 1,:,:] = (data.u.fillna(0) * phi_n).sel(zl = zrange).integrate("zl")
            vout[n - 1,:,:] = (data.v.fillna(0) * phi_n).sel(zl = zrange).integrate("zl")

    return xr.merge([uout.rename("u"),vout.rename("v"),eigenvectors.rename("phi")])


from scipy.optimize import fsolve
def knGuess(N,n):
    return np.pi * n / N.integrate("zl").values

def _iterator(k,soln = False,**kwargs):
    # print(k,end = "\t")

    N = kwargs["N"]
    z = N.zl.values

    #! Need to handle H!
    z = N.zl.values

    phi = np.zeros((2,z.size))
    x_plot = np.linspace(0, N.zl.values[-1], 100)
    sol = scipy.integrate.solve_bvp(
        lambda z,phi: fun(z,phi,k = k,N = N),
        bc,
        z,
        phi
        )
    y_plot = sol.sol(x_plot)[0]

    if soln:
        return sol

    # print(y_plot[-1])
    return y_plot[-1]


def bc(ya,yb):
    return np.array([ya[0],ya[1] - 0.05])

def fun(z,phi,**kwargs):
    k = kwargs["k"]
    N = kwargs["N"]
    Ninterp = N.interp(zl = z)
    NN = (Ninterp[0:len(z)]**2).values
    return np.vstack((phi[1],-k**2 * NN * phi[0]))

def ShootingVmodes(data,H = 5000,nmodes = 5):
    """
    Calculates vertical modes of both U and W. Fixes top boundary conditions as W(0) = 0, W'(0) = 1. Tweaks k until W(H) = 0.

    N : xarray.DataArray. Smoothed buoyancy frequency profile. Must be on the zl grid.
    H : float. Depth of the water column.
    nmodes : int. Number of modes to calculate.

    returns:
    xarray.Dataset containing U and W eigenfunctions 
    """
    ## First need to handle for the case where we're running this on 3D data rather than single water column!
    # data = data.drop_vars(["xb","yb"])

    N = data.N.isel(xb = 0,yb = 0).drop_vars(["xb","yb"])
    H = data.H.isel(xb = 0,yb = 0).drop_vars(["xb","yb"]).values


    # N is on the zl grid. First add surface and seafloor values.
    N_trunc = N.sel(zl = slice(0,H))
    N_extend = np.zeros(N_trunc.shape[0] + 2)
    z_extend = np.zeros(N_extend.shape[0])
    z_extend[1:len(z_extend) - 1] = N_trunc.zl.values
    N_extend[1:len(z_extend) - 1] = N_trunc.values
    N_extend[0] = N_extend[1]
    N_extend[-1] = N_extend[-2]
    z_extend[0] = 0
    z_extend[-1] = H

    N_extend = xr.DataArray(N_extend,dims = "zl",coords = {"zl":z_extend})
    f,M2 = 1/(17 * 3600), (28.984104 / 360) / (3600)

    # Now N spans the entire water column allowing for accurate boundary conditions
    if not N_extend.integrate("zl") == 0: ## Check the case that N is zero, need to return dummy value in this case
        ks = [
            fsolve(
            lambda x:_iterator(x,soln = False,N = N_extend),
            [knGuess(N_extend,i)],
            maxfev = 10
        )[0] for i in range(1,nmodes+1)]

        efuncs = []
        W = (N * 0).expand_dims({"mode":nmodes})
        for i,k in enumerate(ks):
            soln = _iterator(k,soln = True,N = N_extend)
            Weigenfunc = xr.DataArray(
                soln.sol(soln.x)[0],
                dims = ["z_l"],
                coords = {"z_l":soln.x}
            )
            Weigenfunc = Weigenfunc / (np.sqrt((Weigenfunc**2).integrate("z_l")))

            # Ueigenfunc = Weigenfunc.differentiate("z_l").interp(z_l = N_trunc.zl.values).rename({"z_l":"zl"})
            Ueigenfunc = Weigenfunc.differentiate("z_l").interp(z_l = N.zl.values).fillna(0).rename({"z_l":"zl"})
            Ueigenfunc = Ueigenfunc / (np.sqrt((Ueigenfunc**2).integrate("zl")))


            ## Now calculate the actual k from dispersion relation. Divide by sqrt(M2^2 - f^2)
            
            k *= np.sqrt(M2**2 - f**2)
            h_wavelength = Ueigenfunc.isel(zl = 0).drop_vars(["zl"]).rename("Wavelength") * 0 + 1e-3/k 

            efuncs.append(xr.merge([Weigenfunc.rename("W"),Ueigenfunc.rename("U"),h_wavelength]).assign_coords({"mode":i}).expand_dims("mode"))


        efuncs = xr.concat(efuncs,dim = "mode")
        efuncs.mode.attrs["units"] = "km"
        efuncs.mode.attrs["short name"] = "Horizontal wavelength"
        # assert "xb" not in efuncs
        efuncs = efuncs.expand_dims({"xb":data.xb.values,"yb":data.yb.values})
        # These efuncs now contain polynomial spline objects. 
        # They should be used to generate both the vertical and horizontal eigenfunctions zi and zl points

        return efuncs[["U","Wavelength"]].transpose("mode","zl","yb","xb")
    
    else:
        ## In this case we return a dummy values with the right shape
        Ueigenfunc = xr.DataArray(
            N.zl.values * 0,
            dims = ["zl"],
            coords = {"zl":N.zl.values}
        ).rename("U").expand_dims({"xb":data.xb.values,"yb":data.yb.values,"mode":np.arange(nmodes)}).transpose("mode","zl","yb","xb")
        h_wavelength = Ueigenfunc.isel(zl = 0).drop_vars(["zl"]).rename("Wavelength")
        return xr.merge([Ueigenfunc,h_wavelength])

def ShootingVmodes_parallel(data,nmodes = 5):
    """
    data[N,H]: MUST ALREADY BE CHUNKED IN 1,1 HORIZONTALLY
    
    """
    if len(data.zl) == 0:
        return data
    # print(data)
    vmode_template = data.N.expand_dims({"mode":np.arange(nmodes)}).rename("U").drop_vars(["lat","lon"])
    wavenumber_template = vmode_template.isel(zl = 0).drop_vars(["zl"]).rename("Wavelength")
    template = xr.merge([vmode_template,wavenumber_template])
    return xr.map_blocks(
        ShootingVmodes,
        data,kwargs = {"nmodes":nmodes},
        template = template
    )
def getN(rho):
    """Calculates N and smoothes it for use with SL decomposition"""
    rhofull = rho
    Nfull = tt.calculate_N(rhofull)
    return Nfull.rolling(zl = 5,center = True).mean().ffill("zl").bfill("zl")


def DirectionalFilter(data):
    """
    Fourier filter into forward and backward propagating signals
    """

    FT = xrft.fft(
        vmodesFull.u.drop(['lon', 'lat']).sel(xb = slice(200,1200)),dim = ["time","xb"]
    ).load()

    ft = np.real(xrft.ifft(
        FT,dim = ["freq_time","freq_xb"]
    ))

    forward = np.real(xrft.ifft(
        FT.where((FT.freq_xb >= 0) & (FT.freq_time >= 0), 0) + FT.where((FT.freq_xb <= 0) & (FT.freq_time <= 0), 0) - FT.where((FT.freq_xb == 0) & (FT.freq_time == 0), 0),
        dim = ["freq_time","freq_xb"]
    ))

    backward = np.real(xrft.ifft(
        FT.where((FT.freq_xb <= 0) & (FT.freq_time >= 0), 0) + FT.where((FT.freq_xb >= 0) & (FT.freq_time <= 0), 0) - FT.where((FT.freq_xb == 0) & (FT.freq_time == 0), 0),
        dim = ["freq_time","freq_xb"]
    ))

    return xr.merge([forward.rename(f"{data.name}_forward"),backward.rename(f"{data.name}_backward")])