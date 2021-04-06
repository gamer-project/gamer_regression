#!/bin/bash

FILE="table__convergence"

folder1=$1
folder2=$2
folder3=$3
folder4=$4

Record__L1Err="Record__L1Err"

if [ -f "$1/$Record__L1Err" ] && [ -f "$2/$Record__L1Err" ] && [ -f "$3/$Record__L1Err" ] && [ -f "$4/$Record__L1Err" ]
then
  x032=`tail -n 1 $1/$Record__L1Err|awk '{print $3}'`
  x064=`tail -n 1 $2/$Record__L1Err|awk '{print $3}'`
  x128=`tail -n 1 $3/$Record__L1Err|awk '{print $3}'`
  x256=`tail -n 1 $4/$Record__L1Err|awk '{print $3}'`
  
  echo "032    $x032" >  $FILE 
  echo "064    $x064" >> $FILE 
  echo "128    $x128" >> $FILE 
  echo "256    $x256" >> $FILE 
  
  cat $FILE
else
    echo "$Record__L1Err do not exist in $PWD"
fi
