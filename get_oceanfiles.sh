#!/bin/bash


printf 'processing north segment' 
python -m motuclient --motu https://my.cmems-du.eu/motu-web/Motu --service-id GLOBAL_MULTIYEAR_PHY_001_030-TDS --product-id cmems_mod_glo_phy_my_0.083_P1D-m --longitude-min 142 --longitude-max 180 --latitude-min -26.3 --latitude-max -25.7 --date-min 2015-01-01 00:00:00 --date-max 2015-12-31 00:00:00 --depth-min 0.49 --depth-max 6000 --variable so --variable thetao --variable vo --variable zos --variable uo --out-dir /scratch/v45/ab8992/reanalysis_tmp/ttide-20 --out-name north_unprocessed --user 'abarnes' --pwd '$KQ%QqFxjSSbE2'

printf 'processing south segment' 
python -m motuclient --motu https://my.cmems-du.eu/motu-web/Motu --service-id GLOBAL_MULTIYEAR_PHY_001_030-TDS --product-id cmems_mod_glo_phy_my_0.083_P1D-m --longitude-min 142 --longitude-max 180 --latitude-min -56.3 --latitude-max -55.7 --date-min 2015-01-01 00:00:00 --date-max 2015-12-31 00:00:00 --depth-min 0.49 --depth-max 6000 --variable so --variable thetao --variable vo --variable zos --variable uo --out-dir /scratch/v45/ab8992/reanalysis_tmp/ttide-20 --out-name south_unprocessed --user 'abarnes' --pwd '$KQ%QqFxjSSbE2'

printf 'processing east segment' 
python -m motuclient --motu https://my.cmems-du.eu/motu-web/Motu --service-id GLOBAL_MULTIYEAR_PHY_001_030-TDS --product-id cmems_mod_glo_phy_my_0.083_P1D-m --longitude-min 179.7 --longitude-max 180.3 --latitude-min -56 --latitude-max -26 --date-min 2015-01-01 00:00:00 --date-max 2015-12-31 00:00:00 --depth-min 0.49 --depth-max 6000 --variable so --variable thetao --variable vo --variable zos --variable uo --out-dir /scratch/v45/ab8992/reanalysis_tmp/ttide-20 --out-name east_unprocessed --user 'abarnes' --pwd '$KQ%QqFxjSSbE2'

printf 'processing west segment' 
python -m motuclient --motu https://my.cmems-du.eu/motu-web/Motu --service-id GLOBAL_MULTIYEAR_PHY_001_030-TDS --product-id cmems_mod_glo_phy_my_0.083_P1D-m --longitude-min 141.7 --longitude-max 142.3 --latitude-min -56 --latitude-max -26 --date-min 2015-01-01 00:00:00 --date-max 2015-12-31 00:00:00 --depth-min 0.49 --depth-max 6000 --variable so --variable thetao --variable vo --variable zos --variable uo --out-dir /scratch/v45/ab8992/reanalysis_tmp/ttide-20 --out-name west_unprocessed --user 'abarnes' --pwd '$KQ%QqFxjSSbE2'

printf 'processing ic segment' 
python -m motuclient --motu https://my.cmems-du.eu/motu-web/Motu --service-id GLOBAL_MULTIYEAR_PHY_001_030-TDS --product-id cmems_mod_glo_phy_my_0.083_P1D-m --longitude-min 141.7 --longitude-max 180.3 --latitude-min -56.3 --latitude-max -25.7 --date-min 2015-01-01 00:00:00 --date-max 2015-01-01 01:00:00 --depth-min 0.49 --depth-max 6000 --variable so --variable thetao --variable vo --variable zos --variable uo --out-dir /scratch/v45/ab8992/reanalysis_tmp/ttide-20 --out-name ic_unprocessed --user 'abarnes' --pwd '$KQ%QqFxjSSbE2'
