# Carleton Room Booker

A personal Python and Playwright project that checks Carleton University's LibCal study-room availability and prepares a selection for manual confirmation.

## What it does

- Finds the next Tuesday using the America/Toronto timezone. Running on a Tuesday targets the following Tuesday.
- Looks for room 421 from 14:30 to 17:30 by default.
- Checks every half-hour slot before selecting a start time.
- Selects the requested ending time only if LibCal offers it.
- Keeps the browser open for review. It never clicks **Submit Times**.

A prepared selection is not a confirmed reservation. Complete the website's remaining steps yourself.

## Setup (macOS)

Requires Python 3.9 or newer. Download this repository using **Code → Download ZIP**, extract it, then open the extracted folder in VS Code.

In a terminal inside that folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

For later runs, activate the environment and run `python main.py` again.

## Configuration

Edit these values near the top of `main.py`:

```python
PREFERRED_ROOM = "421"
START_TIME = "14:30"
END_TIME = "17:30"
```

Use same-day times on half-hour boundaries (`:00` or `:30`), with the end later than the start. Save before running.

## Manual confirmation

Review the date, room, and times in the browser before continuing. Pressing Enter in the terminal closes the browser; it does not submit a reservation.

If the script stops after selecting a start time, the page may still show a shorter default booking. Do not treat it as the requested booking unless the script reports it prepared and you verify the details.

## Project status and limitations

The room lookup, availability checks, and preparation of a 14:30–15:00 selection were manually tested in November 2026. The revised month-navigation selector has not yet been confirmed by a successful live run. A full 14:30–17:30 selection remains dependent on availability and LibCal's offered ending times.

The script relies on LibCal's page structure and calendar positions. Website changes may require selector updates. An availability-check failure may indicate an occupied slot or an unrecognized page layout. Availability can change before confirmation.

This is an unofficial personal project and is not affiliated with Carleton University. It does not run on a schedule, bypass booking limits, or guarantee a reservation.

## Files

- `main.py`: booking preparation script
- `requirements.txt`: Python dependency, pinned to the development environment's installed version
- `.gitignore`: excludes local environments, caches, and local configuration
