import signal
import sys
import pickle
import requests
import os

import backoff
from requests_ratelimiter import LimiterSession
from sqlite_utils import Database
from yaspin import yaspin

def setup_db() :
    db = Database('markets.db')
    return db

def scrape_all_markets() :

    db = setup_db()
    session = LimiterSession(per_second=4) # Rate limit to 5 requests per second
    checkpoint_path = './markets_checkpoint.pkl'

    try :
        state = pickle.load(open(checkpoint_path,'rb'))
    except :

        print(f"No checkpoint file found under {checkpoint_path}. Starting from scratch")

        state = {
            'cursor' : None,
        }

    if not os.path.isdir("./markets_resps/") :
        os.mkdir('./markets_resps/')

    def sighandler(signum,frame) :
        # Create a checkpoint
        with open("markets_checkpoint.pkl","wb") as f:
            pickle.dump(state,f)

        sys.exit()

    # Register signal handlers to save checkpoints
    signal.signal(signal.SIGINT,sighandler)
    signal.signal(signal.SIGQUIT,sighandler)
    signal.signal(signal.SIGSEGV,sighandler)
    signal.signal(signal.SIGTERM,sighandler)


    try : 
        with yaspin(text="Processing...",timer=True) as spinner :

            resp_count = 0

            while True : 
                resp = list_markets(session,{
                    'params' : {
                        'limit' : '1000',
                        **state
                    }
                })

                try : 
                    payload = resp.json()
                except Exception as e :
                    print(f"Couldn't decode response as JSON : {e}")
                    break

                if 'markets' not in payload or not isinstance(payload,dict) :
                    print(f"Received unknown payload type : {payload},{type(payload)}")
                    break

                if  payload['cursor'] == '' or len(payload['markets']) == 0 :
                    print("No data returned. Done scraping!")
                    break

                with open(f"markets_resps/resp_{resp_count}.jsonl","w") as f :
                    # Create a local copy of the response
                    f.write(str(payload))

                db["markets"].insert_all(
                    payload['markets'],
                    alter=True,
                )

                resp_count += len(payload['markets'])

                # Move on to the next page of responses
                state['cursor'] = payload['cursor']

                spinner.text = f"Scraped {resp_count} records"

    except Exception as e :
        print(f"Unknown exception occurred. Error : {e}")

    # Create a checkpoint
    with open("markets_checkpoint.pkl","wb") as f:
        pickle.dump(state,f)

    return

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_tries=5)
def list_markets(session : requests.Session, args : dict):

    url = 'https://api.elections.kalshi.com/trade-api/v2/markets'
    resp : requests.Response = session.get(url,**args)

    return resp


if __name__ == "__main__" :
    scrape_all_markets()
