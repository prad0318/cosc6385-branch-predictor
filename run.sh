# runs my predictor on every trace and prints the average at the end
total=0
count=0
for f in traces/*/*.bz2
do
  echo $f
  r=$(./src/predict $f | tail -1 | awk '{print $1}')
  echo "$r MPKI"
  total=$(echo "$total + $r" | bc)
  count=$((count + 1))
done
echo ""
echo "========================================"
echo "  AVERAGE MPKI over $count traces: $(echo "scale=3; $total / $count" | bc)"
echo "========================================"
