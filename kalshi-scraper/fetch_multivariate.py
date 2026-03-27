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
    db = Database('multivariate.db')
    return db

def scrape_all_multivariate() :

    db = setup_db()
    session = LimiterSession(per_second=4) # Rate limit to 5 requests per second
    checkpoint_path = './multivariate_checkpoint.pkl'

    try :
        state = pickle.load(open(checkpoint_path,'rb'))
    except :

        print(f"No checkpoint file found under {checkpoint_path}. Starting from scratch")

        state = {
            'cursor' : None,
        }

    if not os.path.isdir("./multivariate_resps/") :
        os.mkdir('./multivariate_resps/')

    def sighandler(signum,frame) :
        # Create a checkpoint
        with open("multivariate_checkpoint.pkl","wb") as f:
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
                resp = list_multivariate(session,{
                    'params' : {
                        'limit' : '200',
                        **state
                    }
                })

                try : 
                    payload = resp.json()
                except Exception as e :
                    print(f"Couldn't decode response as JSON : {e}")
                    break

                if 'events' not in payload or not isinstance(payload,dict) :
                    print(f"Received unknown payload type : {payload},{type(payload)}")
                    break

                if  payload['cursor'] == '' or len(payload['events']) == 0 :
                    print("No data returned. Done scraping!")
                    break

                with open(f"multivariate_resps/resp_{resp_count}.jsonl","w") as f :
                    # Create a local copy of the response
                    f.write(str(payload))

                db["multivariate"].insert_all(
                    payload['events'],
                    alter=True,
                )

                resp_count += len(payload['events'])

                # Move on to the next page of responses
                state['cursor'] = payload['cursor']

                spinner.text = f"Scraped {resp_count} records"

    except Exception as e :
        print(f"Unknown exception occurred. Error : {e}")

    # Create a checkpoint
    with open("multivariate_checkpoint.pkl","wb") as f:
        pickle.dump(state,f)

    return

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_tries=5)
def list_multivariate(session : requests.Session, args : dict):

    url = 'https://api.elections.kalshi.com/trade-api/v2/events/multivariate'
    resp : requests.Response = session.get(url,**args)

    return resp


if __name__ == "__main__" :
    scrape_all_multivariate()
