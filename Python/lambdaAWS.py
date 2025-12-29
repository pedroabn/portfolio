import json
import pandas as pd
from datetime import datetime, timedelta

DATA_PATH = "data/cart_events.csv"

def lambda_handler(event, context=None):
    try:
        # simula query string ?week=YYYY-MM-DD
        week_start = event.get("queryStringParameters", {}).get("week")

        if not week_start:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Parâmetro 'week' é obrigatório"})
            }

        week_start = pd.to_datetime(week_start)
        week_end = week_start + timedelta(days=6)

        df = pd.read_csv(DATA_PATH, parse_dates=["date"])

        df_week = df[(df["date"] >= week_start) & (df["date"] <= week_end)]

        result = (
            df_week
            .groupby(["product_id", "product_name"])
            .size()
            .reset_index(name="add_to_cart_count")
            .sort_values("add_to_cart_count", ascending=False)
            .head(5)
        )

        return {
            "statusCode": 200,
            "body": result.to_json(orient="records")
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
