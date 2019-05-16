# innovativeproject-network-evolution


A helper tool that makes network evolution analysis a breeze

- [DEPENDENCIES](#dependencies)
- [FEATURES](#features)
- [METRICS](#metrics)
- [ADDITIONAL INFO](#additional-info)

## DEPENDENCIES
You'll need Python 3.6 or newer. For now the only dependency is the `psycopg2` library, which can be installed via pip:  
```
$ pip3 install psycopg2
```

## FEATURES
- data adjustment, in case the network statistics are incomplete or too irregular to process
- some metrics to better understand the underlying data
- a graphical interface (WIP)

## METRICS
### failure frequency
![GitHub Logo](/screenshots/failure_frequency.png)
How many failures / alarms are expected per month - a value of 30 for 100 machines means that there were 30 malfunctions over the span of one month

### ???
more to come

## ADDITIONAL INFO
TBA
