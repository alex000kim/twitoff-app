from os import getenv

import spacy
import tweepy

from src.models import DB, User, Tweet

TWITTER_CONSUMER_KEY = getenv('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = getenv('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = getenv('TWITTER_ACCESS_TOKEN_SECRET')

TWITTER_AUTH = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
TWITTER_AUTH.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
TWITTER = tweepy.API(TWITTER_AUTH)

# using a small spacy model because heroku's free dynos can't handle a bigger model
# performance of the small model won't be good
SPACY_MODEL_NAME = "en_core_web_sm"
if not spacy.util.is_package(SPACY_MODEL_NAME):
    spacy.cli.download(SPACY_MODEL_NAME)

nlp = spacy.load(SPACY_MODEL_NAME)


def vectorize_tweet(tweet_text):
    return nlp(tweet_text).vector


def add_or_update_user(name):
    """
    Add or update a user and their tweets.
    Throw an error if user doesn't exist or is private
    """
    try:
        twitter_user = TWITTER.get_user(name)
        db_user = User.query.get(twitter_user.id) or User(id=twitter_user.id, name=name)
        tweets = twitter_user.timeline(count=200,
                                       exclude_replies=True,
                                       include_rts=False,
                                       since_id=db_user.newest_tweet_id)

        if tweets:
            db_user.newest_tweet_id = tweets[0].id

        for tweet in tweets:
            embedding = vectorize_tweet(tweet.text)
            db_tweet = Tweet(id=tweet.id, text=tweet.text, embedding=embedding)
            db_user.tweets.append(db_tweet)

        DB.session.add(db_user)
        DB.session.commit()
    except Exception as e:
        print(f'Unable to process user {name}: {str(e)}')


def update_all_users():
    """Update all Tweets for all Users in the User table."""
    for user in User.query.all():
        add_or_update_user(user.name)
