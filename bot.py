import argparse
import json
import textwrap
import GetOldTweets3 as got

from dotenv import load_dotenv
from os import environ
from expiringdict import ExpiringDict
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy import API

load_dotenv()

# store Twitter specific credentials
CONSUMER_KEY = environ["CONSUMER_KEY"]
CONSUMER_SECRET = environ["CONSUMER_SECRET"]
ACCESS_TOKEN_KEY = environ["ACCESS_TOKEN_KEY"]
ACCESS_TOKEN_SECRET = environ["ACCESS_TOKEN_SECRET"]
ACCOUNT_SCREEN_NAME = "quedijo__"
ACCOUNT_USER_ID = "1269034001639059459"
TRACK = "#quedijo sobre"


class ReplyToTweet(StreamListener):
    def __init__(self, api):
        self.api = api
        self.__max_per_user = 5  # max replies per user within an hour
        self.__rate_limits_per_user = ExpiringDict(
            max_len=1000, max_age_seconds=(1 * 60)
        )

    def on_data(self, data):
        if not data:
            return

        tweet = json.loads(str(data).strip())
        retweeted = tweet.get("retweeted")
        from_self = False  # tweet.get('user', {}).get('id_str','') == ACCOUNT_USER_ID
        print(tweet)

        requesting_user = tweet.get("user", {}).get("screen_name")
        requesting_tweet_id_str = tweet.get("id_str")
        mentioned_user = (
            tweet.get("entities", {}).get("user_mentions", [])[0].get("screen_name")
        )
        query = extract_query_from_tweet(tweet.get("text"), mentioned_user)

        thread = []
        criteria = (
            got.manager.TweetCriteria()
            .setQuerySearch("from:%s %s" % (mentioned_user, query))
            .setTopTweets(True)
        )
        for result in got.manager.TweetManager.getTweets(criteria):
            thread.append(result.permalink)

        if len(thread) == 0:
            print("Nothing found. Replying...")
            last_tweet = self.api.update_status(
                "No encontré nada al respecto 🤔",
                in_reply_to_status_id=requesting_tweet_id_str,
                auto_populate_reply_metadata=True,
            )
        else:
            print("Creating thread...")
            text = 'Esto fue lo que dijo @%s sobre "%s"' % (mentioned_user, query)
            last_tweet = self.api.update_status(build_status(text))
            thread_id_str = last_tweet.id_str
            print(
                "Thread: https://twitter.com/%s/status/%s"
                % (ACCOUNT_SCREEN_NAME, thread_id_str)
            )
            for text in thread:
                last_tweet = self.api.update_status(
                    build_status(text),
                    in_reply_to_status_id=last_tweet.id_str,
                    auto_populate_reply_metadata=True,
                )
                print(
                    "Tweet: https://twitter.com/%s/status/%s"
                    % (ACCOUNT_SCREEN_NAME, thread_id_str)
                )

            print("Replying to request...")
            self.api.update_status(
                "https://twitter.com/%s/status/%s"
                % (ACCOUNT_SCREEN_NAME, thread_id_str),
                in_reply_to_status_id=requesting_tweet_id_str,
                auto_populate_reply_metadata=True,
            )

        print(
            "Replied:  https://twitter.com/%s/status/%s"
            % (ACCOUNT_SCREEN_NAME, last_tweet.id_str)
        )
        return

    def on_error(self, status):
        print(status)


def extract_query_from_tweet(text, mentioned_user):
    for term in TRACK.split(" "):
        text = text.replace(term, "")

    text = text.replace("@%s" % mentioned_user, "")
    return " ".join(text.split())


def get_auth_link_and_show_token():
    auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.secure = True
    auth_url = auth.get_authorization_url()
    input(
        "Log in to https://twitter.com as the user you want to tweet as and hit enter."
    )
    input("Visit %s in your browser and hit enter." % auth_url)
    pin = input("What is your PIN: ")

    token = auth.get_access_token(verifier=pin)
    print("\nThese are your access token and secret.\nDO NOT SHARE THEM WITH ANYONE!\n")
    print("ACCESS_TOKEN\n%s\n" % token[0])
    print("ACCESS_TOKEN_SECRET\n%s\n" % token[1])


def build_status(text):
    return textwrap.shorten(text, width=280, placeholder="...")


if __name__ == "__main__":
    # Cli options
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true")
    options = parser.parse_args()

    if options.auth:
        get_auth_link_and_show_token()
    else:
        auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.secure = True
        auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
        api = API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
        streamListener = ReplyToTweet(api)
        twitterStream = Stream(auth, streamListener)
        twitterStream.filter(track=[TRACK])
