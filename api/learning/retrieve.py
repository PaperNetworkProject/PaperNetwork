"""
Authors : Remi Laot (2016)
Note : 
    . use 'requests' to make HTTP requests (external package)
      installation (console) -> 'pip install requests'
"""

import requests
import json
import pprint
import math
from internal_types import *

# Global variables
epmc_endpoint = "http://www.ebi.ac.uk/europepmc/webservices/rest/"

def search(terms = []):
    # check terms types
    checked_terms = []
    if isinstance(terms, list):
        for term in terms:
            if isinstance(term, (str, int)):
                checked_terms.append(str(term))
    elif isinstance(terms, (str, int)):
        checked_terms.append(terms)
    # construct the query
    query_url = epmc_endpoint + "search"
    query_params = {
        'query' : checked_terms,
        'format' : 'json',
        'pageSize' : 1000 }
    query_results = []
    # perform the queries
    JSON_resp = requests.get(query_url, params = query_params).json() # first query
    if 'errCode' in JSON_resp:
        raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
    else:
        hit_count = int(JSON_resp['hitCount'])
        page_count = int(math.floor(hit_count / 1000) + 1) # TODO look into that again
        print("hit count : {0}".format(hit_count))
        print("page count : {0}".format(page_count))
        for paper in extract_LtdPaperDetails(JSON_resp['resultList']['result']):
            query_results.append(paper)
        # perform extra queries if there is more pages
        if page_count > 1:
            for page in range(1, page_count + 1):
                query_params['page'] = page
                JSON_resp = requests.get(query_url, params = query_params).json() # first query
                if 'errCode' in JSON_resp:
                    raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
                else:
                    for paper in extract_LtdPaperDetails(JSON_resp['resultList']['result']):
                        query_results.append(paper)
    # return papers found
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

test_results = search(["malaria", 2003, "juin"])
#test_results = search(["malaria 2003 juin"])
print("result length : {0}".format(len(test_results)))
for paper in test_results:
    print(paper)