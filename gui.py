from urllib.request import Request, urlopen
from io import BytesIO
from datetime import datetime
from threading import Thread

import PySimpleGUIQt as sg
from PIL import Image

import plotly.plotly as py
import plotly.graph_objs as go
import plotly.io as pio

from utils import *
from wrapper import *
from adjust_alarms import *
from adjust_software import *
from migrations import *
from migrations_global import *
from failure_frequency import *



from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog

# https://pythonspot.com/pyqt5-file-dialog/
# https://stackoverflow.com/questions/38121556/selectedfilters-is-not-a-valid-keyword-argument
class FilePicker(QWidget):
    def __init__(self):
        super().__init__()

    def open(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"Open file", "", "CSV files (*.csv);;All Files (*)", options=options)
        return fileName

def epoch(date):
    return int(date.timestamp() * 1000)


def convert_image(img):
    buf = BytesIO()
    img.save(buf, format="ppm")
    return buf.getvalue()


def update_image_from_bytes(target, b):
    bmp = Image.open(BytesIO(b))
    img_str = convert_image(bmp)
    target.Update(data=img_str)


def update_image_from_url(target, url, api_key):
    req = Request(url, headers={"Authorization": api_key})
    bmp = Image.open(BytesIO(urlopen(req).read()))
    img_str = convert_image(bmp)
    target.Update(data=img_str)


def update_migrations_description(target, d, global_migration):
    s = ''
    if global_migration:
        for m in d:
            s += m[0] + ' -> ' + m[1] + '\n'
            for e in d[m]:
                s += str(e) + ': ' + str(d[m][e]) + '\n'
        s += '\n'
        target.Update(value=s)
    else:
        s = ''
        for op in d.keys():
            s += op + '\n'
            for m in d[op]:
                s += m[0] + ' -> ' + m[1] + '\n'
                for e in d[op][m]:
                    s += str(e) + ': ' + str(d[op][m][e]) + '\n'
            s += '\n'

        target.Update(value=s)


if __name__ == '__main__':
    psql_config = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
    grafana_config = read_config('config.ini', ['host', 'port', 'api_key', 'width', 'height'], section='Grafana')

    tables = []
    operators = []
    with PSQL_wrapper(psql_config) as psql:
        tables = sorted(get_public_tables(psql))

    current_operator = 'Operator: -1'

    ghost = grafana_config['host']
    gport = grafana_config['port']
    width = grafana_config['width']
    height = grafana_config['height']
    api_key = grafana_config['api_key']

    date_format = '%d-%m-%Y'
    dt1 = datetime.today()
    dt2 = datetime(year=dt1.year-1, month=dt1.month, day=dt1.day)

    start = epoch(dt2)
    end = epoch(dt1)

    critical = major = minor = warning = software = tables[0]

    placeholder = convert_image(Image.new('RGB', (int(width), int(height))))

    operators_view_migrations_layout = [
                                         [sg.Image(data=placeholder, key='operators_view_migrations_image')],
                                         [sg.Multiline(default_text='', size=(int(width), 100), disabled=False, key='operators_view_migrations_text')]
                                       ]

    operators_view_alarms_layout = [
                                     [sg.Image(data=placeholder, key='operators_view_alarms_image')]
                                   ]


    operators_view_layout = [
                              [sg.TabGroup([
                                [sg.Tab('Migrations', operators_view_migrations_layout),
                                sg.Tab('Alarms', operators_view_alarms_layout)]])]
                            ]


    sw_view_migrations_layout = [
                                  [sg.Multiline(default_text='', size=(int(width), 500), disabled=False, key='sw_view_migrations_text')]
                                ]
    sw_view_alarms_layout = [
                              [sg.Image(data=placeholder, key='sw_view_alarms_image')]
                            ]

    sw_view_layout = [
                       [sg.TabGroup([
                         [sg.Tab('Migrations', sw_view_migrations_layout),
                          sg.Tab('Alarms', sw_view_alarms_layout)]])]
                     ]

    settings_layout = [
                        [sg.T('Starting date:'),
                         sg.In(dt2.strftime(date_format), key='start_date'),
                         sg.T('End date:'),
                         sg.In(dt1.strftime(date_format), key='end_date'),
                         sg.Button('Apply dates')],
                        [sg.T('')],
                        [sg.T('Critical alarms'),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='critical')
                        ],
                        [sg.T('Major alarms  '),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='major')
                        ],
                        [sg.T('Minor alarms  '),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='minor')
                        ],
                        [sg.T('Warnings        '),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='warning')
                        ],
                        [sg.T('Software table'),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='software')
                        ],
                        [sg.Button('Apply table changes'),
                         sg.Button('Generate graphs')],
                        [sg.T('')],
                        [sg.Button('Populate operators'),
                         sg.Combo(values=['Operator: -1'], size=(150,20), readonly=True, change_submits=True, key='operator_id')],
                        [sg.T('')],
                        [sg.T('Adjust alarms   '),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='alarms_table_adjust'),
                         sg.Button('Adjust alarms')
                        ],
                        [sg.T('Adjust software'),
                         sg.Combo(values=tables, size=(400,20), readonly=True, change_submits=True, key='software_table_adjust'),
                         sg.Button('Adjust software')
                        ],
                        [sg.T('')],
                        [sg.Button('Import CSV')]
                      ]


    """
    [sg.T('Adjust alarms   '),
     sg.In('<empty>', key='alarms_table_adjust', size=(400,20)),
     sg.Button('Choose alarms'),
     sg.Button('Adjust alarms')
    ],
    [sg.T('Adjust software'),
     sg.In('<empty>', key='software_table_adjust', size=(400,20)),
     sg.Button('Choose software'),
     sg.Button('Adjust software')
    ]
    """

    layout = [
               [sg.TabGroup([
                 [sg.Tab('Operators view', operators_view_layout),
                  sg.Tab('SW view', sw_view_layout),
                  sg.Tab('Settings', settings_layout)]])]
             ]

    window = sg.Window('Network evolution', default_element_size=(12,1)).Layout(layout)

    table_combos = ['critical', 'major', 'minor', 'warning', 'software', 'alarms_table_adjust', 'software_table_adjust']

    while True:
        event, values = window.Read()

        # print(event,values)

        if event == None:
            break

        if event in table_combos or event == 'operator_id':
            current_operator = values[event]
            window.FindElement(event).Update(value=values[event])

        if event == 'Apply dates':
            start = epoch(datetime.strptime(values['start_date'], date_format))
            end = epoch(datetime.strptime(values['end_date'], date_format))

        if event == 'Apply table changes':
            critical = values['critical']
            major = values['major']
            minor = values['minor']
            warning = values['warning']
            software = values['software']

        if event == 'Generate graphs':
            url = "http://{0}:{1}/render/d-solo/aos3_X3iz/wykresy?orgId=1&from={2}&to={3}&panelId=2&width={4}&height={5}".format(ghost, gport, start, end, width, height)

            args = (window.FindElement('operators_view_migrations_image'), url, api_key)
            Thread(target=update_image_from_url, args=args).start()

            url = "http://{0}:{1}/render/d-solo/aos3_X3iz/wykresy?orgId=1&from={2}&to={3}&panelId=4&width={4}&height={5}".format(ghost, gport, start, end, width, height)

            args = (window.FindElement('operators_view_alarms_image'), url, api_key)
            Thread(target=update_image_from_url, args=args).start()


            x, y = failure_frequency(psql_config, critical, software)
            critical_alarms = go.Bar(
                x=x,
                y=y,
                name='Critical'
            )

            x, y = failure_frequency(psql_config, major, software)
            major_alarms = go.Bar(
                x=x,
                y=y,
                name='Major'
            )

            x, y = failure_frequency(psql_config, minor, software)
            minor_alarms = go.Bar(
                x=x,
                y=y,
                name='Minor'
            )

            x, y = failure_frequency(psql_config, warning, software)
            warning_alarms = go.Bar(
                x=x,
                y=y,
                name='Warning'
            )

            data = [warning_alarms, minor_alarms, major_alarms, critical_alarms]
            layout = go.Layout(
                barmode='stack'
            )

            fig = go.Figure(data=data, layout=layout)
            b = pio.to_image(fig,format='png')
            target = window.FindElement('sw_view_alarms_image')
            update_image_from_bytes(target, b)

            target = window.FindElement('sw_view_migrations_text')
            migrations = global_migrations(psql_config, critical, major, minor, software)
            update_migrations_description(target, migrations, True)

            target = window.FindElement('operators_view_migrations_text')
            migrations = operator_migrations(psql_config, critical, major, minor, software, current_operator)
            update_migrations_description(target, migrations, False)

        if event == 'Populate operators':
            with PSQL_wrapper(psql_config) as psql:
                operators = sorted(get_operators(psql, software), key=lambda x: int(x.split(' ')[1]))
                window.FindElement('operator_id').Update(values=operators, value=values['operator_id'])

        if event == 'Adjust alarms':
            target = values['alarms_table_adjust']
            adjust_alarms(psql_config, target)
            with PSQL_wrapper(psql_config) as psql:
                tables = get_public_tables(psql)
                for c in table_combos:
                    window.FindElement(c).Update(values=tables, value=values[c])

        if event == 'Adjust software':
            target = values['software_table_adjust']
            adjust_software(psql_config, target)
            with PSQL_wrapper(psql_config) as psql:
                tables = sorted(get_public_tables(psql))
                for c in table_combos:
                    window.FindElement(c).Update(values=tables, value=values[c])

        if event == 'Import CSV':
            filename = FilePicker().open()
            table_name = filename.split('/')[-1].split('.')[0]
            with PSQL_wrapper(psql_config) as psql:
                psql.copy_csv(open(filename, 'r'), table_name, True)
                tables = sorted(get_public_tables(psql))
                for c in table_combos:
                    window.FindElement(c).Update(values=tables, value=values[c])
