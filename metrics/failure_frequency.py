# -*- coding: utf-8 -*-

from math import floor, ceil
from metrics.utils import *
from psycopg2.extensions import AsIs

# at what point do we say that a software should be counted as taking part in alarms that day
# max is 1.00, anything higher than 0.00 will result in lower alarmity rate for softwares that are used in small numbers
relevance_point = 0.00


# in this algorithm we calculate for each software how many alarms it statistically generates per day.
# the final results (numbers) say how many alarms 100 machines with that software would generate in 30 days.
def failure_frequency(psql, table_alarm, table_software, fd_softwares, td_softwares, xd_softwares):
    # get all operator names
    operators = get_operators(psql, table_software)

    # initializing dictionaries
    failures = {}
    soft_life = {}
    soft_operators = {}

    for operator in range(len(operators)):
        # take all software data from sql table
        dates = software_dates(psql, table_software, operators[operator])

        # take all alarms data from sql table
        alarms = {}
        command = "SELECT \"Date\", \"%s\" FROM \"%s\" ORDER BY \"Date\""
        res = psql.exec(command, (AsIs(operators[operator]), AsIs(table_alarm)))

        if res.success is False:
            print('Error:', res.result, sep='\n')
        else:
            # alarms[date] = amount_of_alarms_in_that_day
            for i in range(len(res.result)):
                alarms[res.result[i][0]] = res.result[i][1]

        soft_encountered = {}
        for di in range(len(dates)):
            # state - state of all software at day x
            state = dates[di][1]
            sum = 0

            for software in state:
                sum += software[1]

            # dictionary from software name to software amount
            soft = {}
            for software in state:
                soft[software[0]] = software[1]

            for software in soft:
                # soft_life counts in how many days total a software was encountered
                if software not in failures:
                    failures[software] = 0
                if software not in soft_life:
                    soft_life[software] = 1
                if soft[software]/sum >= relevance_point:
                    soft_life[software] += 1

                # soft_operators counts by how many operators was a software used
                if software not in soft_encountered:
                    soft_encountered[software] = 1
                    if software not in soft_operators:
                        soft_operators[software] = 0
                    soft_operators[software] += 1

            # we assume that each present software was equally responsible for alarms that day (we lack information in this regard)
            if dates[di][0] in alarms:
                for software in soft:
                    if soft[software]/sum >= relevance_point:
                        failures[software] += alarms[dates[di][0]]/sum

    # frequency is total amount of failures per machine with given software divided by total amount of days in which they were used multipled by 100(machines)*30(days).
    frequency = {}
    for software in failures:
        frequency[software] = floor(100*30*failures[software]/soft_life[software])

    # ln < fl < tl < rest
    # function used for ordering software names
    def name_hash(x):
        a = x.upper()
        val = 100000
        if a in fd_softwares:
            val = fd_softwares.index(a)
        if a in td_softwares:
            val = 1000 + td_softwares.index(a)
        if a in xd_softwares:
            val = 2000 + xd_softwares.index(a)
        return val

    soft_tl = []
    soft_fl = []
    soft_rest = []
    # soft_rest is every software which name was not recognized at all
    for software in frequency:
        if software.upper() in fd_softwares:
            soft_fl.append(software)
        if software.upper() in td_softwares:
            soft_tl.append(software)
        if software.upper() in xd_softwares:
            soft_fl.append(software)
            soft_tl.append(software)
        if software.upper() not in fd_softwares and software.upper() not in td_softwares and software.upper() not in xd_softwares:
            soft_rest.append(software)

    # at the end we add the unknown software to both main groups
    soft_tl = sorted(soft_tl, key=name_hash)
    soft_fl = sorted(soft_fl, key=name_hash)
    soft_rest = sorted(soft_rest)
    soft_tl = soft_tl + soft_rest
    soft_fl = soft_fl + soft_rest

    # X is software names, Y is software frequency, Z is average software life duration
    tl_X = []
    tl_Y = []
    tl_Z = []

    fl_X = []
    fl_Y = []
    fl_Z = []

    # we also calculate statistics for frequency data
    tl_stats = {"most_alarms": (0, 0), "least_alarms": (999999, 0), "average_alarms": 0, "longest_lifespan": (0, 0),
                "shortest_lifespan": (999999, 0), "average_lifespan": 0}
    fl_stats = {"most_alarms": (0, 0), "least_alarms": (999999, 0), "average_alarms": 0, "longest_lifespan": (0, 0),
                "shortest_lifespan": (999999, 0), "average_lifespan": 0}

    avg_life = {}
    for software in soft_tl:
        tl_X.append(software)
        tl_Y.append(frequency[software])

        # the statistics calculation is pretty straightforward
        if frequency[software] > tl_stats["most_alarms"][0]:
            tl_stats["most_alarms"] = (frequency[software], software)
        if frequency[software] < tl_stats["least_alarms"][0]:
            tl_stats["least_alarms"] = (frequency[software], software)
        tl_stats["average_alarms"] += frequency[software]

        # we calculate average software life duration as total amount of days in which they were used divided by amount of operators which used them.
        avg_life[software] = soft_life[software] / soft_operators[software]
        tl_Z.append(avg_life[software])

        if avg_life[software] > tl_stats["longest_lifespan"][0]:
            tl_stats["longest_lifespan"] = (avg_life[software], software)
        if avg_life[software] < tl_stats["shortest_lifespan"][0]:
            tl_stats["shortest_lifespan"] = (avg_life[software], software)
        tl_stats["average_lifespan"] += avg_life[software]

    # we round statistics for them to look more neat
    tl_stats["average_alarms"] = ceil(tl_stats["average_alarms"]/len(soft_tl))
    tl_stats["average_lifespan"] = ceil(tl_stats["average_lifespan"] / len(soft_tl))
    tl_stats["longest_lifespan"] = tl_stats["longest_lifespan"]
    tl_stats["shortest_lifespan"] = tl_stats["shortest_lifespan"]
    tl_stats["most_alarms"] = tl_stats["most_alarms"]
    tl_stats["least_alarms"] = tl_stats["least_alarms"]

    for software in soft_fl:
        fl_X.append(software)
        fl_Y.append(frequency[software])

        if frequency[software] > fl_stats["most_alarms"][0]:
            fl_stats["most_alarms"] = (frequency[software], software)
        if frequency[software] < fl_stats["least_alarms"][0]:
            fl_stats["least_alarms"] = (frequency[software], software)
        fl_stats["average_alarms"] += frequency[software]

        avg_life[software] = soft_life[software] / soft_operators[software]
        fl_Z.append(avg_life[software])

        if avg_life[software] > fl_stats["longest_lifespan"][0]:
            fl_stats["longest_lifespan"] = (avg_life[software], software)
        if avg_life[software] < fl_stats["shortest_lifespan"][0]:
            fl_stats["shortest_lifespan"] = (avg_life[software], software)
        fl_stats["average_lifespan"] += avg_life[software]

    fl_stats["average_alarms"] = ceil(fl_stats["average_alarms"] / len(soft_fl))
    fl_stats["average_lifespan"] = ceil(fl_stats["average_lifespan"] / len(soft_fl))
    fl_stats["longest_lifespan"] = fl_stats["longest_lifespan"]
    fl_stats["shortest_lifespan"] = fl_stats["shortest_lifespan"]
    fl_stats["most_alarms"] = fl_stats["most_alarms"]
    fl_stats["least_alarms"] = fl_stats["least_alarms"]

    return [fl_X, fl_Y, fl_Z, fl_stats], [tl_X, tl_Y, tl_Z, tl_stats]
