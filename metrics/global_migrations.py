# -*- coding: utf-8 -*-

from math import floor
from metrics.utils import *
from psycopg2.extensions import AsIs
from copy import deepcopy
from datetime import timedelta

# at what point do we say that a software should be counted as taking part in given migration
# max is 1.00, using 0.00 will result in all softwares considered as taking part and very high calculation time, 1.00 will result in almost no softwares being considered as taking part
relevance_point = 0.01

# what is the max delay between registered migration day and alarm day
# we use it because the date stamps we use are actually not very accurate
alarm_delay = timedelta(days=5)

# how much time can pass between steps of the same migration for them to be considered as the same migration
# GUI might break if different delay will be used
migration_delay = 1000


# in this algorithm we try to find migrations in software data for all operators and calculate statistics for them
def global_migrations(psql, table_critical, table_major, table_minor, table_warnings, table_software, fd_softwares, td_softwares, xd_softwares):

    # we use all alarms table for this algorithm
    table_alarm = [table_critical, table_major, table_minor, table_warnings]

    # we use only one operator for this version of algorithm
    operators = get_operators(psql, table_software)

    global_migration = {}
    for operator in range(len(operators)):
        # take all software data from sql table
        dates = software_dates(psql, table_software, operators[operator])

        # take all alarms data from 4 sql tables
        alarms = [{}, {}, {}, {}]
        for i in range(len(table_alarm)):
            command = "SELECT \"Date\", \"%s\" FROM \"%s\" ORDER BY \"Date\""
            res = psql.exec(command, (AsIs(operators[operator]), AsIs(table_alarm[i])))

            if res.success is False:
                print('Error:', res.result, sep='\n')
            else:
                # alarms[date] = amount_of_alarms_in_that_day
                for j in range(len(res.result)):
                    alarms[i][res.result[j][0]] = res.result[j][1]

        # initializing dictionaries
        migrations = {}
        migrations_size = {}
        assigned_alarms = [{}, {}, {}, {}]
        last_alarm = dates[0][0]

        # consider all registered dates
        for di in range(len(dates) - 1):
            # state1 - state of software at day x, state2 - state of software at day after x
            state1 = dates[di][1]
            state2 = dates[di + 1][1]

            # dictionary from software name to software amount
            soft1 = {}
            soft2 = {}
            # average amount of installed software in state1 and state2
            sum_avg = 0

            for software in state1:
                soft1[software[0]] = software[1]
                soft2[software[0]] = 0
                sum_avg += software[1] / 2

            for software in state2:
                soft2[software[0]] = software[1]
                sum_avg += software[1] / 2
                if software[0] not in soft1:
                    soft1[software[0]] = 0

            # dictionary from software name to software amount
            # in minus we store all software which amount decreased from state1 to state2, plus is the rest
            minus = {}
            plus = {}
            for software in soft1:
                if (soft2[software] - soft1[software]) / sum_avg >= relevance_point:
                    plus[software] = soft2[software] - soft1[software]

                if (soft2[software] - soft1[software]) / sum_avg <= -relevance_point:
                    minus[software] = soft2[software] - soft1[software]

            # this function is used to check the optimal pairing of software from minus to plus
            # we prefer not having multiple pairings including the same software, but it is sometimes still optimal
            def check(index, test_plus, test_minus, scale_plus, scale_minus, result):
                # the lower the mn value, the closer the final pairings are to perfect balance
                mn = 1000000000000000000000000000000

                if index >= len(test_plus):
                    mn = 0

                    # the final mn value is sum of imbalances in remaining unmatched software
                    for soft in test_minus:
                        mn += pow(abs(test_minus[soft]), max(2, scale_minus[soft]))
                    for soft in test_plus:
                        mn += pow(abs(test_plus[soft]), max(2, scale_plus[soft]))

                    for pair in result:
                        mark1 = 0
                        mark2 = 0
                        if pair[0].upper() in fd_softwares:
                            mark1 = 1
                        if pair[0].upper() in td_softwares:
                            mark1 = 2

                        if pair[1].upper() in fd_softwares:
                            mark2 = 1
                        if pair[1].upper() in td_softwares:
                            mark2 = 2

                        # we discard all pairings of software from different software groups
                        if (mark1 == 1 and mark2 == 2) or (mark1 == 2 and mark2 == 1):
                            mn = 1000000000000000000000000000000

                    return mn, result

                # we check the current name of considered software in plus group
                name = 0
                for tst in test_plus:
                    if name == index:
                        name = tst
                        break
                    name += 1

                base_result = deepcopy(result)
                # for currently considered software in plus we pair it with each available software in minus and go deeper in recursion

                for soft in test_minus:
                    # if the considered software in minus group is still not completely assigned
                    if test_minus[soft] < 0:

                        # if there is more unassigned software in considered plus software from considered minus software
                        if -test_minus[soft] <= test_plus[name]:
                            rem = test_minus[soft]
                            rem2 = test_plus[name]
                            # we assign all of the minus software to the plus software
                            test_plus[name] += test_minus[soft]
                            test_minus[soft] = 0
                            # we punish picking the same software multiple times
                            scale_plus[name] += 0.5
                            scale_minus[soft] += 0.5

                            test_result = deepcopy(base_result)
                            test_result.append((soft, name))
                            # consider the same plus software again, get the result from it
                            ans, test_result = check(index, test_plus, test_minus, scale_plus, scale_minus, test_result)

                            # if the result was better than our current best result, replace it
                            if ans < mn:
                                mn = ans
                                result = deepcopy(test_result)

                            # rollback our values from recursion
                            scale_plus[name] -= 0.5
                            scale_minus[soft] -= 0.5
                            test_minus[soft] = rem
                            test_plus[name] = rem2

                        else:
                            rem = test_plus[name]
                            rem2 = test_minus[soft]
                            # we assign fraction of the minus software to the plus software
                            test_minus[soft] += test_plus[name]
                            test_plus[name] = 0
                            # we punish picking the same software multiple times
                            scale_plus[name] += 0.5
                            scale_minus[soft] += 0.5

                            test_result = deepcopy(base_result)
                            test_result.append((soft, name))
                            # consider the next plus software, get the result from it
                            ans, test_result = check(index + 1, test_plus, test_minus, scale_plus, scale_minus
                                                     , test_result)

                            # if the result was better than our current best result, replace it
                            if ans < mn:
                                mn = ans
                                result = deepcopy(test_result)

                            # rollback our values from recursion
                            scale_plus[name] -= 0.5
                            scale_minus[soft] -= 0.5
                            test_plus[name] = rem
                            test_minus[soft] = rem2

                # consider simply not assigning anything to currently considered plus software
                test_result = deepcopy(base_result)
                # consider the next plus software, get the result from it
                ans, test_result = check(index + 1, test_plus, test_minus, scale_plus, scale_minus, test_result)

                # if the result was better than our current best result, replace it
                if ans < mn:
                    mn = ans
                    result = deepcopy(test_result)

                return mn, result

            answer = []
            # if there are any pairs to match at all
            if len(plus) > 0 and len(minus) > 0:

                # setup of scalars for punishing using the same software multiple times in pairings
                scale_p = {}
                scale_m = {}
                for software in soft1:
                    scale_p[software] = 1.5
                    scale_m[software] = 1.5

                # launch the check function
                _, answer = check(0, plus.copy(), minus.copy(), scale_p, scale_m, answer)

                # if the best result was when we paired software from different software groups, discard the migration
                wrong = False
                for pair in answer:
                    mark1 = 0
                    mark2 = 0
                    if pair[0].upper() in fd_softwares:
                        mark1 = 1
                    if pair[0].upper() in td_softwares:
                        mark1 = 2

                    if pair[1].upper() in fd_softwares:
                        mark2 = 1
                    if pair[1].upper() in td_softwares:
                        mark2 = 2

                    if (mark1 == 1 and mark2 == 2) or (mark1 == 2 and mark2 == 1):
                        wrong = True

                # continue = discard migration
                if wrong:
                    continue

                total = 0
                for pl in plus:
                    total += plus[pl]
                for mn in minus:
                    total += abs(minus[mn])

                # we put the registered migration day in the list of days in which the same migration occurred
                for migration in answer:
                    if migration in migrations:
                        migrations[migration] = migrations[migration] + (dates[di][0],)
                    else:
                        migrations[migration] = (dates[di][0],)
                        migrations_size[migration] = {}
                    # we save the size of occurred migrations
                    migrations_size[migration][dates[di][0]] = floor((abs(minus[migration[0]]) + plus[migration[1]]) / 2)

                alarm_day = False
                alarm_score = 0
                # we pair the migration day to the day with most alarms in allowed span by alarm_delay
                for day in range(-1, min(dates[di][0] - last_alarm - timedelta(days=1), alarm_delay).days):
                    checked_day = dates[di][0] - timedelta(days=day)
                    if checked_day in alarms[0]:
                        alarm_day = checked_day
                        last_alarm = checked_day
                        # each alarm counts differently, based on its severity.
                        new_score = 3 * alarms[0][checked_day] + 2 * alarms[1][checked_day] + 1 * alarms[2][checked_day] + 0.5 * alarms[3][checked_day]
                        if new_score > alarm_score:
                            alarm_score = new_score
                            alarm_day = checked_day
                            last_alarm = checked_day

                # if we found a day in allowed span that had any alarms
                if alarm_day:
                    # for count how many of each alarms the migrations had (each pair of software counts separately)
                    for q in range(len(assigned_alarms)):
                        for migration in answer:
                            if migration not in assigned_alarms[q]:
                                assigned_alarms[q][migration] = {}
                            assigned_alarms[q][migration][dates[di][0]]=(floor((alarms[q][alarm_day] / total) * (abs(minus[migration[0]]) + plus[migration[1]])))

        migration_dates = {}

        # we separate migrations based on allowed delay between next migration of the same software (migration_delay)
        for migration in migrations:
            for date in migrations[migration]:
                if migration not in migration_dates:
                    migration_dates[migration] = [(date, date + timedelta(days=1))]
                else:
                    if (date - migration_dates[migration][-1][1]).days <= migration_delay:
                        migration_dates[migration][-1] = (migration_dates[migration][-1][0], date + timedelta(days=1))
                    else:
                        migration_dates[migration].append((date, date + timedelta(days=1)))

        # for all registered pairs of software migrations
        for migration in migration_dates:

            # setup of migration in global migrations, which is dictionary with all migrations summed up
            if migration not in global_migration:
                global_migration[migration] = {}
                global_migration[migration]["count"] = 0
                global_migration[migration]["operators"] = []
                global_migration[migration]["duration"] = 0
                global_migration[migration]["size"] = 0
                global_migration[migration]["critical"] = 0
                global_migration[migration]["major"] = 0
                global_migration[migration]["minor"] = 0
                global_migration[migration]["warnings"] = 0

            global_migration[migration]["count"] += 1
            global_migration[migration]["operators"].append(operators[operator])

            # for delay = 1000 there should be only one date
            for date in range(len(migration_dates[migration])):
                size = 0

                start = migration_dates[migration][date][0]
                end = migration_dates[migration][date][1]
                total = []
                for i in range(len(assigned_alarms)):
                    total.append(0)

                # we look at at each day from start to end of chain of migrations and see if migration occurred that day
                for day in range((end - start).days+1):
                    if start + timedelta(days=day) in migrations_size[migration]:
                        size += migrations_size[migration][start + timedelta(days=day)]

                    for q in range(len(assigned_alarms)):
                        if migration in assigned_alarms[q] and start + timedelta(days=day) in assigned_alarms[q][migration]:
                            total[q] += assigned_alarms[q][migration][start + timedelta(days=day)]

                # add migration duration
                global_migration[migration]["duration"] += (end - start).days
                # add migration size
                global_migration[migration]["size"] += size

                # add migration alarms
                for i in range(len(total)):
                    if i == 0:
                        global_migration[migration]["critical"] += total[i]
                    if i == 1:
                        global_migration[migration]["major"] += total[i]
                    if i == 2:
                        global_migration[migration]["minor"] += total[i]
                    if i == 3:
                        global_migration[migration]["warnings"] += total[i]

    # round migration values and calculate total alarms
    for migration in global_migration:
        cnt = global_migration[migration]["count"]
        global_migration[migration]["duration"] = floor(global_migration[migration]["duration"] / cnt)
        global_migration[migration]["size"] = floor(global_migration[migration]["size"]/cnt)
        global_migration[migration]["critical"] = floor(global_migration[migration]["critical"] / cnt)
        global_migration[migration]["major"] = floor(global_migration[migration]["major"] / cnt)
        global_migration[migration]["minor"] = floor(global_migration[migration]["minor"]/cnt)
        global_migration[migration]["warnings"] = floor(global_migration[migration]["warnings"] / cnt)
        global_migration[migration]['total_alarms'] = global_migration[migration]["critical"] \
                                                    + global_migration[migration]["major"] \
                                                    + global_migration[migration]["minor"] \
                                                    + global_migration[migration]["warnings"]

    return global_migration
