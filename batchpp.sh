#!/bin/bash

for i in {2..30}
do
    python3 recipes.py -r postprocess -e 1xdissipation-full-20 -o $i &
done
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 4 &
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
# python3 recipes.py -r postprocess -e 4xdissipation-full-20 -o 3
