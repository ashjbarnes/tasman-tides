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

## For revision all expts were spun up from full-20 at output 70. We have 10x15 days of data here with t0 at 483
## Filter window is 333, so we need to go 167 + 483 as the first time, since t0 defined middle of window
t0 = 483 + 167

# For times, we have 5 months of data. Do samples twice a month

times = np.arange(t0, 483 + 15 * 24 * 10, 360)
print("Sample times:")
print(times)

for t0 in times_20th:
    for expt in ["1xdissipation-full","4xdissipation-full","smooth"]:
        subprocess.run(f"bash lfilter.sh -e {expt}-20 -t {t0}",cwd = "/home/149/ab8992/tasman-tides",shell = True)

