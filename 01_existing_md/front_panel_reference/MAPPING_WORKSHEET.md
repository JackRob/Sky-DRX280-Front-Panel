# DR-X280 front-panel live mapping worksheet

Run the console with logging enabled before filling this in:

```powershell
py serial_console.py --log frontpanel-test.txt
```

Keep the raw hexadecimal values in the log. They are the useful evidence even
if a provisional name printed by the tester is wrong.

## Front-panel buttons

Press only one button at a time. Hold it briefly, wait for both its `pressed=`
and `released=` reports, then move to the next button.

| Physical label | Press mask | Release mask | Printed name / notes |
|---|---:|---:|---|
| Rewind |  |  |  |
| Stop |  |  |  |
| Record |  |  |  |
| Play |  |  |  |
| Pause |  |  |  |
| Fast-forward |  |  |  |
| Back Up |  |  |  |
| Info |  |  |  |
| TV Guide |  |  |  |
| Up |  |  |  |
| Left |  |  |  |
| Select |  |  |  |
| Right |  |  |  |
| Down |  |  |  |
| Standby/power |  |  |  |

## Six logical status channels

For each row, enter `led N 2`, observe the front panel, record the result, and
then enter `off` before testing the next row.

| Logical channel | Visible lamp / label | Colour | Physical location / notes |
|---:|---|---|---|
| 0 |  |  |  |
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |

## Eight logical ring positions

For each row, enter `ring N 2`, record the lit segment's position, and then
enter `off`. A clock-face description such as “12 o'clock” is ideal.

| Logical position | Clock-face / physical position | Notes |
|---:|---|---|
| 0 |  |  |
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |

## Experimental IR captures

Enter `ir on`, point the original remote at the panel, and press one remote key
at a time. Paste three repeated raw reports for each key so repeat/toggle bits
can be separated from the key identity. Finish with `ir off`.

| Remote key | Raw capture 1 | Raw capture 2 | Raw capture 3 | Notes |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
