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
verbose = True
VERBOSE = True
TIMING = True
TRANSMIT_DATA = False

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def build_paper_network(initial_paper_id, reference_threshold = 2000, explored_threshold = 5000, papers_threshold = 5000, cur_step_ref_buffer_size = 10, cur_step_cit_buffer_size = 2, same_author_weight = 1):
    (known_papers, known_relations, word_count) = dict(), dict(), dict()
    (explored, to_explore) = set(), []
    stop_looking = False
    # find initial paper
    result = search_papers([initial_paper_id])
    for res in result:
        if res.id == initial_paper_id:
            initial_paper_src = res.src
            known_papers[initial_paper_id] = res
    if not initial_paper_id in known_papers:
        if VERBOSE: print ("could not find initial paper in {0} paper(s)".format(len(result)))
        return {}
    # init search
    cur_step_papers = [(initial_paper_src, initial_paper_id)]
    if VERBOSE: print("Starting data retrieval...")
    if TIMING: start_time = time.time()
    c = 0
    # process until we have found as much papers as wanted
    while (len(known_papers) < papers_threshold) and (not stop_looking):
        c+= 1
        # As soon as we have a good set of referenced papers, we can look into citations to find more recent ones
        if (len(known_papers) > reference_threshold): relation_type = ["citations", "references"]
        else: relation_type = ["references"]
        if VERBOSE:
            print("\nknown papers: {0}".format(len(known_papers)))
            print("known relations: {0}\n".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
            print("{0} paper(s) have been explored".format(len(explored)))
            print("{0} paper(s) will be explored during next step".format(len(cur_step_papers)))
            print("{0} other paper(s) have to be explored".format(len(to_explore)))
        if TRANSMIT_DATA:
            send_to_client("\{\"phase\":0,\"papers_count\":{0},\"relations_count\":{1},\"explored_count\":{2}\}".format(len(known_papers), sum(list(map(lambda x : len(known_relations[x]), known_relations))), len(explored)))
        # Get more papers related to already known papers
        result = search_related_papers(related_to = cur_step_papers, look_for = relation_type, request_page_size = 1000, known_papers = known_papers, known_relations = known_relations, word_count = word_count)
        # Update our variables
        explored.update(set(map(lambda x : x[1], cur_step_papers)))
        known_papers = result['papers']
        known_relations = result['relations']
        # update papers to explore
        for paper_id in result['found'].difference(explored):
            to_explore.append((paper_id, known_papers[paper_id].citedCount))
        to_explore.sort(key = lambda x : x[1], reverse = True)
        # check if there still is papers to explore
        if len(to_explore) < 1 : stop_looking = True
        # Choose how many papers to explore next (explore more references)
        cur_step_buffer_size = cur_step_cit_buffer_size if (len(known_papers) > reference_threshold) else cur_step_ref_buffer_size
        # choose next step's papers (to explore)
        cur_step_papers = list(map(lambda x : (known_papers[x[0]].src, x[0]), to_explore[:cur_step_buffer_size]))
        # remove these papers from the to_explore list
        to_explore = to_explore[cur_step_buffer_size:]
        # we also use this iteration over every paper to count the number of occurence of each word
        # this count will be used later to weight the relations between papers
        word_count = result['word_count']
    if TIMING: print("phase 1 - {0} seconds elapsed".format(time.time() - start_time))
    if TIMING: start_time = time.time()
    # Once we have enough papers, we look for the relations between them
    if explored_threshold == -1: explored_threshold = len(to_explore)
    while (len(explored) < explored_threshold) and (len(to_explore) > 0):
        if VERBOSE:
            print("\nknown papers: {0}".format(len(known_papers)))
            print("known relations: {0}\n".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
            print("{0} paper(s) have been explored".format(len(explored)))
            print("{0} paper(s) will be explored during next step".format(len(cur_step_papers)))
            print("{0} other paper(s) have to be explored".format(len(to_explore)))
        if TRANSMIT_DATA:
            send_to_client("\{\"phase\":1,\"papers_count\":{0},\"relations_count\":{1},\"explored_count\":{2}\}".format(len(known_papers), sum(list(map(lambda x : len(known_relations[x]), known_relations))), len(explored)))
        # Get relations not found previously
        known_relations = search_relations(related_to = cur_step_papers, look_for = ["references"], request_page_size = 1000, known_papers = known_papers, known_relations = known_relations)
        # Update explored
        explored.update(set(map(lambda x : x[1], cur_step_papers)))
        # choose next step's papers (to explore)
        cur_step_papers = list(map(lambda x : (known_papers[x[0]].src, x[0]), to_explore[:cur_step_ref_buffer_size]))
        # remove these papers from the to_explore list
        to_explore = to_explore[cur_step_ref_buffer_size:]
    if TIMING: print("phase 2 - {0} seconds elapsed".format(time.time() - start_time))
    if TIMING: start_time = time.time()
    
    final_data = { 'papers' : dict(), 'links' : set() }    
    
    # Once we have the relations data for each papers, we weight the relations
    for paper1 in known_relations:
        for paper2 in known_relations[paper1]:
            weight = 0
            for word_p1 in list(map(normalize_word, known_papers[paper1].title.split(" "))):
                for word_p2 in list(map(normalize_word, known_papers[paper2].title.split(" "))):
                    if word_p1 == word_p2: weight += 1 / (word_count[word_p1] / len(known_papers))
            for author1 in known_papers[paper1].authors:
                for author2 in known_papers[paper2].authors:
                    if author1 == author2: weight += same_author_weight
            final_data['links'].add((paper1, paper2, weight))
    if TIMING: print("phase 3 - {0} seconds elapsed".format(time.time() - start_time))
    #if VERBOSE:
    print("Finished...")
    print("known papers: {0}".format(len(known_papers)))
    print("known relations: {0}".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
    print("explored {0} paper(s)".format(len(explored)))
    print("still {0} paper(s) to explore".format(len(to_explore)))
    if TIMING: start_time = time.time()
    
    for key in known_papers:
        final_data['links'][key] = known_papers[key].to_dict()
        final_data['links'][key]["links"] = []
        for relation in known_relations[key]:
            final_data['links'][key]["links"].append(relation)
    
    file_name = "papers_init{0}-{1}_ref{2}_expl{3}_find{4}.json".format(initial_paper_src, initial_paper_id, str(reference_threshold), str(explored_threshold), str(papers_threshold))
    
    with open(file_name, 'w') as outfile:
        json.dump(final_data, outfile)
    if TIMING: print("phase 4 - {0} seconds elapsed".format(time.time() - start_time))
    
    if TRANSMIT_DATA: send_to_client(json.dumps(final_data))
    
    return {'papers' : known_papers, 'relations' : weighted_relations}
    
# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def search_papers(terms = [], page_size = 1000):
    if TIMING: start_time = time.time()
    # set up queries
    query_base_url = epmc_endpoint + "search?format=json&pageSize=" + str(page_size) + "&query=" + format_search_terms(terms) + "&page="
    hit_count = estimate_search_hit_count(terms)
    page_count = calc_page_count(hit_count, page_size)
    query_urls = set(list(map(lambda p : query_base_url + str(p), range(1, page_count + 1))))
    # perform queries
    responses = perform_queries(query_urls, max_retry_iter = 3)
    # handle responses
    query_results = set()
    for JSON_resp in responses:
        if 'errCode' in JSON_resp:
            raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
        elif 'resultList' in JSON_resp:
            for paper in extract_LtdPaperDetails(JSON_resp['resultList']['result']):
                query_results.add(paper)
    # return papers found
    if TIMING : print("search_papers('{0}') : {1} seconds elapsed".format(format_search_terms(terms), time.time() - start_time))
    return query_results
    
# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----
    
def search_related_papers(related_to, look_for, request_page_size, known_papers, known_relations, word_count):
    query_urls = build_relation_queries(papers = related_to, relation_types = look_for, page_size = request_page_size)
    responses = perform_queries(query_urls, max_retry_iter = 3)
    # handle responses
    found_ids = set()
    for JSON_resp in responses:
        if 'errCode' in JSON_resp:
            raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
        else:
            cur_id = JSON_resp['request']['id']
            if ('referenceList' in JSON_resp) or ('citationList' in JSON_resp):
                if 'referenceList' in JSON_resp: (list_header, item_header, look_for_ref) = 'referenceList', 'reference', True
                else: (list_header, item_header, look_for_ref) = 'citationList', 'citation', False
                for paper in extract_LtdPaperDetails(JSON_resp[list_header][item_header]):
                    #if paper.citedCount > 0:
                    # Update found_ids and known_papers
                    found_ids.add(paper.id)
                    if not (paper.id in known_papers): known_papers[paper.id] = paper
                    # Update known_relations
                    if (look_for_ref):
                        if not cur_id in known_relations: known_relations[cur_id] = set()
                        known_relations[cur_id].add(paper.id)
                    else:
                        if not paper.id in known_relations: known_relations[paper.id] = set()
                        known_relations[paper.id].add(cur_id)
                    # Update word_count
                    for word in set(list(map(normalize_word, paper.title.split(' ')))):
                        if not word in word_count: word_count[word] = 1
                        else: word_count[word] += 1
    return { 'papers' : known_papers, 'relations' : known_relations, 'word_count' : word_count, 'found' : found_ids }

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def search_relations(related_to, look_for, request_page_size, known_papers, known_relations):
    query_urls = build_relation_queries(papers = related_to, relation_types = look_for, page_size = request_page_size)
    # perform queries
    queries = (grequests.get(url) for url in query_urls)
    responses = perform_queries(query_urls, max_retry_iter = 3)
    # handle responses
    for JSON_resp in responses:
        if 'errCode' in JSON_resp:
            raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
        else:
            cur_id = JSON_resp['request']['id']
            if 'referenceList' in JSON_resp: (list_header, item_header, look_for_ref) = 'referenceList', 'reference', True
            else: (list_header, item_header, look_for_ref) = 'citationList', 'citation', False
            for paper in extract_LtdPaperDetails(JSON_resp[list_header][item_header]):
                if paper.id in known_papers:
                    # Update known_relations
                    if (look_for_ref):
                        if not cur_id in known_relations: known_relations[cur_id] = set()
                        known_relations[cur_id].add(paper.id)
                    else:
                        if not paper.id in known_relations: known_relations[paper.id] = set()
                        known_relations[paper.id].add(cur_id)
    return known_relations

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def build_relation_queries(papers, relation_types, page_size):
    # Parameters type checking
    if not isinstance(papers, list):
        raise ValueError("papers : expected list of [src, id]")
    for paper in papers:
        if not isinstance(paper, tuple):
            raise ValueError("papers : expected list of [src, id]")
        for val in paper:
            if not isinstance(val, str):
                raise ValueError("papers : expected str found {0}".format(type(val).__name__    ))
    # set up queries
    query_urls = set()
    for relation_type in relation_types:
        for paper in estimate_relation_hit_counts(papers, relation_type):
            query_url_b = epmc_endpoint + paper[0] + "/" + paper[1] + "/" + relation_type + "/"
            query_url_e = "/" + str(page_size) + "/json/"
            page_count = calc_page_count(paper[2], page_size)
            for url in map(lambda p : query_url_b + str(p) + query_url_e, range(1, page_count + 1)):
                query_urls.add(url)
    return query_urls

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def estimate_relation_hit_count(src = "", id = "", relation_type = ""):
    # Parameters type checking
    if not relation_type in ["citations","references"]:
        raise ValueError("relation_type : expected 'citations' or 'references', found {0}".format(relation_type))
    if (not isinstance(src, str)) or (not isinstance(id, str)):
        raise ValueError("(src, id) : expected (str, str) found ({0}, {1})".format(type(src).__name__, type(id).__name__))
    # Perform count query
    count_query = epmc_endpoint + src + "/" + id + "/" + relation_type + "/1/1/json/"
    JSON_resp = perform_queries(set([count_query]), max_retry_iter = 2)
    # Check the API response
    if (len(JSON_resp) > 0) and (not ('errCode' in JSON_resp[0])): return JSON_resp[0]['hitCount']
    else: raise ValueError("Could not retrieve count data")

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def estimate_relation_hit_counts(papers = [], relation_type = ""):
    # Parameters type checking
        # TODO
    # Perform count query
    count_queries = set(list(map(lambda p : epmc_endpoint + p[0] + "/" + p[1] + "/" + relation_type + "/1/1/json/", papers)))
    responses = perform_queries(count_queries, max_retry_iter = 2)
    # Check the API response
    result = []
    for JSON_resp in responses:
        if (len(JSON_resp) > 0) and (not ('errCode' in JSON_resp)):
            result.append((JSON_resp['request']['source'], JSON_resp['request']['id'], JSON_resp['hitCount']))
        else: raise ValueError("Could not retrieve count data")
    return result

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def estimate_search_hit_count(terms = []):
    # Perform count query
    count_query = epmc_endpoint + "profile?format=json&query=" + format_search_terms(terms)
    JSON_resp = perform_queries(set([count_query]), max_retry_iter = 2)
    # Check the API response
    if (len(JSON_resp) > 0) and (not ('errCode' in JSON_resp[0])):
        for pubType in JSON_resp[0]['profileList']['pubType']:
            if (pubType['name'] == 'ALL'): return pubType['count']
        return 0
    else: raise ValueError("Could not retrieve count data")

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def calc_page_count(hit_count = 0, page_size = 1):
    # Parameters type checking
    if (not isinstance(hit_count, int)) or (not isinstance(page_size, int)):
        raise ValueError("(hit_count, page_size) : expected (int, int) found ({0}, {1})".format(type(hit_count).__name__, type(page_size).__name__))
    # Calculate the number of pages
    return int(math.floor(hit_count / page_size) + 1)

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def perform_queries(queries_set = set(), max_retry_iter = 5):
    # Parameters type checking
    if (not isinstance(queries_set, set)) or (not isinstance(max_retry_iter, int)):
        raise ValueError("perform_queries : expected (set, int) found ({0}, {1})".format(type(queries_set).__name__, type(max_retry_iter).__name__))
    # Variable definitions
    responses = []
    iter_count = 0
    # Perfom the queries until we get a response for each
    # or until we reach the max number of query retry.
    while (len(queries_set) > 0) and (iter_count < max_retry_iter):
        if VERBOSE: print(" .performing {0} API request(s) (attempt number {1})".format(len(queries_set), iter_count))
        if TIMING: start_time = time.time()
        # Perform the queries
        http_queries = (grequests.get(url) for url in queries_set)
        http_responses = grequests.map(http_queries)
        # Check for None responses to re-perform related queries
        for http_response in http_responses:
            if http_response is not None:
                queries_set.discard(http_response.url)
                responses.append(http_response.json()) # we only use JSON in our case
            http_response.close()
        # Count the number of iterations
        iter_count += 1
        if TIMING: print(" .queries performed in {1} seconds".format(len(queries_set), time.time() - start_time))
    return responses
        
# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----
        
def delete_characters(word, characters_to_delete):
    for char in characters_to_delete: word = word.replace(char, "")
    return word

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def normalize_word(word):
    # Parameters type checking
    if not isinstance(word, str):
        raise ValueError("word : expected str, found {0}".format(type(word).__name__))
    # Normalize the word
    return delete_characters(word, ".,?():").lower()

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def format_search_terms(params = [], delimiter = " "):
    output_str = ""
    # Multiple parameters
    if isinstance(params, list):
        for param in params:
            if isinstance(param, (str, int)): output_str += str(param)
    # One parameter
    elif isinstance(params, (str, int)):
        output_str += str(params)
    return output_str
   
# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

def extract_LtdPaperDetails(JSON_list):
    extracted_papers = set()
    for JSON_paper in JSON_list:
        if all (key in JSON_paper for key in ('id', 'source', 'title', 'authorString', 'pubYear')):
            # extract plain data
            id = str(JSON_paper['id'])
            src = str(JSON_paper['source'])
            title = str(JSON_paper['title'])
            pubYear = int(JSON_paper['pubYear'])
            citedCount = int(JSON_paper['citedByCount']) if 'citedByCount' in JSON_paper else 0
            # extract and parse the authors list
            string_authors = JSON_paper['authorString']
            authors = string_authors.split(", ")
            # create a LtdPaperDetails object
            extracted_papers.add(LtdPaperDetails(id = id, src = src, title = title, authors = authors, pubYear = pubYear, citedCount = citedCount))
    return extracted_papers

# ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

build_paper_network("10592235", reference_threshold = 5000, explored_threshold = -1, papers_threshold = 5000, cur_step_ref_buffer_size = 10, cur_step_cit_buffer_size = 2, same_author_weight = 1)