# A place to jot down things we need to keep track of

full-20 output 145. For some reason the yb axis got messed up. We have duplicate values for yb = -132, and then -84 is missing. 
This means that loading the data fails due to yb not monatonically increasing. As a workaround I just shuffled the dimensions along so there's a row of nans at yb = -84. This might cause issues with other postprocessing scripts? Might need to either throw out 145 or manually handle it.

# Quirks of the Lagrange Filter package

All variables need to be in SI

When specifying times in `f(times = [1,2,3])`, the times are in seconds since start of dataset. NOT the actual timestamps of data

If you get NaNs, it's probably because particles were advected beyond the edge of the domain

Can't just pip install on top of analysis3. I needed to set up a dedicated virtualenv

Seems like importing / using dask distributed leads to the hdf error? Looks like we just need to call `client.close()` before running the filtering

# collect_data in parallel new issue?
Started randomly getting `RuntimeError: NetCDF: Not a valid ID`. This seems to get ignored the first time but causes a crash later. suddenly started on the filtering_env. Just re-running seems to do the trick?

**fixed** by removing non monatonically increasing output 027 from notide dataset. Notide now loads in its entirety.