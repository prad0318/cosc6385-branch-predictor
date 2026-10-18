Tomasulo simulator with multi issue (issue width 1 to 4)

Started from the given tomasulo-python code. Files I changed: issue.py, wb.py, commit.py, exe.py, main.py

How to run:

```
cd code
python3 main.py                                  # runs code.in with issue width 1
python3 main.py ../tests/test1_independent.in 2  # input file, issue width
```

The issue width can also go in the input file as a line like: Issue width = 2

Run all my tests with widths 1-4 (outputs go in results/):

```
sh run_tests.sh
```

Report is report.pdf
