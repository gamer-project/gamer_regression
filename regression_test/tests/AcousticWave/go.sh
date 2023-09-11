#!/bin/bash
regression_folder=$1

folder1=$2
folder2=$3
folder3=$4
folder4=$5

Record__L1Err="Record__L1Err"
FILE=${regression_folder}/table__convergence
echo -e "NGrid\tError" > $FILE

if [ -f "$2/$Record__L1Err" ] && [ -f "$3/$Record__L1Err" ] && [ -f "$4/$Record__L1Err" ] && [ -f "$5/$Record__L1Err" ]
then
  x032=`tail -n 1 $2/$Record__L1Err | awk '{print $1,$3}'`
  x064=`tail -n 1 $3/$Record__L1Err | awk '{print $1,$3}'`
  x128=`tail -n 1 $4/$Record__L1Err | awk '{print $1,$3}'`
  x256=`tail -n 1 $5/$Record__L1Err | awk '{print $1,$3}'`

  echo "$x032" >>  $FILE
  echo "$x064" >> $FILE
  echo "$x128" >> $FILE
  echo "$x256" >> $FILE

  #cat $FILE
else
    echo "$Record__L1Err do not exist in $PWD"
fi
