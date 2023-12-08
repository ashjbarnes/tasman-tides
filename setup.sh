#!/bin/bash

# Check if two command line arguments are provided
if [ $# -ne 2 ]; then
  echo "Usage: $0 expt resolution"
  exit 1
fi

expt=$1
res=$2

runname=$1-$2



mkdir rundirs/$runname

echo $runname

cp rundirs/default/*table rundirs/$runname
cp rundirs/default/*input* rundirs/$runname
cp rundirs/default/postprocessing.sh rundirs/$runname


cp rundirs/default/$expt/* rundirs/$runname
cp rundirs/default/layouts/MOM_layout-$res rundirs/$runname/MOM_layout
cp rundirs/default/layouts/config.yaml-$res rundirs/$runname/config.yaml

## Modify config yaml file
sed -i s/EXPTNAME/$runname/ rundirs/$runname/config.yaml

