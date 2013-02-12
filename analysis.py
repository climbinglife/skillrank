#!/usr/bin/env python
"""
analysis.py
Author: Brian Boates

Perform skill rank analysis using term counts
from query and bkgd tables
"""
import os, sys, math
import MySQLdb as mdb
import indeed, utils
import ghlThreads

def nTerms(cur, table):
    """
    return: int | highest count of all terms from table
    params:
            cur: cursor to skillrank database
            table: string | table name for max(count)
    """
    # Column length for a given table
    cur.execute("SELECT id FROM "+table+" ORDER BY id DESC LIMIT 1")
    
    # retrieve the column length
    fetch = cur.fetchone()
    
    # check if term and count were present, if so return them
    if fetch: return fetch[0]
    else:     return None, 0    


def termCount(cur, term, table):
    """
    return: int | term's count in table
    params:
            cur: cursor to skillrank database
            term: string | term to find count for
            table: string | table name for term's count
    """
    # Find the term with highest count in given table
    cur.execute("SELECT count FROM "+table+" WHERE term = \'"+term+"\'")
    
    # retrieve term's count
    fetch = cur.fetchone()
    
    # check if term and count were present, if so, return count
    if fetch: return fetch[0]
    else:     return 0

    
def maxCount(cur, table):
    """
    return: int | highest count of all terms from table
    params:
            cur: cursor to skillrank database
            table: string | table name for max(count)
    """
    # Find the term with highest count in given table
    cur.execute("SELECT term,count FROM "+table+" ORDER BY count DESC LIMIT 1")
    
    # retrieve the term and count
    fetch = cur.fetchone()
    
    # check if term and count were present, if so return them
    if fetch: return fetch[0], fetch[1]
    else:     return None, 0    


def sumCount(cur, table):
    """
    return: int | sum of all counts of all terms from table
    params:
            cur: cursor to skillrank database
            table: string | table name for max(count)
    """
    # sum all counts in given table
    cur.execute("SELECT SUM(count) AS count FROM "+table)
    
    # return the sum of all term counts
    fetch = cur.fetchone()
    
    # check for NULL sum
    if fetch: return fetch[0]
    else:     return 0


def commonness(cur, term, table):
    """
    return: float | commonness factor computed as termCount/maxCount
                  | exists [0,1]
    params:
            cur: cursor to skillrank database
            term: string | term to compute commonness for
            table: string | table name for counts
    """
    return termCount(cur, term, table) / float(maxCount(cur, table)[-1])


def rareness(cur, term, table):
    """
    return: float | rareness factor computed as 1 - termCount/maxCount
                  | exists [0,1]
    params:
            cur: cursor to skillrank database
            term: string | term to compute rareness for
            table: string | table name for counts
    """
    return 1 - commonness(cur, term, table)


def bkgdFreq(cur, term):
    """
    frequency is defined here as number of counts for 
    term divided by count for the average word
    
    return: float | frequency as described above
    params:
        cur: cursor to skillrank db
        term: string | term to compute frequency for
    """
    # determine the length of the term (word, bigram, trigram, etc.)
    length = len(term.split())
    
    # if term is a word
    if length == 1: bkgd_table = 'bkgd_words'
        
    # if term is a bigram
    elif length == 2: bkgd_table = 'bkgd_bigrams'
        
    # if term is a trigram
    elif length == 3: bkgd_table = 'bkgd_trigrams'
        
    # if term is not a word, bigram, or trigram, return R=0
    else: return 0
    
    # get the background count for term from db
    cur.execute("SELECT count from "+bkgd_table+" WHERE term=\'"+term+"\'")
    fetch = cur.fetchone()
    
    # check for NULL count
    if fetch: C_bkgd = fetch[0]
    else:     return 0
    
    # get the count for average word in bkgd (nTerms != 0)
    C_bkgd_avg = float(sumCount(cur, bkgd_table)) / nTerms(cur, bkgd_table)
    
    # compute the bkgd frequency for term
    return C_bkgd / C_bkgd_avg


def relevance(f_query, f_bkgd, termCount, x=0.6):
    """
    return: float | relevance factor computed as described on 
                    Skill Rank "About" page: R = log( f_query/f_bkgd )
    params:
            f_bkgd:  float | "frequency" of word in background
            f_query: float | "frequency" of word in query
            termCount: int | number of occurences of term
    """
    return (  x*math.log(f_query/f_bkgd) + (1-x) ) * termCount


def bkgdGet(cur, table):
    """
    return: dict | dictionary of bkgd terms and counts
    params:
            cur: cursor to skillrank db
            table: string | db table to retrieve
    """
    # connect to the skillrank database and create cursor
#    con = mdb.connect(host='localhost', user='root', db='skillrank')
#    cur = con.cursor()
    
    # get all terms and counts from table
    cur.execute("SELECT term,count FROM "+table)
    fetch = cur.fetchall()
    
    # build the dictionary of terms and counts
    d_bkgd = {}
    for term, count in fetch:
        d_bkgd[term] = count
    
    # close the database cursor and connection
#    if cur: cur.close()
#    if con: con.close()
    
    return d_bkgd


def bestBigrams(words, topWords, N=10, num=100):
    """
    return: list[tuple(string,int)] | re-ranked list of top 
                                      bigrams by query counts
    params:
           words: list[string] | list of all words as strings
        topWords: list[string] | list of top words as strings
               N: int | number of top bigrams to retrieve
             num: int | number of initial bigrams to retrieve
    """
    # get the top N bigrams
    topBigrams = utils.getBigrams(words, num=num)
    
    # get all the bigrams
    allBigrams = utils.getNgrams(words, N=2)
    
    # create bigram dictionary with actual query counts
    dictBigram = {}
    for b in topBigrams:
        dictBigram[b] = allBigrams.count(b)
    
    # sort bigrams by the query counts
    bResults = []
    for key, value in sorted(dictBigram.iteritems(), key=lambda (k,v): (v,k)):
         bResults.append( (key,str(value)) )
    bResults = bResults[::-1]
    
    # loop until N best bigrams are found
    nBestBigrams, i = [], 0
    while len(nBestBigrams) < N and i < len(bResults):
        
        # variable naming for convenience
        w1, w2 = bResults[i][0].split()
        
        # if one of the two words in the bigram are 
        if w1 in topWords or w2 in topWords:
            
            # avoid strange short word bigrams
#            if len(w1+w2) > 8:
                
                # keep current results as a "best" bigram
                nBestBigrams.append( bResults[i] )
        
        # increment loop count
        i += 1
        
    return nBestBigrams


def analyze(cur, jobQuery, terms, x=0.6, nReturn=100, threshold=10):
    """
    Main analysis function to get term relevances
    
    return: list[tuple(term, relevance, count)] | "results"
    params:
            cur: cursor to skillrank db
            jobQuery: string | jobQuery from user input
            terms: list[string] | list of terms as strings
            x: float [0,1] | relevance scaling factor
            nReturn: int | number of top words to return (default=100)
            threshold: int | minimum count for bkgd filtering (default=10)
    """
    # determine if terms are words, bigrams, or trigrams
    length = len(terms[0].split())
    
    # get the appropriate bkgd table
    if   length == 1: bkgd_table = 'bkgd_words'
    elif length == 2: bkgd_table = 'bkgd_bigrams'
    elif length == 3: bkgd_table = 'bkgd_trigrams'
    
    # get the bkgd counts table
    d_bkgd = bkgdGet(cur, bkgd_table)
    
    # get the sum and average bkgd term count
    C_bkgd_sum = float(sum(d_bkgd.values()))
    C_bkgd_max = float(max(d_bkgd.values()))
    C_bkgd_avg = float(C_bkgd_sum) / float( len(d_bkgd) )
    
    # create a unique set of terms
    termSet = set(terms)
    
    # get the sum and average bkgd term count
    C_query_sum = float(sum( [terms.count(term) for term in termSet] ))
    C_query_max = float(max( [terms.count(term) for term in termSet] ))
    C_query_avg = float(C_query_sum) / float( len(termSet) )
    
    # initialize dictionaries for results
    qRelevance, qCount = {}, {}
    
    # loop over each word in the query (uniquely)
    for term in termSet:
                    
        # compute query count for term
        C_query = float(terms.count(term))
    
        # compute query frequency for term
        f_query = C_query / C_query_avg #C_query_max #C_query_sum
        
        # get term bkgd count (0 if term not in bkgd)
        try: C_bkgd = float(d_bkgd[term])
        except KeyError: C_bkgd = 0
        
        # check for very low bkgd count values
        if C_bkgd <= threshold:
            
            # penalize "non-words" with count < threshold (default=10)
            if not utils.isWord(term): f_bkgd = 100.0
            
            # otherwise, give an average frequency
            else: f_bkgd = 1.0
            
        # otherwise compute bkgd frequency
        else: f_bkgd = C_bkgd / C_bkgd_avg
        
        # compute relevance
        R = relevance(f_query, f_bkgd, C_query, x=x)
        
        # assign relevance to word in dictionary
        qRelevance[term] = R
        qCount[term]     = C_query
    
    # sort by relevance, build raw results list
    results = []
    for key, value in sorted(qRelevance.iteritems(), key=lambda (k,v): (v,k)):
         results.append( (key, value, str(qCount[key])) )
         
    # reverse ordering, and only keep top "nReturn" values
    results = results[::-1][:nReturn]
    
    # create list of top nReturn words only
    topTerms = [r[0] for r in results if (len(r[0])>1 or r[0] in ['c','r'])]
    
    # retrieve list of N best bigrams (with their counts)
    topBigrams = bestBigrams(terms, topTerms, N=10, num=100)
        
    # create list of bigram words to remove from results
    toRemove = []
    for b in topBigrams:
        # grab the current bigram
        bigram = b[0].split()     
        # concatenate individual bigram words to remove list
        toRemove += bigram
    
    # only keep bigram removal words for words occuring more than once
    toRemove = list(set( [r for r in toRemove if toRemove.count(r) > 1] ))
    toRemove += ['statistical']
    
    # also concatenate bigram with no space
    for b in topBigrams:
        bigram = b[0].split()
        toRemove += [bigram[0]+bigram[1]]
        
    # append jobQuery words to removal list
    if ' ' in str(jobQuery):
        jq = jobQuery.split()
        for j in jq:
            toRemove.append(str(j))
            toRemove.append(str(j)+'s')
        toRemove.append(str(jobQuery)+'s')
    else:
        toRemove.append(str(jobQuery))
        toRemove.append(str(jobQuery)+'s')
        
    # get list of all relevances
    maxRelevance = max( [float(r[1]) for r in results if r[0] not in toRemove] )
    
    # get the best bigrams with artificial relevances (limit to top 5)
    topBigrams = [b for b in topBigrams if b[0] not in [str(jobQuery),str(jobQuery)+'s']][:5]
    biResults = []
    fakeRelevances = [0.60, 0.50, 0.24, 0.12, 0.08, 0.06, 0.04, 0.02, 0.01, 0.01]
    for i in range(len(topBigrams)):
        term, count = topBigrams[i]
        biResults.append((term, fakeRelevances[i], count))
        toRemove += term.split()
        
    # perform removal of bigram and jobQuery words and normalize R
    results = [(r[0],str(r[1]/maxRelevance),str(int(float(r[2])))) \
                         for r in results if r[0] not in toRemove]
    
    # remove pluralities (might break other words only 
    # differing by one extra letter, probably rare/okay)
    resultWords = [r[0] for r in results]
    results = [r for r in results if r[0][:-1] not in resultWords]
        
    return results, biResults


def getResults(jobQuery, nJobs, start=0):
    """
    return: list[tuple(term,relevance,count)] | "results"
    params:
            jobQuery: string | job query from user form
            nJobs: int | number of jobs to consider
            start: int | index to start indeed.com api search
    """
    # connect to the skillrank database and create cursor
    con = mdb.connect(host='localhost', user='root', db='skillrank')
    cur = con.cursor()
    
    # initialize list for all terms for jobQuery
    terms = []
    
    # retrieve URL's for jobQuery
    urls = indeed.getJobURLs(jobQuery, nURLs=nJobs, start=start)
    
    # if no URL's matched for jobQuery
    if not urls: return []
    
    """    
    # loop through URL's
    for url in urls:
  
        # retrieve information from URL's job posting
        jobkey, position, company, location, words = indeed.parseJobPosting(url)
  
        # append latest words to terms list
        terms += words
        
        # print useful info to terminal
        index = 10*start+urls.index(url)+1
        print index,'# position:',position,'# company:',company,'# location:',location
    """
  
    # get indeed job postings using threads for boosted efficieny
    documents = ghlThreads.threadResults(urls, num_threads=8)
        
    # words lists are the 5th/last item in each
    # tuple returned from threaded documents
    for d in documents:
        terms += d[-1]
            
    # retrieve ranked results
    results, biResults = analyze(cur, jobQuery, terms, x=0.6, nReturn=100, threshold=10)            
        
    # close the database cursor and connection
    if cur: cur.close()
    if con: con.close()
    
    return results, biResults


def main():
    
    # connect to the skillrank database and create cursor
    con = mdb.connect(host='localhost', user='root', db='skillrank')
    cur = con.cursor()
    
    # close the database cursor and connection
    if cur: cur.close()
    if con: con.close()


if __name__ == '__main__':
    main()