#! /usr/bin/env python2.7

import collections
from copy import deepcopy
import datetime
from dateutil import tz
import re
import os
import sys

from pylab import *

LOG_FILE_FORMAT = 'timesheet-\d\d\-\d\d-\d\d\d\d.log'
LOG_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
NUM_TO_DAY_MAP = {1: 'mon',
                  2: 'tue',
                  3: 'wed',
                  4: 'thu',
                  5: 'fri',
                  6: 'sat',
                  7: 'sun'}
PERCENTAGE_CUTOFF = 5


def get_activities_in_localtime(log_dir='/Users/amacleod/.tt/logs'):
    """Parse the activity logs which are in UTC and convert to local time

    :param str log_dir:   Directory in which the time stamped log files are stored.

    :returns: A dictionary of local time stamps and activity engaged in at that time.
    :rtype:  dict
    """

    log_files = [f for f in os.listdir(log_dir) if re.match(LOG_FILE_FORMAT, f)]
    localtime_activities = {}
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    for f in log_files:
        with open(os.path.join(log_dir, f), 'r') as f_p:
            for entry in f_p.readlines():
                ts, activity = entry[:-1].split(' ')
                try:
                    utc_ts = datetime.datetime.strptime(ts, LOG_TIMESTAMP_FORMAT)
                except ValueError as e:
                    print('Issue converting timestamp: ', ts, ' Format:', LOG_TIMESTAMP_FORMAT)
                    sys.exc_traceback()

                utc_ts = utc_ts.replace(tzinfo=from_zone)
                local_ts = utc_ts.astimezone(to_zone)
                localtime_activities[local_ts.strftime(LOG_TIMESTAMP_FORMAT)] = activity
    return localtime_activities


def get_ordered_activity_timestamps():
    """Return dict of timestamp and activities in reverse order. Order is based on the local timestamp of the activities."""

    ordered_timestamps = collections.OrderedDict(sorted(get_activities_in_localtime().items(), key=lambda t: t[0]))
    ordered_timestamps = [x for x in ordered_timestamps.items()]
    return ordered_timestamps


def get_activity_timings(filter_off=True):
    """A generator which yields a tuple of (activity, year, week number, day of week, total seconds).

    This is the total number of seconds over a continuous period engaged
    in that activity. Day of the weeks is numeric: 7 - Sunday... 1 - Monday.
    Order is in reverse timestamp, that is the most recent activity is listed
    first.

    By default, "Off" activities are filtered from the results.
    """

    ordered_timestamps = get_ordered_activity_timestamps()
    for x in range(len(ordered_timestamps) - 1, 1, -1):
        end_ts, end_activity = ordered_timestamps[x]
        start_ts, start_activity = ordered_timestamps[x - 1]
        if filter_off and start_activity == 'Off':  # Skip the off activity
            continue
        end_time = datetime.datetime.strptime(end_ts, LOG_TIMESTAMP_FORMAT)
        start_time = datetime.datetime.strptime(start_ts, LOG_TIMESTAMP_FORMAT)
        time_diff = end_time - start_time
        time_delta = time_diff.days * 24 * 3600 + time_diff.seconds
        if time_delta > 15 * 3600:  # more then 15 hours
            warning_msg = 'Warning: Probably an issue with activity {0} entry starting {1}, ending {2}'.format(start_activity, start_ts, end_ts)
            hrs = int(time_delta/3600.0)
            mins = int((time_delta - (hrs * 3600.0))/60.0)
            print('{0}: {1} hrs, {2} mins'.format(warning_msg, hrs, mins))
        year, week_number, day_of_week = end_time.isocalendar()
        yield (start_activity, year, week_number, day_of_week, time_delta)


def get_wow_changes(weeks_ago=1):
    """Return the week over week change for the previous full week.

    The statistics are computed from Monday until Sunday. The week over
    week percentages for the last complete week is computed by default
    (ie. weeks_ago=1). Specifying the number of weeks ago will compute
    as a change over the average of that many weeks. This is done in a
    rolling manner.

    If an activity was not engaged in during the previous week, the
    precentage is a 0.0% increase by default.

    :param int weeks_ago:  The number of weeks used to compute the average wow change.

    :returns:  A dictionary of activities and the wow change.
    :rtype: dict
    """

    def get_previous_weekly_tally(weeks_ago, cur_week, weekly_info):
        """Return a cummulative tally of activity times and counts of the specific set of weeks"""

        def compute_weeks_ago_index(cur_week_index, weeks_ago):
            """Compute the week index from the current week the specific number of weeks ago"""
            current_yr, current_week = cur_week_index.split('-')
            prev_week = int(current_week) - weeks_ago
            if prev_week < 1:
                prev_week = 52 + prev_week
                current_yr = int(current_yr)  - 1
            return '{0}-{1}'.format(current_yr, prev_week)

        previous_weekly_tally = {}
        active_week_count = {}
        for i in range(weeks_ago):
            week_index = compute_weeks_ago_index(cur_week, i + 1)
            if week_index in weekly_info:  #  May be no data for this week
                for activity in weekly_info[week_index]:
                    if activity in previous_weekly_tally:
                        previous_weekly_tally[activity]['count'] += weekly_info[week_index][activity]['count']
                        previous_weekly_tally[activity]['time'] += weekly_info[week_index][activity]['time']
                        active_week_count[activity] += 1
                    else:
                        previous_weekly_tally[activity] = {'count': weekly_info[week_index][activity]['count'],
                                                           'time': weekly_info[week_index][activity]['time']}
                        active_week_count[activity] = 1
        for activity in previous_weekly_tally:
            previous_weekly_tally[activity]['count'] = 1.0 * previous_weekly_tally[activity]['count'] / active_week_count[activity]
            previous_weekly_tally[activity]['time'] = 1.0 * previous_weekly_tally[activity]['time'] / active_week_count[activity]
        return previous_weekly_tally

    wow_change = {}
    default_percentage = 0.0
    current_weekly_info = {}
    weekly_info = get_weekly_info()
    for cnt, week in enumerate(sorted(weekly_info.keys())):
        if cnt > weeks_ago:
            wow_change[week] = {}
            for activity in weekly_info[week]:
                current_weekly_info[activity]= {'count': weekly_info[week][activity]['count'],
                                                'time':weekly_info[week][activity]['time']}
                wow_count = default_percentage
                wow_time = default_percentage
                previous_weekly_tally = get_previous_weekly_tally(weeks_ago, week, weekly_info)
                if activity in previous_weekly_tally:
                    cur = current_weekly_info[activity]['count']
                    prev = previous_weekly_tally[activity]['count']
                    if prev >= 1.0:
                        wow_count = 100.0 * (cur - prev) / prev
                    cur = current_weekly_info[activity]['time']
                    prev = previous_weekly_tally[activity]['time']
                    if prev > 1:
                        wow_time = 100.0 * (cur - prev) / prev
                wow_change[week][activity] = {'wow_count': wow_count,
                                              'wow_time': wow_time}

    return wow_change


def get_weekly_info():
    """ Return a dictionary of weekly totals, counts and time in seonds, for each activity engaged during the week.

    Weeks are based on the week of the year (01 - 52) calendar.
    """
    weekly_info = {}
    current_day = -1
    current_week = -1
    for activity, yr, week, day_of_week, time_delta in get_activity_timings():
        if week < 10:
            weekly_key = '{0}-0{1}'.format(yr, week)
        else:
            weekly_key = '{0}-{1}'.format(yr, week)
        if weekly_key not in weekly_info:
            weekly_info[weekly_key] = {}
        if activity not in weekly_info[weekly_key]:
            weekly_info[weekly_key][activity] = {'count': 1,
                                                 'time': time_delta}
        else:
            weekly_info[weekly_key][activity]['count'] += 1
            weekly_info[weekly_key][activity]['time'] += time_delta
    return weekly_info


def print_wow_change(weeks_ago=1):
    wow_changes_info = get_wow_changes(weeks_ago)
    for week in sorted(wow_changes_info.keys()):
        print('Week: {0}'.format(week))
        for activity in sorted(wow_changes_info[week].keys()):
            wow_count = wow_changes_info[week][activity]['wow_count']
            wow_time = wow_changes_info[week][activity]['wow_time']
            print('\t{0:<12s} WoW counts: {1:>6.1f}%\tWow time: {2:>6.1f}%'.format(activity, wow_count, wow_time))


def print_weekly_timings():
    weekly_info = get_weekly_info()
    for week in sorted(weekly_info.keys()):
        print('Week: {0}'.format(week))
        for activity in sorted(weekly_info[week].keys()):
            cnt = weekly_info[week][activity]['count']
            hrs = int(weekly_info[week][activity]['time'] / 3600)
            mins = int(weekly_info[week][activity]['time'] % 60)
            print('\tActivity: {0:<12s} Counts: {1:>3d}\tTime: {2:>3d} hrs, {3:2d} mins'.format(activity, cnt, hrs, mins))


def print_weekly_summary_timings():
    weekly_info = get_weekly_info()
    for week in sorted(weekly_info.keys()):
        total_time = 0.0
        total_count = 0
        for activity in weekly_info[week]:
            total_time += weekly_info[week][activity]['time']
            total_count += weekly_info[week][activity]['count']
        total_hours = int(total_time / 3600)
        total_mins = int(total_time % 60)
        print('Week: {0}\tActivity Counts: {1:>3d}\tWorked: {2:>3d} hrs, {3:>2d} mins'.format(week, total_count, total_hours, total_mins))


def get_overall_actitivity_info():
    """Return an activity summation structure over all time.

    """
    activity_cnts = {'weekday_cnt': 0,
                     'weekend_cnt': 0}
    activities = {}
    total = 0
    current_day = -1
    current_week = -1
    for activity, yr, week, day_of_week, time_delta in get_activity_timings():
        total += time_delta
        if activity not in activities.keys():
            activities[activity] = {'total_time': 0,
                                    'weekday_timings': [],
                                    'weekday_count': 0,
                                    'weekend_timings': [],
                                    'weekend_count': 0}
        activities[activity]['total_time'] += time_delta
        if day_of_week in range(1,6):  # Weekday
            activities[activity]['weekday_timings'].append(time_delta)
            activities[activity]['weekday_count'] += 1
            if day_of_week != current_day or week != current_week:
                # Assumption is we don't skip a year of tracking
                current_day = day_of_week
                current_week = week
                activity_cnts['weekday_cnt'] += 1
        else:  # Weekend
            activities[activity]['weekend_timings'].append(time_delta)
            activities[activity]['weekend_count'] += 1
            if day_of_week != current_day or week != current_week:
                # Assumption is we don't skip a year of tracking
                current_day = day_of_week
                current_week = week
                activity_cnts['weekend_cnt'] += 1

    for activity in activities.keys():
        activities[activity]['percentage_totals'] = activities[activity]['total_time']*100.0/total
    activity_info = {'activities': activities,
                     'counts': activity_cnts}
    return activity_info


def daily_statistics():
    # Initialize returned data structure
    daily_statistics = {}
    current_day = 0
    for day in NUM_TO_DAY_MAP.keys():
        daily_statistics[day] = {'context_switches': 0,
                                 'day_cnts': 0,
                                 'total_time': 0}
    for activity, yr, week, day_of_week, time_delta in get_activity_timings():
        if day_of_week != current_day:
            try:
                daily_statistics[day_of_week]['day_cnts'] += 1
            except ValueError:
                # First entry
                pass
            current_day = day_of_week
        daily_statistics[day_of_week]['context_switches'] += 1
        daily_statistics[day_of_week]['total_time'] += time_delta
        if activity not in daily_statistics[day_of_week].keys():
            daily_statistics[day_of_week][activity] = {'total_time': time_delta,
                                                         'cnt': 1}
        else:
            daily_statistics[day_of_week][activity]['total_time'] += time_delta
            daily_statistics[day_of_week][activity]['cnt'] += 1
    return daily_statistics


def show_percentage_pie_plot():
    # Get data
    activity_info = get_overall_actitivity_info()
    activities = activity_info['activities']

    # make a square figure and axes
    figure(1, figsize=(12,12))
    ax = axes([0.1, 0.1, 0.8, 0.8])


    # The slices will be ordered and plotted counter-clockwise.
    key_list = [k for k in activities.keys() if activities[k]['percentage_totals'] > PERCENTAGE_CUTOFF]
    labels = key_list
    fracs = [activities[k]['percentage_totals'] for k in key_list]
    explode = [0.05 for k in key_list]

    pie(fracs, explode=explode, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
                    # The default startangle is 0, which would start
                    # the Frogs slice on the x-axis.  With startangle=90,
                    # everything is rotated counter-clockwise by 90 degrees,
                    # so the plotting starts on the positive y-axis.

    title('Acitiviy Log', bbox={'facecolor':'0.8', 'pad':5})

    show()


def show_wow_activity_plot(activity='Coding', weeks=4):
    """Display week-over-week percentag change line plot for the given activity.

    Note that the display is capped at maximum increase of 1000%.

    :param str activity:  The activity to plot.
    :param int weeks:     The number of preceding weeks used in the week-over-week
                          calculation.
    """
    percentage_cap = 1000.0
    wow_changes = get_wow_changes(weeks_ago=weeks)

    # Order based on week
    week_labels = sorted(wow_changes.keys())
    week_axis = arange(0.0, len(week_labels), 1)
    xticks(week_axis, week_labels, rotation='vertical')

    # Build up the Y-axis data set
    wow_cnt_change = []
    wow_time_change = []
    for week in week_labels:
        if activity in wow_changes[week]:
            # Cap maximum
            if wow_changes[week][activity]['wow_count'] > percentage_cap:
                wow_cnt_change.append(percentage_cap)
            else:
                wow_cnt_change.append(wow_changes[week][activity]['wow_count'])
            if wow_changes[week][activity]['wow_time'] > percentage_cap:
                wow_time_change.append(percentage_cap)
            else:
                wow_time_change.append(wow_changes[week][activity]['wow_time'])
        else:
            wow_cnt_change.append(0.0)
            wow_time_change.append(0.0)

    xlabel('Week')
    ylabel('Percentage')
    title('Week over Week {0} Activity Change (Capped at 1000%)'.format(activity))
    plot(week_axis, wow_cnt_change)
    plot(week_axis, wow_time_change)
    grid(True)
    rcParams['figure.figsize'] = 20, 10  # Make width=20 inches, height= 10 inches
    show()


def plot_day_activity_percentages():
    # Get the list of activities which consume more than the cutoff percentage
    activity_info = get_overall_actitivity_info()
    activities = activity_info['activities']
    activity_list = [k for k in activities.keys() if activities[k]['percentage_totals'] > PERCENTAGE_CUTOFF]

    # Initialize our plot data structure
    daily_stats = daily_statistics()
    plot_data = {}
    for day in NUM_TO_DAY_MAP:
        plot_data[day] = {}
        for activity in activity_list:
            percentage = 0.0
            if daily_stats[day].get(activity):
                percentage = 100.0 * daily_stats[day][activity]['total_time']/daily_stats[day]['total_time']
            plot_data[day][activity] = percentage

    # Order based on day
    day_labels = sorted(plot_data.keys())
    day_axis = arange(0, len(day_labels), 1)
    xticks(day_axis, NUM_TO_DAY_MAP.values(), rotation='vertical')

    xlabel('Day')
    ylabel('Time Percentage')
    title('Daily Percentage Of Time Spent On Activity')

    # Plot each activity
    for activity in activity_list:
        y_data = []
        for day in day_labels:
            y_data.append(plot_data[day][activity])
        plot(day_axis, y_data, label=activity)

    grid(True)
    rcParams['figure.figsize'] = 20, 10  # Make width=20 inches, height= 10 inches
    legend()
    show()


def get_activity_statistics():
    def average_mins(timing_list):
        cnt = len(timing_list)
        if cnt == 0:
            return 0
        else:
            return int(sum(timing_list) / cnt / 60.0)

    def medium_mins(timing_list):
        cnt = len(timing_list)
        if cnt == 0:
            return 0
        else:
            mid = int(cnt/2)
            return int(sorted(timing_list)[mid] / 60.0)

    activity_info = get_overall_actitivity_info()
    activities = activity_info['activities']
    activity_counts = activity_info['counts']
    print('Weekday Stats:')
    print('==============\n')
    print('Activity | cnt |  avg |  medium')
    print('         |     | mins |    mins')
    print('---------+-----+------+--------')
    total_work_time = 0
    for activity in activities.keys():
        print('{0:<8} | {1:>3} | {2:>4} | {3:>7}'.format(activity,
                                           activities[activity]['weekday_count'],
                                           average_mins(activities[activity]['weekday_timings']),
                                           medium_mins(activities[activity]['weekday_timings'])))

        print('---------+-----+------+--------')
        total_work_time += sum(activities[activity]['weekday_timings'])
    print('Total days: {0}'.format(activity_counts['weekday_cnt']))
    print('Average work day (mins): {0}'.format(int(total_work_time / activity_counts['weekday_cnt'] / 60)))
    print('\nWeekend Stats:')
    print('==============\n')
    print('Activity | cnt |  avg |  medium')
    print('         |     | mins |    mins')
    print('---------+-----+------+--------')
    total_work_time = 0
    for activity in activities.keys():
        print('{0:<8} | {1:>3} | {2:>4} | {3:>7}'.format(activity,
                                           activities[activity]['weekend_count'],
                                           average_mins(activities[activity]['weekend_timings']),
                                           medium_mins(activities[activity]['weekend_timings'])))
        print('---------+-----+------+--------')
        total_work_time += sum(activities[activity]['weekend_timings'])
    print('Total days: {0}'.format(activity_counts['weekend_cnt']))
    print('Average work day (mins): {0}'.format(int(total_work_time / activity_counts['weekend_cnt'] / 60)))


def get_daily_statistics():
    daily_stats = daily_statistics()
    activities = set([])
    for day in NUM_TO_DAY_MAP.keys():
        activities = activities.union(daily_stats[day].keys())
    activities = activities.difference(set(['day_cnts', 'total_time', 'context_switches']))
    activities = sorted(list(activities))
    print('Day | Activity | Percenatage')
    sep = ('----+----------+------------')
    for day in NUM_TO_DAY_MAP.keys():
        print(sep)
        sep = ('    +----------+------------')
        day_string = '{0} '.format(NUM_TO_DAY_MAP[day])
        for activity in activities:
            try:
                percentage = 100.0 * daily_stats[day][activity]['total_time']/daily_stats[day]['total_time']
                # print(daily_stats[day][activity]['total_time'])
                # print(daily_stats[day]['total_time'])
            except KeyError:
                percentage = 0.0
            print('{0}|{1:10}|{2:>6.2f} %'.format(day_string, activity, percentage))
            day_string = '    '
            # if activity != activities[-1]:
            #     print(sep)
            print(sep)
        ctx_sw = 1.0*daily_stats[day]['context_switches']/daily_stats[day]['day_cnts']
        print('{0}|{1:10}|{2:>6.2f}'.format(day_string, 'ctx_sw', ctx_sw))
        print(sep)
        work_tm = 1.0*daily_stats[day]['total_time']/daily_stats[day]['day_cnts']/60.0
        print('{0}|{1:10}|{2:>6.2f} mins'.format(day_string, 'work_tm', work_tm))
        sep = ('----+----------+------------')
    print(sep)

if __name__ == '__main__':
    get_daily_statistics()
