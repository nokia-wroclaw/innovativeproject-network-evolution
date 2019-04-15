from wrapper import *
from math import floor
from utils import *
from psycopg2.extensions import AsIs

prox = 50


def adjust_software(args, table_name):
    with PSQL_wrapper(args) as psql:
        res = psql.copy_table(table_name, table_name + "_ADJUSTED")
        table_name += "_ADJUSTED"

        operators = get_operators(psql, table_name)
        #print(operators)
        for operator in range(len(operators)):
            dates = []
            command = """SELECT DISTINCT \"Date\", \"SW_version\", \"Value\" FROM \"%s\"
                                WHERE \"Operator_name\" = '%s'
                                ORDER BY \"Date\""""
            res = psql.exec(command, (AsIs(table_name), AsIs(operators[operator])))

            if res.success is False:
                print('Error:', res.result, sep='\n')

            else:
                dates.append([res.result[0][0], [[res.result[0][1], res.result[0][2]]]])
                di = 0
                for i in range(1,len(res.result)):
                    if res.result[i][0] == dates[di][0]:
                        dates[di][1].append([res.result[i][1],res.result[i][2]])
                    else:
                        di += 1
                        dates.append([res.result[i][0], [[res.result[i][1], res.result[i][2]]]])

            for di in range(len(dates) - 1):
                State1 = dates[di][1]
                State2 = dates[di + 1][1]

                sum1 = 0
                sum2 = 0
                for software in State1:
                    sum1 += software[1]

                for software in State2:
                    sum2 += software[1]

                soft1 = {}
                soft2 = {}
                for software in State1:
                    soft1[software[0]] = software[1]
                    soft2[software[0]] = 0

                for software in State2:
                    soft2[software[0]] = software[1]
                    if software[0] not in soft1:
                        soft1[software[0]] = 0

                lost = True
                for software in soft1:
                    if soft2[software] > soft1[software] + prox:
                        lost = False

                if sum2 < sum1 and lost:
                    for j in range(di + 2, len(dates) - 1):
                        State3 = dates[j][1]
                        sum3 = 0
                        for software in State3:
                            sum3 += software[1]

                        soft3 = {}
                        for software in soft1:
                            soft3[software] = 0
                        for software in soft2:
                            soft3[software] = 0

                        for software in State3:
                            soft3[software[0]] = software[1]
                            if software[0] not in soft1:
                                soft1[software[0]] = 0

                        fits = True
                        for software in soft1:
                            if soft1[software] - soft3[software] > prox:
                                fits = False
                                break

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
                                res = psql.exec(command, (
                                    AsIs(table_name), AsIs(ag), AsIs(operators[operator]),AsIs(software),
                                    AsIs(dates[di+1][0]), AsIs(dates[j][0])))
                                #print(res)
                                #print(ag, operators[operator], dates[di+1][0], dates[j][0], software)
                            break

                        broken = False
                        for software in soft2:
                            if abs(soft2[software] - soft3[software]) > prox:
                                broken = True
                                break

                        if broken or abs(sum3 - sum2) > prox:
                            break


#arg = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
#adjust_software(arg, "CM_MACRO_SW_version_2018-03-01_2019-03-07")
