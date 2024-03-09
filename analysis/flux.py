import matplotlib.pyplot as plt
import pandas as pd

#Load the CSV data into a DataFrame
data = pd.read_csv('./data.csv')

#Filter out bodies with flux of 255 and type 'blackhole'
filtered_data = data[(data['flux'] != 255) & (data['type'] != 'blackhole')]

#Group the filtered data by the 'body' column
grouped_data = filtered_data.groupby('body')

#Create a time series line chart for units with a change in flux
plt.figure(figsize=(12, 6))
for body, group in grouped_data:
    flux_diff = group['flux'].diff().fillna(0)
    if (flux_diff != 0).any():
        # mooth the flux data using a 5-point moving average
        smoothed_flux = group['flux'].rolling(window=5, min_periods=1).mean()
        plt.plot(group['observation'], smoothed_flux, label=f'Body {body}')

plt.xlabel('Observation')
plt.ylabel('Smoothed Flux')
plt.title('Smoothed Flux Over Observation for Units with Change in Flux')
plt.grid(True)
plt.show()
