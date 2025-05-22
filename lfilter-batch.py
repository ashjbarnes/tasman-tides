import numpy as np
import subprocess


times_40th = np.arange(4320,17520, 720)
times_20th = times_40th + 17784


# To start with, just do the first 5 months
times_40th = np.arange(4320,4320 + 10 * 30 * 24, 720)

# FILL IN GAPS 
# Callum suggested we include two datapoints per month. Add 360 to every time to achieve this. Comment out to go back to old times
times_40th -= 360

times_20th = times_40th + 17784


for t0 in times_20th:
    for expt in ["full","beamless","smooth"]:
        subprocess.run(f"bash lfilter.sh -e {expt}-20 -t {t0}",cwd = "/home/149/ab8992/tasman-tides",shell = True)
        subprocess.run(f"bash lfilter.sh -e {expt}-10 -t {t0}",cwd = "/home/149/ab8992/tasman-tides",shell = True)

for t0 in times_40th:
    for expt in ["full","beamless","smooth"]:
        subprocess.run(f"bash lfilter.sh -e {expt}-40 -t {t0}",cwd = "/home/149/ab8992/tasman-tides",shell = True)
