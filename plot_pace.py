import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3

# Connect to SQLite database
conn = sqlite3.connect('vec.sqlite')
cur = conn.cursor()

# Set filtering parameters
event_id = 1
car_class = 'GT3'

# Get data from SQLite database
timing = pd.read_sql_query('SELECT driver_id,lap,lap_time FROM timing WHERE event_id = ?', conn, params=(event_id,))
results = pd.read_sql_query('SELECT driver_id,class FROM results WHERE event_id = ?', conn, params=(event_id,))
drivers = pd.read_sql_query('SELECT id,name FROM drivers', conn)

df = timing.merge(drivers,left_on='driver_id',right_on='id').merge(results,on='driver_id')
df_class = df[df['class'] == car_class]
df_filtered = df_class[df_class['lap_time'] < df_class['lap_time'].quantile(0.95)]
ranks = df_filtered.groupby('name')['lap_time'].median().sort_values().index

# Plot
sns.set_style('whitegrid')
sns.catplot(x='lap_time',y='name',data=df_filtered,kind='box',order=ranks,showfliers = False)
plt.xlabel('Lap time')
plt.ylabel('Driver')
plt.tick_params(axis='both', labelsize=7)
plt.show()