# A place to jot down things we need to keep track of

full-20 output 145. For some reason the yb axis got messed up. We have duplicate values for yb = -132, and then -84 is missing. 
This means that loading the data fails due to yb not monatonically increasing. As a workaround I just shuffled the dimensions along so there's a row of nans at yb = -84. This might cause issues with other postprocessing scripts? Might need to either throw out 145 or manually handle it.
