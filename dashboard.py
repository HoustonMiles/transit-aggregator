import os
import pandas as pd
import matplotlib.pyplot as plt
from pymongo import MongoClient
from collections import Counter
from textblob import TextBlob
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["transit_aggregator"]
collection = db["articles"]

docs = list(collection.find({}, {'_id': 0}))
df = pd.DataFrame(docs)

# --- Prep: categories and sentiment (same as analysis.py) ---
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
df['sentiment_score'] = df['headline'].apply(
    lambda x: TextBlob(str(x)).sentiment.polarity if x else None
)

stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
             'or', 'is', 'are', 'with', 'after', 'new', 'as', 'from', 'that',
             'over', 'its', 'by', 'be', 'into', 'has', 'will', 'but', 'up'}

# --- Build the dashboard ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Transit News Aggregator — Dashboard', fontsize=16, fontweight='bold')

# Panel 1: Articles by city
ax = axes[0, 0]
city_counts = df.groupby('city').size().sort_values(ascending=False)
ax.bar(city_counts.index, city_counts.values, color=['#185FA5', '#3B6D11', '#854F0B'])
ax.set_title('Articles by City')
ax.set_ylabel('Article count')
for i, v in enumerate(city_counts.values):
    ax.text(i, v + 1, str(v), ha='center', fontweight='bold')

# Panel 2: Topic categories by city (stacked bar)
ax = axes[0, 1]
cat_by_city = df.groupby(['city', 'category']).size().unstack(fill_value=0)
cat_by_city.plot(kind='bar', stacked=True, ax=ax, colormap='tab10')
ax.set_title('Topic Categories by City')
ax.set_ylabel('Article count')
ax.legend(fontsize=8, loc='upper right')
ax.tick_params(axis='x', rotation=0)

# Panel 3: Average sentiment by city
ax = axes[1, 0]
sentiment_by_city = df.groupby('city')['sentiment_score'].mean()
colors = ['#639922' if v >= 0 else '#A32D2D' for v in sentiment_by_city.values]
ax.bar(sentiment_by_city.index, sentiment_by_city.values, color=colors)
ax.axhline(0, color='black', linewidth=0.8)
ax.set_title('Average Headline Sentiment by City')
ax.set_ylabel('Sentiment score (-1 to 1)')
for i, v in enumerate(sentiment_by_city.values):
    ax.text(i, v + (0.005 if v >= 0 else -0.015), f'{v:.3f}', ha='center', fontweight='bold')

# Panel 4: Top keywords (overall)
ax = axes[1, 1]
words = []
for headline in df['headline'].dropna():
    for word in headline.lower().split():
        word = word.strip('.,!?:;"\'-')
        if word and word not in stopwords and len(word) > 2:
            words.append(word)
top_words = Counter(words).most_common(10)
labels, counts = zip(*top_words)
ax.barh(labels[::-1], counts[::-1], color='#7F77DD')
ax.set_title('Top 10 Keywords (All Cities)')
ax.set_xlabel('Frequency')

plt.tight_layout()
plt.savefig('dashboard.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved: dashboard.png")
