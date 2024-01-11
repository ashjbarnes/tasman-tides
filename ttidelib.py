# A file to keep all common functions that might be used for postprocessing and analysis fo the ttide experiment

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
import xesmf
import dask
import cmocean
from pathlib import Path
from xmovie import Movie 
import xrft
import argparse
import io
import sys
from dask.distributed import Client,default_client
home = Path("/home/149/ab8992/tasman-tides")
gdata = Path("/g/data/nm03/ab8992")


def logmsg(message,logfile = home / "logs" /"mainlog"):
    """
    Write a message out to the logfile. If message is None, create a new logfile with the current time
    """
    current_time = dt.datetime.now().strftime("%d-%m-%y %H:%M:%S")

    with open(logfile,"a") as f:
        f.write(current_time + ":\t" + message + "\n")
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

def beamgrid(data,lat0 = -42.1,lon0 = 147.2,beamwidth = 400,beamlength = 1500,plot = False,xname = "xh",yname = "yh",vmin = None,vmax = None,chunks = 12):
    # make a docstring describing these variables
    """
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
    

def collect_data(exptname,rawdata = None,ppdata = None,surface_data = None,bathy = False,outputs = "output*",chunks = "auto",timerange = (None,None)):
    """
    Collect all data required for analysis into a single xarray.Dataset
    expname : str
        Name of the experiment
    rawdata : list of str
        List of raw data variables to include
    ppdata : list of str
        List of postprocessed data variables to include. Note that thse aren't organised in to "outputs" given that they are often filtered temporally and so don't fit within the same output bins as model runs
    outputs : str
        Glob string to match the output directories
    chunks : dict
        Chunks to use for dask. If "auto", use the default chunking for each variable. Surface variables are only given a time chunk
    timerange : Can choose the times instead of output. If None, use all times
    """

    rawdata_path = Path("/g/data/nm03/ab8992/outputs/") / exptname / outputs
    ppdata_path = Path("/g/data/nm03/ab8992/postprocessed/") / exptname

    timechunk = -1
    if "time" in chunks:
        timechunk = chunks["time"]

    data = {}
    if type(rawdata) != type(None):
        for var in rawdata:
            data[var] = xr.open_mfdataset(str(rawdata_path / var / "*"),chunks = chunks,decode_times = False).sel(time = slice(timerange[0],timerange[1])
            )

    if type(ppdata) != type(None):
        for var in ppdata:
            data[var + "_topdown"] = xr.open_mfdataset(
                str(ppdata_path / var / "topdown" / "*.nc"),chunks = chunks,decode_times = False).rename({var:var + "_topdown"}).sel(time = slice(timerange[0],timerange[1])
            )
            data[var + "_transect"] = xr.open_mfdataset(
                str(ppdata_path / var / "transect" / "*.nc"),chunks = chunks,decode_times = False).rename({var:var + "_transect"}).sel(time = slice(timerange[0],timerange[1])
            )

    if bathy == True:
        data["bathy"] = xr.open_mfdataset(str(rawdata_path.parent / "bathy_transect.nc")).rename({"elevation":"bathy"})


    ## Merge data into dataset
    data = xr.merge([data[i] for i in data])

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

##### FILTERING AND DIAGNOSTICS #####

m2 = 360 / 28.984104 ## Period of m2 in hours
averaging_window = int(12 * m2) ## this comes out to be 149.0472 hours, so close enough to a multiple of tidal periods
m2f = 1/ m2    ## Frequency of m2 in radians per hour


def m2filter(field,freq = m2f,tol = 0.015):
    """
    Filter about the m2 frequency. Just pass a field and it will return the real part of the filtered field
    """
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
    if anomaly == True:
        data["dissipation_topdown"] -= data["dissipation_topdown"].mean("time")
        data["dissipation_transect"] -= data["dissipation_transect"].mean("time")
        vmax_topdown = 400000
        vmin_topdown = -400000
        vmax_transect = 200
        vmin_transect = -200
        cmap = "Rdbu"
    fig = plt.figure(figsize=(20, 12))
    ax = fig.subplots(2,1)

    cmap = matplotlib.cm.get_cmap('plasma')

    ## HORIZONTAL PLOTS FIRST

    data["vorticity_topdown"].plot.contour(ax = ax[0],levels = [-0.075,-0.025,0.025,0.075],cmap = cmap,linestyle = "solid")
    data["dissipation_topdown"].plot(ax = ax[0],cmap = cmap,cbar_kwargs={'label': "Dissipation"},vmax = vmax_topdown)

    ## Add bathymetry plot
    plot_topo(ax[0],data["bathy"])


    ## Second axis: vertical transect
    data["vorticity_transect"].plot.contour(ax = ax[1],levels = [-0.075,-0.025,0.025,0.075],cmap = cmap,linestyle = "solid")
    data["dissipation_transect"].plot(ax = ax[1],cmap = cmap,cbar_kwargs={'label': "Dissipation"},vmax = vmax_transect)
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
    try:
    # Try to get the existing Dask client
        client = default_client()
    except ValueError:
        # If there's no existing client, create a new one
        client = Client()
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
        def process_chunk(data,i):
            fig = plot_function(data.isel(time = i),**plot_kwargs)
            fig.savefig(tmppath / f"frame_{str(i).zfill(5)}.png")
            plt.close()
            return None
        
        frames = [process_chunk(data,i) for i in range(len(data.time))]
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

    fig,ax = plt.subplots(1,figsize=(15, 12))
    # time = data["speed"].time.values[i]
    exptname = "full-20" #TODO make this a kwarg

    cmap = cmocean.cm.speed
    data["speed"].plot(ax = ax,cmap = cmap,cbar_kwargs={'label': "Surface speed (m/s)"},vmin = 0,vmax = 1.5)

    ## Add bathymetry plot
    plot_topo(ax,data["bathy"])

    fig.suptitle(exptname)
    ax.set_xlabel('km from Tas')
    ax.set_ylabel('km S to N')
    ax.set_title('Surface speed')
    return fig

