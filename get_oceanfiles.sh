#!/bin/bash

printf 'processing north segment' 
copernicus-marine subset --dataset-id cmems_mod_glo_phy_my_0.083_P1D-m --variable so --variable thetao --variable vo --variable zos --variable uo --start-datetime 2015-01-01 --end-datetime 2015-12-31 --minimum-longitude 142 --maximum-longitude 180 --minimum-latitude -26.3 --maximum-latitude -25.7 -f north_unprocessed.nc

printf 'processing south segment' 
copernicus-marine subset --dataset-id cmems_mod_glo_phy_my_0.083_P1D-m --variable so --variable thetao --variable vo --variable zos --variable uo --start-datetime 2015-01-01 --end-datetime 2015-12-31 --minimum-longitude 142 --maximum-longitude 180 --minimum-latitude -56.3 --maximum-latitude -55.7 -f south_unprocessed.nc

printf 'processing east segment' 
copernicus-marine subset --dataset-id cmems_mod_glo_phy_my_0.083_P1D-m --variable so --variable thetao --variable vo --variable zos --variable uo --start-datetime 2015-01-01 --end-datetime 2015-12-31 --minimum-longitude 179.7 --maximum-longitude 180.3 --minimum-latitude -56 --maximum-latitude -26 -f east_unprocessed.nc

printf 'processing west segment' 
copernicus-marine subset --dataset-id cmems_mod_glo_phy_my_0.083_P1D-m --variable so --variable thetao --variable vo --variable zos --variable uo --start-datetime 2015-01-01 --end-datetime 2015-12-31 --minimum-longitude 141.7 --maximum-longitude 142.3 --minimum-latitude -56 --maximum-latitude -26 -f west_unprocessed.nc

printf 'processing ic segment' 
copernicus-marine subset --dataset-id cmems_mod_glo_phy_my_0.083_P1D-m --variable so --variable thetao --variable vo --variable zos --variable uo --start-datetime 2015-01-01 --end-datetime 2015-01-01 --minimum-longitude 141.7 --maximum-longitude 180.3 --minimum-latitude -56.3 --maximum-latitude -25.7 -f ic_unprocessed.nc

