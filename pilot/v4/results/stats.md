# CodeTwin AI study v2 -- results

## Subjects

| Project | Mode | Changes | Calib | Test | KLoC | Test files | Suite (s) | Affected | Killed mutants | Period |
|---|---|---|---|---|---|---|---|---|---|---|
| anuraghazra_m_github-readme-stats | history | 7 | 2 | 5 | 1.1 | 10.3 | 28.8 | 5.1 | 0 | 2026-11-14 to 2026-11-14 |
| burntsushi_m_ripgrep | history | 14 | 5 | 9 | 38.8 | 34.2 | 134.1 | 1.9 | 0 | 2026-11-14 to 2026-11-14 |
| clap-rs_m_clap | history | 24 | 9 | 15 | 17.0 | 39.5 | 918.8 | 7.6 | 0 | 2026-11-14 to 2026-11-14 |
| cli_m_cli | history | 24 | 9 | 15 | 6.7 | 22.0 | 28.9 | 3.8 | 0 | 2026-11-14 to 2026-11-14 |
| grpc_m_grpc-go | history | 16 | 6 | 10 | 67.0 | 40.0 | 82.3 | 5.6 | 0 | 2026-11-14 to 2026-11-14 |
| iamkun_m_dayjs | history | 13 | 5 | 8 | 7.9 | 47.5 | 129.6 | 8.2 | 0 | 2026-11-14 to 2026-11-14 |
| sharkdp_m_fd | history | 14 | 5 | 9 | 4.0 | 7.6 | 5.6 | 1.0 | 0 | 2026-11-14 to 2026-11-14 |
| sveltejs_m_svelte | history | 1 | 1 | 0 | 38.7 | 18.0 | 3.5 | 0.0 | 0 | 2026-11-14 to 2026-11-14 |
| tokio-rs_m_tokio | history | 23 | 9 | 14 | 111.7 | 40.0 | 319.0 | 1.2 | 0 | 2026-11-14 to 2026-11-14 |
| tokio-rs_m_tracing | history | 21 | 8 | 13 | 54.4 | 39.9 | 315.5 | 4.8 | 0 | 2026-11-14 to 2026-11-14 |
| zeromicro_m_go-zero | history | 15 | 6 | 9 | 61.8 | 40.0 | 80.0 | 3.5 | 0 | 2026-11-14 to 2026-11-14 |

Skipped changes: {"anuraghazra_m_github-readme-stats": {"no source change / no tests": 6}, "axios_m_axios": {"no source change / no tests": 3}, "burntsushi_m_ripgrep": {}, "clap-rs_m_clap": {}, "cli_m_cli": {}, "grpc_m_grpc-go": {}, "iamkun_m_dayjs": {"no source change / no tests": 11}, "sharkdp_m_fd": {}, "sveltejs_m_svelte": {}, "tokio-rs_m_tokio": {}, "tokio-rs_m_tracing": {}, "zeromicro_m_go-zero": {}}

## Selection quality (HIST)

| Technique | Test red % | Time red % | Precision | Recall | Safe % | Mutants detected % | Fault-safe % | NameRTS-GT safe % |
|---|---|---|---|---|---|---|---|---|
| base:File coverage | 75.9 [71.2, 80.5] | 70.4 [64.8, 75.9] | 0.73 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| base:Function coverage | 85.1 [81.9, 88.1] | 80.7 [76.2, 84.7] | 0.90 | 0.970 | 91.6 [86.0, 96.3] | -- (0/0) | -- | 100.0 |
| base:Hybrid | 66.8 [60.2, 72.9] | 61.0 [53.9, 67.9] | 0.63 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| base:Line coverage | 86.6 [83.4, 89.5] | 82.1 [77.6, 86.3] | 0.94 | 0.963 | 89.7 [83.2, 95.3] | -- (0/0) | -- | 100.0 |
| base:Name matching | 88.2 [85.8, 90.5] | 84.3 [80.5, 88.0] | 0.75 | 0.789 | 63.6 [54.2, 72.0] | -- (0/0) | -- | 100.0 |
| base:Retest-all | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| base:Static import | 68.5 [61.7, 74.8] | 62.1 [55.1, 69.2] | 0.68 | 0.934 | 87.9 [81.3, 93.5] | -- (0/0) | -- | 100.0 |
| budget:0.25:CodeTwin | 64.7 [62.1, 67.2] | 72.9 [70.6, 75.0] | 0.37 | 0.908 | 75.7 [67.3, 83.2] | -- (0/0) | -- | 100.0 |
| crc:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:plain | 34.9 [26.8, 43.2] | 34.3 [26.3, 42.5] | 0.46 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:plain | 83.8 [79.3, 87.9] | 79.4 [74.0, 84.3] | 0.89 | 0.952 | 87.9 [81.3, 93.5] | -- (0/0) | -- | 100.0 |
| win:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| win:0.05:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| win:0.1:plain | 33.2 [25.5, 41.1] | 32.3 [24.4, 40.3] | 0.43 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| win:0.2:plain | 82.4 [77.5, 86.6] | 77.4 [71.8, 82.7] | 0.86 | 0.966 | 90.7 [85.0, 96.3] | -- (0/0) | -- | 100.0 |
| aci:0.01:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:plain | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:plain | 31.5 [23.6, 39.5] | 30.7 [22.9, 39.0] | 0.43 | 0.990 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:plain | 82.1 [77.5, 86.4] | 77.1 [71.7, 82.4] | 0.86 | 0.966 | 90.7 [85.0, 95.3] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:filecov | 34.7 [26.7, 42.8] | 33.9 [26.1, 42.2] | 0.45 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:filecov | 80.7 [75.6, 85.5] | 76.3 [70.4, 81.9] | 0.85 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:hybrid | 34.7 [26.7, 42.8] | 33.9 [26.0, 42.0] | 0.45 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:hybrid | 79.7 [74.3, 84.7] | 75.3 [69.1, 81.1] | 0.83 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-risk:full | 21.4 [15.0, 28.4] | 20.5 [14.2, 27.3] | 0.33 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-risk:full | 56.9 [48.7, 64.8] | 52.6 [44.7, 60.7] | 0.63 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:filecov | 34.5 [26.6, 42.8] | 33.9 [25.9, 42.2] | 0.46 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:filecov | 80.2 [74.9, 85.0] | 75.5 [69.6, 81.0] | 0.85 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:hybrid | 33.1 [25.2, 41.4] | 32.5 [24.4, 40.6] | 0.44 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:hybrid | 77.2 [71.4, 82.6] | 72.5 [65.9, 78.7] | 0.80 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-line:full | 22.7 [15.6, 30.3] | 22.6 [15.3, 30.2] | 0.34 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-line:full | 46.5 [38.0, 55.2] | 42.2 [33.8, 50.5] | 0.57 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:filecov | 32.7 [25.1, 40.4] | 32.1 [24.5, 40.0] | 0.42 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:filecov | 77.0 [71.8, 82.0] | 72.3 [66.2, 78.2] | 0.79 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:hybrid | 28.6 [21.1, 36.2] | 28.3 [20.9, 36.2] | 0.40 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:hybrid | 71.5 [65.1, 77.6] | 66.8 [59.9, 73.3] | 0.75 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.01:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.05:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.1:abstain-file:full | 12.0 [6.7, 17.8] | 11.3 [6.3, 16.9] | 0.24 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| crc:0.2:abstain-file:full | 25.8 [18.4, 33.7] | 23.7 [16.6, 31.3] | 0.39 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:filecov | 30.7 [23.2, 38.7] | 30.1 [22.3, 38.0] | 0.40 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:filecov | 79.8 [74.7, 84.6] | 75.0 [69.0, 80.6] | 0.82 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:hybrid | 30.2 [22.4, 38.0] | 29.6 [21.9, 37.5] | 0.40 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:hybrid | 78.9 [73.4, 83.7] | 74.1 [68.0, 79.8] | 0.80 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-risk:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-risk:full | 15.0 [9.2, 21.2] | 14.3 [8.8, 20.3] | 0.26 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-risk:full | 54.0 [46.0, 62.0] | 48.9 [40.9, 56.8] | 0.60 | 0.989 | 95.3 [90.7, 99.1] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:filecov | 30.9 [23.2, 39.1] | 30.2 [22.5, 38.1] | 0.42 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:filecov | 79.4 [74.2, 84.2] | 74.4 [68.4, 80.1] | 0.83 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:hybrid | 29.4 [21.7, 37.4] | 28.9 [21.2, 36.9] | 0.40 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:hybrid | 76.5 [70.7, 82.0] | 71.4 [64.7, 77.7] | 0.79 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-line:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-line:full | 18.3 [11.8, 25.4] | 18.1 [11.6, 25.0] | 0.30 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-line:full | 45.7 [37.1, 54.4] | 41.1 [33.0, 49.2] | 0.56 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:filecov | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:filecov | 30.1 [22.4, 38.1] | 29.7 [22.0, 37.6] | 0.40 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:filecov | 76.8 [71.6, 81.8] | 71.8 [65.8, 77.7] | 0.78 | 0.996 | 98.1 [95.3, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:hybrid | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:hybrid | 27.0 [19.5, 34.9] | 26.7 [19.1, 34.6] | 0.38 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:hybrid | 71.2 [64.7, 77.3] | 66.4 [59.4, 73.0] | 0.74 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.01:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.05:abstain-file:full | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.13 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.1:abstain-file:full | 10.0 [5.2, 15.4] | 9.3 [4.7, 14.5] | 0.23 | 1.000 | 100.0 [100.0, 100.0] | -- (0/0) | -- | 100.0 |
| aci:0.2:abstain-file:full | 25.5 [18.2, 33.3] | 23.2 [16.3, 30.6] | 0.38 | 0.998 | 99.1 [97.2, 100.0] | -- (0/0) | -- | 100.0 |

## Budget mode (HIST, recall)

| Budget | CodeTwin | Coverage-ranked | Random |
|---|---|---|---|
| 0.1 | 0.820 [0.767, 0.872] | 0.820 [0.766, 0.871] | 0.744 [0.682, 0.804] |
| 0.25 | 0.908 [0.872, 0.941] | 0.908 [0.872, 0.941] | 0.781 [0.726, 0.834] |
| 0.5 | 0.970 [0.951, 0.987] | 0.973 [0.954, 0.989] | 0.858 [0.819, 0.893] |

## Calibration per project

| Project | alpha | lambda | feasible | n calib | abstain file | abstain line |
|---|---|---|---|---|---|---|
| anuraghazra_m_github-readme-stats | 0.01 | -1.000 | False | 2 | 80.0 | 100.0 |
| anuraghazra_m_github-readme-stats | 0.05 | -1.000 | False | 2 | 80.0 | 100.0 |
| anuraghazra_m_github-readme-stats | 0.1 | -1.000 | False | 2 | 80.0 | 100.0 |
| anuraghazra_m_github-readme-stats | 0.2 | -1.000 | False | 2 | 80.0 | 100.0 |
| burntsushi_m_ripgrep | 0.01 | -1.000 | False | 5 | 100.0 | 100.0 |
| burntsushi_m_ripgrep | 0.05 | -1.000 | False | 5 | 100.0 | 100.0 |
| burntsushi_m_ripgrep | 0.1 | -1.000 | False | 5 | 100.0 | 100.0 |
| burntsushi_m_ripgrep | 0.2 | 1.000 | True | 5 | 100.0 | 100.0 |
| clap-rs_m_clap | 0.01 | -1.000 | False | 9 | 73.3 | 6.7 |
| clap-rs_m_clap | 0.05 | -1.000 | False | 9 | 73.3 | 6.7 |
| clap-rs_m_clap | 0.1 | 0.984 | True | 9 | 73.3 | 6.7 |
| clap-rs_m_clap | 0.2 | 0.987 | True | 9 | 73.3 | 6.7 |
| cli_m_cli | 0.01 | -1.000 | False | 9 | 20.0 | 40.0 |
| cli_m_cli | 0.05 | -1.000 | False | 9 | 20.0 | 40.0 |
| cli_m_cli | 0.1 | 0.651 | True | 9 | 20.0 | 40.0 |
| cli_m_cli | 0.2 | 0.990 | True | 9 | 20.0 | 40.0 |
| grpc_m_grpc-go | 0.01 | -1.000 | False | 6 | 60.0 | 40.0 |
| grpc_m_grpc-go | 0.05 | -1.000 | False | 6 | 60.0 | 40.0 |
| grpc_m_grpc-go | 0.1 | -1.000 | False | 6 | 60.0 | 40.0 |
| grpc_m_grpc-go | 0.2 | 0.977 | True | 6 | 60.0 | 40.0 |
| iamkun_m_dayjs | 0.01 | -1.000 | False | 5 | 25.0 | 25.0 |
| iamkun_m_dayjs | 0.05 | -1.000 | False | 5 | 25.0 | 25.0 |
| iamkun_m_dayjs | 0.1 | -1.000 | False | 5 | 25.0 | 25.0 |
| iamkun_m_dayjs | 0.2 | 0.985 | True | 5 | 25.0 | 25.0 |
| sharkdp_m_fd | 0.01 | -1.000 | False | 5 | 66.7 | 0.0 |
| sharkdp_m_fd | 0.05 | -1.000 | False | 5 | 66.7 | 0.0 |
| sharkdp_m_fd | 0.1 | -1.000 | False | 5 | 66.7 | 0.0 |
| sharkdp_m_fd | 0.2 | 1.000 | True | 5 | 66.7 | 0.0 |
| sveltejs_m_svelte | 0.01 | -1.000 | False | 1 | -- | -- |
| sveltejs_m_svelte | 0.05 | -1.000 | False | 1 | -- | -- |
| sveltejs_m_svelte | 0.1 | -1.000 | False | 1 | -- | -- |
| sveltejs_m_svelte | 0.2 | -1.000 | False | 1 | -- | -- |
| tokio-rs_m_tokio | 0.01 | -1.000 | False | 9 | 100.0 | 64.3 |
| tokio-rs_m_tokio | 0.05 | -1.000 | False | 9 | 100.0 | 64.3 |
| tokio-rs_m_tokio | 0.1 | 1.000 | True | 9 | 100.0 | 64.3 |
| tokio-rs_m_tokio | 0.2 | 1.000 | True | 9 | 100.0 | 64.3 |
| tokio-rs_m_tracing | 0.01 | -1.000 | False | 8 | 100.0 | 84.6 |
| tokio-rs_m_tracing | 0.05 | -1.000 | False | 8 | 100.0 | 84.6 |
| tokio-rs_m_tracing | 0.1 | -1.000 | False | 8 | 100.0 | 84.6 |
| tokio-rs_m_tracing | 0.2 | 0.038 | True | 8 | 100.0 | 84.6 |
| zeromicro_m_go-zero | 0.01 | -1.000 | False | 6 | 66.7 | 44.4 |
| zeromicro_m_go-zero | 0.05 | -1.000 | False | 6 | 66.7 | 44.4 |
| zeromicro_m_go-zero | 0.1 | -1.000 | False | 6 | 66.7 | 44.4 |
| zeromicro_m_go-zero | 0.2 | 0.977 | True | 6 | 66.7 | 44.4 |

## Abstention rates (pooled)

```
{
 "0.01:file:HIST": 0.6915887850467289,
 "0.01:file:NRTS": null,
 "0.01:line:HIST": 0.4766355140186916,
 "0.01:line:NRTS": null,
 "0.05:file:HIST": 0.6915887850467289,
 "0.05:file:NRTS": null,
 "0.05:line:HIST": 0.4766355140186916,
 "0.05:line:NRTS": null,
 "0.1:file:HIST": 0.6915887850467289,
 "0.1:file:NRTS": null,
 "0.1:line:HIST": 0.4766355140186916,
 "0.1:line:NRTS": null,
 "0.2:file:HIST": 0.6915887850467289,
 "0.2:file:NRTS": null,
 "0.2:line:HIST": 0.4766355140186916,
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
  "HIST": 0.0,
  "NRTS": null
 },
 "aci:0.05": {
  "HIST": 0.0,
  "NRTS": null
 },
 "crc:0.1": {
  "HIST": 0.14018691588785046,
  "NRTS": null
 },
 "win:0.1": {
  "HIST": 0.1588785046728972,
  "NRTS": null
 },
 "aci:0.1": {
  "HIST": 0.17757009345794392,
  "NRTS": null
 },
 "crc:0.2": {
  "HIST": 0.29906542056074764,
  "NRTS": null
 },
 "win:0.2": {
  "HIST": 0.308411214953271,
  "NRTS": null
 },
 "aci:0.2": {
  "HIST": 0.308411214953271,
  "NRTS": null
 }
}
```

## Triggers vs line-coverage misses

```
{
 "anuraghazra_m_github-readme-stats": {
  "file": {
   "test": 5,
   "unsafe": 1,
   "safe": 4,
   "flag_unsafe": 1,
   "flag_safe": 3,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 4,
    "static_runtime_conflict": 0,
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
   "test": 5,
   "unsafe": 1,
   "safe": 4,
   "flag_unsafe": 1,
   "flag_safe": 4,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 3,
    "static_runtime_conflict": 0,
    "module_level_change": 5
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 1
   }
  },
  "risk": {
   "test": 5,
   "unsafe": 1,
   "safe": 4,
   "flag_unsafe": 1,
   "flag_safe": 1,
   "per_trigger": {
    "r(c) > 0.1": 2
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 1
   }
  }
 },
 "burntsushi_m_ripgrep": {
  "file": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 9,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 6,
    "static_runtime_conflict": 6,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 9,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 6,
    "static_runtime_conflict": 5,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 9,
   "per_trigger": {
    "r(c) > 0.1": 9
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "clap-rs_m_clap": {
  "file": {
   "test": 15,
   "unsafe": 2,
   "safe": 13,
   "flag_unsafe": 1,
   "flag_safe": 10,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 9,
    "static_runtime_conflict": 5,
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
   "test": 15,
   "unsafe": 2,
   "safe": 13,
   "flag_unsafe": 0,
   "flag_safe": 1,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 1,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 15,
   "unsafe": 2,
   "safe": 13,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {
    "r(c) > 0.1": 0
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "cli_m_cli": {
  "file": {
   "test": 15,
   "unsafe": 0,
   "safe": 15,
   "flag_unsafe": 0,
   "flag_safe": 3,
   "per_trigger": {
    "dynamic_call": 2,
    "untested_change": 3,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 15,
   "unsafe": 0,
   "safe": 15,
   "flag_unsafe": 0,
   "flag_safe": 6,
   "per_trigger": {
    "dynamic_call": 1,
    "untested_change": 5,
    "static_runtime_conflict": 0,
    "module_level_change": 5
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 15,
   "unsafe": 0,
   "safe": 15,
   "flag_unsafe": 0,
   "flag_safe": 3,
   "per_trigger": {
    "r(c) > 0.1": 3
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "grpc_m_grpc-go": {
  "file": {
   "test": 10,
   "unsafe": 1,
   "safe": 9,
   "flag_unsafe": 1,
   "flag_safe": 5,
   "per_trigger": {
    "dynamic_call": 3,
    "untested_change": 4,
    "static_runtime_conflict": 3,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 1,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 10,
   "unsafe": 1,
   "safe": 9,
   "flag_unsafe": 1,
   "flag_safe": 3,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 4,
    "static_runtime_conflict": 0,
    "module_level_change": 2
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 1
   }
  },
  "risk": {
   "test": 10,
   "unsafe": 1,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 2,
   "per_trigger": {
    "r(c) > 0.1": 2
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "iamkun_m_dayjs": {
  "file": {
   "test": 8,
   "unsafe": 1,
   "safe": 7,
   "flag_unsafe": 1,
   "flag_safe": 1,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 0,
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
   "test": 8,
   "unsafe": 1,
   "safe": 7,
   "flag_unsafe": 1,
   "flag_safe": 1,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 1
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 8,
   "unsafe": 1,
   "safe": 7,
   "flag_unsafe": 1,
   "flag_safe": 2,
   "per_trigger": {
    "r(c) > 0.1": 3
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 1
   }
  }
 },
 "sharkdp_m_fd": {
  "file": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 6,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 6,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 9,
   "unsafe": 0,
   "safe": 9,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {
    "r(c) > 0.1": 0
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "sveltejs_m_svelte": {
  "file": {
   "test": 0,
   "unsafe": 0,
   "safe": 0,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {},
   "per_trigger_unsafe": {}
  },
  "line": {
   "test": 0,
   "unsafe": 0,
   "safe": 0,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {},
   "per_trigger_unsafe": {}
  },
  "risk": {
   "test": 0,
   "unsafe": 0,
   "safe": 0,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {},
   "per_trigger_unsafe": {}
  }
 },
 "tokio-rs_m_tokio": {
  "file": {
   "test": 14,
   "unsafe": 0,
   "safe": 14,
   "flag_unsafe": 0,
   "flag_safe": 14,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 14,
    "static_runtime_conflict": 3,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 14,
   "unsafe": 0,
   "safe": 14,
   "flag_unsafe": 0,
   "flag_safe": 9,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 9,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 0,
    "static_runtime_conflict": 0,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 14,
   "unsafe": 0,
   "safe": 14,
   "flag_unsafe": 0,
   "flag_safe": 14,
   "per_trigger": {
    "r(c) > 0.1": 14
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 0
   }
  }
 },
 "tokio-rs_m_tracing": {
  "file": {
   "test": 13,
   "unsafe": 4,
   "safe": 9,
   "flag_unsafe": 4,
   "flag_safe": 9,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 7,
    "static_runtime_conflict": 12,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 4,
    "module_level_change": 0
   }
  },
  "line": {
   "test": 13,
   "unsafe": 4,
   "safe": 9,
   "flag_unsafe": 4,
   "flag_safe": 7,
   "per_trigger": {
    "dynamic_call": 0,
    "untested_change": 3,
    "static_runtime_conflict": 10,
    "module_level_change": 0
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 1,
    "static_runtime_conflict": 4,
    "module_level_change": 0
   }
  },
  "risk": {
   "test": 13,
   "unsafe": 4,
   "safe": 9,
   "flag_unsafe": 4,
   "flag_safe": 3,
   "per_trigger": {
    "r(c) > 0.1": 7
   },
   "per_trigger_unsafe": {
    "r(c) > 0.1": 4
   }
  }
 },
 "zeromicro_m_go-zero": {
  "file": {
   "test": 9,
   "unsafe": 2,
   "safe": 7,
   "flag_unsafe": 2,
   "flag_safe": 4,
   "per_trigger": {
    "dynamic_call": 2,
    "untested_change": 5,
    "static_runtime_conflict": 1,
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
   "test": 9,
   "unsafe": 2,
   "safe": 7,
   "flag_unsafe": 2,
   "flag_safe": 2,
   "per_trigger": {
    "dynamic_call": 1,
    "untested_change": 2,
    "static_runtime_conflict": 0,
    "module_level_change": 3
   },
   "per_trigger_unsafe": {
    "dynamic_call": 0,
    "untested_change": 2,
    "static_runtime_conflict": 0,
    "module_level_change": 2
   }
  },
  "risk": {
   "test": 9,
   "unsafe": 2,
   "safe": 7,
   "flag_unsafe": 0,
   "flag_safe": 0,
   "per_trigger": {
    "r(c) > 0.1": 0
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
| - all coverage | 0.820 | 64.5 | -- |
| - co-change | 0.908 | 75.7 | -- |
| - file coverage | 0.902 | 73.8 | -- |
| - function coverage | 0.908 | 75.7 | -- |
| - line coverage | 0.897 | 74.8 | -- |
| - name match | 0.908 | 75.7 | -- |
| - static import | 0.908 | 75.7 | -- |
| - test changed | 0.896 | 72.9 | -- |
| Full model | 0.908 | 75.7 | -- |

## Per-project (CRC alpha=0.1 plain / line-abstain hybrid)

- anuraghazra_m_github-readme-stats: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 80.0, time red 60.8
- burntsushi_m_ripgrep: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 100.0, time red 95.8
- clap-rs_m_clap: plain safe 86.7, time red 80.4; line-abstain+hybrid safe 86.7, time red 77.5; line cov safe 86.7, time red 80.4
- cli_m_cli: plain safe 100.0, time red 72.0; line-abstain+hybrid safe 100.0, time red 62.3; line cov safe 100.0, time red 72.5
- grpc_m_grpc-go: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 90.0, time red 78.4
- iamkun_m_dayjs: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 87.5, time red 91.2
- sharkdp_m_fd: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 100.0, time red 38.2
- sveltejs_m_svelte: plain safe --, time red --; line-abstain+hybrid safe --, time red --; line cov safe --, time red --
- tokio-rs_m_tokio: plain safe 100.0, time red 98.7; line-abstain+hybrid safe 100.0, time red 98.7; line cov safe 100.0, time red 98.7
- tokio-rs_m_tracing: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 69.2, time red 95.6
- zeromicro_m_go-zero: plain safe 100.0, time red 0.0; line-abstain+hybrid safe 100.0, time red 0.0; line cov safe 77.8, time red 93.8

## Per-change residual-risk estimate r(c) vs observed misses

```
{
 "budget25:HIST": {
  "n": 107,
  "mean_predicted": 0.2906455680621643,
  "observed_miss_rate": 0.24299065420560748,
  "brier": 0.03976363812966833,
  "brier_constant": 0.1839461961743383,
  "ece5": 0.06787052361528044,
  "bins": [
   [
    0.0,
    0.2,
    61,
    0.015056801277185044,
    0.03278688524590164
   ],
   [
    0.2,
    0.4,
    21,
    0.2518880700561067,
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
    25,
    0.9956384573426021,
    0.96
   ]
  ]
 },
 "crc10:HIST": {
  "n": 107,
  "mean_predicted": 0.0544440734897234,
  "observed_miss_rate": 0.018691588785046728,
  "brier": 0.04022726016880911,
  "brier_constant": 0.018342213293737454,
  "ece5": 0.07313566227477014,
  "bins": [
   [
    0.0,
    0.2,
    92,
    0.0,
    0.021739130434782608
   ],
   [
    0.2,
    0.4,
    11,
    0.3756544310630998,
    0.0
   ],
   [
    0.4,
    0.6,
    4,
    0.4233292804265767,
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
 "linecov:HIST": {
  "n": 107,
  "mean_predicted": 0.1978601241341603,
  "observed_miss_rate": 0.102803738317757,
  "brier": 0.13223439868860537,
  "brier_constant": 0.09223512970565115,
  "ece5": 0.17255786875854306,
  "bins": [
   [
    0.0,
    0.2,
    68,
    0.012553980332287037,
    0.07352941176470588
   ],
   [
    0.2,
    0.4,
    18,
    0.3705574927983424,
    0.0
   ],
   [
    0.4,
    0.6,
    10,
    0.46177328935294276,
    0.1
   ],
   [
    0.6,
    0.8,
    6,
    0.6891653306643147,
    0.5
   ],
   [
    0.8,
    1.0,
    5,
    0.9789205743748297,
    0.4
   ]
  ]
 },
 "aci10:HIST": {
  "n": 107,
  "mean_predicted": 0.08680486601308787,
  "observed_miss_rate": 0.018691588785046728,
  "brier": 0.054208518556762744,
  "brier_constant": 0.01834221329373745,
  "ece5": 0.08680486601308789,
  "bins": [
   [
    0.0,
    0.2,
    88,
    0.0,
    0.011363636363636364
   ],
   [
    0.2,
    0.4,
    11,
    0.3756544310630998,
    0.0
   ],
   [
    0.4,
    0.6,
    4,
    0.4233292804265767,
    0.0
   ],
   [
    0.6,
    0.8,
    2,
    0.7313023999999999,
    0.5
   ],
   [
    0.8,
    1.0,
    2,
    1.0,
    0.0
   ]
  ]
 }
}
```

## Paired tests (HIST)

```
{
 "recall@0.1: CodeTwin vs Coverage-ranked": {
  "n": 105,
  "nonzero": 0,
  "p": 1.0,
  "mean_diff": 0.0
 },
 "recall@0.1: CodeTwin vs Random": {
  "n": 105,
  "nonzero": 33,
  "p": 3.469442567502918e-06,
  "mean_diff": 0.07613189177850832
 },
 "recall@0.25: CodeTwin vs Coverage-ranked": {
  "n": 105,
  "nonzero": 0,
  "p": 1.0,
  "mean_diff": 0.0
 },
 "recall@0.25: CodeTwin vs Random": {
  "n": 105,
  "nonzero": 42,
  "p": 1.9616219011103327e-08,
  "mean_diff": 0.12683918219068596
 },
 "recall@0.5: CodeTwin vs Coverage-ranked": {
  "n": 105,
  "nonzero": 1,
  "p": 0.31731050786291415,
  "mean_diff": -0.002380952380952381
 },
 "recall@0.5: CodeTwin vs Random": {
  "n": 105,
  "nonzero": 44,
  "p": 7.600383585977628e-09,
  "mean_diff": 0.11280904233038244
 },
 "safety: CRC(alpha=0.1) vs Line coverage": {
  "a_only": 9,
  "b_only": 0,
  "p": 0.00390625
 },
 "time_red: CRC(alpha=0.1) vs Line coverage": {
  "n": 107,
  "nonzero": 65,
  "p": 2.4051050298460756e-12,
  "mean_diff": -0.47817326422241957
 },
 "safety: CRC(alpha=0.1) vs Function coverage": {
  "a_only": 7,
  "b_only": 0,
  "p": 0.015625
 },
 "time_red: CRC(alpha=0.1) vs Function coverage": {
  "n": 107,
  "nonzero": 68,
  "p": 2.9936119189604826e-12,
  "mean_diff": -0.463827864798959
 },
 "safety: CRC(alpha=0.1) vs File coverage": {
  "a_only": 0,
  "b_only": 1,
  "p": 1.0
 },
 "time_red: CRC(alpha=0.1) vs File coverage": {
  "n": 107,
  "nonzero": 83,
  "p": 2.7979138683128402e-09,
  "mean_diff": -0.3607995750977731
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
 "anuraghazra_m_github-readme-stats": {
  "cov_line": 4.873527455120481,
  "cov_func": 0.8837528778263539,
  "cov_file": 2.1890921885473253,
  "static_inv_dist": 0.8985255767341209,
  "name_match": 0.7585765780595428,
  "cochange": 0.3828494056569086,
  "test_changed": 8.06332188785881
 },
 "burntsushi_m_ripgrep": {
  "cov_line": 4.874356861984686,
  "cov_func": 0.6687972422445425,
  "cov_file": 2.341321679949692,
  "static_inv_dist": 0.8448575389892793,
  "name_match": 0.8311094441140272,
  "cochange": 0.3899384692925381,
  "test_changed": 7.7165876490743015
 },
 "clap-rs_m_clap": {
  "cov_line": 4.408761587074247,
  "cov_func": 1.3577348212169147,
  "cov_file": 2.7470235978840343,
  "static_inv_dist": 0.568752663617407,
  "name_match": 0.9383534351993306,
  "cochange": 0.38243177736755257,
  "test_changed": 7.955445194678286
 },
 "cli_m_cli": {
  "cov_line": 4.707576768905796,
  "cov_func": 0.46835882786775346,
  "cov_file": 2.440362404557014,
  "static_inv_dist": 1.3613636678804903,
  "name_match": 1.1263655889003144,
  "cochange": 0.30436953234031816,
  "test_changed": 7.95859622375788
 },
 "grpc_m_grpc-go": {
  "cov_line": 4.524827942966445,
  "cov_func": 0.7484320471755929,
  "cov_file": 3.108764235540022,
  "static_inv_dist": 0.19629840333718257,
  "name_match": 0.6653754158922006,
  "cochange": 1.338775496466348,
  "test_changed": 8.280331269198804
 },
 "iamkun_m_dayjs": {
  "cov_line": 4.611513992010695,
  "cov_func": 0.6295449542060008,
  "cov_file": 2.6506217796221203,
  "static_inv_dist": 0.7082544026731746,
  "name_match": 0.7437869501295845,
  "cochange": 0.5479839833834276,
  "test_changed": 8.02161853019284
 },
 "sharkdp_m_fd": {
  "cov_line": 4.86605818447894,
  "cov_func": 0.6702492342534085,
  "cov_file": 2.3977714171317808,
  "static_inv_dist": 0.8859080519104098,
  "name_match": 0.7887861494262105,
  "cochange": 0.5747499190778218,
  "test_changed": 8.013041827778691
 },
 "sveltejs_m_svelte": {
  "cov_line": 4.873216903557129,
  "cov_func": 0.6630396311395348,
  "cov_file": 2.418982676139839,
  "static_inv_dist": 0.8822296772051031,
  "name_match": 0.7853668988022021,
  "cochange": 0.608227781491696,
  "test_changed": 8.032605533295749
 },
 "tokio-rs_m_tokio": {
  "cov_line": 4.829505202739993,
  "cov_func": 0.6752191258203859,
  "cov_file": 2.2154287311303142,
  "static_inv_dist": 0.8743104677710559,
  "name_match": 0.7250526635925338,
  "cochange": 0.5121285347212461,
  "test_changed": 7.69304373782324
 },
 "tokio-rs_m_tracing": {
  "cov_line": 5.798846705745437,
  "cov_func": 0.4133797118712862,
  "cov_file": 1.2921572974050821,
  "static_inv_dist": 2.056829876803582,
  "name_match": 0.7900028688846542,
  "cochange": 0.9512180706989871,
  "test_changed": 7.636301660369727
 },
 "zeromicro_m_go-zero": {
  "cov_line": 4.875376408205568,
  "cov_func": 0.637144092764872,
  "cov_file": 2.3453785492035006,
  "static_inv_dist": 0.9046287727485008,
  "name_match": 0.7392178216668681,
  "cochange": 0.7205954096978355,
  "test_changed": 7.925799723165564
 }
}
```

## Failure cases (CRC alpha=0.1, unsafe)

```
{
 "anuraghazra_m_github-readme-stats": [],
 "burntsushi_m_ripgrep": [],
 "clap-rs_m_clap": [
  {
   "sha": "44a8976",
   "subject": "PR 2161",
   "safe": false,
   "time_red": 0.4591949157774442,
   "missed": [
    "tests/arg_aliases_short.rs"
   ],
   "missed_scores": [
    0.015
   ],
   "trig_line": [],
   "trig_file": [
    "untested_change"
   ],
   "fault_safe": true,
   "mut_n": 0
  },
  {
   "sha": "6bf9e89",
   "subject": "PR 2154",
   "safe": false,
   "time_red": 0.8124538838645672,
   "missed": [
    "tests/template_help.rs",
    "tests/version.rs"
   ],
   "missed_scores": [
    0.186,
    0.196
   ],
   "trig_line": [],
   "trig_file": [],
   "fault_safe": true,
   "mut_n": 0
  }
 ],
 "cli_m_cli": [],
 "grpc_m_grpc-go": [],
 "iamkun_m_dayjs": [],
 "sharkdp_m_fd": [],
 "tokio-rs_m_tokio": [],
 "tokio-rs_m_tracing": [],
 "zeromicro_m_go-zero": []
}
```
