#!/usr/bin/bash

logfile='resubmit.log'
counterfile='resubmit.count'
outfile='mom6.err'
source /g/data/hh5/public/apps/miniconda3/envs/analysis3-24.04/bin/activate
MAX_RESUBMISSIONS=5
date >> ${logfile}

# Define errors from which a resubmit is appropriate
declare -a errors=(
	           "Segmentation"
                   "Segmentation fault: address not mapped to object"
                   "Segmentation fault: invalid permissions for mapped object"
                   "Transport retry count exceeded"
                   "atmosphere/input.nml"
                   "ORTE has lost communication with a remote daemon"
                   "MPI_ERRORS_ARE_FATAL"
                   "eta has dropped below bathyT"
		  )

resub=false
for error in "${errors[@]}"
do
  if grep -q "${error}" ${outfile}
  then
     echo "Error found: ${error}" >> ${logfile}
     resub=true
     break
  else
     echo "Error not found: ${error}" >> ${logfile}
  fi
done

if ! ${resub}
then
  echo "Error not eligible for resubmission" >> ${logfile}
  exit 0
fi

if [ -f "${counterfile}" ]
then
  PAYU_N_RESUB=$(cat ${counterfile})
else
  echo "Reset resubmission counter" >> ${logfile}
  PAYU_N_RESUB=${MAX_RESUBMISSIONS}
fi

echo "Resubmission counter: ${PAYU_N_RESUB}" >> ${logfile}

if [[ "${PAYU_N_RESUB}" -gt 0 ]]
then
  # Sweep and re-run
  cp MOM_override_smallstep MOM_override
  payu sweep >> ${logfile}
  payu run -n 50 -f  >> ${logfile}
  # Decrement resub counter and save to counter file
  ((PAYU_N_RESUB=PAYU_N_RESUB-1))
  echo "${PAYU_N_RESUB}" > ${counterfile}
else
  echo "Resubmit limit reached ... " >> ${logfile}
  rm ${counterfile}
fi

echo "" >> ${logfile}