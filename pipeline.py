import requests
import logging
import os
import json
import time
import psycopg2
from psycopg2.extras import execute_values

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf=8"),
        logging.StreamHandler(),
    ],
)

with open("config.json", encoding="utf=8") as f:
    CONFIG = json.load(f)
    
URL = CONFIG["api_url"]
PARAMS = {
    "latitude": CONFIG["latitude"],
    "longitude": CONFIG["longitude"],
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
    "timezone": "Asia/Kolkata",
    "past_days": CONFIG["past_days"],
    "forecast_days": CONFIG["forecast_days"],
}

def extract():
    wait = 1
    for attempt in range(1, CONFIG["max_tries"] + 1):
        logging.info(f"calling the weather API (attempt {attempt})...")
        try:
            response = requests.get(URL, params=PARAMS, timeout=10)
        except requests.RequestException as e:
            logging.warning(f"Network problem: {e}")
            response = None

        if response is not None and response.status_code == 200:
            data = response.json()
            logging.info(f"API OK: got {len(data["daily"]["time"])} days")
            return data
        
        if response is not None and response.status_code < 500 and response.status_code != 429:
            raise Exception(f"API problem: status {response.status_code}, not retrying")

        if attempt < CONFIG["max_tries"]:
            logging.warning(f"API not ready, waiting {wait} sec before trying again")
            time.sleep(wait)
            wait = wait * 2
    raise Exception(f"API still down after {CONFIG["max_tries"]} tries")

def transform(raw):
    daily = raw["daily"]
    rows = []
    for i in range(len(daily["time"])):
        date = daily["time"][i]
        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]
        rain = daily["precipitation_sum"][i]

        if temp_max is None or temp_min is None:
            logging.warning(f"Skipping {date}: temperature missing")
            continue
        if rain is None:
            rain = 0.0

        rows.append((date, temp_max, temp_min, rain))
    logging.info(f"Transformed {len(rows)} clean rows")
    return rows

def load(rows):
    conn = None
    try:
        conn = psycopg2.connect(
            host=CONFIG["db_host"],
            port=CONFIG["db_port"],
            dbname=CONFIG["db_name"],
            user=CONFIG["db_user"],
            password=os.environ.get("PG_PASSWORD"),
        )
        cur = conn.cursor()

        cur.execute("""
              CREATE TABLE IF NOT EXISTS weather_daily (
                 day       DATE PRIMARY KEY,
                 temp_max  NUMERIC(4, 1),
                 temp_min  NUMERIC(4, 1),
                 rain_mm   NUMERIC(6, 1),
                 loaded_at TIMESTAMP DEFAULT NOW()
             )
        """)

        execute_values(
            cur, 
            """
            INSERT INTO weather_daily (day, temp_max, temp_min, rain_mm)
            VALUES %s
            ON CONFLICT (day) DO UPDATE
            SET temp_max   = EXCLUDED.temp_max,
                temp_min = EXCLUDED.temp_min,
                rain_mm = EXCLUDED.rain_mm,
                loaded_at = Now()
            """,
            rows,
        )

        conn.commit()
        logging.info(f"Loaded {len(rows)} days to into weather_daily")

    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
        logging.error(f"Database problem, nothing saved: {e}")

    finally:
        if conn is not None:
            conn.close()

logging.info(f"Pipeline started for {CONFIG['city']}")
try:
    raw = extract()
    rows = transform(raw)
    # load(rows)
except Exception as e:
    logging.error(f"Pipeline stopped: {e}. Nothing loaded, the old data is safe")
logging.info("Pipeline finished")


