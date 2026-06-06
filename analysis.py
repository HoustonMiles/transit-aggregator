import os
import pandas as pd
from pymongo import MongoClient
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

# Connect to MongoDB
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["transit_aggregator"]
collection = db["articles"]

# Load all articles into a DataFrame
docs = list(collection.find({}, {'_id': 0}))
df = pd.DataFrame(docs)

print(f"Total articles: {len(df)}\n")

# --- Analysis 1: Article count by agency ---
print("=== Articles by Agency ===")
print(df.groupby(['city', 'agency']).size().reset_index(name='count').to_string(index=False))

# --- Analysis 2: Article count by city ---
print("\n=== Articles by City ===")
print(df.groupby('city').size().reset_index(name='count').to_string(index=False))

# --- Analysis 3: Top keywords in headlines ---
print("\n=== Top 20 Keywords in Headlines ===")
stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 
             'or', 'is', 'are', 'with', 'after', 'new', 'as', 'from', 'that',
             'over', 'its', 'by', 'be', 'into', 'has', 'will', 'but', 'up'}
words = []
for headline in df['headline'].dropna():
    for word in headline.lower().split():
        word = word.strip('.,!?:;"\'-')
        if word and word not in stopwords and len(word) > 2:
            words.append(word)
top_words = Counter(words).most_common(20)
for word, count in top_words:
    print(f"  {word:<20} {count}")

# --- Analysis 4: Keywords by city ---
print("\n=== Top 10 Keywords by City ===")
for city in df['city'].unique():
    city_df = df[df['city'] == city]
    words = []
    for headline in city_df['headline'].dropna():
        for word in headline.lower().split():
            word = word.strip('.,!?:;"\'-')
            if word and word not in stopwords and len(word) > 2:
                words.append(word)
    top = Counter(words).most_common(10)
    print(f"\n  {city}:")
    for word, count in top:
        print(f"    {word:<20} {count}")

# --- Analysis 5: Coverage comparison ---
print("\n=== Coverage Comparison (Southeast vs Major Cities) ===")
df['region'] = df['city'].apply(lambda x: 'Southeast' if x == 'Charleston' else 'Major City')
print(df.groupby('region').size().reset_index(name='count').to_string(index=False))

# --- Analysis 6: Summary Stats ---
print("\n=== Summary Statistics ===")
print(f"Total articles: {len(df)}")
print(f"Sources: {df['agency'].nunique()} agencies across {df['city'].nunique()} cities")
print(f"\nDate range per agency:")
df_dated = df[df['date'].notna()]
for agency in df_dated['agency'].unique():
    agency_df = df_dated[df_dated['agency'] == agency]
    print(f"  {agency}: {agency_df['date'].min()} → {agency_df['date'].max()}")

# --- Analysis 7: Sentiment Analysis ---
print("\n=== Sentiment Analysis by City ===")
from textblob import TextBlob

def get_sentiment(text):
    if not text:
        return None
    score = TextBlob(str(text)).sentiment.polarity
    if score > 0.1:
        return 'positive'
    elif score < -0.1:
        return 'negative'
    else:
        return 'neutral'

df['sentiment'] = df['headline'].apply(get_sentiment)
print(df.groupby(['city', 'sentiment']).size().unstack(fill_value=0).to_string())

print("\n=== Average Sentiment Score by City ===")
df['sentiment_score'] = df['headline'].apply(
    lambda x: TextBlob(str(x)).sentiment.polarity if x else None
)
print(df.groupby('city')['sentiment_score'].mean().round(3).to_string())

categories = {
    'Infrastructure': ['bridge', 'road', 'station', 'construction', 'improvement', 'project', 'plan', 'repair'],
    'Safety': ['crash', 'accident', 'safety', 'death', 'killed', 'stabbing', 'crime', 'warning'],
    'Policy/Politics': ['mamdani', 'hochul', 'board', 'bill', 'budget', 'admin', 'council', 'program'],
    'Service': ['service', 'delay', 'strike', 'train', 'bus', 'subway', 'lirr', 'mta', 'route'],
    'Fares/Costs': ['fare', 'fares', 'price', 'cost', 'free', 'discount', 'gas'],
}

def categorize(headline):
    headline = headline.lower()
    for category, keywords in categories.items():
        if any(kw in headline for kw in keywords):
            return category
    return 'Other'

df['category'] = df['headline'].dropna().apply(categorize)
print(df.groupby(['city', 'category']).size().unstack(fill_value=0).to_string())
