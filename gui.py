import datetime
from itertools import cycle

from bokeh.io import output_file, show, curdoc
from bokeh.models.widgets import RadioButtonGroup, Dropdown, DataTable, DateFormatter, TableColumn, DatePicker, Div, Button, TextInput
from bokeh.models import Panel, Tabs, ColumnDataSource, HoverTool, Legend, LegendItem, LayoutDOM
from bokeh.plotting import figure
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.layouts import row, column
from bokeh.palettes import Colorblind8 as palette
from bokeh.core.properties import value, String

from utils import *
from wrapper import *
from adjust_alarms import *
from adjust_software import *
from migrations import *
from migrations_global import *
from failure_frequency import *


def epoch(date):
    return int(date.timestamp() * 1000)


psql_config = read_config('config.ini', ['host', 'port', 'dbname', 'user', 'password'])
defaults = read_config(
    'config.ini', ['critical', 'major', 'minor', 'warning', 'software'], section='Defaults')

tables = []
with PSQL_wrapper(psql_config) as psql:
    tables = sorted(get_public_tables(psql))


date_format = '%d-%m-%Y'
dt1 = datetime.datetime.today()
dt2 = datetime.datetime(year=dt1.year-2, month=dt1.month, day=dt1.day)

start = epoch(dt2)
end = epoch(dt1)

critical = defaults['critical']
major    = defaults['major']
minor    = defaults['minor']
warning  = defaults['warning']
software = defaults['software']


width = 1500
height = 735


text_style = {'white-space': 'pre',
              'padding-top': '6px',
              'padding-bottom': '7px',
              '-webkit-touch-callout': 'none',
              '-webkit-user-select': 'none',
              '-khtml-user-select': 'none',
              '-moz-user-select': 'none',
              '-ms-user-select': 'none',
              '-o-user-select': 'none',
              'user-select': 'none',
              'pointer-events': 'none'}

operator_selection = Dropdown(label="Operator", button_type="warning", menu=[], width=200)
operator_date_picker_start = DatePicker(max_date=dt1, value=dt2.date())
operator_date_picker_end = DatePicker(max_date=dt1, value=dt1.date())
operator_settings = row(operator_selection,
                        Div(text='   Starting date:', style=text_style),
                        operator_date_picker_start,
                        Div(text='   End date:', style=text_style),
                        operator_date_picker_end)

op_migrations_source = ColumnDataSource(data=dict())
op_migrations_figure = figure(plot_width=width, plot_height=height+136)
op_migrations_figure.sizing_mode = 'scale_both'
op_migrations_hover = HoverTool(tooltips=[('Date', '@date{%F}')], formatters={"date": "datetime"})


op_migrations_columns = [
    TableColumn(field="migration", title="Migration"),
    TableColumn(field="start", title="Start"),
    TableColumn(field="end", title="End"),
    TableColumn(field="duration", title="Duration"),
    TableColumn(field="size", title="Size"),
    TableColumn(field="critical", title="Critical"),
    TableColumn(field="major", title="Major"),
    TableColumn(field="minor", title="Minor"),
    TableColumn(field="warning", title="Warning")
]


op_migrations_details_table_source = ColumnDataSource(data=dict())
op_migrations_details_table = DataTable(source=op_migrations_details_table_source, columns=op_migrations_columns)
op_migrations_details_table.sizing_mode = 'scale_both'
op_migrations_details_column = column(operator_settings, op_migrations_details_table)
op_migrations_details_column.sizing_mode = 'scale_both'


op_migrations_summary_columns = [
    TableColumn(field="a", title="From"),
    TableColumn(field="b", title="To"),
    TableColumn(field="duration", title="Duration"),
    TableColumn(field="total", title="Alarms")
]

op_migrations_summary_source = ColumnDataSource(data=dict())
op_migrations_summary = DataTable(source=op_migrations_details_table_source, columns=op_migrations_summary_columns, width=250, index_position=None, fit_columns=True)
op_migrations_column = column(operator_settings, row(op_migrations_figure, op_migrations_summary))
op_migrations_column.sizing_mode = 'scale_both'

op_migrations_figure_tab = Panel(child=op_migrations_column, title="Graph")
op_migrations_details_tab = Panel(child=op_migrations_details_column, title="Details")

op_migrations_selection = Tabs(tabs=[op_migrations_figure_tab, op_migrations_details_tab], active=0)
op_migrations = Panel(child=op_migrations_selection, title="Migrations")

op_alarms_critical_source = ColumnDataSource(data=dict())
op_alarms_critical_figure = figure(plot_width=width, plot_height=height)
op_alarms_critical_figure.sizing_mode = 'scale_both'
op_alarms_critical_column = column(operator_settings, op_alarms_critical_figure)
op_alarms_critical_column.sizing_mode = 'scale_both'
op_alarms_critical_tab = Panel(child=op_alarms_critical_column, title="Critical")
op_alarms_critical_hover = HoverTool(
    tooltips=[
        ('Date', '@date{%F}'),
        ("Critical", "@critical")],
    formatters={"date": "datetime"}
)

op_alarms_major_source = ColumnDataSource(data=dict())
op_alarms_major_figure = figure(plot_width=width, plot_height=height)
op_alarms_major_figure.sizing_mode = 'scale_both'
op_alarms_major_column = column(operator_settings, op_alarms_major_figure)
op_alarms_major_column.sizing_mode = 'scale_both'
op_alarms_major_tab = Panel(child=op_alarms_major_column, title="Major")
op_alarms_major_hover = HoverTool(
    tooltips=[
        ('Date', '@date{%F}'),
        ("Major", "@major")],
    formatters={"date": "datetime"}
)

op_alarms_minor_source = ColumnDataSource(data=dict())
op_alarms_minor_figure = figure(plot_width=width, plot_height=height)
op_alarms_minor_figure.sizing_mode = 'scale_both'
op_alarms_minor_column = column(operator_settings, op_alarms_minor_figure)
op_alarms_minor_column.sizing_mode = 'scale_both'
op_alarms_minor_tab = Panel(child=op_alarms_minor_column, title="Minor")
op_alarms_minor_hover = HoverTool(
    tooltips=[
        ('Date', '@date{%F}'),
        ("Minor", "@minor")],
    formatters={"date": "datetime"}
)

op_alarms_warning_source = ColumnDataSource(data=dict())
op_alarms_warning_figure = figure(plot_width=width, plot_height=height)
op_alarms_warning_figure.sizing_mode = 'scale_both'
op_alarms_warning_column = column(operator_settings, op_alarms_warning_figure)
op_alarms_warning_column.sizing_mode = 'scale_both'
op_alarms_warning_tab = Panel(child=op_alarms_warning_column, title="Warning")
op_alarms_warning_hover = HoverTool(
    tooltips=[
        ('Date', '@date{%F}'),
        ("Warning", "@warning")],
    formatters={"date": "datetime"}
)

date_formatter = DatetimeTickFormatter(
    seconds="%d %B %Y",
    minutes="%d %B %Y",
    hours="%d %b %Y",
    days="%d %b %Y",
    months="%d %b %Y",
    years="%d %b %Y"
)

op_alarms_critical_figure.xaxis.formatter = date_formatter
op_alarms_major_figure.xaxis.formatter    = date_formatter
op_alarms_minor_figure.xaxis.formatter    = date_formatter
op_alarms_warning_figure.xaxis.formatter  = date_formatter
op_migrations_figure.xaxis.formatter      = date_formatter


alarm_type_selection = Tabs(tabs=[op_alarms_critical_tab, op_alarms_major_tab, op_alarms_minor_tab, op_alarms_warning_tab], active=0)
alarm_type_selection.sizing_mode = 'scale_both'

op_alarms = Panel(child=alarm_type_selection, title="Alarms")


software_mode_radio = RadioButtonGroup(labels=["From", "To"], active=0, width=100)
software_selection = Dropdown(label="Software version", button_type="warning", menu=[], width=200)
software_settings = row(software_selection, software_mode_radio)


software_failure_source = ColumnDataSource(data=dict())
software_failure_figure = figure(plot_width=width, plot_height=height+64)
software_failure_figure.sizing_mode = 'scale_both'
software_failure_column = column(software_failure_figure)
software_failure_column.sizing_mode = 'scale_both'
software_failure_frequency = Panel(child=software_failure_column, title="Failure frequency")
software_alarm_types = ['Critical', 'Major', 'Minor', 'Warning']


software_lifespan_figure = figure(plot_width=width, plot_height=height+64) #+27
software_lifespan_figure.sizing_mode = 'scale_both'
software_lifespan_column = column(software_lifespan_figure)
software_lifespan_column.sizing_mode = 'scale_both'
software_lifespan = Panel(child=software_lifespan_column, title="Lifespan")



software_migrations_columns = [
    TableColumn(field="migration", title="Migration"),
    TableColumn(field="duration", title="Average duration"),
    TableColumn(field="size", title="Average size"),
    TableColumn(field="count", title="Number of operators"),
    TableColumn(field="critical", title="Critical alarm average"),
    TableColumn(field="major", title="Major alarm average"),
    TableColumn(field="minor", title="Minor alarm average"),
    TableColumn(field="warning", title="Warning average")
]


software_migrations_source = ColumnDataSource(data=dict())
software_migrations_table = DataTable(source=software_migrations_source, columns=software_migrations_columns, width=width, height=height)
software_migrations_table.sizing_mode = 'scale_both'
software_migrations_column = column(software_settings, software_migrations_table)
software_migrations_column.sizing_mode = 'scale_both'
software_migrations = Panel(child=software_migrations_column, title="Migrations")


critical_table_selection  = Dropdown(label=critical, button_type="warning", menu=tables, width=500, value=critical)
major_table_selection     = Dropdown(label=major, button_type="warning", menu=tables, width=500, value=major)
minor_table_selection     = Dropdown(label=minor, button_type="warning", menu=tables, width=500, value=minor)
warning_table_selection   = Dropdown(label=warning, button_type="warning", menu=tables, width=500, value=warning)
software_table_selection  = Dropdown(label=software, button_type="warning", menu=tables, width=500, value=software)

div_col = column(
            Div(text='Critical alarms table', style=text_style),
            Div(text='Major alarms table', style=text_style),
            Div(text='Minor alarms table', style=text_style),
            Div(text='Warnings table', style=text_style),
            Div(text='Software table', style=text_style)
        )

select_col = column(
            critical_table_selection,
            major_table_selection,
            minor_table_selection,
            warning_table_selection,
            software_table_selection
        )


reload_tables = Button(label="Reload table lists", button_type="success", width=200)
repopulate_dropdowns = Button(label="Repopulate dropdown menus", button_type="success", width=205)
save_defaults = Button(label="Save defaults", button_type="success", width=200)
button_row_1 = row(reload_tables, repopulate_dropdowns, save_defaults)
button_row_1.sizing_mode = 'scale_both'

adjust_dropdown = Dropdown(label='Adjust table', button_type='warning', width=625, value=None)
adjust_alarms_button = Button(label="Adjust alarm table", button_type="success", width=308)
adjust_software_button = Button(label="Adjust software table", button_type="success", width=307)

button_row_2 = row(adjust_alarms_button, adjust_software_button)
button_row_2.sizing_mode = 'scale_both'

load_csv_input = TextInput(value='~/', title="CSV path:")
load_csv_button = Button(label="Load CSV", button_type="success", width=625)


operators_view_tab = Panel(child=Tabs(tabs=[op_migrations, op_alarms]), title="Operators view")
sw_view_tab = Panel(child=Tabs(tabs=[software_failure_frequency, software_lifespan, software_migrations]), title="Software view")
settings_tab = Panel(child=column(load_csv_input, load_csv_button, row(div_col, select_col), button_row_1, adjust_dropdown, button_row_2), title="Settings")


tabs = Tabs(tabs=[operators_view_tab, sw_view_tab, settings_tab])


with PSQL_wrapper(psql_config) as psql:
    operator_selection.menu = sorted(get_operators(psql, software), key=lambda x: int(x.split(' ')[1]))
    software_selection.menu = ['all'] + sorted(get_softwares(psql, software))



x, y1, z = failure_frequency(psql_config, critical, software)
_, y2, _ = failure_frequency(psql_config, major, software)
_, y3, _ = failure_frequency(psql_config, minor, software)
_, y4, _ = failure_frequency(psql_config, warning, software)


software_failure_figure = figure(x_range=x, plot_width=width, plot_height=height+64)
software_failure_column.children[0] = software_failure_figure
software_failure_figure.sizing_mode = 'scale_both'

software_failure_source.data = dict(softwares=x, Critical=y1, Major=y2, Minor=y3, Warning=y4)
software_failure_figure.vbar_stack(software_alarm_types, width=0.9, color=['red', 'orange', 'green', 'blue'],
                                   x='softwares', source=software_failure_source, legend=[value(x) for x in software_alarm_types])
software_failure_figure.legend.location = "top_left"
software_failure_figure.legend[0].items.sort(reverse=True, key=lambda aux: software_alarm_types.index(aux.label['value']))

software_failure_hover = HoverTool(tooltips=[('Warning', '@Warning'), ('Minor', '@Minor'), ('Major', '@Major'), ('Critical', '@Critical')])
software_failure_figure.add_tools(software_failure_hover)



software_lifespan_figure = figure(x_range=x, plot_width=width, plot_height=height+64)
software_lifespan_column.children[0] = software_lifespan_figure
software_lifespan_figure.sizing_mode = 'scale_both'
software_lifespan_figure.vbar(x=x, top=z, width=0.9)

software_lifespan_hover = HoverTool(tooltips=[('Average lifespan (days)', '@top')])
software_lifespan_figure.add_tools(software_lifespan_hover)



def get_migrations_dict(source, sdate, edate, filter=None, mode=0, software=False):
    if filter == 'all':
        filter = None

    instances = source.keys()

    a = []
    b = []
    migration = []
    start = []
    end = []
    duration = []
    size = []
    count = []
    crit = []
    majr = []
    minr = []
    warn = []
    total = []

    for i in instances:
        if filter is not None and i[mode] != filter:
            continue

        t = source[i]

        a.append(i[0])
        b.append(i[1])
        migration.append(' -> '.join(list(i)))

        if software:
            count.append(t['count'])
        else:
            starting_date = t['begin']
            end_date = t['end']

            if starting_date < sdate or end_date > edate:
                continue

            starting_date = starting_date.strftime(date_format)
            end_date = end_date.strftime(date_format)
            start.append(starting_date)
            end.append(end_date)

        dur = t['duration']

        if dur == 1:
            formatter = ' day'
        else:
            formatter = ' days'

        duration.append(str(dur) + formatter)

        s = t['size']

        if s == 1:
            formatter = ' machine'
        else:
            formatter = ' machines'

        size.append(str(s) + formatter)

        crit.append(t['critical'])
        majr.append(t['major'])
        minr.append(t['minor'])
        warn.append(t['warnings'])

        total.append(t['critical'] + t['major'] + t['minor'] + t['warnings'])

    if software:
        return dict(migration=migration, count=count, duration=duration, size=size, critical=crit, major=majr, minor=minr, warning=warn)
    else:
        return dict(migration=migration, start=start, end=end, duration=duration, size=size, critical=crit, major=majr, minor=minr, warning=warn, a=a, b=b, total=total)



def update_operators_view(attr, old, new):
    global op_migrations_figure
    operator_selection.label = new

    with PSQL_wrapper(psql_config) as psql:
        # update alarms
        command = """
            SELECT "Date", "{0}"
            FROM "{1}"
            ORDER BY 1,2
        """

        sdate = operator_date_picker_start.value
        edate = operator_date_picker_end.value

        res = psql.exec(command.format(new, critical)).result
        date1, points1 = zip(*[t for t in res if sdate <= t[0] <= edate])
        op_alarms_critical_source.data = dict(date=date1, critical=points1)
        op_alarms_critical_figure.line('date', 'critical', source=op_alarms_critical_source, line_width=1.5)
        op_alarms_critical_figure.add_tools(op_alarms_critical_hover)

        res = psql.exec(command.format(new, major)).result
        date2, points2 = zip(*[t for t in res if sdate <= t[0] <= edate])
        op_alarms_major_source.data = dict(date=date2, major=points2)
        op_alarms_major_figure.line('date', 'major', source=op_alarms_major_source, line_width=1.5)
        op_alarms_major_figure.add_tools(op_alarms_major_hover)

        res = psql.exec(command.format(new, minor)).result
        date3, points3 = zip(*[t for t in res if sdate <= t[0] <= edate])
        op_alarms_minor_source.data = dict(date=date3, minor=points3)
        op_alarms_minor_figure.line('date', 'minor', source=op_alarms_minor_source, line_width=1.5)
        op_alarms_minor_figure.add_tools(op_alarms_minor_hover)

        res = psql.exec(command.format(new, warning)).result
        date4, points4 = zip(*[t for t in res if sdate <= t[0] <= edate])
        op_alarms_warning_source.data = dict(date=date4, warning=points4)
        op_alarms_warning_figure.line('date', 'warning', source=op_alarms_warning_source, line_width=1.5)
        op_alarms_warning_figure.add_tools(op_alarms_warning_hover)

        # update migrations figure
        command = """
            SELECT "Date" AS "time", "SW_version" AS metric, avg("Value") AS "Value"
            FROM "{0}"
            WHERE "Operator_name" = '{1}'
            GROUP BY "Date",2
            ORDER BY 1,2
        """.format(software, new)
        res = psql.exec(command.format(new, critical)).result
        date, sw, points = zip(*[t for t in res if sdate <= t[0] <= edate])

        tooltips = [('Date', '@date{%F}')]

        softwares = set(sw)
        dates = list(dict.fromkeys(date))
        op_migrations_source.data = dict(date=dates)

        datapoints = dict()

        for version in softwares:
            datapoints[version] = []
            tooltips.append((version, '@' + version))

        for d in dates:
            pairs = [(t[1], t[2]) for t in res if t[0] == d]
            softs, _ = zip(*pairs)

            for soft in softwares:
                if soft in softs:
                    datapoints[soft].append(next(p[1] for p in pairs if p[0] == soft))
                else:
                    datapoints[soft].append(0)

        for version in softwares:
            op_migrations_source.data[version] = datapoints[version]

        colors = cycle(palette)

        op_migrations_figure = figure(plot_width=width, plot_height=height+136)
        op_migrations_column.children[1].children[0] = op_migrations_figure
        op_migrations_figure.sizing_mode = 'scale_both'
        op_migrations_figure.xaxis.formatter = date_formatter

        legend_items = []

        for version in softwares:
            color = next(colors)
            l = op_migrations_figure.line('date', version, source=op_migrations_source, line_width=4, color=color, alpha=0.8)
            legend_items.append(LegendItem(label = version, renderers = [l]))

        new_legend = Legend(items = legend_items, location = 'top_left')
        new_legend.click_policy = 'hide'
        op_migrations_figure.renderers.append(new_legend)

        op_migrations_hover = HoverTool(tooltips=tooltips, formatters={"date": "datetime"})
        op_migrations_figure.add_tools(op_migrations_hover)

        # update migrations details
        migrations = operator_migrations(psql_config, critical, major, minor, warning, software, new)
        op_migrations_details_table_source.data = get_migrations_dict(migrations[new], sdate, edate)


def update_operators_view_date(attr, old, new):
    l = operator_selection.label
    if l != "Operator" and operator_date_picker_start.value <= operator_date_picker_end.value:
        update_operators_view(attr, old, l)



def update_software_view(attr, old, new):
    software_selection.label = 'Software version: ' + new

    migrations = global_migrations(psql_config, critical, major, minor, warning, software)
    software_migrations_source.data = get_migrations_dict(migrations, None, None, filter=new, mode=software_mode_radio.active, software=True)


def update_software_view_radio(attr, old, new):
    l = software_selection.label
    if l.startswith("Software version:"):
        l = l.split(' ')[-1]

    if l != "Software version":
        update_software_view(attr, old, l)


operator_selection.on_change('value', update_operators_view)
operator_date_picker_start.on_change('value', update_operators_view_date)
operator_date_picker_end.on_change('value', update_operators_view_date)

software_selection.on_change('value', update_software_view)
software_mode_radio.on_change('active', update_software_view_radio)


curdoc().title = "Network evolution"
curdoc().add_root(tabs)
