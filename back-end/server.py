from autobahn.asyncio.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

import time
import grequests
import requests
import json
import pprint
import math
from internal_types import *

epmc_endpoint = "http://www.ebi.ac.uk/europepmc/webservices/rest/"

VERBOSE = True
TIMING = True
NO_CLIENT = False
DUMP_FILE = False

if NO_CLIENT: client = open("dumps/sent_to_client.txt", "w")

class MyServerProtocol(WebSocketServerProtocol):

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))


    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
       print("received: {0}".format(payload.decode('utf8')))
       self.sendMessage(payload,isBinary)
       self.build_paper_network(initial_paper_id = payload.decode('utf8'), reference_threshold = 100, explored_threshold = -1, papers_threshold = 300, cur_step_ref_buffer_size = 25, cur_step_cit_buffer_size = 1, mined_terms_search_buffer_size = 25, same_author_weight = 1)

        

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

    def send(self,message):
        if NO_CLIENT: client.write(message + "\n")
        else: self.sendMessage(payload = message.encode('utf-8'), isBinary = False)   
   
   
    # ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- ----- -----

    def build_paper_network(self, initial_paper_id, reference_threshold = 2000, explored_threshold = 5000, papers_threshold = 5000, cur_step_ref_buffer_size = 10, cur_step_cit_buffer_size = 2, mined_terms_search_buffer_size = 10, same_author_weight = 1):
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
        
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        if VERBOSE: print("\n- - - - - - - - - Looking for referenced papers (0) - - - - - - - - -\n")
        if TIMING: start_time = time.time()
        # process until we have found as much referenced papers as wanted
        while (len(known_papers) < reference_threshold) and (not stop_looking):
            # Get more papers related to already known papers
            result = search_related_papers(related_to = cur_step_papers, look_for = ["references"], request_page_size = 1000, known_papers = known_papers, known_relations = known_relations, word_count = word_count)
            # Update our variables
            explored.update(set(map(lambda x : x[1], cur_step_papers)))
            known_papers = result['papers']
            known_relations = result['relations']
            to_explore = list(filter(lambda id : not (id in explored), known_papers)) # TODO: sort to explore to explore first relevant papers            
            # check if there still is papers to explore
            if (len(to_explore) > 0) and (len(known_papers) < reference_threshold):
                # choose next step's papers (to explore)
                cur_step_papers = list(map(lambda id : (known_papers[id].src, id), to_explore[:cur_step_ref_buffer_size]))
                # remove these papers from the to_explore list
                to_explore = to_explore[cur_step_ref_buffer_size:]
                # we also use this iteration over every paper to count the number of occurence of each word
                # this count will be used later to weight the relations between papers
                word_count = result['word_count']
            else: stop_looking = True
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            relations_count = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
            message = {
                "phase" : 0,
                "papers_found" : len(known_papers),
                "papers_explored" : len(explored),
                "relations_found": relations_count
            }
            self.send(json.dumps(message))
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            
            if VERBOSE:
                print("\n. Explored {0} / {1} paper(s)".format(len(explored), len(known_papers)))
                print(". Found {0} relation(s)\n".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))
        
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        if VERBOSE: print("\n- - - - - - - - - Requesting mined terms for referenced papers (1) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        term_counts = dict()
        referenced_papers_to_explore = list(map(lambda id: (known_papers[id].src, id), known_papers))
        init_count = len(referenced_papers_to_explore)
        while len(referenced_papers_to_explore) > 0:
            responses = perform_queries(build_mined_terms_queries(referenced_papers_to_explore[:mined_terms_search_buffer_size], page_size = 1000), max_retry_iter = 2)
            for JSON_resp in responses:
                if 'errCode' in JSON_resp:
                    raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
                else:
                    cur_id = JSON_resp['request']['id']
                    if not (cur_id in term_counts): term_counts[cur_id] = dict()
                    if 'semanticTypeList' in JSON_resp:
                        for semantic_type in JSON_resp['semanticTypeList']['semanticType']:
                            for term in semantic_type['tmSummary']:
                                term_counts[cur_id][term['term']] = term['count']
            referenced_papers_to_explore = referenced_papers_to_explore[mined_terms_search_buffer_size:]
            
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            relations_count = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
            message = {
                "phase" : 1,
                "papers_known" : init_count,
                "papers_explored_for_terms" : init_count - len(referenced_papers_to_explore)
            }
            self.send(json.dumps(message))
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            
            if VERBOSE: print("\n. Requested mined terms for {0} / {1} paper(s)\n".format(init_count - len(referenced_papers_to_explore), init_count))                  
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))
        
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        if VERBOSE: print("\n- - - - - - - - - Calculating relevance for referenced papers based on mined terms (2) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        
        papers_relevance = dict()
        for id in known_papers:
            if id != initial_paper_id:
                relevance = 0
                if initial_paper_id in term_counts:
                    for term_in_init in term_counts[initial_paper_id]:
                        if id in term_counts:
                            for term_in_other in term_counts[id]:
                                if term_in_init == term_in_other: relevance += 1
                papers_relevance[id] = relevance
        
        if VERBOSE:
            average = 0
            for id in papers_relevance: average += papers_relevance[id]
            if len(papers_relevance) > 0: average = average / len(papers_relevance)
            print(". Average paper's relevance: {0}\n".format(average))
            
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))
        
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        citations_for_top = 50
        if VERBOSE: print("\n- - - - - - - - - Looking for relevant citations (3) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        
        relevant_ref_papers = list(filter(lambda id : (id in papers_relevance), known_papers))
        referenced_papers = list(map(lambda id: (id, papers_relevance[id]), relevant_ref_papers))
        referenced_papers.sort(key = lambda rp : rp[1], reverse = True)
        referenced_papers_to_explore = list(map(lambda rp : (known_papers[rp[0]].src, rp[0]), referenced_papers))
        stop_looking = False if len(referenced_papers_to_explore) > 0 else False
        
        # Get more papers related to already known papers
        while (len(known_papers) < papers_threshold) and (not stop_looking):
            result = search_related_papers(related_to = referenced_papers_to_explore[:cur_step_cit_buffer_size], look_for = ["citations", "references"], request_page_size = 1000, known_papers = known_papers, known_relations = known_relations, word_count = word_count)
            # Update our variables
            explored.update(set(referenced_papers_to_explore[:cur_step_cit_buffer_size]))
            referenced_papers_to_explore = referenced_papers_to_explore[cur_step_cit_buffer_size:]
            if len(cur_step_papers) == 0: stop_looking = True
            known_papers = result['papers']
            known_relations = result['relations']
            word_count = result['word_count']
            
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            relations_count = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
            message = {
                "phase" : 3,
                "papers_found" : len(known_papers),
                "papers_explored" : len(explored),
                "relations_found": relations_count
            }
            self.send(json.dumps(message))
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            
            if VERBOSE:
                print("\n. Explored {0} / {1} paper(s)".format(len(explored), len(known_papers)))
                print(". Found {0} relation(s)\n".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))

        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        if VERBOSE: print("\n- - - - - - - - - Looking for relations between know papers (4) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        
        to_explore = list(filter(lambda id : not (id in explored), known_papers)) # TODO: sort to explore to explore first relevant papers
        stop_looking = False if (len(to_explore) > 0) else True
        if explored_threshold == -1: explored_threshold = len(known_papers)
        # Once we have enough papers, we look for the relations between them
        while (len(explored) < explored_threshold) and (not stop_looking):
            # Get relations not found previously
            known_relations = search_relations(related_to = cur_step_papers, look_for = ["references"], request_page_size = 1000, known_papers = known_papers, known_relations = known_relations)
            # Update explored and to_explore
            explored.update(set(map(lambda x : x[1], cur_step_papers)))
            to_explore = list(filter(lambda id : not (id in explored), known_papers)) # TODO: sort to explore to explore first relevant papers
            # check if there still is papers to explore and choose the next one to explore
            if (len(to_explore) > 0) and (len(explored) < explored_threshold):
                cur_step_papers = list(map(lambda id : (known_papers[id].src, id), to_explore[:cur_step_ref_buffer_size]))
            else: stop_looking = True
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            relations_count = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
            message = {
                "phase" : 4,
                "papers_found" : len(known_papers),
                "papers_explored" : len(explored),
                "relations_found": relations_count
            }
            self.send(json.dumps(message))
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            
            if VERBOSE:
                print("\n. Explored {0} / {1} paper(s)".format(len(explored), len(known_papers)))
                print(". Found {0} relation(s)\n".format(sum(list(map(lambda x : len(known_relations[x]), known_relations)))))
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))
        if TIMING: start_time = time.time()

        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
        
        if VERBOSE: print("\n- - - - - - - - - Requesting mined terms for new papers (5) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        need_to_request_mined_terms = []
        for id in known_papers:
            if not (id in term_counts): need_to_request_mined_terms.append(id)
        referenced_papers_to_explore = list(map(lambda id: (known_papers[id].src, id), need_to_request_mined_terms))
        init_count = len(referenced_papers_to_explore)
        while len(referenced_papers_to_explore) > 0:
            responses = perform_queries(build_mined_terms_queries(referenced_papers_to_explore[:mined_terms_search_buffer_size], page_size = 1000), max_retry_iter = 2)
            for JSON_resp in responses:
                if 'errCode' in JSON_resp:
                    raise ValueError("epmc api error : {0} - {1}".format(JSON_resp['errCode'], JSON_resp['errMsg']))
                else:
                    cur_id = JSON_resp['request']['id']
                    if not (cur_id in term_counts): term_counts[cur_id] = dict()
                    if 'semanticTypeList' in JSON_resp:
                        for semantic_type in JSON_resp['semanticTypeList']['semanticType']:
                            for term in semantic_type['tmSummary']:
                                term_counts[cur_id][term['term']] = term['count']
            referenced_papers_to_explore = referenced_papers_to_explore[mined_terms_search_buffer_size:]
            
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            relations_count = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
            message = {
                "phase" : 5,
                "papers_known" : init_count,
                "papers_explored_for_terms" : init_count - len(referenced_papers_to_explore)
            }
            self.send(json.dumps(message))
            # - - - - - - - - - - - - - SEND TO CLIENT - - - - - - - - - - - - -
            
            if VERBOSE: print("\n. Requested mined terms for {0} / {1} paper(s)\n".format(init_count - len(referenced_papers_to_explore), init_count))                  
        if TIMING: print("done in {0} seconds".format(time.time() - start_time))
        
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---    
        
        if VERBOSE: print("\n- - - - - - - - - Producing final data (6) - - - - - - - - -\n")    
        if TIMING: start_time = time.time()
        final_data = { 'title': 'final' , 'nodes' : [], 'links' : [] }    
        
        relations_to_weight = sum(list(map(lambda x : len(known_relations[x]), known_relations)))
        
        indexes = dict()
        
        # ADD papers to node
        for key in known_papers:
            # add to final data
            final_data['nodes'].append(known_papers[key].to_dict())
            index = len(final_data['nodes']) - 1
            # set index
            final_data['nodes'][index]["index"] = index
            indexes[known_papers[key].id] = index
            # init links
            final_data['nodes'][index]["links"] = []
        
        # set links for papers
        for paper in final_data['nodes']:
            if paper["id"] in known_relations:
                for other_id in known_relations[paper["id"]]:
                    paper["links"].append(indexes[other_id]) # references
                    final_data["nodes"][other_id]["links"].append(indexes[paper["id"]]) # citations
            #
            for other_id in known_relations
        
        # add links data
        for paper1 in known_relations:
            for paper2 in known_relations[paper1]:
                weight = 0
                for word_p1 in list(map(normalize_word, known_papers[paper1].title.split(" "))):
                    for word_p2 in list(map(normalize_word, known_papers[paper2].title.split(" "))):
                        if word_p1 == word_p2: weight += 1 / (word_count[word_p1] / len(known_papers))
                if paper1 in term_counts:
                    for term_p1 in term_counts[paper1]:
                        if paper2 in term_counts:
                            for term_p2 in term_counts[paper2]:
                                if term_p1 == term_p2: weight += term_counts[paper2][term_p1]/term_counts[paper1][term_p1]
                for author1 in known_papers[paper1].authors:
                    for author2 in known_papers[paper2].authors:
                        if author1 == author2: weight += same_author_weight
                final_data["links"].append({"source" : indexes[paper1], "target" : indexes[paper2], "weight" : weight})                 
        
        max_weight = max(list(map(lambda link: link["weight"], final_data["links"])))
        for link in final_data["links"]:
            link["weight"] = link["weight"] / max_weight

        if TIMING: print("done in {0} seconds".format(time.time() - start_time))

        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---    
        
        file_name = "dumps/papers_init{0}-{1}_ref{2}_expl{3}_find{4}.json".format(initial_paper_src, initial_paper_id, str(reference_threshold), str(explored_threshold), str(papers_threshold))
        
        if DUMP_FILE:
            with open(file_name, 'w') as outfile:
                outfile.write(json.dumps(final_data, indent=4, sort_keys=True))

        self.send(json.dumps(final_data))
        
        return final_data
        
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
            if ('referenceList' in JSON_resp) or ('citationList' in JSON_resp):
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

def build_mined_terms_queries(papers, page_size):
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
    for paper in estimate_mined_terms_hit_counts(papers):
        query_url_b = epmc_endpoint + paper[0] + "/" + paper[1] + "/textMinedTerms//"
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

def estimate_mined_terms_hit_counts(papers = []):
    # Parameters type checking
        # TODO
    # Perform count query
    count_queries = set(list(map(lambda p : epmc_endpoint + p[0] + "/" + p[1] + "/textMinedTerms//1/1/json/", papers)))
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
                try:
                    responses.append(http_response.json()) # we only use JSON in our case
                    queries_set.discard(http_response.url)
                except:
                    if VERBOSE: print(" .request failed ({0})".format(http_response.url))
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



if __name__ == '__main__':

    
        
    try:
        import asyncio
    except ImportError:
        # Trollius >= 0.3 was renamed
        import trollius as asyncio

    factory = WebSocketServerFactory(u"ws://127.0.0.1:9000")
    factory.protocol = MyServerProtocol

    loop = asyncio.get_event_loop()
    coro = loop.create_server(factory, '0.0.0.0', 9000)
    server = loop.run_until_complete(coro)

    try:
        print("Server started");
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        loop.close()

if NO_CLIENT: client.close()