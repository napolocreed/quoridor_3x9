# 3×9 with 10 walls: branch proof table

The central opening is fixed first. Every legal Player-2 reply is covered by one of the 18 reflection classes below. Each representative was solved in a fresh process and with a fresh transposition table.

| Representative | Forced reply | Covered indices | Child proof depth | Total bound | Nodes | Search seconds |
|---:|---|---|---:|---:|---:|---:|
| 0 | `P(1,1)` | 0 | 33 | 35 | 781,540,088 | 179.548 |
| 1 | `H(0,0)` | 1,2 | 31 | 33 | 388,884,472 | 90.045 |
| 3 | `H(1,0)` | 3,4 | 31 | 33 | 110,791,871 | 23.376 |
| 5 | `H(2,0)` | 5,6 | 31 | 33 | 196,600,639 | 43.196 |
| 7 | `H(3,0)` | 7,8 | 31 | 33 | 258,108,979 | 58.509 |
| 9 | `H(4,0)` | 9,10 | 31 | 33 | 211,777,059 | 46.615 |
| 11 | `H(5,0)` | 11,12 | 31 | 33 | 111,140,125 | 24.200 |
| 13 | `H(6,0)` | 13,14 | 31 | 33 | 93,259,258 | 21.520 |
| 15 | `P(0,0)` | 15,16 | 31 | 33 | 964,808,063 | 228.248 |
| 17 | `V(0,0)` | 17,18 | 31 | 33 | 154,455,837 | 32.684 |
| 19 | `V(1,0)` | 19,20 | 31 | 33 | 41,904,722 | 7.887 |
| 21 | `V(2,0)` | 21,22 | 31 | 33 | 145,819,818 | 31.476 |
| 23 | `V(3,0)` | 23,24 | 31 | 33 | 80,652,667 | 17.563 |
| 25 | `V(4,0)` | 25,26 | 31 | 33 | 99,053,712 | 20.713 |
| 27 | `V(5,0)` | 27,28 | 31 | 33 | 80,847,868 | 15.699 |
| 29 | `V(6,0)` | 29,30 | 31 | 33 | 102,201,210 | 22.032 |
| 31 | `V(7,0)` | 31,32 | 31 | 33 | 161,216,501 | 34.930 |
| 33 | `H(7,0)` | 33,34 | 31 | 33 | 277,284,255 | 61.842 |

Aggregate nodes: **4,260,347,144**. Sequential sum of reported search time: **960.084 seconds**. These totals intentionally double-count states shared between independent branches; that independence is the point.
