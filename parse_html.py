import pandas as pd
import requests
from io import StringIO
import sqlite3
import re

def parse(url: str) -> None:
    """Parses the requested page.

    Args:
        url (str): The url to parse. Must be from the simracing.club ResultsSystem page.
        The HTML like looks like this: https://simracing.club/ResultsSystem/vec/s17/d1r1.html
            r - round
            d - division
            s - season
            vec - series
    """
    html = requests.get(url).text

    # Connect to SQLite database
    conn = sqlite3.connect('vec.sqlite')
    cur = conn.cursor()

    # Parse event info. There is only one table with this content, so locating it is simple.
    df_list = pd.read_html(StringIO(html), match='Server Name')
    if len(df_list) > 1:
        print('Error: unexpected html structure (event info)')
        exit()
    else:
        df = df_list[0]
        date = df.iloc[1, 1]
        track = df.iloc[2, 1]
        numbers = re.findall('[0-9]+', url) # extract division, season and race information from the url string
        season = int(numbers[0])
        division = int(numbers[1])
        race = int(numbers[2])
        cur.execute('''INSERT OR IGNORE INTO events (season, division, race, date, track) VALUES (?, ?, ?, ?, ?)''',
                    (season, division, race, date, track))

    # Get generated event_id for future use
    cur.execute('''SELECT id FROM events WHERE date == ?''', (date,))
    event_id = cur.fetchone()[0]

    # Parse driver names and results
    # Driver names are tricky because one team has up to three drivers, but we are interested in the individual
    # performances. Scrips splits the column with driver names into pieces and uses the generated driver IDs to
    # normalize the results table.
    df_list = pd.read_html(StringIO(html), match='Total time')
    if len(df_list) > 1:
        print('Error: unexpected html structure (driver names and results)')
        exit()
    else:
        df = df_list[0]

        # Drivers
        drivers_all = df['Drivers']
        for d in drivers_all:  # d is a string of multiple drivers in one team separated by a comma
            drivers_team = d.split(',')
            for t in drivers_team:  # t is a dirty string with a single driver
                driver = t.strip().title() # make formatting consistent
                cur.execute('''INSERT OR IGNORE INTO drivers (name) VALUES (?)''', (driver,))

        # Results
        for i in range(len(df)):  # for all entries in the race
            # need conversion otherwise the type is numpy int and SQLite saves it as BLOB
            class_pos = int(df['In Class'][i])
            car_num = int(df['Car'][i])
            car_class = df['Class'][i]
            team = df['Team'][i]
            car = df['Car Model'][i]
            drivers_team = drivers_all[i].split(',')
            for t in drivers_team:  # for all drivers in every team
                driver = t.strip().title()
                cur.execute('''SELECT id FROM drivers WHERE name = ?''', (driver,))  # get driver_id
                driver_id = cur.fetchone()[0]
                cur.execute('''INSERT OR IGNORE INTO results (event_id, driver_id, class_pos, car_num, class, team, car)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''', (event_id, driver_id, class_pos, car_num, car_class, team, car))

    # Parse stint info
    # Stint contains info on when every driver was in the specific car. These tables are found with the "match"
    # parameter. Code loops through tables, extracts the first and final laps of stints and maps them with the
    # driver IDs.
    df_list = pd.read_html(StringIO(html), match='Startlap', skiprows=1)
    if len(df_list) == 0:
        print('Error: unexpected html structure (stint info)')
        exit()
    else:
        for df in df_list:
            for i in range(len(df)):
                driver = df['Driver'][i]
                if pd.isna(driver): # driver info can be empty if server crashes during the race
                    continue
                else:
                    driver = driver.strip().title()
                    cur.execute('''SELECT id FROM drivers WHERE name = ?''', (driver,))  # get driver_id
                    driver_id = cur.fetchone()[0]
                    lap_start = df['Startlap'][i][1:] # get i-th element from Startlap column and remove starting L to get an integer
                    lap_end = df['Ending lap'][i][1:]
                    cur.execute('''INSERT OR IGNORE INTO stints (event_id, driver_id, lap_start, lap_end)
                                VALUES (?, ?, ?, ?)''', (event_id, driver_id, lap_start, lap_end))

    # Parse timing info
    # This bit is the most difficult because:
    # 1) Qualifying and Race session HTML tables have the same structure, and we are only interested in the Race session.
    # 2) Only information about the first driver in every car is available. The script has to trace back to the team,
    # drivers in that team, laps covered by these drivers, and finally back to live timing data to map this information
    # properly.
    # 3) The data is not perfect, some lap times are missing or invalidated.
    df_list = pd.read_html(StringIO(html), match='Fuel level')
    for df in df_list:
        if len(df) < 20:  # arbitrary number of laps to remove timing data from qualification sessions
            continue
        else:  # for all teams (every table includes timing data for one team)
            driver = df.columns[0][0] # driver name is the first element in every column name string
            driver = driver.strip().title()
            cur.execute('''SELECT id FROM drivers WHERE name = ?''', (driver,))  # get driver_id from the HTML table
            driver_id = cur.fetchone()[0]

            cur.execute('''SELECT car_num FROM results WHERE driver_id = ? AND event_id = ?''',
                        (driver_id, event_id))  # get car_num for this driver. It assumes the car number is unique for any event
            car_num = cur.fetchone()[0]

            cur.execute('''SELECT driver_id FROM results WHERE car_num = ? AND event_id = ?''',
                        (car_num, event_id))  # get all driver_ids for this team
            drivers_in_team = cur.fetchall()
            drivers_in_team = [i[0] for i in drivers_in_team] # convert a list of tuples to list

            for j in range(len(df)):
                lap_time = df.iloc[j,5]
                if lap_time == '00:00.---': # incomplete or invalid lap
                    continue # discard these entries for simplicity
                else:
                    lap_time = sum(x * float(t) for x, t in zip([60,1], lap_time.split(":"))) # convert MM:SS.SSS string to seconds

                lap = int(df.iloc[j, 0])
                fuel = float(df.iloc[j, 1][:-1])/100

                cur.execute('''SELECT driver_id FROM stints WHERE event_id = ? AND lap_start <= ? AND lap_end >= ?''',
                            (event_id, lap, lap)) # get all driver_ids on a specific lap
                driver_id = cur.fetchall()
                driver_id = [i[0] for i in driver_id] # convert a list of tuples to list
                current_driver = list(set(drivers_in_team).intersection(driver_id)) # find the driver in the car for a specific lap
                if len(current_driver) == 0: # empty list means driver who started the race retired before making a single pit stop
                    current_driver = drivers_in_team[0]
                elif len(current_driver) > 1: # unexpected result - an intersection should have only one driver
                    print('Error: unexpected result when working on live timing data')
                    exit()
                else:
                    current_driver = current_driver[0]

                cur.execute('''INSERT OR IGNORE INTO timing (event_id, driver_id, lap, lap_time, fuel)
                            VALUES (?, ?, ?, ?, ?)''', (event_id, current_driver, lap, lap_time, fuel))

    # Commit and close the connection
    conn.commit()
    cur.close()