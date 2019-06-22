# -*- coding: utf-8 -*-

import datetime
from base64 import b64decode
from io import TextIOWrapper, BytesIO
from itertools import cycle, islice
from functools import partial

from bokeh.io import output_file, show, curdoc
from bokeh.models.widgets import RadioButtonGroup, Dropdown, DataTable, DateFormatter, TableColumn, DatePicker, Div, Button, TextInput
from bokeh.models.widgets.tables import HTMLTemplateFormatter
from bokeh.models import Panel, Tabs, ColumnDataSource, HoverTool, Legend, LegendItem, LayoutDOM, CustomJS, Range1d, LinearAxis, Title
from bokeh.plotting import figure
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.layouts import row, column, gridplot
from bokeh.palettes import Set1_9 as palette
from bokeh.core.properties import value, String
from bokeh.core.validation import silence
from bokeh.core.validation.warnings import MISSING_RENDERERS

from metrics import *

# we have a lot of empty plots, since none of them can be rendered without a configuration, hence warning suppression
silence(MISSING_RENDERERS, True)

# reading basic configuration from a config.ini file
psql_config = read_config('config.ini', 'PSQL', ['host', 'port', 'dbname', 'user', 'password'])
defaults = read_config('config.ini', 'Defaults', ['critical', 'major', 'minor', 'warning', 'software'])
software_names = read_config('config.ini', 'Softwares', ['FD', 'TD', 'XD'])

fd_softwares = list(map(lambda aux: aux.upper(), software_names['FD'].split(',')))
td_softwares = list(map(lambda aux: aux.upper(), software_names['TD'].split(',')))
xd_softwares = list(map(lambda aux: aux.upper(), software_names['XD'].split(',')))
software_alarm_types = ['Critical', 'Major', 'Minor', 'Warning']

# setting up global variables used thorough the program
tables = []

try:
    with PSQL_wrapper(psql_config) as psql:
        tables = sorted(get_public_tables(psql))
except Exception as e:
    print(e)
    print("[CRITICAL] Could not connect to PostgreSQL database, shutting down...")
    import sys
    sys.exit(1)

date_format = '%d-%m-%Y'
dt1 = datetime.datetime.today()
dt2 = datetime.datetime(year=dt1.year-2, month=dt1.month, day=dt1.day)

start = int(dt2.timestamp() * 1000)
end = int(dt1.timestamp() * 1000)

critical = defaults['critical']
major    = defaults['major']
minor    = defaults['minor']
warning  = defaults['warning']
software = defaults['software']

software_view_initialized = False
fd1, td1 = [], []
fd2, td2 = [], []
fd3, td3 = [], []
fd4, td4 = [], []

software_view_migrations_fetched = False
migrations = {}

operators_view_initialized = False
tooltips = []
machines_maxval = 0
machines_total_max = 0
alarms_maxval = 0
original_software_names = set()

width = 950
height = 550

# date formatter for the graphs
date_formatter = DatetimeTickFormatter(
    seconds="%d %B %Y",
    minutes="%d %B %Y",
    hours="%d %b %Y",
    days="%d %b %Y",
    months="%d %b %Y",
    years="%d %b %Y"
)

# JavaScript templates for migrations table cell coloring
migrations_template = """
    var arr = {0}.split(" -> ");
    var a1 = arr[0].toUpperCase();
    var a2 = arr[1].toUpperCase();
"""

summary_template_js = """
    var a1 = a.toUpperCase();
    var a2 = b.toUpperCase();
"""

# migrations table cell coloring function
general_template = """
    <div style="background:<%=
        (function colorfromint() {{
            var fd_order = {0}.concat({2});
            var td_order = {1}.concat({2});
            var i1, i2;

            {3}

            i1 = fd_order.indexOf(a1);
            i2 = fd_order.indexOf(a2);

            if (i1 !== -1 && i2 !== -1) {{
                if (i2 - i1 >= 3) {{
                    return ("palegreen");
                }}
                else if (i1 > i2) {{
                    return("lightcoral");
                }}
            }}

            i1 = td_order.indexOf(a1);
            i2 = td_order.indexOf(a2);

            if (i1 !== -1 && i2 !== -1) {{
                if (i2 - i1 >= 3) {{
                    return ("palegreen");
                }}
                else if (i1 > i2) {{
                    return("lightcoral");
                }}
            }}

            }}()) %>;
        color: black">
    <%= value %>
    </div>
"""

# table cell coloring for boolean values
bool_color_template = """
    <div style="background:<%=
        (function colorfromint() {{
            if ({0}) {{
                return("powderblue");
            }}
            if ({1}) {{
                return("lightsalmon");
            }}
            }}()) %>;
        color: black">
    <%= value %>
    </div>
"""

formatter = HTMLTemplateFormatter(template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('migration')))

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


def text_style_with_bg(color):
    """Adds a background color to a div"""
    temp = {**text_style}
    temp['background'] = color
    return temp


# setting up the first graphical components
color_legend = row(Div(text='  daring migration  ', style=text_style_with_bg('palegreen')),
                   Div(text='  regression  ', style=text_style_with_bg('lightcoral')),
                   Div(text='  smallest value  ', style=text_style_with_bg('powderblue')),
                   Div(text='  biggest value  ', style=text_style_with_bg('lightsalmon')))

# initializing the operators' view
operator_selection = Dropdown(label="Operator", button_type="warning", menu=[], width=200)
operator_date_picker_start = DatePicker(max_date=dt1, value=dt2.date())
operator_date_picker_end = DatePicker(max_date=dt1, value=dt1.date())
operator_settings = row(operator_selection,
                        Div(text='   Starting date:', style=text_style),
                        operator_date_picker_start,
                        Div(text='   End date:', style=text_style),
                        operator_date_picker_end,
                        Div(text=' ', style=text_style))

# line graph
op_migrations_source = ColumnDataSource(data=dict())
op_migrations_figure_lines = figure(title="Operator migrations", plot_width=width, plot_height=height)
op_migrations_figure_lines.sizing_mode = 'scale_both'

# stacked graph
op_migrations_figure_stacked = figure(title="Operator migrations", plot_width=width, plot_height=height)
op_migrations_figure_stacked.sizing_mode = 'scale_both'
op_migrations_hover = HoverTool(tooltips=[('Date', '@date{%F}')], formatters={"date": "datetime"})

# migration details tab columns
op_migrations_columns = [
    TableColumn(field="migration", title="Migration", formatter=formatter),
    TableColumn(field="start", title="Start"),
    TableColumn(field="end", title="End"),
    TableColumn(field="duration", title="Duration (days)", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('shortest_migration', 'longest_migration'))),
    TableColumn(field="size", title="Size (machines)", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('smallest_migration', 'biggest_migration'))),
    TableColumn(field="critical", title="Critical", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_critical', 'most_critical'))),
    TableColumn(field="major", title="Major", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_major', 'most_major'))),
    TableColumn(field="minor", title="Minor", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_minor', 'most_minor'))),
    TableColumn(field="warning", title="Warning", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_warnings', 'most_warnings'))),
    TableColumn(field="total", title="Alarms total", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_total', 'most_total')))
]

# migration details tab
op_migrations_details_table_source = ColumnDataSource(data=dict())
op_migrations_details_table = DataTable(source=op_migrations_details_table_source, columns=op_migrations_columns,
                                        fit_columns=True, editable=False, reorderable=False, selectable=False)
op_migrations_details_table.sizing_mode = 'scale_both'
op_migrations_details_column = column(row(operator_settings, color_legend), op_migrations_details_table)
op_migrations_details_column.sizing_mode = 'scale_both'

summary_formatter = HTMLTemplateFormatter(template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), summary_template_js))

# migrations summary sidebar
op_migrations_summary_columns = [
    TableColumn(field="a", title="From", formatter=summary_formatter),
    TableColumn(field="b", title="To", formatter=summary_formatter),
    TableColumn(field="duration", title="Duration", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('shortest_migration', 'longest_migration'))),
    TableColumn(field="total", title="Alarms", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_total', 'most_total')))
]
op_migrations_summary = DataTable(source=op_migrations_details_table_source, columns=op_migrations_summary_columns, width=250, index_position=None,
                                  fit_columns=True, editable=False, reorderable=False, selectable=False)

# migrations stats sidebar
op_stats_columns_1 = [
    TableColumn(field="biggest", title="Biggest migration", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('biggest')))),
    TableColumn(field="smallest", title="Smallest migration", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('smallest'))))
]

op_stats_columns_2 = [
    TableColumn(field="shortest", title="Shortest migration", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('shortest')))),
    TableColumn(field="longest", title="Longest migration", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('longest'))))
]

op_stats_columns_3 = [
    TableColumn(field="most_alarms", title="Most alarms", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('most_alarms')))),
    TableColumn(field="most_critical", title="Most critical alarms", formatter=HTMLTemplateFormatter(
        template=general_template.format(str(fd_softwares), str(td_softwares), str(xd_softwares), migrations_template.format('most_critical'))))
]

op_stats_source = ColumnDataSource(data=dict())
op_stats_1 = DataTable(source=op_stats_source, columns=op_stats_columns_1, width=250, height=45, index_position=None,
    fit_columns=True, editable=False, reorderable=False, selectable=False)
op_stats_2 = DataTable(source=op_stats_source, columns=op_stats_columns_2, width=250, height=45, index_position=None,
    fit_columns=True, editable=False, reorderable=False, selectable=False)
op_stats_3 = DataTable(source=op_stats_source, columns=op_stats_columns_3, width=250, height=70, index_position=None,
    fit_columns=True, editable=False, reorderable=False, selectable=False)

op_stats = column(op_stats_1, op_stats_2, op_stats_3)

lines_generate_button = Button(label="Generate graph", button_type="warning", width=200)
stacked_generate_button = Button(label="Generate graph", button_type="warning", width=200)

# final tab declarations
op_migrations_line_column = column(row(operator_settings, lines_generate_button, Div(text='', style=text_style), color_legend),
                                   row(op_migrations_figure_lines, column(op_stats, op_migrations_summary)))
op_migrations_stacked_column = column(row(operator_settings, stacked_generate_button, Div(text='', style=text_style), color_legend),
                                      row(op_migrations_figure_stacked, column(op_stats, op_migrations_summary)))

op_migrations_figure_lines_tab = Panel(child=op_migrations_line_column, title="Line graph")
op_migrations_figure_stacked_tab = Panel(child=op_migrations_stacked_column, title="Stacked graph")
op_migrations_details_tab = Panel(child=op_migrations_details_column, title="Details")

op_migrations = Tabs(tabs=[op_migrations_figure_lines_tab, op_migrations_figure_stacked_tab, op_migrations_details_tab], active=0)


# initializing the software view
software_mode_radio = RadioButtonGroup(labels=["From", "To"], active=0, width=100)
software_selection = Dropdown(label="Software version", button_type="warning", menu=[], width=200)
software_settings = row(software_selection, software_mode_radio)

fd_generate_button = Button(label="Generate graphs", button_type="warning", width=200)
td_generate_button = Button(label="Generate graphs", button_type="warning", width=200)

software_stats_columns = [
    TableColumn(field="min_alarms", title="Minimal number of alarms"),
    TableColumn(field="max_alarms", title="Maximal number of alarms"),
    TableColumn(field="max_critical", title="Maximal number of critical alarms"),
    TableColumn(field="shortest_lifespan", title="Shortest lifespan"),
    TableColumn(field="longest_lifespan", title="Longest lifespan"),
    TableColumn(field="average_lifespan", title="Average lifespan")
]

# frequency division tab
fd_stats_source = ColumnDataSource(data=dict())
fd_stats = DataTable(source=fd_stats_source, columns=software_stats_columns, index_position=None,
                     fit_columns=True, editable=False, reorderable=False, selectable=False, sortable=False)
fd_stats.height = 18
fd_stats.sizing_mode = 'scale_both'

td_stats_source = ColumnDataSource(data=dict())
td_stats = DataTable(source=td_stats_source, columns=software_stats_columns, index_position=None,
                     fit_columns=True, editable=False, reorderable=False, selectable=False, sortable=False)
td_stats.sizing_mode = 'scale_both'
td_stats.height = 18


fd_failure_source = ColumnDataSource(data=dict())
fd_failure_figure = figure(plot_width=width//2, plot_height=int(height*1.35), title="Failure frequency")
fd_failure_figure.sizing_mode = 'stretch_both'

fd_lifespan_source = ColumnDataSource(data=dict())
fd_lifespan_figure = figure(plot_width=width//2, plot_height=int(height*1.35), title="Lifespan")
fd_lifespan_figure.sizing_mode = 'stretch_both'

fd_figure = gridplot([fd_failure_figure, fd_lifespan_figure], ncols=2, toolbar_location='right')
fd_column = column(fd_generate_button, fd_stats, fd_figure)
fd_column.sizing_mode = 'scale_both'
fd_panel = Panel(child=fd_column, title="Frequency division")

# time division tab
td_failure_source = ColumnDataSource(data=dict())
td_failure_figure = figure(plot_width=width//2, plot_height=int(height*1.35), title="Failure frequency")
td_failure_figure.sizing_mode = 'stretch_both'

td_lifespan_source = ColumnDataSource(data=dict())
td_lifespan_figure = figure(plot_width=width//2, plot_height=int(height*1.35), title="Lifespan")
td_lifespan_figure.sizing_mode = 'stretch_both'

td_figure = gridplot([td_failure_figure, td_lifespan_figure], ncols=2, toolbar_location='right')
td_column = column(td_generate_button, td_stats, td_figure)
td_column.sizing_mode = 'scale_both'
td_panel = Panel(child=td_column, title="Time division")

# hover for operators in software details tab
table_hover = """
    <div style="background:<%=
        (function colorfromint() {{
            if ({0}) {{
                return("powderblue");
            }}
            if ({1}) {{
                return("lightsalmon");
            }}
            }}()) %>;
        color: black"; title="<%= operators %>">
    <%= value %>
    </div>
"""

software_migrations_columns = [
    TableColumn(field="migration", title="Migration", formatter=formatter),
    TableColumn(field="duration", title="Average duration (days)", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('shortest_migration', 'longest_migration'))),
    TableColumn(field="size", title="Average size (machines)", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('smallest_migration', 'biggest_migration'))),
    TableColumn(field="count", title="Number of operators", formatter=HTMLTemplateFormatter(
        template=table_hover.format('smallest_count', 'biggest_count'))),
    TableColumn(field="critical", title="Critical alarm average", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_critical', 'most_critical'))),
    TableColumn(field="major", title="Major alarm average", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_major', 'most_major'))),
    TableColumn(field="minor", title="Minor alarm average", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_minor', 'most_minor'))),
    TableColumn(field="warning", title="Warning average", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_warnings', 'most_warnings'))),
    TableColumn(field="total", title="Total average", formatter=HTMLTemplateFormatter(
        template=bool_color_template.format('least_total', 'most_total'))),
]

# software details tab
software_migrations_source = ColumnDataSource(data=dict())
software_migrations_table = DataTable(source=software_migrations_source, columns=software_migrations_columns, width=width, height=int(height*0.85),
                                      fit_columns=True, editable=False, reorderable=False, selectable=False)
software_migrations_table.sizing_mode = 'scale_both'
software_migrations_column = column(row(software_settings, color_legend), software_migrations_table)
software_migrations_column.sizing_mode = 'scale_both'
software_migrations = Panel(child=software_migrations_column, title="Migrations")

# settings tab
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

adjust_dropdown = Dropdown(label='Adjust table', menu=tables, button_type='warning', width=625, value=None)
adjust_alarms_button = Button(label="Adjust alarm table", button_type="success", width=308)
adjust_software_button = Button(label="Adjust software table", button_type="success", width=307)

button_row_2 = row(adjust_alarms_button, adjust_software_button)
button_row_2.sizing_mode = 'scale_both'

csv_file_source = ColumnDataSource({'file_contents': [], 'file_name': []})

load_csv_button = Button(label="Load CSV", button_type="success", width=625)
load_csv_button.callback = CustomJS(args=dict(file_source=csv_file_source), code = """
    function read_file(filename) {
        var reader = new FileReader();
        reader.onload = load_handler;
        reader.readAsDataURL(filename);
    }

    function load_handler(event) {
        var b64string = event.target.result;
        file_source.data = {'file_contents' : [b64string], 'file_name':[input.files[0].name]};
        file_source.trigger("change");
    }

    var input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.onchange = function(){
        if (window.FileReader) {
            read_file(input.files[0]);
        }
    }
    input.click();
""")

# binding all the tabs together
operators_view_tab = Panel(child=op_migrations, title="Operators view")
sw_view_tab = Panel(child=Tabs(tabs=[fd_panel, td_panel, software_migrations]), title="Software view")
settings_tab = Panel(child=column(load_csv_button, row(div_col, select_col), button_row_1, adjust_dropdown, button_row_2), title="Settings")

tabs = Tabs(tabs=[operators_view_tab, sw_view_tab, settings_tab])

# populating dropdown menus
with PSQL_wrapper(psql_config) as psql:
    operator_selection.menu = sorted(get_operators(psql, software), key=lambda x: int(x.split(' ')[1]))
    software_selection.menu = ['all'] + sorted(get_softwares(psql, software))


def get_migrations_dict(source, sdate, edate, filter=None, mode=0, software=False):
    """Returns a dictionary suitable to fill relevant ColumnDataSources, used in both operators' and software view"""

    if filter == 'all':
        filter = None

    instances = source.keys()

    a, b, migration, start, end, duration, count = [], [], [], [], [], [], []
    size, crit, majr, minr, warn, total, operators = [], [], [], [], [], [], []
    most_critical, most_major, most_minor, most_warnings = [], [], [], []
    least_critical, least_major, least_minor, least_warnings = [], [], [], []
    biggest_migration, smallest_migration = [], []
    longest_migration, shortest_migration = [], []
    most_total, least_total = [], []
    biggest_count, smallest_count = [], []

    for i in instances:
        if filter is not None and i[mode] != filter:
            continue

        t = source[i]

        if software:
            a.append(i[0])
            b.append(i[1])
            migration.append(' -> '.join(list(i)))

            operators.append('\n'.join(sorted(t['operators'], key=lambda x: int(x.split(' ')[1]))))
            count.append(t['count'])

        else:
            starting_date = t['begin']
            end_date = t['end']

            if starting_date < sdate or end_date > edate:
                continue

            a.append(i[0])
            b.append(i[1])
            migration.append(' -> '.join(list(i)))

            starting_date = starting_date.strftime(date_format)
            end_date = end_date.strftime(date_format)
            start.append(starting_date)
            end.append(end_date)

        duration.append(t['duration'])
        size.append(t['size'])

        crit.append(t['critical'])
        majr.append(t['major'])
        minr.append(t['minor'])
        warn.append(t['warnings'])
        total.append(t['total_alarms'])

        if software is False:
            most_total.append(t['most_total'])
            least_total.append(t['least_total'])

            most_critical.append(t['most_critical'])
            most_major.append(t['most_major'])
            most_minor.append(t['most_minor'])
            most_warnings.append(t['most_warnings'])

            least_critical.append(t['least_critical'])
            least_major.append(t['least_major'])
            least_minor.append(t['least_minor'])
            least_warnings.append(t['least_warnings'])

            biggest_migration.append(t['biggest_migration'])
            smallest_migration.append(t['smallest_migration'])
            longest_migration.append(t['longest_migration'])
            shortest_migration.append(t['shortest_migration'])

    if software is True:
        def map_helper(lst, fun):
            if lst == []:
                return []
            else:
                value = fun(list(map(int, lst)))
                return [int(elem) == value for elem in lst]

        most_critical = map_helper(crit, max)
        most_major = map_helper(majr, max)
        most_minor = map_helper(minr, max)
        most_warnings = map_helper(warn, max)

        least_critical = map_helper(crit, min)
        least_major = map_helper(majr, min)
        least_minor = map_helper(minr, min)
        least_warnings = map_helper(warn, min)

        most_total = map_helper(total, max)
        least_total = map_helper(total, min)

        biggest_migration = map_helper(size, max)
        smallest_migration = map_helper(size, min)

        longest_migration = map_helper(duration, max)
        shortest_migration = map_helper(duration, min)

        biggest_count = map_helper(count, max)
        smallest_count = map_helper(count, min)

        return dict(migration=migration, count=count, duration=duration, size=size,
            critical=crit, major=majr, minor=minr, warning=warn, operators=operators, total=total,
            biggest_migration=biggest_migration, smallest_migration=smallest_migration,
            longest_migration=longest_migration, shortest_migration=shortest_migration,
            most_critical=most_critical, most_major=most_major, most_minor=most_minor, most_warnings=most_warnings,
            least_critical=least_critical, least_major=least_major, least_minor=least_minor, least_warnings=least_warnings,
            biggest_count=biggest_count, smallest_count=smallest_count,
            most_total=most_total, least_total=least_total)
    else:
        return dict(migration=migration, start=start, end=end, duration=duration, size=size,
            critical=crit, major=majr, minor=minr, warning=warn, a=a, b=b, total=total,
            biggest_migration=biggest_migration, smallest_migration=smallest_migration,
            longest_migration=longest_migration, shortest_migration=shortest_migration,
            most_critical=most_critical, most_major=most_major, most_minor=most_minor, most_warnings=most_warnings,
            least_critical=least_critical, least_major=least_major, least_minor=least_minor, least_warnings=least_warnings,
            most_total=most_total, least_total=least_total)



def update_operators_view_line_graph():
    """Redraws operators' view line graph"""
    if operators_view_initialized:
        op_migrations_hover = HoverTool(tooltips=tooltips, formatters={"date": "datetime"})
        range_epsilon = 0.03

        op_migrations_figure_lines = figure(title="Operator migrations", plot_width=width, plot_height=height)
        op_migrations_figure_lines.y_range = Range1d(start=-int(range_epsilon*machines_maxval), end=machines_maxval+int(range_epsilon*machines_maxval))
        op_migrations_figure_lines.sizing_mode = 'scale_both'
        op_migrations_figure_lines.xaxis.formatter = date_formatter

        legend_items = []
        colors_cycle = cycle(palette)

        for version in original_software_names:
            color = next(colors_cycle)
            legend_item = op_migrations_figure_lines.line('date', version.replace('.', ''), source=op_migrations_source, line_width=4, color=color, alpha=0.8)
            legend_items.append(LegendItem(label = version, renderers = [legend_item]))

        op_migrations_figure_lines.add_tools(op_migrations_hover)
        op_migrations_figure_lines.extra_y_ranges = {"alarms": Range1d(start=-int(range_epsilon*alarms_maxval), end=alarms_maxval+int(range_epsilon*alarms_maxval))}
        op_migrations_figure_lines.add_layout(LinearAxis(y_range_name="alarms"), 'right')
        op_migrations_figure_lines.add_layout(Title(text="Number of machines", align="center"), "left")
        op_migrations_figure_lines.add_layout(Title(text="Number of alarms", align="center"), "right")

        alarms_legend = []

        legend_item = op_migrations_figure_lines.line('date', 'critical', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Critical alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_lines.line('date', 'major', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Major alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_lines.line('date', 'minor', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Minor alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_lines.line('date', 'warning', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Warnings", renderers = [legend_item]))

        new_legend = Legend(items = alarms_legend + legend_items, location = 'top_left')
        new_legend.click_policy = 'hide'
        op_migrations_figure_lines.renderers.append(new_legend)

        op_migrations_line_column.children[1].children[0] = op_migrations_figure_lines



def update_operators_view_stacked_graph():
    """Redraws operators' view stacked graph"""
    if operators_view_initialized:
        orig_softwares = list(original_software_names)
        softwares = list(map(lambda aux: aux.replace('.', ''), orig_softwares))

        op_migrations_hover = HoverTool(tooltips=tooltips, formatters={"date": "datetime"})
        range_epsilon = 0.03

        op_migrations_figure_stacked = figure(title="Operator migrations", plot_width=width, plot_height=height)
        op_migrations_figure_stacked.y_range = Range1d(start=-int(range_epsilon*machines_total_max), end=machines_total_max+int(range_epsilon*machines_total_max))
        op_migrations_figure_stacked.sizing_mode = 'scale_both'
        op_migrations_figure_stacked.xaxis.formatter = date_formatter

        legend_items = []
        colors_cycle = cycle(palette)

        op_migrations_figure_stacked.varea_stack(softwares, x='date', source=op_migrations_source, color=list(islice(colors_cycle, len(softwares))))
        renderers = iter(op_migrations_figure_stacked.renderers)

        colors_cycle = cycle(palette)
        op_migrations_figure_stacked.varea_stack(softwares, x='date', source=op_migrations_source, color=list(islice(colors_cycle, len(softwares))))

        # adding legend items twice to prevent user from breaking the graph whilst keeping the legend interactive
        for version in orig_softwares:
            legend_items.append(LegendItem(label = version, renderers = [next(renderers)]))

        op_migrations_figure_stacked.add_tools(op_migrations_hover)
        op_migrations_figure_stacked.extra_y_ranges = {"alarms": Range1d(start=-int(range_epsilon*alarms_maxval), end=alarms_maxval+int(range_epsilon*alarms_maxval))}
        op_migrations_figure_stacked.add_layout(LinearAxis(y_range_name="alarms"), 'right')
        op_migrations_figure_stacked.add_layout(Title(text="Number of machines", align="center"), "left")
        op_migrations_figure_stacked.add_layout(Title(text="Number of alarms", align="center"), "right")

        alarms_legend = []

        legend_item = op_migrations_figure_stacked.line('date', 'critical', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Critical alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_stacked.line('date', 'major', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Major alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_stacked.line('date', 'minor', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Minor alarms", renderers = [legend_item]))

        legend_item = op_migrations_figure_stacked.line('date', 'warning', source=op_migrations_source, line_width=1.5, y_range_name="alarms", color='black')
        legend_item.visible = False
        alarms_legend.append(LegendItem(label = "Warnings", renderers = [legend_item]))

        new_legend = Legend(items = alarms_legend + legend_items, location = 'top_left')
        new_legend.click_policy = 'hide'
        op_migrations_figure_stacked.renderers.append(new_legend)

        op_migrations_stacked_column.children[1].children[0] = op_migrations_figure_stacked



def update_operators_view(attr, old, new):
    """Fetches data for operators' view and fills in sidebars"""
    global op_migrations_figure_lines, op_migrations_figure_stacked, tooltips
    global machines_maxval, machines_total_max, alarms_maxval, original_software_names, operators_view_initialized

    operator_selection.label = new

    with PSQL_wrapper(psql_config) as psql:
        # set time limits according to date pickers
        sdate = operator_date_picker_start.value
        edate = operator_date_picker_end.value

        command = """
            SELECT "Date", "{0}"
            FROM "{1}"
            ORDER BY 1,2
        """

        res = psql.exec(command.format(new, critical)).result
        dataset1 = [t for t in res if sdate <= t[0] <= edate]

        res = psql.exec(command.format(new, major)).result
        dataset2 = [t for t in res if sdate <= t[0] <= edate]

        res = psql.exec(command.format(new, minor)).result
        dataset3 = [t for t in res if sdate <= t[0] <= edate]

        res = psql.exec(command.format(new, warning)).result
        dataset4 = [t for t in res if sdate <= t[0] <= edate]

        # fetch migration data
        command = """
            SELECT "Date" AS "time", "SW_version" AS metric, avg("Value") AS "Value"
            FROM "{0}"
            WHERE "Operator_name" = '{1}'
            GROUP BY "Date",2
            ORDER BY 1,2
        """.format(software, new)
        res = psql.exec(command.format(new, critical)).result
        date, sw, points = zip(*[t for t in res if sdate <= t[0] <= edate])

        tooltips = [('Date', '@date{%F}'), ('Critical alarms', '@critical'), ('Major alarms', '@major'),
                    ('Minor alarms', '@minor'), ('Warnings', '@warning')]

        original_software_names = set(sw)
        softwares = set([s.replace('.', '') for s in original_software_names])

        dates = list(dict.fromkeys(date))
        op_migrations_source.data = dict(date=dates)

        datapoints = dict()
        total_lst = []
        machines_maxval = 0
        for version, version_name in zip(softwares, original_software_names):
            datapoints[version] = []
            tooltips.append((version_name, '@' + version))

        tooltips.append(('Machines total', '@total'))

        # find the maximum amount of machines and their alarms (used for setting graph's axis limits)
        for d in dates:
            pairs = [(t[1], t[2]) for t in res if t[0] == d]
            softs, _ = zip(*pairs)
            total = 0

            for soft in softwares:
                if soft in softs:
                    point = next(p[1] for p in pairs if p[0] == soft)
                    machines_maxval = max(machines_maxval, point)
                    datapoints[soft].append(point)
                    total += point
                else:
                    datapoints[soft].append(0)

            total_lst.append(total)

        for version in softwares:
            op_migrations_source.data[version] = datapoints[version]

        op_migrations_source.data['total'] = total_lst
        machines_total_max = max(total_lst)

        alarms_maxval = 0
        for a in [('critical', dataset1), ('major', dataset2), ('minor', dataset3), ('warning', dataset4)]:
            temp = []

            for d in dates:
                point = next((t[1] for t in a[1] if t[0] == d), None)
                if point is None:
                    temp.append(0)
                else:
                    alarms_maxval = max(alarms_maxval, point)
                    temp.append(point)

            op_migrations_source.data[a[0]] = temp


        # update migrations details
        migrations, stats = operator_migrations(psql, critical, major, minor, warning, software, new, fd_softwares, td_softwares, xd_softwares)
        op_migrations_details_table_source.data = get_migrations_dict(migrations, sdate, edate)

        d = {}
        d['biggest'] = [' -> '.join(list(stats['biggest'][0][1]))]
        d['smallest'] = [' -> '.join(list(stats['smallest'][0][1]))]
        d['shortest'] = [' -> '.join(list(stats['shortest'][0][1]))]
        d['longest'] = [' -> '.join(list(stats['longest'][0][1]))]
        d['most_alarms'] = [' -> '.join(list(stats['most_alarms'][0][1]))]
        d['most_critical'] = [' -> '.join(list(stats['most_critical'][0][1]))]
        op_stats_source.data = d

        operators_view_initialized = True



def update_operators_view_date(attr, old, new):
    """Operators' view date picker callback"""
    label = operator_selection.label
    if label != "Operator" and operator_date_picker_start.value <= operator_date_picker_end.value:
        update_operators_view(attr, old, label)


def update_software_view_graphs(button):
    """Software view "Generate graph" callback"""
    global software_view_initialized, tables_changed
    global fd1, td1, fd2, td2, fd3, td3, fd4, td4

    def stringify(tup):
        return [str(tup[0]) + ' (' + tup[1] + ')']

    if not software_view_initialized:
        try:
            with PSQL_wrapper(psql_config) as psql:
                fd1, td1 = failure_frequency(psql, critical, software, fd_softwares, td_softwares, xd_softwares)
                fd2, td2 = failure_frequency(psql, major,    software, fd_softwares, td_softwares, xd_softwares)
                fd3, td3 = failure_frequency(psql, minor,    software, fd_softwares, td_softwares, xd_softwares)
                fd4, td4 = failure_frequency(psql, warning,  software, fd_softwares, td_softwares, xd_softwares)
            software_view_initialized = True
        except:
            print("[WARN] Could not generate graph, make sure your settings are correct")
            return


    software_failure_hover = HoverTool(tooltips=[('Warning', '@Warning'), ('Minor', '@Minor'), ('Major', '@Major'), ('Critical', '@Critical')])
    software_lifespan_hover = HoverTool(tooltips=[('Average lifespan (days)', '@top')])

    if button is 1:
        fd_failure_figure = figure(x_range=fd1[0], plot_width=width//2, plot_height=int(height*1.35), title="Failure frequency")
        fd_failure_figure.add_layout(Title(text="Expected number of alarms per 100 machines over one month", align="center"), "left")
        fd_failure_figure.sizing_mode = 'stretch_both'
        fd_failure_source.data = dict(softwares=fd1[0], Critical=fd1[1], Major=fd2[1], Minor=fd3[1], Warning=fd4[1])
        fd_failure_figure.vbar_stack(software_alarm_types, width=0.9, color=['red', 'orange', 'green', 'blue'],
                                           x='softwares', source=fd_failure_source, legend=[value(x) for x in software_alarm_types])
        fd_failure_figure.legend.location = "top_left"
        fd_failure_figure.legend[0].items.sort(reverse=True, key=lambda aux: software_alarm_types.index(aux.label['value']))
        fd_failure_figure.add_tools(software_failure_hover)

        fd_lifespan_figure = figure(x_range=fd1[0], plot_width=width//2, plot_height=int(height*1.35), title="Lifespan")
        fd_lifespan_figure.add_layout(Title(text="Average number of days software was in use", align="center"), "left")
        fd_lifespan_figure.sizing_mode = 'stretch_both'
        fd_lifespan_figure.vbar(x=fd1[0], top=fd1[2], width=0.9)
        fd_lifespan_figure.add_tools(software_lifespan_hover)

        fd_column.children[2] = gridplot([fd_failure_figure, fd_lifespan_figure], ncols=2, toolbar_location='right')


        d = {}
        int_lists = list(map(lambda aux: list(map(int, aux)), [fd1[1], fd2[1], fd3[1], fd4[1]]))
        alarms_total = list(zip(list(map(sum, zip(*int_lists))), fd1[0]))

        min_alarms = min(alarms_total)
        max_alarms = max(alarms_total)
        max_critical = fd1[3]['most_alarms']

        d['min_alarms'] = stringify(min_alarms)
        d['max_alarms'] = stringify(max_alarms)
        d['max_critical'] = stringify(max_critical)
        d['shortest_lifespan'] = stringify(fd1[3]['shortest_lifespan'])
        d['longest_lifespan'] = stringify(fd1[3]['longest_lifespan'])
        d['average_lifespan'] = [fd1[3]['average_lifespan']]

        fd_stats_source.data = d

    else:
        td_failure_figure = figure(x_range=td1[0], plot_width=width//2, plot_height=int(height*1.35), title="Failure frequency")
        td_failure_figure.add_layout(Title(text="Expected number of alarms per 100 machines over one month", align="center"), "left")
        td_failure_figure.sizing_mode = 'stretch_both'
        td_failure_source.data = dict(softwares=td1[0], Critical=td1[1], Major=td2[1], Minor=td3[1], Warning=td4[1])
        td_failure_figure.vbar_stack(software_alarm_types, width=0.9, color=['red', 'orange', 'green', 'blue'],
                                           x='softwares', source=td_failure_source, legend=[value(x) for x in software_alarm_types])
        td_failure_figure.legend.location = "top_left"
        td_failure_figure.legend[0].items.sort(reverse=True, key=lambda aux: software_alarm_types.index(aux.label['value']))
        td_failure_figure.add_tools(software_failure_hover)

        td_lifespan_figure = figure(x_range=td1[0], plot_width=width//2, plot_height=int(height*1.35), title="Lifespan")
        td_lifespan_figure.add_layout(Title(text="Average number of days software was in use", align="center"), "left")
        td_lifespan_figure.sizing_mode = 'stretch_both'
        td_lifespan_figure.vbar(x=td1[0], top=td1[2], width=0.9)
        td_lifespan_figure.add_tools(software_lifespan_hover)

        td_column.children[2] = gridplot([td_failure_figure, td_lifespan_figure], ncols=2, toolbar_location='right')


        d = {}
        int_lists = list(map(lambda aux: list(map(int, aux)), [td1[1], td2[1], td3[1], td4[1]]))
        alarms_total = list(zip(list(map(sum, zip(*int_lists))), td1[0]))

        min_alarms = min(alarms_total)
        max_alarms = max(alarms_total)
        max_critical = td1[3]['most_alarms']

        d['min_alarms'] = stringify(min_alarms)
        d['max_alarms'] = stringify(max_alarms)
        d['max_critical'] = stringify(max_critical)
        d['shortest_lifespan'] = stringify(td1[3]['shortest_lifespan'])
        d['longest_lifespan'] = stringify(td1[3]['longest_lifespan'])
        d['average_lifespan'] = [td1[3]['average_lifespan']]

        td_stats_source.data = d


def update_software_view_migrations(attr, old, new):
    """Software view details tab update on dropdown selection"""
    global software_view_migrations_fetched, migrations
    software_selection.label = 'Software version: ' + new

    if not software_view_migrations_fetched:
        try:
            with PSQL_wrapper(psql_config) as psql:
                migrations = global_migrations(psql, critical, major, minor, warning, software, fd_softwares, td_softwares, xd_softwares)
            software_view_migrations_fetched = True
        except:
            print("[WARN] Could not fetch migrations data, make sure your settings are correct")
            return

    software_migrations_source.data = get_migrations_dict(migrations, None, None, filter=new, mode=software_mode_radio.active, software=True)


def update_software_view_radio(attr, old, new):
    """Dropdown button label and data update"""
    label = software_selection.label
    if label.startswith("Software version:"):
        label = label.split(' ')[-1]

    if label != "Software version":
        update_software_view_migrations(attr, old, label)


def update_critical_table_selection(attr, old, new):
    """Updating the currently chosen critical alarms table in settings"""
    global critical, software_view_initialized, software_view_migrations_fetched
    critical = new
    critical_table_selection.label = new
    software_view_initialized = False
    software_view_migrations_fetched = False


def update_major_table_selection(attr, old, new):
    """Updating the currently chosen major alarms table in settings"""
    global major, software_view_initialized, software_view_migrations_fetched
    major = new
    major_table_selection.label = new
    software_view_initialized = False
    software_view_migrations_fetched = False


def update_minor_table_selection(attr, old, new):
    """Updating the currently chosen minor alarms table in settings"""
    global minor, software_view_initialized, software_view_migrations_fetched
    minor = new
    minor_table_selection.label = new
    software_view_initialized = False
    software_view_migrations_fetched = False


def update_warning_table_selection(attr, old, new):
    """Updating the currently chosen warning alarms table in settings"""
    global warning, software_view_initialized, software_view_migrations_fetched
    warning = new
    warning_table_selection.label = new
    software_view_initialized = False
    software_view_migrations_fetched = False


def update_software_table_selection(attr, old, new):
    """Updating the currently chosen software table in settings"""
    global software, software_view_initialized, software_view_migrations_fetched
    software = new
    software_table_selection.label = new
    software_view_initialized = False
    software_view_migrations_fetched = False


def load_csv(attr, old, new):
    """File picker for loading data into a database"""
    try:
        raw_contents = csv_file_source.data['file_contents'][0]
        prefix, b64_contents = raw_contents.split(",", 1)
        file_contents = TextIOWrapper(BytesIO(b64decode(b64_contents)))

        with PSQL_wrapper(psql_config) as psql:
            copy_csv(psql, file_contents, csv_file_source.data['file_name'][0].split('.')[0])
    except:
        print("[INFO] Error loading file contents")


def update_tables_lists(event):
    """Repopulating dropdown menus for table lists"""
    global tables
    with PSQL_wrapper(psql_config) as psql:
        tables = sorted(get_public_tables(psql))
        critical_table_selection.menu = tables
        major_table_selection.menu = tables
        minor_table_selection.menu = tables
        warning_table_selection.menu = tables
        software_table_selection.menu = tables
        adjust_dropdown.menu = tables


def update_dropdowns(event):
    """Repopulating dropdown menus for operators"""
    with PSQL_wrapper(psql_config) as psql:
        operator_selection.menu = sorted(get_operators(psql, software), key=lambda x: int(x.split(' ')[1]))
        software_selection.menu = ['all'] + sorted(get_softwares(psql, software))


def update_defaults(event):
    """Saving current settings to config.ini"""
    new_vals = {}
    new_vals['critical'] = critical_table_selection.value
    new_vals['major']    = major_table_selection.value
    new_vals['minor']    = minor_table_selection.value
    new_vals['warning']  = warning_table_selection.value
    new_vals['software'] = software_table_selection.value
    write_new_defaults('config.ini', new_vals)


def update_adjust_dropdown(attr, old, new):
    """Adjust dropdown label update"""
    adjust_dropdown.label = new


def adjust_alarms_callback(event):
    """Adjust alarms callback"""
    with PSQL_wrapper(psql_config) as psql:
        adjust_alarms(psql, adjust_dropdown.label)


def adjust_software_callback(event):
    """Adjust software callback"""
    with PSQL_wrapper(psql_config) as psql:
        adjust_software(psql, adjust_dropdown.label)


# binding callbacks for various buttons, dropdowns etc
operator_selection.on_change('value', update_operators_view)
operator_date_picker_start.on_change('value', update_operators_view_date)
operator_date_picker_end.on_change('value', update_operators_view_date)

lines_generate_button.on_click(update_operators_view_line_graph)
stacked_generate_button.on_click(update_operators_view_stacked_graph)

fd_generate_button.on_click(partial(update_software_view_graphs, button=1))
td_generate_button.on_click(partial(update_software_view_graphs, button=2))

software_selection.on_change('value', update_software_view_migrations)
software_mode_radio.on_change('active', update_software_view_radio)

csv_file_source.on_change('data', load_csv)

critical_table_selection.on_change('value', update_critical_table_selection)
major_table_selection.on_change('value', update_major_table_selection)
minor_table_selection.on_change('value', update_minor_table_selection)
warning_table_selection.on_change('value', update_warning_table_selection)
software_table_selection.on_change('value', update_software_table_selection)

reload_tables.on_click(update_tables_lists)
repopulate_dropdowns.on_click(update_dropdowns)
save_defaults.on_click(update_defaults)

adjust_dropdown.on_change('value', update_adjust_dropdown)
adjust_alarms_button.on_click(adjust_alarms_callback)
adjust_software_button.on_click(adjust_software_callback)

# running the program
curdoc().title = "Network evolution"
curdoc().add_root(tabs)
