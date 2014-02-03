# -*- coding: utf-8 -*-

"""
Parses text written with wikimedia syntax to generate plain text files.
Adapted from Wikipedia Dump Reader (https://launchpad.net/wikipediadumpreader/)
for the Portuguese Wikipedia.
"""

import logging
import re
from xml.etree import cElementTree as ET

_link_files_regexp = re.compile("([Aa]rquivo|[Ii]magem?|[Ff]icheiro|[Ff]ile):")

def link(m):
    '''
    Function to treat links.
    I'm not sure about image links appearing in the middle of running text. 
    I'm adding new patterns here as I find them
    '''
    groups = m.groups()
    if len(groups) == 1:
        txt = groups[0]
        if _link_files_regexp.search(txt):
            # it's a link for displaying a file
            return ''
        return txt
    else:
        return groups[1]

def filter_markup(t):
    """
    Parses a piece of text containing wikimedia markup.
    Ref: http://meta.wikimedia.org/wiki/Help:Wikitext_reference
    """
    if t.startswith('#REDIRECIONAMENTO') or t.startswith('#REDIRECIONAMENTO') \
        or t.startswith(u'{{desambiguação'):
        # it is a redirect page, or a disambiguation one, and we don't want it.
        return ''
    
    # the order of the sub patterns is important!!!
    
    t = t.replace('&nbsp;', ' ')
    t = t.replace(u'–', '-')
    t = t.replace(u'—', '-')
    
    t = re.sub('(?s)<!--.*?-->', "", t) # force removing comments
    t = re.sub("(\n\[\[[a-z][a-z][\w-]*:[^:\]]+\]\])+($|\n)","", t) # force remove last (=languages) list
    t = re.sub('(?i)\[\[:?Categoria:(.*?)\]\]', '', t)
    
    # Removes everything in the sections Ver também, Bibliografia, Links Externos
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Ver também(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Bibliografia(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Ligações Externas(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    
    # Replaces mathematical formulae with __MATH__. It is important to remove these early on
    # because they often have curly brackets (using Latex notation), which can mess with the parse
    t = re.sub('(?s)<math(\s[^>]*)?>.*?</math>', '__MATH__', t)
    
    # Replaces IPA signs for __IPA__. It seems better than to ignore, since it often appears in the
    # beginning of articles.
#     t = re.sub('{{IPA2\|.*?}}', '__IPA__', t)
    
    # some formatting options appear as {{{width|200}}}
    t = re.sub("{{{[^}{]*}}}", '', t)
    
    # Replaces all templates not treated before ( marked between {{ and }} ) with __TEMPLATE__
    # The regexp is applied until no more changes are made, so nested templates are taken care of
    # (e.g., {{ aaa {{ bbb {{ ccc }} }} }} 
    check = True
    while check:
        t, check = re.subn(r'{{[^}{]*}}', '__TEMPLATE__', t)
    
    # Replaces *what I think that are* templates between {| and |}. Similar to the last block.
    check = True
    while check:
        t, check = re.subn(r'''(?sx)
            {\|            # open {|
            .*
            \|}            # close |}
            ''', '__TEMPLATE__', t)
    
    # Removes some tags and their contents
    t = re.sub(r'''(?isux)
    <
    (small|sup|gallery|noinclude|ol|
    includeonly|onlyinclude|timeline|
    table|ref|code|source|t[rdh])
    \s*[-$!%@&_#\w=.,:;\'" ]*
    >
    .*?
    </\1\s*>
    ''', '', t)
    
    # Treats section titles
    t = re.sub(r"(^|\n)(=+) *[^\n]*\2 *(?=\n)", '', t )
    
    # bold and italics markup
    t = t.replace("'''", "")
    t = t.replace("''", "")
    
#     t = re.sub("(?u)^ \t]*==[ \t]*(\w)[ \t]*==[ \t]*\n", '(Image: \\1)', t)
    
    # I'm not sure if this order below could make any problem. It is meant to solve nested links as
    # [[Image: blabla [[bla]] bla]]
    t = re.sub("(?s)\[\[([^][|]*?)\]\]", link, t)
    t = re.sub("(?s)\[\[([Aa]nexo:[^]|[:]*)\|([^][]*)\]\]", link, t)
    t = re.sub("(?s)\[\[[Mm]ultim.dia:(.*?)\]\]", '__FILE__', t)
    t = re.sub("(?s)\[\[(:?[Ii]mage:[^][:]*)\|([^][]*)\]\]", '', t)
    t = re.sub("(?s)\[\[([^][|]*)\|([^][|]*)\]\]", link, t)
        
    # external links
    t = re.sub('\[(?:https?|ftp)://[^][\s]+?\s+(.+?)\]', '\\1', t)
    t = re.sub('\[?(?:https?|ftp)://[^][\s]+\]?', '__LINK__', t)
#     t = re.sub('(https?|ftp)://[^][\s]+', '__LINK__', t)
        
    t = re.sub("""(?msx)\[\[(?:
    [Aa]rquivo|
    [Ii]magem?|
    [Ff]icheiro|
    [Ff]ile)
    :.*?\]\]""", '', t)
    
    # Ignore tables
    t = re.sub('\{\|(?P<head>[^!|}]+)(?P<caption>(\|\+.*)?)(?P<body>(.*\n)+?)\|\}', '', t)

    # replace <br> and <hr> for line breaks
    t = re.sub(r'</?[hb]r\s*[-#\w=.,:;\'" ]*/?>', r'\n', t)
    
    # removes some tags, but don't touch the text
    # we don't check for matching opening and closing tags for two reasons:
    # 1) efficiency 2) to cope with badly formed tags
    t = re.sub(r'''(?isxu)
    </?                        # opening or closing tag
    (blockquote|tt|b|u|s|p|i|  # any of these tags
    sub|span|big|font|poem|
    nowiki|strong|cite|div|
    center|ref|references|
    em|var|li|
    noinclude|gallery)         # sometimes, a stray element like <noinclude> remains here
    \s*                        # white space
    [-?$#%@\w/&=().,:;\'" ]*   # xml attributes 
    /?>                        # close tag bracket
    ''', '', t)
    
    # lists 
    # a trailing newline is appended to the text to deal with lists as the last item in a page
    t += '\n'
    t = re.sub("\n(([#*:;]+[^\n]+\n)+)", '\n', t)
    
    t = t.replace('--', '-')
    
    return t


def get_articles(wikifile):
    """
    Generator function. Parses the Wikipedia XML dump file and yields an 
    article at a time as raw text. 
    """
    # reading the dump file, one text a time, so we don't overload the memory
    context = iter(ET.iterparse(wikifile))
    
    skip_next = False
    title = ''
    
    logger = logging.getLogger("Logger")

    for _, elem in context:
        
        if elem.tag.endswith('title'):
            skip_next = False
            title = elem.text
            if re.search(u'(?i)desambiguação', title) or re.match(u'(?i)Wikip(e|é)dia:', title)\
                or re.match('(?i)(Anexo|Ajuda|MediaWiki|Categoria|Predefinição|Portal|Livro):', title): 
                # this page's content isn't relevant; skip its text element
                skip_next = True
        
        if elem.tag.endswith('text'):
            if not skip_next:
                text = elem.text
                
                if text is not None and \
                    not (re.match('(?i)#(REDIRECIONAMENTO|REDIRECT)', text) or \
                         re.match(u'(?i){{desambiguação', text) or \
                         # pages for year's day are troublesome because of lots of templates
                         # and have few useful text
                         re.match('(?i){{dia do ano', text)):
                    logger.debug("Reading %s..." % title)
                    parsed = filter_markup(text)
                    yield parsed
                                    
        elem.clear()
    
