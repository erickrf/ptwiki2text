# -*- coding: utf-8 -*-

"""
Script for reading, parsing and tokenizing data from the Portuguese Wikipedia.

Author: Erick Rocha Fonseca
"""

import logging
import re
from os import path
import nltk
import argparse
from nltk.tokenize.regexp import RegexpTokenizer

from wiki_parser import get_articles

def tokenize(text, wiki=True):
    """
    Returns a list of lists of the tokens in text.
    Each line break in the text starts a new list.
    @param wiki: If True, performs some cleaning action on the text, such as replacing
    numbers for the __NUMBER__ keyword.
    """
    ret = []
    
    if type(text) != unicode:
        text = unicode(text, 'utf-8')
    
    if wiki:
        text = clean_text(text, correct=True)
    else:
        # replace numbers for __NUMBER__ and store them to replace them back
        numbers = re.findall(ur'\d+(?: \d+)*(?:[\.,]\d+)*[²³]*', text)
        numbers.extend(re.findall(ur'[²³]+', text))
        text = re.sub(ur'\d+( \d+)*([\.,]\d+)*[²³]*', '__NUMBER__', text)
        text = re.sub(ur'[²³]+', '__NUMBER__', text)
    
    # clitic pronouns
    regexp = r'''(?ux)
        (?<=\w)                           # a letter before
        -(me|
        te|
        o|a|no|na|lo|la|se|
        lhe|lho|lha|lhos|lhas|
        nos|
        vos|
        os|as|nos|nas|los|las|            # unless if followed by more chars
        lhes)(?![-\w])                    # or digits or hyphens
    '''
    text = re.sub(regexp, r'- \1', text)
    
    regexp = ur'''(?ux)
    # the order of the patterns is important!!
    ([^\W\d_]\.)+|                # one letter abbreviations, e.g. E.U.A.
    __NUMBER__:__NUMBER__|        # time and proportions
    [DSds][Rr][Aa]?\.|            # common abbreviations such as dr., sr., sra., dra.
    [^\W\d_]{1,2}\$|              # currency
    \w+([-']\w+)*-?|              # words with hyphens or apostrophes, e.g. não-verbal, McDonald's
                                  # or a verb with clitic pronoun removed (trailing hyphen is kept)
    -+|                           # any sequence of dashes
    \.{3,}|                       # ellipsis or sequences of dots
    __LINK__|                     # links found on wikipedia
    \S                            # any non-space character
    '''
    
    # loads trained model for tokenizing Portuguese sentences (provided by NLTK)
    sent_tokenizer = nltk.data.load('tokenizers/punkt/portuguese.pickle')
    
    # the sentence tokenizer doesn't consider line breaks as sentence delimiters, so
    # we split them manually.
    sentences = []
    lines = text.split('\n')
    for line in lines:
        sentences.extend(sent_tokenizer.tokenize(line, realign_boundaries=True))
    
    t = RegexpTokenizer(regexp)
    
    for p in sentences:
        if p.strip() == '':
            continue
        
        # Wikipedia cleaning 
        if wiki:
            # discard sentences with troublesome templates or links
            if any((x in p for x in ['__TEMPLATE__', '{{', '}}', '[[', ']]'])):
                continue
        
        new_sent = t.tokenize(p)
        
        if wiki:
            # discard sentences that are a couple of words (it happens sometimes
            # when extracting data from lists).
            if len(new_sent) <= 2:
                continue
        elif len(numbers) > 0:
            # put back numbers that were previously replaced
            for i in xrange(len(new_sent)):
                token = new_sent[i]
                while '__NUMBER__' in token:
                    token = token.replace('__NUMBER__', numbers.pop(0), 1)
                new_sent[i] = token
        
        ret.append(new_sent)
        
    return ret

def clean_text(text, correct=True):
    """
    Apply some transformations to the text, such as mapping numbers to a __NUMBER__ keyword
    and simplifying quotation marks.
    @param correct: If True, tries to correct punctuation misspellings. 
    """
    
    # replaces different kinds of quotation marks with "
    # take care not to remove apostrophes
    text = re.sub(ur"(?u)(\W)[‘’′`']", r'\1"', text)
    text = re.sub(ur"(?u)[‘’`′'](\W)", r'"\1', text)
    text = re.sub(ur'(?u)[«»“”]', '"', text)
    
    if correct:
        # tries to fix mistyped tokens (common in Wikipedia-pt) as ,, '' ..
        text = re.sub(r'(?<!\.)\.\.(?!\.)', '.', text) # take care with ellipses 
        text = re.sub(r'([,";:])\1,', r'\1', text)
        
        # inserts space after leading hyphen. It happens sometimes in cases like:
        # blablabla -that is, bloblobloblo
        text = re.sub(' -(?=[^\W\d_])', ' - ', text)
    
    # replaces numbers with the __NUMBER__ token
    text = re.sub(ur'\d+( \d+)*([\.,]\d+)*[²³]*', '__NUMBER__', text)
    text = re.sub(ur'[²³]+', '__NUMBER__', text)
    
    # replaces special ellipsis character 
    text = re.sub(u'…', '...', text)
    
    return text



def build_corpus_from_wiki(wikifile, output_dir='.', total_articles=0, one_per_file=True):
    """
    Reads a specified number of articles and saves them as a raw text files.
    @param wikifile: path to the Wikipedia XML dump file
    @param total_articles: the maximum number of articles to read. None or 
    any number below 1 means all articles.
    @param one_per_file: saves one article per file.
    @param output_dir: directory where output files should be saved
    """
    
    def save_articles(articles, file_num):
        text = '\n'.join(articles)
        tokens = tokenize(text, wiki=True)
        text = '\n'.join([' '.join(sent) for sent in tokens])
        
        filename = path.join(output_dir, wiki_basename % str(file_num))
            
        with open(filename, 'w') as f:
            f.write(text.encode('utf-8'))
            logger.info('Saved file %s' % filename)

    articles = []
    size = 0
    file_num = 1
    wiki_basename = 'wiki-%s.txt'

    logger = logging.getLogger("Logger")
    
    for article_num, article in enumerate(get_articles(wikifile)):
        
        if one_per_file:
            articles = [article]
            save_articles(articles, article_num)
        else:
            articles.append(article)
            size += len(article)
        
            # at around each 50MB, save to a new file
            if size >= 50000000:
                save_articles(articles, file_num)
                size = 0
                file_num += 1
                articles = []
            
        if (article_num + 1) == total_articles:
            # if max number of articles have already been read
            break
    
    if size > 0 and not one_per_file:
        save_articles(articles, file_num)
    
    logger.info("Successfully read %d articles." % (article_num + 1))


if __name__ == '__main__':
    
    log_format = '%(message)s'
    logging.basicConfig(format=log_format)
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.INFO)
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-i', help='Wikipedia dump file', dest='wikifile', required=True)
    parser.add_argument('-o', help='Output directory', dest='output_dir', default='.')
    parser.add_argument('--one', help='Saves one article per file', action='store_true')
    parser.add_argument('--max', help='Maximum number of articles to read', type=int, default=0)
    args = parser.parse_args()
    
    build_corpus_from_wiki(args.wikifile, args.output_dir, args.max, one_per_file=args.one)

