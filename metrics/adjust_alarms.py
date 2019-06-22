# -*- coding: utf-8 -*-

from psycopg2.extensions import AsIs


# create a new modified table from original alarms table that is easier/better for other algorithms to process
# this algorithm turns nulls to 0 in value field in the table
def adjust_alarms(psql, table_name):
    # create new copied sql table
    psql.copy_table(table_name, table_name + "_ADJUSTED")
    table_name += "_ADJUSTED"

    # get all operator names
    operators = psql.get_column_names(table_name)[3:]

    for operator in range(len(operators)):
        # instead of having blank spots in value field set 0
        command = """
                    UPDATE \"%s\"
                    SET \"%s\" = 0
                    WHERE \"%s\" is NULL
                  """
        psql.exec(command, (AsIs(table_name), AsIs(operators[operator]), AsIs(operators[operator])))
