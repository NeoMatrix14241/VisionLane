import pandas as pd
import numpy as np
# Original data as CSV string
csv_data = """
Paper Size,Width (in),Height (in),DPI,Width (px),Height (px)
A0,33.11,46.81,150,4967,7021
A0,33.11,46.81,300,9933,14043
A0,33.11,46.81,600,19866,28087
A1,23.39,33.11,150,3508,4967
A1,23.39,33.11,300,7017,9933
A1,23.39,33.11,600,14034,19866
A2,16.54,23.39,150,2481,3508
A2,16.54,23.39,300,4961,7017
A2,16.54,23.39,600,9922,14034
A3,11.69,16.54,150,1753,2481
A3,11.69,16.54,300,3508,4961
A3,11.69,16.54,600,7016,9922
A4,8.27,11.69,150,1240,1754
A4,8.27,11.69,300,2481,3508
A4,8.27,11.69,600,4962,7016
A5,5.83,8.27,150,875,1240
A5,5.83,8.27,300,1750,2481
A5,5.83,8.27,600,3500,4962
A6,4.13,5.83,150,620,875
A6,4.13,5.83,300,1240,1750
A6,4.13,5.83,600,2480,3500
Letter,8.5,11,150,1275,1650
Letter,8.5,11,300,2550,3300
Letter,8.5,11,600,5100,6600
Legal,8.5,14,150,1275,2100
Legal,8.5,14,300,2550,4200
Legal,8.5,14,600,5100,8400
Tabloid,11,17,150,1650,2550
Tabloid,11,17,300,3300,5100
Tabloid,11,17,600,6600,10200
Executive,7.25,10.5,150,1087,1575
Executive,7.25,10.5,300,2175,3150
Executive,7.25,10.5,600,4350,6300
B4,9.84,13.9,150,1476,2085
B4,9.84,13.9,300,2952,4173
B4,9.84,13.9,600,5904,8346
B5,6.93,9.84,150,1039,1476
B5,6.93,9.84,300,2079,2952
B5,6.93,9.84,600,4157,5904
B6,4.92,6.93,150,738,1039
B6,4.92,6.93,300,1476,2079
B6,4.92,6.93,600,2952,4157
C4,9.02,12.76,150,1353,1914
C4,9.02,12.76,300,2706,3829
C4,9.02,12.76,600,5412,7658
C5,6.38,9.02,150,957,1353
C5,6.38,9.02,300,1914,2706
C5,6.38,9.02,600,3829,5412
DL,4.33,8.66,150,650,1299
DL,4.33,8.66,300,1299,2598
DL,4.33,8.66,600,2598,5197
"""
# Load into DataFrame
from io import StringIO
df = pd.read_csv(StringIO(csv_data))
# Extract unique paper sizes with dimensions
paper_dimensions = df.groupby("Paper Size")[["Width (in)", "Height (in)"]].first().reset_index()
# Create DPI values from 1 to 1200
dpi_values = np.arange(1, 9001)
# Generate new data
generated_data = []
for _, row in paper_dimensions.iterrows():
    for dpi in dpi_values:
        width_px = round(row["Width (in)"] * dpi)
        height_px = round(row["Height (in)"] * dpi)
        generated_data.append([
            row["Paper Size"],
            row["Width (in)"],
            row["Height (in)"],
            dpi,
            width_px,
            height_px
        ])
# Create expanded DataFrame
expanded_df = pd.DataFrame(generated_data, columns=["Paper Size", "Width (in)", "Height (in)", "DPI", "Width (px)", "Height (px)"])
# Save to CSV if desired
expanded_df.to_csv("uniform_data.csv", index=False)
print(expanded_df.head())
