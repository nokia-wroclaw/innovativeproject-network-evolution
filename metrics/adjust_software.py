# -*- coding: utf-8 -*-

from math import floor
from metrics.utils import *
from psycopg2.extensions import AsIs

# value used for checking if two states are similar, can be modified, for prox = 0 states are considered similar if they are the same, for prox = inf all states are similar.
prox = 50


# create a new modified table from original software table that is easier/better for other algorithms to process
# this algorithm checks for blackouts in received data and adjust the data acordingly when blackout was detected
def adjust_software(psql, table_name):
    # create new copied sql table
    psql.copy_table(table_name, table_name + "_ADJUSTED")
    table_name += "_ADJUSTED"

    # get all operator names
    operators = get_operators(psql, table_name)

    for operator in range(len(operators)):
        # take all software data from sql table
        dates = software_dates(psql, table_name, operators[operator])

        # consider all registered dates
        for di in range(len(dates) - 1):
            # state1 - state of software at day x, state2 - state of software at day after x
            state1 = dates[di][1]
            state2 = dates[di + 1][1]

            sum1 = 0
            sum2 = 0
            for software in state1:
                sum1 += software[1]

            for software in state2:
                sum2 += software[1]

            # dictionary from software name to software amount
            soft1 = {}
            soft2 = {}
            for software in state1:
                soft1[software[0]] = software[1]
                soft2[software[0]] = 0

            for software in state2:
                soft2[software[0]] = software[1]
                if software[0] not in soft1:
                    soft1[software[0]] = 0

            # if software at state2 is considerably lower than the same software at state1, consider having a blackout
            lost = True
            for software in soft1:
                if soft2[software] > soft1[software] + prox:
                    lost = False

            if sum2 < sum1 and lost:
                # check for how long the blackout persists
                for j in range(di + 2, len(dates) - 1):
                    state3 = dates[j][1]
                    sum3 = 0
                    for software in state3:
                        sum3 += software[1]

                    soft3 = {}
                    for software in soft1:
                        soft3[software] = 0
                    for software in soft2:
                        soft3[software] = 0

                    for software in state3:
                        soft3[software[0]] = software[1]
                        if software[0] not in soft1:
                            soft1[software[0]] = 0

                    # first check if the blackout ended, if it did then state3 should be similar to state1
                    fits = True
                    for software in soft1:
                        if soft1[software] - soft3[software] > prox:
                            fits = False
                            break

                    # if the blackout did happen and end then adjust all states in blackout period
                    if fits and sum1 - sum3 <= prox:
                        for software in soft3:
                            ag = floor((soft3[software] + soft1[software]) / 2)
                            command = """UPDATE \"%s\"
                                            SET \"Value\" = %s
                                            WHERE \"Operator_name\" = '%s'
                                            AND \"SW_version\" = '%s'
                                            AND \"Date\" >= '%s'
                                            AND \"Date\" < '%s'
                                            """
                            psql.exec(command, (
                                AsIs(table_name), AsIs(ag), AsIs(operators[operator]),AsIs(software),
                                AsIs(dates[di+1][0]), AsIs(dates[j][0])))
                        break

                    # if the blackout didnt end yet and is still being considered then check if state3 is similar to state2, in which blackout was detected
                    broken = False
                    for software in soft2:
                        if abs(soft2[software] - soft3[software]) > prox:
                            broken = True
                            break

                    # if it isn't similar then stop considering it as blackout
                    if broken or abs(sum3 - sum2) > prox:
                        break
