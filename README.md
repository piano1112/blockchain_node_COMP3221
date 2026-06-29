# COMP3221 Assignment 2

## Example Execution
~~~
./Run.sh node.py 8000 nodes.txt
~~~

## System Architecture
~~~
node.py              # main entry point
network.py           # TCP connections + messaging
transaction.py       # validation logic
block.py             # block creation + hashing
blockchain.py        # chain + state
mempool.py           # transaction pool
consensus.py         # consensus thread
utils.py             # JSON + hashing helpers
~~~

## Produce PlantUML Class Diagram
~~~
cd ../
pyreverse -o puml -p A2 submission/*.py
~~~
Then Option+D (MacOS) on classes_A2.puml to preview