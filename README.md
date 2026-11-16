# Madurai Weather Pipeline

This project gets the daily weather for Madurai from a free weather API and saves it in a PostgreSQL table. I built it in week 8 of my data engineering study plan.

It gets the last 7 days and the next 7 days. When I run it again, it does not add the same day twice. It only updates the day with the newest forecast.

## How it works

- Extract: calls the Open-Meteo API. If the API is down, it waits and tries again (up to 3 times).
- Transform: the API sends the dates and temperatures as separate lists, so I join them into one row per day. If a temperature is missing I skip that day, and if rain is missing I use 0.
- Load: saves the rows into the weather_daily table using UPSERT. If something goes wrong, nothing is saved.

Every step is written to logs/pipeline.log and also shown on the screen.

## How to run

You need Python and PostgreSQL installed.

1. Open the project folder in a terminal.
2. Create the virtual environment and switch it on:

   py -m venv .venv
   .venv\Scripts\Activate.ps1

3. Install the libraries:

   pip install -r requirements.txt

4. Set your Postgres password:

   $env:PG_PASSWORD = "your password"

5. Run it:

   python pipeline.py

The table is created automatically the first time.

## Settings

All the settings are in config.json: the city, the location, how many days to get, the database details and the API address. To change something, you only edit this file, not the code.

The password is not in config.json because this file goes to GitHub. The password stays in an environment variable on my computer.

## What I learned

- How to call an API from Python and check the status code before using the data.
- A pipeline should be safe to run more than once. My first try added duplicate rows. UPSERT fixed it.
- If one row is bad, rollback makes sure nothing is half saved.
- How to retry when an API is down instead of crashing.
- Small mistakes break things: a missing letter in a setting name, or an extra comma at the end of a JSON file.
- Setting up the Postgres password took me a long time, but now I understand where it is used.
