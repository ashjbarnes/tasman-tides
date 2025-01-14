## Notes

I've removed all dask references from the package, and confirm that it works in serial on just one z level

Compared to the 'parallel' version, it took 2.30 vs like 2.20 for a single time and z. Parallelising with dask over 2 z levels, it took the same amount of time. A bit of slow down running 20 - this took 4 mins. However, this is probably due to all of the workers trying to read the data at the same point. Need to adjust so that each z level is saved as a separate file on the jobfs. Algorithm as follows:

1. Open dask client. Read data and save split in zlevels to jobfs
2. Run lfilter(n) over ever zlevel. Should save intermediate files, either scratch or jobfs
3. Integrate cst vertically (maybe top half and bottom half?) and archive
4. Save full u and v fields to disk
5. Modal decomposition of u and v, save this to disk too. This way we save loading full 4D u and v later, and it's on the fast access jobfs now. 

## Testing number of threads on 40th degree run:
Tests done with 4 timesteps, U sampled only, one z level per run

Single run in serial: 3:40
Single threaded, 20 in parallel: 5:30
Double threaded, 14 in parallel: 4:17

## Test importing filtering ahead of time:
Double threaded: 3:48. Saves 30s

## Running 20 layers in parallel for 20th degree 
* Tested all (u,uv,uu,vv,v) over 2 timesteps
* This takes about 4 minutes per timestep in total
* Multiplying by 149 timesteps, this is 9 hours of walltime. Unacceptable for 40th degree!

## Test not loading data, passing paths
* Default: takes 22GB and 4 min 50
* Reading from scratch: 4 min 30 but only 10gb mem used
* less than 4 mins when not also reading and saving


## Plan
Normal nodes have 48 cores each. We can then do 96 layers simultaneously, splitting the job into two lots of 75. This is a total of 4 nodes at a time

1. Need a callable function that can be qsub'd, taking arguments for z-level and time window
2. Function also tidies and catalogues outputs. Ought to calculate CST for example
3. Wrap this with a bash / python script which calls the qsubbable function


Normal queue 20th degree:
10 mins with 96 cpu request

Normal queue 40th degree
30 mins with 48 cpu request
Looks like I'm not utilising the extra cpus!
20 mins with 96 cpus but only 48 levels. So ~ extra 10 mins for doubled jobs. Potentially only 5 mins per job? Will test now running the same but with 15 timesteps to check scaling. - running 20th degree 48 levels took 3hrs17, or less than 2 mins per task!

For 40th degree, looks like 1 timestep for slow filter takes 15 mins walltime, doing 48 z levels in parallel. So, Multiplying by 149 hours means 37 hours of walltime. In total, including two lots of filtering and top and bottom depths, we need:

15 hours * all zlevel * 1 filter ~ 20 iterations of 2:40 hrs each 5 times fewer jobs and 5 times less walltime per job
OR sapphire rapids?? testing 96 zl runs now
## Qsub times

test 40th degree, 48 levels over 15 timesteps: 82 minutes = about 5 mins per job. Hence, total walltime expected to be around 50 hours total

Sapphire rapids with 96 cpus per node: ran 15 timesteps of 40th degree in 1 hour 10. 