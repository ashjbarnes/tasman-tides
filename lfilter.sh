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
if [ -f "/g/data/nm03/ab8992/postprocessed/vertical_eigenfunctions/vmode-t0-$(tvalue).nc" ]
then
    echo "Vmodes already exist"
else
    echo "Running vmodes"
    python3 recipes.py -r vmodes -e $evalue -t $tvalue -q 1 &
fi
for i in $(seq 0 9)
    do
        filepath="/g/data/nm03/ab8992/postprocessed/${evalue}/lfiltered/t0-${tvalue}/FastFilter${i}.nc"
        filepath2="/g/data/nm03/ab8992/postprocessed/${evalue}/lfiltered/t0-${tvalue}/SlowFilter${i}.nc"
        if [ -f "$filepath" ] && [ -f "$filepath2" ]
        then
            echo "File $filepath exists."
        else
	    echo "filtering $filepath" 
            python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -n $i -w 149 -q 1 &
        fi
done
