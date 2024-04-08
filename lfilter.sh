#!/bin/bash

# Parse command-line arguments
while getopts t:e:z: flag
do
    case "${flag}" in
        t) tvalue=${OPTARG};;
        e) evalue=${OPTARG};;
        z) zvalue=${OPTARG};;
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
        filepath="/g/data/nm03/ab8992/postprocessed/${evalue}/lfiltered/t0-${tvalue}/filtered_${i}.nc"
        if [ -f "$filepath" ]
        then
            echo "File $filepath exists."
        else
            echo "File $filepath does not exist."
            python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -z $i &
        fi
    done
else
    # If the zvalue is not a range, just run the command once
    python3 recipes.py -r lagrange_filter -e $evalue -t $tvalue -z $zvalue *
fi
