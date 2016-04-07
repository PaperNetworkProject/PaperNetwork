"""
Authors : Remi Laot (2016)
Note : 
    . use 'requests' to make HTTP requests (external package)
      installation (console) -> 'pip install requests'
"""

import time
import grequests
import requests
import json
import pprint
import math
from internal_types import *

# Global variables
epmc_endpoint = "http://www.ebi.ac.uk/europepmc/webservices/rest/"

def search(terms = []):
    start_time = time.time()
    # construct base url
    query_url = epmc_endpoint + "search?format=json&pageSize=1000&query="
    count_url = epmc_endpoint + "profile?format=json&query="
    if isinstance(terms, list):
        for term in terms:
            if isinstance(term, (str, int)):
                query_url += str(term)
                count_url += str(term)
    elif isinstance(terms, (str, int)):
        query_url += str(terms)
        count_url += str(terms)
    query_url += "&page="
    # compute the number of pages for the query
    query_results = []    
    JSON_resp = requests.get(count_url).json() # first query
    if 'errCode' in JSON_resp:
        raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
    else:
        query_urls = []
        hit_count = 0
        # construct each requests
        for pubType in JSON_resp['profileList']['pubType']:
            if (pubType['name'] == 'ALL'):
                hit_count = pubType['count']
        page_count = int(math.floor(hit_count / 1000) + 1)
        for page in range(1, page_count + 1):
            query_urls.append(query_url + str(page))
        # perform queries
        queries = (grequests.get(url) for url in query_urls)
        responses = grequests.map(queries)
        print ("queries done")
        for response in responses:
            if not (response is None):
                JSON_resp = response.json()
                if 'errCode' in JSON_resp:
                    raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
                elif 'resultList' in JSON_resp:
                    for paper in extract_LtdPaperDetails(JSON_resp['resultList']['result']):
                        query_results.append(paper)
            response.close()
    # return papers found
    print("--- {0} seconds - {1} results ---".format(time.time() - start_time, len(query_results)))
    return query_results

def extract_LtdPaperDetails(JSON_list):
    extracted_papers = []
    for JSON_paper in JSON_list:
        if all (key in JSON_paper for key in ('id', 'source', 'title', 'authorString', 'pubYear', 'citedByCount')):
            # extract plain data
            id = JSON_paper['id']
            src = JSON_paper['source']
            title = JSON_paper['title']
            pubYear = int(JSON_paper['pubYear'])
            citedCount = int(JSON_paper['citedByCount'])
            # extract and parse the authors list
            string_authors = JSON_paper['authorString']
            authors = string_authors.split(", ")
            # create a LtdPaperDetails object
            extracted_papers.append(LtdPaperDetails(id, src, title, authors, pubYear, citedCount))
    return extracted_papers

test_results = search(["malaria"])
#test_results = search(["malaria 2003 juin"])
print("result length : {0}".format(len(test_results)))