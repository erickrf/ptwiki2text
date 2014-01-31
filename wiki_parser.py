# -*- coding: utf-8 -*-

"""
Parses text written with wikimedia syntax to generate plain text files.
Adapted from Wikipedia Dump Reader (https://launchpad.net/wikipediadumpreader/)
for the Portuguese Wikipedia.
"""


import logging
import re
from xml.etree import cElementTree as ET

def convertWikiList(txtLines):
    """ Parser for the namedlist/unnamedlist/definition """
    def indexDiff(a, b):
        x = 0
        for c1, c2 in zip(a, b):
            if c1 == c2:
                x += 1
            else:
                break
        return x
    
    out = ""
    mode = "%s"
    stack = []
    c = ""
    common = 0
    pattern = re.compile('[*#:;]+')
    for line in txtLines:
        linehead = re.match(pattern, line)
        if linehead:
            sl = linehead.end()
        sp = len(stack)
        common = indexDiff(stack, line)
        #for common, x in enumerate(zip(stack, line)):
        #    if x[0] != x[1]:
        #        break
        #else:
        #    common = min(len(stack), len(line))
        for x in range(sp, common, -1):
            c = stack.pop()
            #print "pop", c
            if c == '*':
                out += "</ul>"
            if c == '#':
                out += "</ol>"
            if c == ':':
                out += "</dd></dl>"
        lastpoped = c
        if not linehead:
            break
        for x in range(common, sl):
            c = line[x]
            stack.append(c)
            #print "push", c
            if c == '*':
                out += "<ul>"
                mode = "<li>%s</li>"
            elif c == '#':
                out += "<ol>"
                mode = "<li>%s</li>"
            elif c == ':' and lastpoped == '*':
                out += "<dl><dd>"
                mode = "<dd>%s</dd>"
            elif c == ';':
                k = line.find(':', x+1)
                if k > -1:
                    head, line = line[x+1:k], line[k+1:]
                    sl = 0
                else:
                    head, line = line[x+1:], "" # "" will be skipped
                out += "<dl><dt><b>%s</b></dt><dd>" % head
                stack[-1] = ':'
                mode = "%s"
        k = line[sl:].strip()
        if k:
            out += mode % k
    return out

def link(m):
    '''
    Function to treat links.
    I'm not sure about image links appearing in the middle of running text. 
    I'm adding new patterns here as I find them
    '''
    groups = m.groups()
    if len(groups) == 1:
        txt = groups[0]
        if re.search("([Aa]rquivo|[Ii]magem?|[Ff]icheiro|[Ff]ile):", txt):
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
    
    t = re.sub('(?s)<!--.*?-->', "", t) # force removing comments
    
    t = re.sub("(\n\[\[[a-z][a-z][\w-]*:[^:\]]+\]\])+($|\n)","", t) # force remove last (=languages) list
       
    t = re.sub('(?i)\[\[:?Categoria:(.*?)\]\]', '', t)
    
    # Removes everything in the sections Ver também, Bibliografia, Links Externos
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Ver também(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Bibliografia(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    t = re.sub(u'(?is)\n(=+)\s*(?:{{)?Ligações Externas(?:}})?\s*\\1.*?(\n\\1\s|$)', '\\2', t)
    
    # Replaces mathematical formulae with __MATH__. It is important to remove these early on
    # because they often have curly brackets (using Latex notation), which can mess with the parse
    t = re.sub('(?s)<math\s*>.*?</math>', '__MATH__', t)
    
    # Remove references
    t = re.sub('(?s)<ref([^>]*?)/>', '', t)
    t = re.sub('(?s)<ref(.*?)>.*?</ref>', '', t)
    
    #t = re.sub('(?s)<ref([> ].*?)(</ref>|/>)', '', t)
    t = re.sub('<references/>', '', t)
    
    # Replaces IPA signs for __IPA__. It seems better than to ignore, since it often appears in the
    # beginning of articles.
    t = re.sub('{{IPA2\|.*?}}', '__IPA__', t)
    
    # some formatting options appear as {{{width|200}}}
    t = re.sub("{{{[^}{]*}}}", '', t)
    
    t = re.sub('(?i){{carece de fontes(.*?)}}', '', t)
    
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
    
    # Treats section titles
    t = re.sub("\n(?P<level>=+) *(?P<title>[^\n]*)\\1 *(?=\n)", '', t )
    
    # bold and italics markup
    t = re.sub("'''(.+?)'''", "\\1", t)
    t = re.sub("''(.+?)''", "\\1", t)
    
    t = re.sub("(?u)^ \t]*==[ \t]*(\w)[ \t]*==[ \t]*\n", '<h2>(Image: \\1)</h2>', t)
    
    # I'm not sure if this order below could make any problem. It is meant to solve nested links as
    # [[Image: blabla [[bla]] bla]]
    t = re.sub("(?s)\[\[([^][|]*?)\]\]", link, t)
    t = re.sub("(?s)\[\[([Aa]nexo:[^]|[:]*)\|([^][]*)\]\]", link, t)
    t = re.sub("(?s)\[\[[Mm]ultim.dia:(.*?)\]\]", '__FILE__', t)
    t = re.sub("(?s)\[\[(:?[Ii]mage:[^][:]*)\|([^][]*)\]\]", link, t)
    t = re.sub("(?s)\[\[([^][|]*)\|([^][|]*)\]\]", link, t)
        
    # external links
    t = re.sub('\[(?:https?|ftp)://[^][\s]+?\s+(.+?)\]', '\\1', t)
    t = re.sub('\[(?:https?|ftp)://[^][\s]+\]', '__LINK__', t)
    t = re.sub('(https?|ftp)://[^][\s]+', '__LINK__', t)
    
    t = re.sub('\n----', '\n', t)
    
    t = re.sub("""(?msx)\[\[(?:
    [Aa]rquivo|
    [Ii]magem?|
    [Ff]icheiro|
    [Ff]ile)
    :(.*?)\]\]""", '', t)
    
    # Ignore tables
    t = re.sub('\{\|(?P<head>[^!|}]+)(?P<caption>(\|\+.*)?)(?P<body>(.*\n)+?)\|\}', '', t)
    
    t = re.sub('<div([^>]*?)>', '', t)
    t = re.sub('</div\s*>', '', t)
    t = re.sub('<center([^>]*?)>', '', t)
    t = re.sub('</center\s*>', '', t)
    t = re.sub(r'<br\s*[-#\w=.,:;\'" ]*/?>', r'\n', t)
        
    # Treats HTML entities that may appear
    t = re.sub('&nbsp;', ' ', t)
    
    # removes some tags, but leaves the text within
    t = re.sub('(?is)<blockquote\s*[-#\w=.,:;\'" ]*>(.*?)</blockquote>', r'\1', t)
    t = re.sub(r'(?is)<(tt|b|u|s)\s*>(.*?)</\1>', r'\2', t)
    t = re.sub(r'(?is)<sub\s*>(.*?)</sub>', r'\1', t)
    t = re.sub('(?is)<span\s*[-#\w=.,:;\'" ]*>(.*?)</span>', r'\1', t)
    t = re.sub('(?is)<big\s*[-#\w=.,:;\'" ]*>(.*?)</big>', r'\1', t)
    t = re.sub('(?is)<font\s*[-#\w=.,:;\'" ]*>(.*?)</font>', r'\1', t)
    t = re.sub(r'(?is)<poem\s*>(.*?)</poem>', r'\1', t)
    t = re.sub(r'(?is)<nowiki\s*>(.*?)</nowiki>', r'\1', t)
    
    # Replace source code with a special token
    t = re.sub('(?s)<code(.*?)>.*?</code>', '__CODE__', t)
    t = re.sub('(?s)<source(.*?)>.*?</source>', '__CODE__', t)
    
    # Removes some tags
    t = re.sub('(?is)<small\s*>.*?</small>', '', t)
    t = re.sub('(?is)<sup\s*>.*?</sup>', '', t)
    t = re.sub('(?is)<gallery\s*[-#\w=.,:;\'" ]*>.*?</gallery>', '', t)
    t = re.sub('(?is)<noinclude\s*[-#\w=.,:;\'" ]*>.*?</noinclude>', '', t)
    t = re.sub('(?is)<includeonly\s*[-#\w=.,:;\'" ]*>.*?</includeonly>', '', t)
    t = re.sub('(?is)<onlyinclude\s*[-#\w=.,:;\'" ]*>.*?</onlyinclude>', '', t)
    t = re.sub('(?is)<timeline(.*?)>.*?</timeline>', '', t)
    t = re.sub('(?is)<table(.*?)>.*?</table>', '', t)
    
    # lists 
    # a trailing newline is appended to the text to deal with lists as the last item in a page
    t += '\n'
    t = re.sub("\n(([#*:;]+[^\n]+\n)+)", '\n', t)
    
    t = re.sub(u'—|--', '-', t)
    
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
                    parsed = filter_markup(text, html=False)
                    yield parsed
                                    
        elem.clear()
    
