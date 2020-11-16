import re
import json
import string
import requests

from bs4 import BeautifulSoup
from nltk import word_tokenize

client_token = "7EqlHqrqGw3QY_o9irFW_P86AYI3n7nU-LFev3HUBZWU5kHqNzevHXwm8FHWb9cn"
puncts = set(string.punctuation)

def get_lyric_link(artists, name, both = True, debug = False):
    
    """
    Returns the link of the song name given artists + name of the song
    """

    link = "https://api.genius.com/search?q="
    space = "%20"
    headers = {"Authorization": "Bearer " + client_token}
    
    #this could prove disastrous, double check it...
    # update: yes it did, just replace accents.
    name_repl = {"Beyonce": "Beyoncé", 
                 "Amine": "Aminé",
                 "D.R.A.M.": "DRAM",
                 "$ign": "\$ign"}
    repl = {
        "a|á|ạ|à|ả|ã|ă|ắ|ặ|ằ|ẳ|ẵ|â|ấ|ậ|ầ|ẩ|ẫ": "a",
        "é|ẹ|è|ẻ|ẽ|ê|ế|ệ|ề|ể|ễ|ë": "e",
        "í|ị|ì|ỉ|ĩ": "i",
        "ó|ọ|ò|ỏ|õ|ô|ố|ộ|ồ|ổ|ỗ|ơ|ớ|ợ|ờ|ỡ": "o",
        "ú|ụ|ù|ủ|ũ|ư|ứ|ự|ừ|ử|ữ": "u",
        "ý|ỵ|ỳ|ỷ|ỹ": "y"
    }
    artistregex = {
        "\$": "\\\\$"
    }
    filler = [" and ", " featuring ", " & ", " x ", " / "]

    artiststmp = re.sub(",", "", artists)
    name = re.sub(",", "", name)
    
    if both: 
        page = requests.get(link + re.sub(" ", space, name) +
                             space + re.sub(" ", space, artiststmp), headers = headers)

    else:
        page = requests.get(link + re.sub(" ", space, name), headers = headers)

        
    # now that we searched, remove filler words that may not appear
    # in actual song title
    page = json.loads(page.content)["response"]["hits"]
    # print(page)

    for i in filler:
        artiststmp = re.sub(i, " ", artiststmp, flags = re.I | re.S)
        
    tokenized_artist_and_name = word_tokenize(artiststmp + " " + name)
    check = [re.sub(",", "", x) for x in tokenized_artist_and_name if x not in puncts]


    # fix artist tokens to be used in re.search
    for i in artistregex:
        for j in range(len(check)):
            check[j] = re.sub(i, artistregex[i], check[j], flags = re.I | re.S)
            
    if debug:
        print(check, "$$$")    
        
    top = []
    
    if len(page) == 1:
        return page[0]["result"]["path"], page[0]["result"]["full_title"]
    else:
        
        # for each result
        for i in range(len(page)):
            c = 0
            
            # remove accents from title
            title = page[i]["result"]["full_title"]
            for j in repl:
                title = re.sub(j, repl[j], title, flags = re.I | re.S)

            if debug:
                print(title, "###")
                
            # check if every artist + name token in the full title
            # bugs out with parentheses and stuff. fixed with word_tokenize
            for j in check:
                if re.search(j, title, flags = re.I | re.S) != None:
                    c += 1
                    
            # if each word in artist x name combo appears in the full title of the request, 
            # select that one as our candidate
            # might wanna do like 80% or something
            # print(c, len(check))
            if c == len(check):
                try:
                    # no pageview checks; we have a database of random af songs
                    #if page[i]["result"]["stats"]["pageviews"] > 0:
                    return page[i]["result"]["path"], page[i]["result"]["full_title"]
                except KeyError:
                    continue
    
    # if here, we had no results that matched our artist + name.
    # return nothing as we checked 1 or >1
    return "", ""

def scrape_lyrics(artist, name, snip):
    
    # fix artist names w/ these
    # not necessary for title search..possibly
    repl = {
        "á|ạ|à|ả|ã|ă|ắ|ặ|ằ|ẳ|ẵ|â|ấ|ậ|ầ|ẩ|ẫ": "a",
        "é|ẹ|è|ẻ|ẽ|ê|ế|ệ|ề|ể|ễ|ë": "e",
        "í|ị|ì|ỉ|ĩ": "i",
        "ó|ọ|ò|ỏ|õ|ô|ố|ộ|ồ|ổ|ỗ|ơ|ớ|ợ|ờ|ỡ": "o",
        "ú|ụ|ù|ủ|ũ|ư|ứ|ự|ừ|ử|ữ": "u",
        "ý|ỵ|ỳ|ỷ|ỹ": "y",
        "\$": "\\\\$"
    }
    
    base_link = "https://genius.com"
    headers = {"Authorization": "Bearer " + client_token}
    content = requests.get(base_link + snip, headers = headers).content
        
    data = BeautifulSoup(content, "lxml").get_text()
    
    ##########################################
    
    # this regex right here is sketch, its catching some of the javascript links
    # lyric_regex = ".{0," + str(len(row["Name"])) + "}?Lyrics\n.+?More on Genius"
    
    # this regex here assumes the song title is the exact same as the one that appears in the Million Song Dataset
    # accounted for accent normalization.
    name, num_char_removed = title_normalizer(name)
    lyric_regex = name + ".{0," + str(max(num_char_removed + 10, 100)) + "}Lyrics\n?.+?More on Genius"
    
    ##########################################
    
    # get lyrics - possible flow
    # don't subset (stick to this for now, we can just clean it later)
    # subset (don't: the proxies are throwing some strange cloudflare message; causing subsetting to break)
    # remove accents (yes)

    # subset down the data
    # data = data[re.search(base_link + snip, data).end():]    
    try:
        lyrics = re.search(lyric_regex, data, flags = re.I | re.S).group()[:-16]
        
    except AttributeError:
        
        # now replace accents and perform search
        for i in repl:
            name = re.sub(i, repl[i], name, flags = re.I | re.S)
            data = re.sub(i, repl[i], data, flags = re.I | re.S)
            
        name, num_char_removed = title_normalizer(name)
        lyric_regex = name + ".{0," + str(max(num_char_removed + 10, 100)) + "}Lyrics\n?.+?More on Genius"
           
        try:
            lyrics = re.search(lyric_regex, data, flags = re.I | re.S).group()[:-16]
            
        # unable to get lyrics
        except AttributeError:
            lyrics = ""

    return lyrics

def title_normalizer(name):
    """
    changes all punctuation in a song title to match any character.
    important because these cause no match in the search. 
    
    For example:
    - genius has: Won’t Get Up Again
    - we have: Won't Get Up Again
    
    also for cases such as parentheses:
    - genius has The Darkness (Darker Mix By Komor Kommando)
    - we have: The Darkness (Darker Mix)
    
    returns: cleaned title, number of characters removed
    
    """
    
    # step 1: remove all the parentheses stuff
    
    n = re.sub("\(.+?\)", "", name, flags = re.I | re.S).strip()
    
    # step 2: change punct to match any character
    s = ''
    for i in range(len(n)):
        if n[i] in puncts:
            s += '.'
        else:
            s += n[i]
    
    return s, len(name) - len(s)

def title_normalizer_cloudflare(name):
    """
    changes all punctuation in a song title to match any character.
    also changes stuff in parentheses to match any character
    
    returns: cleaned title
    
    """
    
    n = list(re.finditer('\(.+?\)', name, flags = re.I | re.S))
    
    s = ''
    for i in range(len(name)):
        
        flag = False
        # step 1: remove all the parentheses stuff, match any char
        for possible_match in n:
            if (possible_match.start() <= i < possible_match.end()):
                s += '.'
                flag = True
                continue
        if flag:
            continue
            
        # step 2: change punct to match any character
        if name[i] in puncts:
            s += '.'
        else:
            s += name[i]
    
    return s

def get_lyrics(text):
    text = [x.strip() for x in text.split(" by ")]
    print(text)
    artists, name = text[1], text[0]
    lyric_link, full_title = get_lyric_link(artists, name)
    print("Lyric link is", lyric_link)
    print("Full title is", full_title)
    lyrics = scrape_lyrics(artists, name, lyric_link)
    

    if 'cloud_flare_always_on_short_message' in lyrics:
        name_regex = title_normalizer_cloudflare(lyrics.split("|")[0].strip())
        idxs = list(re.finditer(name_regex, lyrics, flags = re.I | re.S))
        lyrics = lyrics[idxs[-1].start():]  

    lyrics = lyrics.strip()
    lyrics = re.sub("\[.+?\]", "", lyrics)
    lyrics = re.sub("[Aa]lbum", "", lyrics)

    print(re.sub("\n+", "\n", lyrics.strip()))

    return lyric_link, re.sub("\n+", "\n", lyrics).strip()
