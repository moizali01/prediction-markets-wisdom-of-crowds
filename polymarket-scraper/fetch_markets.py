import signal
import sys
import pickle
import requests
from os import path

import backoff
from requests_ratelimiter import LimiterSession
from sqlite_utils import Database
from yaspin import yaspin


def setup_db():
    db = Database("markets.db")

    return db


def scrape_all_markets():

    db = setup_db()
    session = LimiterSession(per_second=5)  # Rate limit to 5 requests per second
    checkpoint_path = "./markets_checkpoint.pkl"

    try:
        state = pickle.load(open(checkpoint_path, "rb"))
    except Exception:
        print(
            f"No checkpoint file found under {checkpoint_path}. Starting from scratch"
        )

        state = {
            "offset": 0,
        }

    def sighandler(signum, frame):
        # Create a checkpoint
        with open("markets_checkpoint.pkl", "wb") as f:
            pickle.dump(state, f)

        sys.exit()

    # Register signal handlers to save checkpoints
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGQUIT, sighandler)
    signal.signal(signal.SIGSEGV, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    try:
        with yaspin(text="Processing...", timer=True) as spinner:
            while True:
                resp = list_markets(session, {"params": {"limit": "100", **state}})

                try:
                    payload = resp.json()
                except Exception as e:
                    print(f"Couldn't decode response as JSON : {e}")
                    break

                if not isinstance(payload, list):
                    print(f"Received unknown payload type : {payload},{type(payload)}")
                    break

                if len(payload) == 0:
                    print("No data returned. Done scraping!")
                    break

                with open(f"resps/resp_{state['offset']}.jsonl", "w") as f:
                    # Create a local copy of the response
                    f.write(str(payload))

                db["markets"].insert_all(
                    payload,
                    alter=True,
                )

                # Move on to the next page of responses
                state["offset"] += min(100, len(payload))

                spinner.text = f"Scraping {state['offset']}th record"

    except Exception as e:
        print(f"Unknown exception occurred. Error : {e}")

    # Create a checkpoint
    with open("markets_checkpoint.pkl", "wb") as f:
        pickle.dump(state, f)

    return


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def public_search(session: requests.Session, args: dict):

    url = "https://gamma-api.polymarket.com/search"
    resp: requests.Response = session.get(url, params={**args})

    return resp


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_markets(session: requests.Session, args: dict):

    url = "https://gamma-api.polymarket.com/markets"
    resp: requests.Response = session.get(url, params={**args})

    return resp


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_market_positions(session: requests.Session, market_id: str, args: dict):
    url = "https://data-api.polymarket.com/v1/market-positions"
    resp: requests.Response = session.get(
        url,
        params={
            "market": market_id,
            **args,
        },
    )

    return resp


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_trades(session: requests.Session, condition_id: str, args: dict):
    url = "https://data-api.polymarket.com/trades"
    resp: requests.Response = session.get(
        url,
        params={
            "market": condition_id,
            **args,
        },
    )

    return resp


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_prices_history(session: requests.Session, args: dict):
    url = "https://clob.polymarket.com/prices-history"
    resp: requests.Response = session.get(
        url,
        params={**args},
    )

    return resp


if __name__ == "__main__":
    db = Database("price_history.db")
    session = LimiterSession(per_second=5)
    
    market_ids = ["82855088893985825781350466813737280564000275725006328179621744619327480699369", "55194745453074297560900438908357749978780021444937743754846798173575377021411"]

    for market_id in market_ids:
        print(f"Fetching price history for Token ID {market_id}...")
        
        try:
            # We can specify an interval like 'max', '1d', '1h', etc. 'max' gives the full history
            resp = get_prices_history(session, {"market": market_id, "interval": "max"})
            
            if resp.status_code == 200:
                data = resp.json()
                # The API returns data points under the "history" key natively
                history = data.get("history", [])
                
                print(f"Fetched {len(history)} price history data points for target asset.")
                
                if len(history) > 0:
                    # Add the market_id to each record so you can query multiple markets easily
                    for record in history:
                        record["market_id"] = market_id
                        
                    db["price_history"].insert_all(history, alter=True)
                    print("Successfully saved price history to new_assets.db")
                else:
                    print("No price history returned for this market.")
            else:
                print(f"Error fetching data: HTTP {resp.status_code} - {resp.text}")
                
        except Exception as e:
            print(f"Failed to fetch or parse price history: {e}")