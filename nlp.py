import re
import nltk
import json
import random

# import nltk
# nltk.download("vader_lexicon")
# from nltk.sentiment.vader import SentimentIntensityAnalyzer

def inquiry_reply_parser(text, sentiments):
    """
    Returns a somewhat appropriate response to a given inquiry and response before inquiry.
    """
    neg = 0
    pos = 0
    print(text)
    
    # parse inquiry
    text = text.lower().strip()
    if "could be worse" in text:
        pos += 2
    if "could be better" in text:
        neg += 2
    if "not bad" in text:
        neg -= 4
        pos += 4
        
    text = nltk.word_tokenize(text)

    positive_words = ['good', 'great', 'amazing', 'great', 
                      'joy', 'positive', 'awesome']
    negative_words = ['meh', 'bad', 'evil', 'not']
    
    negative_responses = ["Hopefully things get better for you.", "Sorry to hear about that.", 
                          "I hope your situation will improve soon."]
    positive_responses = ["I'm glad you're doing well!", 
                          "Awesome!",
                          "Wow! Glad to hear :)"]
    neutral_responses = ["I am doing fine.", 
                         "Pretty good for me."]
    
    for word in text:
        if word in sentiments['positive']:
            pos += 1
            continue
        elif word in sentiments['negative']:
            neg += 1
            continue
        elif word in sentiments['fear']:
            neg += 1
            continue
        elif word in sentiments['sadness']:
            neg += 1
            continue
        elif word in sentiments['anger']:
            neg += 1
            continue
        elif word in sentiments['surprise']:
            pos += 1
            continue
        elif word in sentiments['disgust']:
            neg += 1
            continue
        elif word in sentiments['joy']:
            pos += 1
            continue
        elif word in sentiments['anticipation']:
            neg += 1
    
    for i in negative_words:
        if i in text:
            neg += 2
            break
        
    for i in positive_words:
        if i in text:
            pos += 2
            break
              
    print(neg, pos)
    
    # respond appropriately
    if neg > pos:
        return random.choice(negative_responses) + " " + random.choice(neutral_responses)
    elif neg < pos:
        return random.choice(positive_responses) + " " + random.choice(neutral_responses)
    else:
        return random.choice(neutral_responses)

def word_overlap(sent1, sent2):
    words1, words2 = set(nltk.word_tokenize(sent1.lower())), set(nltk.word_tokenize(sent2.lower()))
    return len(words1.intersection(words2))

# class SentimentAnalyzer:
#     def __init__(self):
#         self.analyzer = SentimentIntensityAnalyzer()

#     def sentiment(self, sent):
#         # returns neg, neu, pos, compound
#         scores = self.analyzer.polarity_scores(sent)
#         return max(scores)
