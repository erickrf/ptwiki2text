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

from wiki_parser import get_articles, filter_markup

# these variables appear at module level for faster access and to avoid
# repeated initialization

_tokenizer_regexp = ur'''(?ux)
    # the order of the patterns is important!!
    ([^\W\d_]\.)+|                # one letter abbreviations, e.g. E.U.A.
    \d{1,3}(\.\d{3})*(,\d+)|      # numbers in format 999.999.999,99999
    \d{1,3}(,\d{3})*(\.\d+)|      # numbers in format 999,999,999.99999
    \d+:\d+|                      # time and proportions
    \d+([-\\/]\d+)*|              # dates. 12/03/2012 12-03-2012
    [DSds][Rr][Aa]?\.|            # common abbreviations such as dr., sr., sra., dra.
    [Mm]\.?[Ss][Cc]\.?|           # M.Sc. with or without capitalization and dots
    [Pp][Hh]\.?[Dd]\.?|           # Same for Ph.D.
    [^\W\d_]{1,2}\$|              # currency
    (?:(?<=\s)|^)[\#@]\w*[A-Za-z_]+\w*|  # Hashtags and twitter user names
    \w+([-']\w+)*-?|              # words with hyphens or apostrophes, e.g. não-verbal, McDonald's
                                  # or a verb with clitic pronoun removed (trailing hyphen is kept)
    -+|                           # any sequence of dashes
    \.{3,}|                       # ellipsis or sequences of dots
    __LINK__|                     # links found on wikipedia
    \S                            # any non-space character
    '''
_tokenizer = RegexpTokenizer(_tokenizer_regexp)

# clitic pronouns
_clitic_regexp_str = r'''(?ux)
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
_clitic_regexp = re.compile(_clitic_regexp_str)

def tokenize(text, wiki=True, min_sentence_size=0):
    """
    Returns a list of lists of the tokens in text.
    Each line break in the text starts a new list.
    
    :param wiki: If True, performs some cleaning action on the text, 
        such as replacing any digit for 9.
    :param min_sentence_size: If greater than zero, sentences
        with fewer tokens than this number will be discarded. 
    """
    ret = []
    
    if type(text) != unicode:
        text = unicode(text, 'utf-8')
    
    if wiki:
        text = clean_text(text, correct=True)
    
    text = _clitic_regexp.sub(r'- \1', text)
    
    # loads trained model for tokenizing Portuguese sentences (provided by NLTK)
    sent_tokenizer = nltk.data.load('tokenizers/punkt/portuguese.pickle')
    
    # the sentence tokenizer doesn't consider line breaks as sentence delimiters, so
    # we split them manually.
    sentences = []
    lines = text.split('\n')
    for line in lines:
        sentences.extend(sent_tokenizer.tokenize(line, realign_boundaries=True))
    
    for p in sentences:
        if p.strip() == '':
            continue
        
        # Wikipedia cleaning 
        if wiki:
            # discard sentences with troublesome templates or links
            if p[0] in ['!', '|'] or '{{' in p or '}}' in p or '[[' in p \
                or ']]' in p or '{|' in p or '|}' in p or '__TEMPLATE__' in p:
                continue
        
        new_sent = _tokenizer.tokenize(p)
        
        if min_sentence_size > 0:
            # discard sentences that are a couple of words (it happens sometimes
            # when extracting data from lists).
            if len(new_sent) < min_sentence_size:
                continue
        
        ret.append(new_sent)
        
    return ret

def clean_text(text, correct=True):
    """
    Apply some transformations to the text, such as 
    replacing digits for 9 and simplifying quotation marks.
    
    :param correct: If True, tries to correct punctuation misspellings. 
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
    
    # replaces numbers with the 9's
    text = re.sub(r'\d', '9', text)
    
    # replaces special ellipsis character 
    text = text.replace(u'…', '...')
    
    return text



def build_corpus_from_wiki(wikifile, output_dir='.', total_articles=0, 
                           one_per_file=True, min_sent_size=0):
    """
    Reads a specified number of articles and saves them as a raw text files.
    
    :param wikifile: path to the Wikipedia XML dump file
    :param total_articles: the maximum number of articles to read. None or 
        any number below 1 means all articles.
    :param one_per_file: saves one article per file.
    :param output_dir: directory where output files should be saved
    """
    
    def save_articles(articles, file_num):
        text = '\n'.join(articles)
        tokens = tokenize(text, wiki=True, min_sentence_size=min_sent_size)
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

def convert_file(wikifile, min_sent_size=0):
    """
    Reads a file containing a single wikipedia article. It will remove 
    mediawiki markup and return the text.
    """
    with open(wikifile, "rb") as f:
        text = f.read()
    
    text = unicode(text, "utf-8")
    filtered = filter_markup(text)
    return tokenize(filtered, min_sentence_size=min_sent_size)

if __name__ == '__main__':
    
    log_format = '%(message)s'
    logging.basicConfig(format=log_format)
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.INFO)
    
    parser = argparse.ArgumentParser(description=__doc__)
    
    # the input may be a dump of the Wikipedia or a file containing the source code
    # for a single article
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-a', 
                             help='File with single wikipedia article', dest='wikifile')
    input_group.add_argument('-i', 
                             help='Wikipedia dump file', dest='dumpfile')
    
    parser.add_argument('-o', 
                        help='Output directory', dest='output_dir', default='.')
    parser.add_argument('--one', 
                        help='Saves one article per file', action='store_true')
    parser.add_argument('--size', help='Minimum sentence size', type=int, default=0)
    parser.add_argument('--max', 
                        help='Maximum number of articles to read', type=int, default=0)
    args = parser.parse_args()
    
    if args.dumpfile:
        build_corpus_from_wiki(args.dumpfile, args.output_dir, 
                               args.max, one_per_file=args.one, min_sent_size=args.size)
    elif args.wikifile:
        result = convert_file(args.wikifile, args.size)
        text = '\n'.join(' '.join(sent) for sent in result)
        print text.encode("utf-8") 

