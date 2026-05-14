#!/usr/bin/env python3

import sys
import csv
from datetime import datetime

# CSV setup
csv_filename = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
csv_file = open(csv_filename, 'w', newline='')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(['Time', 'AZ_Actual', 'AZ_Target', 'EL_Actual', 'EL_Target'])
csv_file.flush()

# Print to stderr so step.py can capture it
print(f"[LOG] Logging to {csv_filename}", file=sys.stderr, flush=True)

try:
    for line in sys.stdin:
        line = line.strip()
        
        if not line or not line.startswith('#'):
            continue
        
        try:
            data = line[1:].split(',')
            if len(data) == 4:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                csv_writer.writerow([timestamp] + data)
                csv_file.flush()
        except Exception as e:
            pass

except KeyboardInterrupt:
    pass

csv_file.close()