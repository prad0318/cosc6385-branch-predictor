# runs all my test cases with issue width 1 to 4 and saves the output in results/
cd code
for t in ../tests/*.in
do
  for w in 1 2 3 4
  do
    name=$(basename $t .in)
    python3 main.py $t $w > ../results/${name}_width$w.txt
    echo "$name width $w: $(grep 'Total cycles' ../results/${name}_width$w.txt)"
  done
done
