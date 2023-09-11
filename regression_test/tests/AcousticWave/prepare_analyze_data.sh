gamer_folder=${1}
gamer_test_folder=${gamer_folder}/bin
regression_folder=${gamer_folder}/regression_test/tests/AcousticWave

#Resolution convergence : check error in different resolution
#sh ${regression_folder}/go.sh ${regression_folder} ${gamer_test_folder}/AcousticWave_input*
sh ${regression_folder}/go.sh ${regression_folder} ${gamer_test_folder}/AcousticWave_*


