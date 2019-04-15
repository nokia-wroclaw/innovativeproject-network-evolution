from wrapper import *
from math import floor
from utils import *
from psycopg2.extensions import AsIs



prox = 50
relevance_point = 0.00


def failure_frequency(args, table_alarm, table_software):

    with PSQL_wrapper(args) as psql:
        #table_alarm = "PM_KPI_1_CRITICAL_2018-03-01_2019-02-28_ADJUSTED"
        #table_alarm = "PM_KPI_2_MAJOR_2018-03-01_2019-02-28_ADJUSTED"
        #table_alarm = "PM_KPI_3_MINOR_2018-03-01_2019-02-28_ADJUSTED"
        #table_alarm = "PM_KPI_4_WARNING_2018-03-01_2019-02-28_ADJUSTED"

        #table_software = "CM_MACRO_SW_version_2018-03-01_2019-03-07_ADJUSTED"
        operators = get_operators(psql, table_software)
        #print(operators)
        failures = {}
        soft_life = {}
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

            alarms = {}
            command = "SELECT \"Date\", \"%s\" FROM \"%s\" ORDER BY \"Date\""
            res = psql.exec(command, (AsIs(operators[operator]), AsIs(table_alarm)))

            if res.success is False:
                print('Error:', res.result, sep='\n')
            else:
                for i in range(len(res.result)):
                    alarms[res.result[i][0]] = res.result[i][1]

            for di in range(len(dates)):
                State = dates[di][1]
                sum = 0

                for software in State:
                    sum += software[1]

                soft = {}
                for software in State:
                    soft[software[0]] = software[1]

                for software in soft:
                    if software not in failures:
                        failures[software] = 0
                    if software not in soft_life:
                        soft_life[software] = 1
                    if soft[software]/sum >= relevance_point:
                        soft_life[software] += 1

                if dates[di][0] in alarms:
                    #print(alarms[dates[di][0]])
                    for software in soft:
                        if soft[software]/sum >= relevance_point:
                            failures[software] += alarms[dates[di][0]]/sum

        frequency = {}
        for software in failures:
            frequency[software] = floor(100*30*failures[software]/soft_life[software])
            #print(software, ": ", frequency[software])

        X = []
        Y = []
        for software in frequency:
            X.append(software)
            Y.append(frequency[software])

        return X, Y


#arg = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
#failure_frequency(arg, "PM_KPI_3_MINOR_2018-03-01_2019-02-28_ADJUSTED", "CM_MACRO_SW_version_2018-03-01_2019-03-07_ADJUSTED")
