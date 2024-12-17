#!/bin/bash

# Parse command-line arguments
while getopts t:e:z:w: flag
do
    case "${flag}" in
        t) tvalue=${OPTARG};;
        e) evalue=${OPTARG};;
        z) zvalue=${OPTARG};;
        w) wvalue=${OPTARG};;
    esac
done



# Check if the zvalue contains a dash, indicating a range
if [[ $zvalue == *-* ]]
then
    # Split the zvalue into start and end of the range
    IFS='-' read -ra RANGE <<< "$zvalue"

    # Iterate over the range and run the command
    for i in $(seq ${RANGE[0]} ${RANGE[1]})
    do
        filepath="/g/data/nm03/ab8992/postprocessed/${evalue}/lfiltered/bp-t0-${tvalue}/highpass_${i}.nc"
        filepath2="/g/data/nm03/ab8992/postprocessed/${evalue}/lfiltered/bp-t0-${tvalue}/lowpass_${i}.nc"
        if [ -f "$filepath" ] && [ -f "$filepath2" ]
        then
            echo "File $filepath exists."
        else
	    echo "filtering $filepath" 
            python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -z $i -w $wvalue &
        fi
    done
else
    # If the zvalue is not a range, just run the command once
    python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -z $zvalue -w $wvalue &
fi
