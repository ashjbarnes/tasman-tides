# A file to keep all common functions that might be used for postprocessing and analysis fo the ttide experiment

from matplotlib import rc
import numpy as np
from netCDF4 import Dataset
import matplotlib.pyplot as plt
import os
import xarray as xr
import subprocess
import matplotlib.pyplot as plt
import shutil

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


