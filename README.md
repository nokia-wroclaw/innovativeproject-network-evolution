# innovativeproject-network-evolution


A helper tool that makes network evolution analysis a breeze.

- [DEPENDENCIES](#dependencies)
- [FEATURES](#features)
- [METRICS](#metrics)
- [HOW TO USE](#how-to-use)
- [ADDITIONAL INFO](#additional-info)

## DEPENDENCIES
You'll need Python 3.6 or newer. The libraries below are necessary and can be installed via pip:  
```
$ pip3 install psycopg2
$ pip3 install bokeh
```
You will also need to have PostgreSQL installed on your machine, we tested version 11.3 ourselves but any other recent release should be fine as well.

## FEATURES
- An interactive, fast graphical interface
- Automatic calculation and visualization of all statistics
- Numerous different views on information gathered from input
- Allows you to load any amount of data
- Data adjusting to make up for imperfect input data

## METRICS
### Operators View
![GitHub Logo](/screenshots/operator_view.png)
Allows you to view all gathered data in regard to any chosen operator. The main plot shows how many machines with a specific software the operator had in his network in the chosen interval of time. The standard interval is 1 year.  The plot can be interacted with and any lines can be turned off and on to allow for easier viewing of changes in the amount of specific software installed.

### Migrations
![GitHub Logo](/screenshots/migrations.png)
On the right you can see a table which lists all detected migrations of softwares in the main plot. Migration is a continuous event describing the change of installed software on the used machines in the network. The ‘duration’ statistic is calculated by subtracting the first date when a specific software migration was detected from the last day when the same migration was detected. ‘Alarms’ statistic lists how many alarms were detected which occured in dates close to the dates of migrations. ‘Size’ simply states how many machines were taking part in specific migration. 

You can also view detailed info on detected migrations by choosing tab ‘Details’ in the menu. Additionally you can also view a separate plot showing how many alarms when detected in operator’s network by choosing ‘Alarms’ tab in the menu. 

### Failure Frequency
![GitHub Logo](/screenshots/failure_frequency.png)
The ‘Failure Frequency’ tab found in ‘Software view’ in the menu depicts how many alarms specific softwares cause in relation to each other. The data is calculated based on information gathered from all available operators. It is worth noting that the data is based on both the alarms that occurred during migrations and the alarms that occurred outside of them. The numeric values on bars have specific meaning. They say how many alarms would occur on average during 30 days if you had a network with 100 machines with the specific software installed on them. 

### Software Lifespan
![GitHub Logo](/screenshots/software_lifespan.png)
This bar graph depicts how many days on average were specific softwares used in any network. For the sake of calculations we assumed that a software was used in a network during given day if at least 1% of all machines that day had the specific software installed on them. 

### Software Migrations
![GitHub Logo](/screenshots/software_migrations.png)
This table combines all the data gathered from calculating migrations for all available operators. You can choose to view migrations of any chosen software using the provided interface, allowing for easy data lookup. Most of the values in the table are averages of migrations found in networks. The table also features statistic ‘Number of Operators’, which shows in how many different networks was the given migration found. The list of those specific networks is also available.

## HOW TO USE
TBA

## ADDITIONAL INFO
The project was tested on macOS 10.14.5 Mojave, using Python version: 3.7.3 and PostgreSQL version: 11.3.



