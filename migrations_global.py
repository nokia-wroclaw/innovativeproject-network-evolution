from wrapper import *
from math import floor
from utils import *
from psycopg2.extensions import AsIs
from copy import deepcopy
from datetime import timedelta

prox = 50
alarm_delay = timedelta(days=5)
migration_delay = 1000


def global_migrations(args, table_critical, table_major, table_minor, table_software):
    with PSQL_wrapper(args) as psql:
        table_alarm = []
        table_alarm.append(table_critical)
        table_alarm.append(table_major)
        table_alarm.append(table_minor)
        #table_alarm.append("PM_KPI_1_CRITICAL_2018-03-01_2019-02-28_ADJUSTED")
        #table_alarm.append("PM_KPI_2_MAJOR_2018-03-01_2019-02-28_ADJUSTED")
        #table_alarm.append("PM_KPI_3_MINOR_2018-03-01_2019-02-28_ADJUSTED")
        ##table_alarm.append("PM_KPI_4_WARNING_2018-03-01_2019-02-28_ADJUSTED")

        #table_software = "CM_MACRO_SW_version_2018-03-01_2019-03-07_ADJUSTED"
        operators = get_operators(psql, table_software)
        #print(operators)

        global_migration = {}
        for operator in range(len(operators)):
            dates = []
            command = """SELECT DISTINCT \"Date\", \"SW_version\", \"Value\" FROM \"%s\"
                                        WHERE \"Operator_name\" = '%s'
                                        ORDER BY \"Date\""""
            res = psql.exec(command, (AsIs(table_software), AsIs(operators[operator])))

            if res.success is False:
                print('Error:', res.result, sep='\n')

            else:
                dates.append([res.result[0][0], [[res.result[0][1], res.result[0][2]]]])
                di = 0
                for i in range(1, len(res.result)):
                    if res.result[i][0] == dates[di][0]:
                        dates[di][1].append([res.result[i][1], res.result[i][2]])
                    else:
                        di += 1
                        dates.append([res.result[i][0], [[res.result[i][1], res.result[i][2]]]])

            alarms = [{}, {}, {}]
            for i in range(len(table_alarm)):
                command = "SELECT \"Date\", \"%s\" FROM \"%s\" ORDER BY \"Date\""
                res = psql.exec(command, (AsIs(operators[operator]), AsIs(table_alarm[i])))

                if res.success is False:
                    print('Error:', res.result, sep='\n')
                else:
                    for j in range(len(res.result)):
                        alarms[i][res.result[j][0]] = res.result[j][1]

            migrations = {}
            migrations_size = {}
            assigned_alarms = [{}, {}, {}]
            last_alarm = dates[0][0]

            for di in range(len(dates) - 1):
                State1 = dates[di][1]
                State2 = dates[di + 1][1]

                soft1 = {}
                soft2 = {}
                for software in State1:
                    soft1[software[0]] = software[1]
                    soft2[software[0]] = 0

                for software in State2:
                    soft2[software[0]] = software[1]
                    if software[0] not in soft1:
                        soft1[software[0]] = 0

                minus = {}
                plus = {}
                for software in soft1:
                    if soft2[software] - soft1[software] >= prox:
                        plus[software] = soft2[software] - soft1[software]

                    if soft2[software] - soft1[software] <= -prox:
                        minus[software] = soft2[software] - soft1[software]


                def check(index, test_plus, test_minus, scale_plus, scale_minus, result):
                    mn = 1000000000000000000000000000000

                    if index >= len(test_plus):
                        mn = 0
                        for soft in test_minus:
                            #print(soft, test_minus[soft])
                            mn += pow(abs(test_minus[soft]), max(2, scale_minus[soft]))
                        for soft in test_plus:
                            #print(soft, test_plus[soft])
                            mn += pow(abs(test_plus[soft]), max(2, scale_plus[soft]))
                        return mn, result

                    name = 0
                    for tst in test_plus:
                        if name == index:
                            name = tst
                            break
                        name += 1

                    base_result = deepcopy(result)
                    for soft in test_minus:
                        if test_minus[soft] < 0:

                            if -test_minus[soft] <= test_plus[name]:
                                rem = test_minus[soft]
                                rem2 = test_plus[name]
                                test_plus[name] += test_minus[soft]
                                test_minus[soft] = 0
                                scale_plus[name] += 0.5
                                scale_minus[soft] += 0.5

                                test_result = deepcopy(base_result)
                                test_result.append((soft, name))
                                if test_plus[name] <= 0.0 * plus[name]:
                                    test_plus[name] = 0
                                    ans, test_result = check(index + 1, test_plus, test_minus, scale_plus, scale_minus
                                                             , test_result)
                                else:
                                    ans, test_result = check(index, test_plus, test_minus, scale_plus, scale_minus
                                                             , test_result)

                                #print(ans, mn, test_result, base_result)
                                if ans < mn:
                                    mn = ans
                                    result = deepcopy(test_result)

                                scale_plus[name] -= 0.5
                                scale_minus[soft] -= 0.5
                                test_minus[soft] = rem
                                test_plus[name] = rem2

                            else:
                                rem = test_plus[name]
                                rem2 = test_minus[soft]
                                test_minus[soft] += test_plus[name]
                                test_plus[name] = 0
                                if test_minus[soft] >= 0.0 * minus[soft]:
                                    test_minus[soft] = 0
                                scale_plus[name] += 0.5
                                scale_minus[soft] += 0.5

                                test_result = deepcopy(base_result)
                                test_result.append((soft, name))
                                ans, test_result = check(index + 1, test_plus, test_minus, scale_plus, scale_minus
                                                         , test_result)

                                #print(ans, mn, test_result, base_result)
                                if ans < mn:
                                    mn = ans
                                    result = deepcopy(test_result)

                                scale_plus[name] -= 0.5
                                scale_minus[soft] -= 0.5
                                test_plus[name] = rem
                                test_minus[soft] = rem2

                    test_result = deepcopy(base_result)
                    ans, test_result = check(index + 1, test_plus, test_minus, scale_plus, scale_minus, test_result)
                    if ans < mn:
                        mn = ans
                        result = deepcopy(test_result)

                    return mn, result


                answer = []
                if len(plus) > 0 and len(minus) > 0:

                    scale_p = {}
                    scale_m = {}
                    for software in soft1:
                        scale_p[software] = 1.5
                        scale_m[software] = 1.5

                    # for software in plus:
                    #print(plus[software])
                    # for software in minus:
                    #print(minus[software])
                    _, answer = check(0, plus.copy(), minus.copy(), scale_p, scale_m, answer)

                    total = 0
                    for pl in plus:
                        total += plus[pl]
                        #print(pl, plus[pl])
                    for mn in minus:
                        total += abs(minus[mn])
                        #print(mn, minus[mn])
                    #print(dates[di][0], answer)

                    for migration in answer:
                        if migration in migrations:
                            migrations[migration] = migrations[migration] + (dates[di][0],)
                        else:
                            migrations[migration] = (dates[di][0],)
                            migrations_size[migration] = {}
                        migrations_size[migration][dates[di][0]] = floor((abs(minus[migration[0]]) + plus[migration[1]]) / 2)

                    alarm_day = False
                    alarm_score = 0
                    #print(min(dates[di][0] - last_alarm - timedelta(days=1), alarm_delay).days)
                    for day in range(-1, min(dates[di][0] - last_alarm - timedelta(days=1), alarm_delay).days):
                        #print(dates[di][0] - timedelta(days=day))
                        checked_day = dates[di][0] - timedelta(days=day)
                        if checked_day in alarms[0]:
                            alarm_day = checked_day
                            last_alarm = checked_day
                            new_score = 3 * alarms[0][checked_day] + 2 * alarms[1][checked_day] + 1 * alarms[2][checked_day]
                            if new_score > alarm_score:
                                alarm_score = new_score
                                alarm_day = checked_day
                                last_alarm = checked_day

                    ##print(alarm_day)
                    if alarm_day != False:
                        for q in range(len(assigned_alarms)):
                            for migration in answer:
                                if migration not in assigned_alarms[q]:
                                    assigned_alarms[q][migration] = {}
                                assigned_alarms[q][migration][dates[di][0]]=(floor((alarms[q][alarm_day] / total) * (abs(minus[migration[0]]) + plus[migration[1]])))
                                #print(migration, alarm_day,
                                #      alarms[q][alarm_day], total, floor(
                                #        (alarms[q][alarm_day] / total) * (
                                #                    abs(minus[migration[0]]) + plus[migration[1]])))

            migration_dates = {}

            for migration in migrations:
                for date in migrations[migration]:
                    if migration not in migration_dates:
                        migration_dates[migration] = [(date, date + timedelta(days=1))]
                    else:
                        if (date - migration_dates[migration][-1][1]).days <= migration_delay:
                            migration_dates[migration][-1] = (migration_dates[migration][-1][0], date + timedelta(days=1))
                        else:
                            migration_dates[migration].append((date, date + timedelta(days=1)))

            #print("\nFORMATED MIGRATIONS:")
            for migration in migration_dates:

                if migration not in global_migration:
                    global_migration[migration] = {}
                    global_migration[migration]["count"] = 0
                    global_migration[migration]["duration"] = 0
                    global_migration[migration]["size"] = 0
                    global_migration[migration]["critical"] = 0
                    global_migration[migration]["major"] = 0
                    global_migration[migration]["minor"] = 0

                global_migration[migration]["count"] += 1

                #print()
                #print(migration, ": ")

                for date in range(len(migration_dates[migration])):
                    size = 0

                    start = migration_dates[migration][date][0]
                    end = migration_dates[migration][date][1]
                    total = []
                    for i in range(len(assigned_alarms)):
                        total.append(0)

                    for day in range((end - start).days+1):

                        if start + timedelta(days=day) in migrations_size[migration]:
                            size += migrations_size[migration][start + timedelta(days=day)]

                        for q in range(len(assigned_alarms)):
                            if migration in assigned_alarms[q] and start + timedelta(days=day) in assigned_alarms[q][migration]:
                                total[q] += assigned_alarms[q][migration][start + timedelta(days=day)]

                    #print(start, "->", end)

                    #if (end-start).days <= 1:
                        #print("DURATION:", (end-start).days, "day")
                    #else:
                        #print("DURATION:", (end - start).days, "days")

                    #print("SIZE:", size)

                    global_migration[migration]["duration"] += (end - start).days
                    global_migration[migration]["size"] += size

                    for i in range(len(total)):
                        if i == 0:
                            #print("CRITICAL:", total[i])
                            global_migration[migration]["critical"] += total[i]
                        if i == 1:
                            #print("MAJOR:", total[i])
                            global_migration[migration]["major"] += total[i]
                        if i == 2:
                            #print("MINOR:", total[i])
                            global_migration[migration]["minor"] += total[i]

                    #print()

        #print(global_migration)
        for migration in global_migration:
            #print()
            #print(migration, ": ")

            cnt = global_migration[migration]["count"]
            #print("COUNT: ", cnt)

            global_migration[migration]["duration"] = floor(global_migration[migration]["duration"] / cnt)
            #if floor(global_migration[migration]["duration"]/cnt) <= 1:
                #print("AVG DURATION:", global_migration[migration]["duration"], "day")
            #else:
                #print("AVG DURATION:", global_migration[migration]["duration"], "days")

            global_migration[migration]["size"] = floor(global_migration[migration]["size"]/cnt)
            #print("AVG SIZE:", global_migration[migration]["size"])

            global_migration[migration]["critical"] = floor(global_migration[migration]["critical"] / cnt)
            #print("AVG CRITICAL:", global_migration[migration]["critical"])

            global_migration[migration]["major"] = floor(global_migration[migration]["major"] / cnt)
            #print("AVG MAJOR:",  global_migration[migration]["major"])

            global_migration[migration]["minor"] = floor(global_migration[migration]["minor"]/cnt)
            #print("AVG MINOR:",  global_migration[migration]["minor"])

        return global_migration


#arg = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
#global_migrations(arg, "PM_KPI_1_CRITICAL_2018-03-01_2019-02-28_ADJUSTED", "PM_KPI_2_MAJOR_2018-03-01_2019-02-28_ADJUSTED", "PM_KPI_3_MINOR_2018-03-01_2019-02-28_ADJUSTED", "CM_MACRO_SW_version_2018-03-01_2019-03-07_ADJUSTED")