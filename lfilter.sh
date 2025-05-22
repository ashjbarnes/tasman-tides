#!/bin/bash

# Parse command-line arguments
while getopts t:e:z:w: flag
do
    case "${flag}" in
        t) tvalue=${OPTARG};;
        e) evalue=${OPTARG};;
    esac
done



# Check if the zvalue contains a dash, indicating a range

    # Iterate over the range and run the command
if [ -f "/g/data/nm03/ab8992/postprocessed/vertical_eigenfunctions/vmode-t0-${tvalue}.nc" ]
then
    echo "Vmodes already exist"
else
    echo "Running vmodes"
#    python3 recipes.py -r vmodes -e $evalue -t $tvalue -q 1
fi
for i in $(seq 0 13)
    do
        filepath="/g/data/nm03/ab8992/postprocessed/${evalue}/bandpassed/t0-${tvalue}/Filtered${i}.nc"
        if [ -f "$filepath" ]
        then
            echo "File $filepath exists."
        else
	    echo "filtering $filepath" 
            python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -n $i -w 233 -q 1
        fi
done
