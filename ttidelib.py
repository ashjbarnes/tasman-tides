# A file to keep all common functions that might be used for postprocessing and analysis fo the ttide experiment

from matplotlib import rc
import numpy as np
import matplotlib.pyplot as plt
import os
import haversine
import xarray as xr
import subprocess
import matplotlib.pyplot as plt
import shutil
import xesmf
import pathlib as Path
from xmovie import Movie 
import xrft
def setup_mom6(name,tname,overrides = [],walltime = None,common_forcing = False,default_dir = "default"):
    ## If common forcing is provided, set another input folder that contains the windstress for all runs in this experiment
    default_dir = f"/home/149/ab8992/bottom_near_inertial_waves/automated/{default_dir}/*"
    
    if name in os.listdir("/home/149/ab8992/bottom_near_inertial_waves/automated"):
        shutil.rmtree("/home/149/ab8992/bottom_near_inertial_waves/automated/" + name)
    
    # subprocess.run(["/home/149/ab8992/tools/myscripts/automated_mom6/copydir",name])
    subprocess.run(f"cp {default_dir} /home/149/ab8992/bottom_near_inertial_waves/automated/{name} -r",shell = True)

    ## We've created the new directory with name 'name'
    # Now need to edit config file to point to the name of the topography configuraation 'tname'
    file = open("/home/149/ab8992/bottom_near_inertial_waves/automated/" + name + "/config.yaml","r")
    config = file.readlines()
    file.close()
    ##Iterate through and find jobname and input
    
    for line in range(len(config)):
        if "jobname" in config[line][0:10]:
            config[line] = "jobname: " + name  + "\n"
            
        if "input" in config[line][0:10]:
            if common_forcing == False:
                config[line] = "input: /g/data/v45/ab8992/mom6_channel_configs/" + tname + "\n"
            else:
                config[line] = f"input:\n     - /g/data/v45/ab8992/mom6_channel_configs/{tname}\n     - /g/data/v45/ab8992/mom6_channel_configs/{common_forcing}\n"
            
        if "walltime" in config[line][0:10] and walltime != None:
            config[line] = "walltime: " + str(walltime)
    file = open("/home/149/ab8992/bottom_near_inertial_waves/automated/" + name + "/config.yaml","w")
    file.writelines(config)
    
    
    ## Update override file
    
    file = open("/home/149/ab8992/bottom_near_inertial_waves/automated/" + name + "/MOM_override","r")
    override_file = file.readlines()
    file.close()
    
    for i in overrides:
        override_file.append("#override " + i + str("\n"))
        
    file = open("/home/149/ab8992/bottom_near_inertial_waves/automated/" + name + "/MOM_override","w")
    file.writelines(override_file)
    
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
    

def make_movie(data,plot_function,runname,plotname,plot_kwargs = {}):
    """
    data_list : dictionary of dataarrays required by plot function
    plot_function : function to plot data
    runname : name of the run eg full-20
    plotname : name of the plot eg "h_energy_transfer"
    plot_kwargs : kwargs to pass to plot function
    """

    outpath = f"/g/data/v45/ab8992/dropbox/tasman-tides/{runname}/movies/{plotname}/"
    if not os.path.exists(outpath):
        os.makedirs(outpath)
    
    print(f"Making movie and writing to {outpath}")
    mov = Movie(data,plot_function,input_check = False,plot_kwargs = plot_kwargs)
    mov.save(outpath,overwrite_existing = True,parallel = True,parallel_compute_kwargs=dict(scheduler="processes", num_workers=28)) # ,
    print("finsished.")
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



def hef(u,v,i):
    """
    Calculate the horizontal energy fluxes from the u and v velocities and ith time index. Time window is 12 m2 periods
    """
    t0 = u.time[0].values
    u_ = u.sel(
            time = slice(t0 + i,t0 + i + averaging_window)
            ).chunk({"time":-1}).drop(["lat","lon"])
    v_ = v.sel(
            time = slice(t0 + i,t0 + i + averaging_window)
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

    nstress_u = (uf * uf).mean("time")
    nstress_v = (vf * vf).mean("time")
    n_strain = dux - dvy

    shear = (uf * vf).mean("time")
    shear_strain = duy + dvx
    out = xr.Dataset(
        {
            "nstress_u":nstress_u,
            "nstress_v":nstress_v,
            "n_strain":n_strain,
            "shear":shear,
            "shear_strain":shear_strain,
            "total":((nstress_u - nstress_v) * n_strain - shear * shear_strain)
        }
    )

    return out