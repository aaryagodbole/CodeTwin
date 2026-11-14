# CodeTwin AI study v2 -- results

## Subjects

| Project | Mode | Changes | Calib | Test | KLoC | Test files | Suite (s) | Affected | Killed mutants | Period |
|---|---|---|---|---|---|---|---|---|---|---|
| lang_javascript | history | 21 | 8 | 13 | 38.7 | 33.7 | 90.0 | 6.8 | 0 | 2018-08-28 to 2023-10-06 |
| lang_rust | history | 96 | 38 | 58 | 117.3 | 34.3 | 395.5 | 3.7 | 0 | 2017-04-12 to 2025-01-13 |
| lang_go | history | 55 | 22 | 33 | 61.8 | 32.2 | 58.4 | 4.2 | 0 | 2018-10-11 to 2023-01-13 |

Skipped changes: {"lang_javascript": {"no source change / no tests": 20}, "lang_rust": {}, "lang_go": {}}

## Selection quality (HIST)

| Technique | Test red % | Time red % | Precision | Recall | Safe % | Mutants detected % | Fault-safe % | NameRTS-GT safe % |
|---|---|---|---|---|---|---|---|---|
| base:File coverage | 80.2 [76.0, 84.1] | 76.2 [71.0, 81.2] | 0.77 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| base:Function coverage | 87.1 [83.9, 89.9] | 84.1 [79.8, 88.2] | 0.94 | 0.982 | 95.2 [90.4, 99.0] | -- (0/0) | -- | 100.0 |
| base:Hybrid | 75.5 [70.0, 80.6] | 70.8 [64.5, 76.9] | 0.72 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| base:Line coverage | 88.0 [84.9, 90.7] | 84.9 [80.7, 88.9] | 0.97 | 0.971 | 92.3 [86.5, 97.1] | -- (0/0) | -- | 100.0 |
| base:Name matching | 89.2 [86.7, 91.4] | 86.8 [83.0, 90.2] | 0.80 | 0.795 | 65.4 [56.7, 74.0] | -- (0/0) | -- | 100.0 |
| base:Retest-all | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| base:Static import | 77.6 [72.0, 82.9] | 72.3 [65.9, 78.7] | 0.78 | 0.898 | 83.7 [76.0, 90.4] | -- (0/0) | -- | 100.0 |
| budget:0.25:CodeTwin | 64.0 [61.7, 66.3] | 74.1 [72.0, 76.0] | 0.35 | 0.926 | 82.7 [75.0, 89.4] | -- (0/0) | -- | 100.0 |
| crc:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:plain | 73.1 [67.1, 78.9] | 69.2 [62.5, 75.6] | 0.67 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:plain | 78.3 [72.1, 84.1] | 75.2 [68.5, 81.5] | 0.87 | 0.989 | 97.1 [93.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:plain | 88.6 [85.4, 91.4] | 85.3 [81.0, 89.4] | 0.98 | 0.911 | 83.7 [76.0, 90.4] | -- (0/0) | -- | 100.0 |
| win:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| win:0.05:plain | 76.2 [69.8, 82.0] | 72.8 [66.0, 79.2] | 0.79 | 0.990 | 97.1 [93.3, 100.0] | -- (0/0) | -- | 100.0 |
| win:0.1:plain | 78.5 [72.1, 84.3] | 75.3 [68.8, 81.7] | 0.87 | 0.983 | 96.2 [92.3, 99.0] | -- (0/0) | -- | 100.0 |
| win:0.2:plain | 89.0 [86.1, 91.5] | 86.1 [82.0, 89.9] | 0.97 | 0.929 | 86.5 [79.8, 92.3] | -- (0/0) | -- | 100.0 |
| aci:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:plain | 73.0 [66.2, 79.6] | 69.8 [62.6, 76.8] | 0.80 | 0.991 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:plain | 80.1 [74.2, 85.5] | 77.1 [70.7, 83.2] | 0.89 | 0.977 | 94.2 [89.4, 98.1] | -- (0/0) | -- | 100.0 |
| aci:0.2:plain | 89.0 [86.2, 91.5] | 86.1 [82.1, 90.0] | 0.97 | 0.924 | 85.6 [78.8, 92.3] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:filecov | 73.1 [67.0, 78.9] | 69.2 [62.5, 75.5] | 0.67 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:filecov | 75.1 [69.0, 80.7] | 71.1 [64.4, 77.5] | 0.77 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:filecov | 84.5 [81.0, 87.6] | 80.5 [76.0, 85.0] | 0.88 | 0.979 | 94.2 [89.4, 98.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:hybrid | 73.1 [67.0, 78.9] | 69.2 [62.5, 75.4] | 0.67 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:hybrid | 73.7 [67.3, 79.7] | 69.4 [62.4, 76.1] | 0.76 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:hybrid | 83.1 [79.0, 86.8] | 79.0 [73.7, 84.0] | 0.88 | 0.979 | 94.2 [89.4, 98.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:full | 73.1 [67.1, 78.8] | 69.2 [62.4, 75.5] | 0.67 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:full | 65.4 [57.4, 73.1] | 62.5 [54.2, 70.6] | 0.74 | 0.997 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:full | 66.2 [58.5, 73.8] | 62.9 [54.8, 70.5] | 0.77 | 0.979 | 94.2 [89.4, 98.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:filecov | 71.7 [65.5, 77.5] | 67.7 [60.9, 74.1] | 0.66 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:filecov | 75.9 [69.6, 81.7] | 72.7 [65.9, 79.2] | 0.82 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:filecov | 84.5 [80.7, 88.1] | 81.5 [76.7, 85.9] | 0.90 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:hybrid | 69.3 [63.0, 75.4] | 64.9 [57.7, 71.8] | 0.63 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:hybrid | 73.5 [66.5, 79.8] | 69.9 [62.5, 76.8] | 0.79 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:hybrid | 82.1 [77.4, 86.3] | 78.6 [73.1, 84.0] | 0.87 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:full | 30.6 [22.8, 38.6] | 26.4 [19.5, 33.9] | 0.34 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:full | 33.7 [25.1, 42.2] | 30.3 [22.3, 38.3] | 0.47 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:full | 37.4 [28.7, 46.1] | 34.0 [25.9, 42.6] | 0.50 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:filecov | 71.1 [64.9, 77.1] | 67.1 [60.4, 73.5] | 0.65 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:filecov | 74.7 [68.3, 80.5] | 71.5 [64.7, 78.0] | 0.78 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:filecov | 82.9 [79.0, 86.5] | 79.8 [75.0, 84.4] | 0.85 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:hybrid | 68.2 [61.5, 74.5] | 63.8 [56.6, 70.9] | 0.63 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:hybrid | 71.7 [64.9, 78.1] | 68.2 [60.7, 75.4] | 0.75 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:hybrid | 79.9 [75.0, 84.5] | 76.4 [70.5, 81.9] | 0.83 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:full | 13.3 [8.0, 19.1] | 10.9 [6.4, 15.8] | 0.22 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:full | 15.5 [9.4, 22.1] | 14.0 [8.3, 20.2] | 0.28 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:full | 19.7 [12.9, 26.9] | 18.3 [11.7, 25.2] | 0.33 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:filecov | 69.7 [62.9, 76.2] | 65.7 [58.5, 72.6] | 0.70 | 0.998 | 99.0 [97.1, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:filecov | 75.8 [69.8, 81.4] | 71.7 [65.2, 78.0] | 0.78 | 0.993 | 97.1 [93.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:filecov | 84.0 [80.3, 87.3] | 79.7 [74.8, 84.4] | 0.88 | 0.972 | 93.3 [88.5, 97.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:hybrid | 68.1 [61.1, 74.7] | 63.6 [56.2, 70.9] | 0.69 | 0.998 | 99.0 [97.1, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:hybrid | 73.8 [67.4, 79.8] | 69.4 [62.4, 76.1] | 0.76 | 0.993 | 97.1 [93.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:hybrid | 82.1 [77.6, 86.1] | 77.4 [71.7, 82.8] | 0.86 | 0.972 | 93.3 [88.5, 98.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:full | 59.3 [51.1, 67.3] | 56.1 [47.9, 64.4] | 0.66 | 0.998 | 99.0 [97.1, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:full | 63.4 [55.2, 71.4] | 60.5 [52.2, 68.8] | 0.73 | 0.993 | 97.1 [93.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:full | 72.0 [64.6, 78.9] | 69.1 [61.4, 76.4] | 0.81 | 0.972 | 93.3 [88.5, 98.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:filecov | 71.5 [64.4, 78.0] | 68.2 [60.9, 75.3] | 0.76 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:filecov | 77.2 [71.0, 82.9] | 74.1 [67.5, 80.5] | 0.83 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:filecov | 84.5 [80.7, 88.0] | 81.5 [76.7, 85.9] | 0.90 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:hybrid | 69.4 [62.1, 76.2] | 65.8 [58.2, 73.3] | 0.74 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:hybrid | 74.8 [68.3, 80.9] | 71.2 [64.2, 78.1] | 0.80 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:hybrid | 82.1 [77.5, 86.3] | 78.6 [73.0, 83.8] | 0.87 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:full | 31.0 [23.0, 39.4] | 27.4 [19.9, 35.3] | 0.42 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:full | 34.1 [25.7, 42.7] | 30.7 [22.8, 39.0] | 0.47 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:full | 37.4 [29.0, 46.2] | 34.0 [25.8, 42.3] | 0.50 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:filecov | 70.4 [63.5, 76.9] | 67.0 [59.6, 73.9] | 0.72 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:filecov | 75.5 [69.3, 81.2] | 72.4 [65.9, 78.7] | 0.78 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:filecov | 83.2 [79.3, 87.0] | 80.2 [75.4, 84.9] | 0.85 | 0.986 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:hybrid | 67.7 [60.3, 74.7] | 64.1 [56.3, 71.6] | 0.70 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:hybrid | 72.6 [66.0, 78.8] | 69.1 [61.8, 76.1] | 0.76 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:hybrid | 80.3 [75.4, 84.8] | 76.9 [71.0, 82.4] | 0.83 | 0.986 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:full | 12.1 [6.8, 17.9] | 10.3 [5.6, 15.5] | 0.23 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:full | 15.5 [9.3, 22.3] | 14.0 [8.3, 20.2] | 0.28 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:full | 20.0 [13.3, 27.3] | 18.7 [12.1, 25.9] | 0.33 | 0.986 | 98.1 [95.2, 100.0] | -- (0/0) | -- | 100.0 |

## Budget mode (HIST, recall)

| Budget | CodeTwin | Coverage-ranked | Random |
|---|---|---|---|
| 0.1 | 0.846 [0.792, 0.896] | 0.848 [0.794, 0.897] | 0.736 [0.671, 0.799] |
| 0.25 | 0.926 [0.890, 0.958] | 0.926 [0.890, 0.958] | 0.777 [0.722, 0.831] |
| 0.5 | 0.978 [0.960, 0.993] | 0.978 [0.960, 0.993] | 0.861 [0.822, 0.897] |

## Calibration per project

| Project | alpha | lambda | feasible | n calib | abstain file | abstain line |
|---|---|---|---|---|---|---|
| lang_javascript | 0.01 | -1.000 | False | 8 | 61.5 | 69.2 |
| lang_javascript | 0.05 | -1.000 | False | 8 | 61.5 | 69.2 |
| lang_javascript | 0.1 | -1.000 | False | 8 | 61.5 | 69.2 |
| lang_javascript | 0.2 | 0.395 | True | 8 | 61.5 | 69.2 |
| lang_rust | 0.01 | -1.000 | False | 38 | 94.8 | 63.8 |
| lang_rust | 0.05 | 0.023 | True | 38 | 94.8 | 63.8 |
| lang_rust | 0.1 | 0.066 | True | 38 | 94.8 | 63.8 |
| lang_rust | 0.2 | 0.977 | True | 38 | 94.8 | 63.8 |
| lang_go | 0.01 | -1.000 | False | 22 | 51.5 | 45.5 |
| lang_go | 0.05 | 0.395 | True | 22 | 51.5 | 45.5 |
| lang_go | 0.1 | 0.632 | True | 22 | 51.5 | 45.5 |
| lang_go | 0.2 | 0.971 | True | 22 | 51.5 | 45.5 |

## Abstention rates (pooled)

```
{
 "0.01:file:HIST": 0.7692307692307693,
 "0.01:file:NRTS": null,
 "0.01:line:HIST": 0.5865384615384616,
 "0.01:line:NRTS": null,
 "0.05:file:HIST": 0.7692307692307693,
 "0.05:file:NRTS": null,
 "0.05:line:HIST": 0.5865384615384616,
 "0.05:line:NRTS": null,
 "0.1:file:HIST": 0.7692307692307693,
 "0.1:file:NRTS": null,
 "0.1:line:HIST": 0.5865384615384616,
 "0.1:line:NRTS": null,
 "0.2:file:HIST": 0.7692307692307693,
 "0.2:file:NRTS": null,
 "0.2:line:HIST": 0.5865384615384616,
 "0.2:line:NRTS": null
}
```

## Risk-based abstention rates (r(c) > alpha)

```
{
 "crc:0.01": {
  "HIST": 0.0,
  "NRTS": null
 },
 "win:0.01": {
  "HIST": 0.0,
  "NRTS": null
 },
 "aci:0.01": {
  "HIST": 0.0,
  "NRTS": null
 },
 "crc:0.05": {
  "HIST": 0.0,
  "NRTS": null
 },
 "win:0.05": {
  "HIST": 0.1346153846153846,
  "NRTS": null
 },
 "aci:0.05": {
  "HIST": 0.15384615384615385,
  "NRTS": null
 },
 "crc:0.1": {
  "HIST": 0.14423076923076922,
  "NRTS": null
 },
 "win:0.1": {
  "HIST": 0.16346153846153846,
  "NRTS": null
 },
 "aci:0.1": {
  "HIST": 0.19230769230769232,
  "NRTS": null
 },
 "crc:0.2": {
  "HIST": 0.2403846153846154,
  "NRTS": null
 },
 "win:0.2": {
  "HIST": 0.19230769230769232,
  "NRTS": null
 },
 "aci:0.2": {
  "HIST": 0.19230769230769232,
  "NRTS": null
 }
}
```

## Triggers vs line-coverage misses

```
{
 "lang_javascript": {
  "file": {
   "test": 13,
   "unsafe": 1,
   "safe": 12,
   "flag_unsafe": 1,
   "flag_safe": 7,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 8,
    "static_runtime_conflict": 1,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 13,
   "unsafe": 1,
   "safe": 12,
   "flag_unsafe": 1,
   "flag_safe": 8,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 4,
    "static_runtime_conflict": 0,
    "module_level_change": 8
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 1
   }
  },
  "risk": {
   "test": 13,
   "unsafe": 1,
   "safe": 12,
   "flag_unsafe": 0,
   "flag_safe": 1,
   "per_trigger": {
    "r(c) > 0.1": 1
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "lang_rust": {
  "file": {
   "test": 58,
   "unsafe": 5,
   "safe": 53,
   "flag_unsafe": 5,
   "flag_safe": 50,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 41,
    "static_runtime_conflict": 28,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 5,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 58,
   "unsafe": 5,
   "safe": 53,
   "flag_unsafe": 5,
   "flag_safe": 32,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 21,
    "static_runtime_conflict": 20,
    "module_level_change": 1
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 5,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 58,
   "unsafe": 5,
   "safe": 53,
   "flag_unsafe": 2,
   "flag_safe": 3,
   "per_trigger": {
    "r(c) > 0.1": 5
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 2
   }
  }
 },
 "lang_go": {
  "file": {
   "test": 33,
   "unsafe": 2,
   "safe": 31,
   "flag_unsafe": 2,
   "flag_safe": 15,
   "per_trigger": {
    "dynamic_call": 6,
    "untested_change": 15,
    "static_runtime_conflict": 2,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 33,
   "unsafe": 2,
   "safe": 31,
   "flag_unsafe": 2,
   "flag_safe": 13,
   "per_trigger": {
    "dynamic_call": 3,
    "untested_change": 11,
    "static_runtime_conflict": 0,
    "module_level_change": 10
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 0,
    "module_level_change": 2
   }
  },
  "risk": {
   "test": 33,
   "unsafe": 2,
   "safe": 31,
   "flag_unsafe": 0,
   "flag_safe": 13,
   "per_trigger": {
    "r(c) > 0.1": 13
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 }
}
```

## Ablation (HIST, 25% budget)

| Model | Recall | Safe % | Mutants detected % |
|---|---|---|---|
| - all coverage | 0.824 | 67.3 | -- |
| - co-change | 0.926 | 82.7 | -- |
| - file coverage | 0.921 | 80.8 | -- |
| - function coverage | 0.926 | 82.7 | -- |
| - line coverage | 0.924 | 82.7 | -- |
| - name match | 0.926 | 82.7 | -- |
| - static import | 0.926 | 82.7 | -- |
| - test changed | 0.919 | 80.8 | -- |
| Full model | 0.926 | 82.7 | -- |

## Per-project (CRC alpha=0.1 plain / line-abstain hybrid)

- lang_javascript: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 92.3, time red 72.4
- lang_rust: plain safe 98.3, time red 88.0; line-abstain+hybrid safe 100.0, time red 87.7; line cov safe 91.4, time red 89.2
- lang_go: plain safe 93.9, time red 82.3; line-abstain+hybrid safe 100.0, time red 66.1; line cov safe 93.9, time red 82.3

## Per-change residual-risk estimate r(c) vs observed misses

```
{
 "budget25:HIST": {
  "n": 104,
  "mean_predicted": 0.20773870451918788,
  "observed_miss_rate": 0.17307692307692307,
  "brier": 0.022049602608101706,
  "brier_constant": 0.14312130177514787,
  "ece5": 0.034661781442264804,
  "bins": [
   [
    0.0,
    0.2,
    81,
    0.01299256210194397,
    0.0
   ],
   [
    0.2,
    0.4,
    3,
    0.21790212564788455,
    0.0
   ],
   [
    0.4,
    0.6,
    0,
    null,
    null
   ],
   [
    0.6,
    0.8,
    0,
    null,
    null
   ],
   [
    0.8,
    1.0,
    20,
    0.9949360681397212,
    0.9
   ]
  ]
 },
 "crc10:HIST": {
  "n": 104,
  "mean_predicted": 0.043074556758550105,
  "observed_miss_rate": 0.028846153846153848,
  "brier": 0.03200869169878346,
  "brier_constant": 0.028014053254437878,
  "ece5": 0.03503144554074044,
  "bins": [
   [
    0.0,
    0.2,
    94,
    0.020406827482192576,
    0.031914893617021274
   ],
   [
    0.2,
    0.4,
    10,
    0.2561512119563108,
    0.0
   ],
   [
    0.4,
    0.6,
    0,
    null,
    null
   ],
   [
    0.6,
    0.8,
    0,
    null,
    null
   ],
   [
    0.8,
    1.0,
    0,
    null,
    null
   ]
  ]
 },
 "linecov:HIST": {
  "n": 104,
  "mean_predicted": 0.05386013319431315,
  "observed_miss_rate": 0.07692307692307693,
  "brier": 0.07722495982426787,
  "brier_constant": 0.07100591715976332,
  "ece5": 0.08829769568715438,
  "bins": [
   [
    0.0,
    0.2,
    92,
    0.024013551634481045,
    0.08695652173913043
   ],
   [
    0.2,
    0.4,
    11,
    0.26626108688279637,
    0.0
   ],
   [
    0.4,
    0.6,
    1,
    0.46333514612555116,
    0.0
   ],
   [
    0.6,
    0.8,
    0,
    null,
    null
   ],
   [
    0.8,
    1.0,
    0,
    null,
    null
   ]
  ]
 },
 "aci10:HIST": {
  "n": 104,
  "mean_predicted": 0.07025655067941118,
  "observed_miss_rate": 0.057692307692307696,
  "brier": 0.04373929155974598,
  "brier_constant": 0.0543639053254438,
  "ece5": 0.052670508971287125,
  "bins": [
   [
    0.0,
    0.2,
    90,
    0.021272426679195818,
    0.044444444444444446
   ],
   [
    0.2,
    0.4,
    11,
    0.26626108688279637,
    0.0
   ],
   [
    0.4,
    0.6,
    1,
    0.46333514612555116,
    0.0
   ],
   [
    0.6,
    0.8,
    0,
    null,
    null
   ],
   [
    0.8,
    1.0,
    2,
    0.9999778838474134,
    1.0
   ]
  ]
 }
}
```

## Paired tests (HIST)

```
{
 "recall@0.1: CodeTwin vs Coverage-ranked": {
  "n": 101,
  "nonzero": 1,
  "p": 0.31731050786291415,
  "mean_diff": -0.0024752475247524753
 },
 "recall@0.1: CodeTwin vs Random": {
  "n": 101,
  "nonzero": 33,
  "p": 7.545271197594474e-07,
  "mean_diff": 0.11023970254168274
 },
 "recall@0.25: CodeTwin vs Coverage-ranked": {
  "n": 101,
  "nonzero": 0,
  "p": 1.0,
  "mean_diff": 0.0
 },
 "recall@0.25: CodeTwin vs Random": {
  "n": 101,
  "nonzero": 41,
  "p": 2.404664402790536e-08,
  "mean_diff": 0.1494011544011544
 },
 "recall@0.5: CodeTwin vs Coverage-ranked": {
  "n": 101,
  "nonzero": 0,
  "p": 1.0,
  "mean_diff": 0.0
 },
 "recall@0.5: CodeTwin vs Random": {
  "n": 101,
  "nonzero": 44,
  "p": 7.593723928073565e-09,
  "mean_diff": 0.11755579129341505
 },
 "safety: CRC(alpha=0.1) vs Line coverage": {
  "a_only": 5,
  "b_only": 0,
  "p": 0.0625
 },
 "time_red: CRC(alpha=0.1) vs Line coverage": {
  "n": 104,
  "nonzero": 20,
  "p": 8.857457687863547e-05,
  "mean_diff": -0.09757240758853462
 },
 "safety: CRC(alpha=0.1) vs Function coverage": {
  "a_only": 2,
  "b_only": 0,
  "p": 0.5
 },
 "time_red: CRC(alpha=0.1) vs Function coverage": {
  "n": 104,
  "nonzero": 19,
  "p": 0.00034155628132162525,
  "mean_diff": -0.0897861686000668
 },
 "safety: CRC(alpha=0.1) vs File coverage": {
  "a_only": 0,
  "b_only": 3,
  "p": 0.25
 },
 "time_red: CRC(alpha=0.1) vs File coverage": {
  "n": 104,
  "nonzero": 43,
  "p": 0.4468231296804849,
  "mean_diff": -0.010357731113529398
 }
}
```

## Ground-truth check: killers of killed mutants inside the coverage-affected set

```
{}
```

## Coefficients

```
{
 "lang_javascript": {
  "cov_line": 4.6376916642114505,
  "cov_func": 0.8027487374473635,
  "cov_file": 2.4638571409774035,
  "static_inv_dist": 0.625849994547322,
  "name_match": 0.715213111170486,
  "cochange": 0.374972084491539,
  "test_changed": 8.029404880916106
 },
 "lang_rust": {
  "cov_line": 5.442155162536993,
  "cov_func": 0.9511900775279644,
  "cov_file": 1.0914470938530259,
  "static_inv_dist": 1.7514040891895173,
  "name_match": 0.8751340862709841,
  "cochange": 0.2444074409359001,
  "test_changed": 5.276605712956233
 },
 "lang_go": {
  "cov_line": 4.418463563668771,
  "cov_func": 0.11281856806342684,
  "cov_file": 3.284989068554582,
  "static_inv_dist": 0.7233057737317913,
  "name_match": 0.7577008646022259,
  "cochange": 1.1446120792411105,
  "test_changed": 8.02757747441788
 }
}
```

## Failure cases (CRC alpha=0.1, unsafe)

```
{
 "lang_javascript": [],
 "lang_rust": [
  {
   "sha": "fa41521",
   "subject": "PR 2008",
   "safe": false,
   "time_red": 0.9538018598377033,
   "missed": [
    "tracing-subscriber/tests/multiple_subscriber_filter_interests_cached.rs",
    "tracing-subscriber/tests/unhinted_subscriber_filters_dont_break_other_subscribers.rs",
    "tracing-subscriber/tests/utils.rs"
   ],
   "missed_scores": [
    0.038,
    0.038,
    0.038
   ],
   "trig_line": [
    "static_runtime_conflict"
   ],
   "trig_file": [
    "untested_change",
    "static_runtime_conflict"
   ],
   "fault_safe": true,
   "mut_n": 0
  }
 ],
 "lang_go": [
  {
   "sha": "97b482a",
   "subject": "PR 2116",
   "safe": false,
   "time_red": 0.9235625450680474,
   "missed": [
    "core/stores/sqlc/cachedsql_test.go"
   ],
   "missed_scores": [
    0.313
   ],
   "trig_line": [
    "untested_change",
    "module_level_change"
   ],
   "trig_file": [
    "untested_change"
   ],
   "fault_safe": true,
   "mut_n": 0
  },
  {
   "sha": "0f00dc6",
   "subject": "PR 2463",
   "safe": false,
   "time_red": 0.7120699465454482,
   "missed": [
    "core/threading/routinegroup_test.go"
   ],
   "missed_scores": [
    0.287
   ],
   "trig_line": [
    "untested_change",
    "module_level_change"
   ],
   "trig_file": [
    "untested_change"
   ],
   "fault_safe": true,
   "mut_n": 0
  }
 ]
}
```
