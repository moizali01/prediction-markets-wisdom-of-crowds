import signal
import sys
import pickle
import requests
from os import path

import backoff
from requests_ratelimiter import LimiterSession
from sqlite_utils import Database
from yaspin import yaspin

def setup_db() :
    db = Database('inactive_events.db')

    return db



def scrape_all_inactive_events() :

    db = setup_db()
    session = LimiterSession(per_second=5) # Rate limit to 5 requests per second
    checkpoint_path = './inactive_events_checkpoint.pkl'

    try :
        state = pickle.load(open(checkpoint_path,'rb'))
    except :

        print(f"No checkpoint file found under {checkpoint_path}. Starting from scratch")

        state = {
            'offset' : 0,
            'inactive' : True,
        }

    def sighandler(signum,frame) :
        # Create a checkpoint
        with open("inactive_events_checkpoint.pkl","wb") as f:
            pickle.dump(state,f)

        sys.exit()

    # Register signal handlers to save checkpoints
    signal.signal(signal.SIGINT,sighandler)
    signal.signal(signal.SIGQUIT,sighandler)
    signal.signal(signal.SIGSEGV,sighandler)
    signal.signal(signal.SIGTERM,sighandler)


    try : 
        with yaspin(text="Processing...",timer=True) as spinner :
            while True : 
                resp = list_inactive_events(session,{
                    'params' : {
                        'limit' : '100',
                        **state
                    }
                })

                try : 
                    payload = resp.json()
                except Exception as e :
                    print(f"Couldn't decode response as JSON : {e}")
                    break

                if not isinstance(payload,list) :
                    print(f"Received unknown payload type : {payload},{type(payload)}")
                    break

                if len(payload) == 0 :
                    print("No data returned. Done scraping!")
                    break

                with open(f"resps/resp_{state['offset']}.jsonl","w") as f :
                    # Create a local copy of the response
                    f.write(str(payload))

                db["inactive_events"].insert_all(
                    payload,
                    alter=True,
                )

                # Move on to the next page of responses
                state['offset'] += min(100,len(payload))

                spinner.text = f"Scraping {state['offset']}th record"

    except Exception as e :
        print(f"Unknown exception occurred. Error : {e}")

    # Create a checkpoint
    with open("inactive_events_checkpoint.pkl","wb") as f:
        pickle.dump(state,f)

    return

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_tries=5)
def list_inactive_events(session : requests.Session, args : dict):

    url = 'https://gamma-api.polymarket.com/inactive_events'
    resp : requests.Response = session.get(url,**args)

    return resp


if __name__ == "__main__" :
    scrape_all_inactive_events()
